"""Ustawienia interfejsu i detektora (config.json) oraz ścieżki plików."""

from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from .storage import StorageError, atomic_write_text

APP_DIR_NAME = "DeathCounter"
LEGACY_APP_DIR_NAME = "DS2DeathCounter"

# Gry wbudowane na liście wyboru; każda gra (także dodana przez użytkownika) ma własny folder
# games/<id>/ z licznikiem, bossami i kalibracją.
GAMES = {
    "ds1": "Dark Souls I",
    "ds2": "Dark Souls II",
    "ds3": "Dark Souls III",
    "sekiro": "Sekiro: Shadows Die Twice",
    "eldenring": "Elden Ring",
}
DEFAULT_GAME = "ds1"
GAMES_DIR = "games"
GAME_NAME_MAX = 60
_GAME_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# Wzorce: napis śmierci, ramka paska zdrowia bossa, komunikat zwycięstwa – (pole w Calibration, pole w AppPaths).
TEMPLATE_FIELDS = {
    "death": ("template", "template"),
    "boss_bar": ("boss_bar_template", "boss_bar_template"),
    "victory": ("victory_template", "victory_template"),
}


@dataclass
class DetectorSettings:
    threshold: float = 0.70           # minimalne dopasowanie wzorca (TM_CCOEFF_NORMED)
    hysteresis: float = 0.10          # napis uznany za zniknięty poniżej threshold - hysteresis
    confirm_samples: int = 3          # tyle kolejnych próbek z napisem = jedna śmierć
    sample_interval_ms: int = 100     # odstęp między próbkami
    rearm_seconds: float = 3.0        # tyle sekund bez napisu, zanim detektor znów się uzbroi
    cooldown_seconds: float = 8.0     # minimalny odstęp między dwiema zliczonymi śmierciami
    search_margin: float = 0.5        # margines szukania wokół miejsca wzorca (ułamek jego rozmiaru)
    freeze_timeout_seconds: float = 5.0  # po tylu sekundach bez zmian obrazu zgłaszamy brak obrazu

    def sanitize(self) -> None:
        self.threshold = _clamp(self.threshold, 0.30, 0.99)
        self.hysteresis = _clamp(self.hysteresis, 0.0, 0.5)
        self.confirm_samples = int(_clamp(self.confirm_samples, 1, 50))
        self.sample_interval_ms = int(_clamp(self.sample_interval_ms, 20, 1000))
        self.rearm_seconds = _clamp(self.rearm_seconds, 0.5, 60.0)
        self.cooldown_seconds = _clamp(self.cooldown_seconds, 0.0, 120.0)
        self.search_margin = _clamp(self.search_margin, 0.0, 3.0)
        self.freeze_timeout_seconds = _clamp(self.freeze_timeout_seconds, 1.0, 120.0)


@dataclass
class CaptureSettings:
    device_index: int = 0
    output_index: int | None = None   # None = monitor główny

    def sanitize(self) -> None:
        self.device_index = max(0, int(self.device_index))
        if self.output_index is not None:
            self.output_index = max(0, int(self.output_index))


OVERLAY_MODES = ("both", "window", "rtss")


@dataclass
class OverlaySettings:
    enabled: bool = False
    mode: str = "both"            # "window" – okno na wierzchu, "rtss" – RivaTuner, "both" – oba
    x: int = 20
    y: int = 20
    font_size: int = 28
    hide_from_capture: bool = False

    def sanitize(self) -> None:
        self.x = int(_clamp(self.x, -20000, 20000))
        self.y = int(_clamp(self.y, -20000, 20000))
        self.font_size = int(_clamp(self.font_size, 10, 200))
        if self.mode not in OVERLAY_MODES:
            self.mode = "both"


@dataclass
class RtssSettings:
    auto_start: bool = True          # uruchamiaj RTSS razem z licznikiem
    install_declined: bool = False   # użytkownik odmówił instalacji – nie pytamy przy każdym starcie

    def sanitize(self) -> None:
        pass


@dataclass
class BossSettings:
    track: bool = False              # „Śledź walkę z bossem”
    bar_confirm_samples: int = 10    # tyle kolejnych próbek z paskiem bossa = początek walki (ok. 1 s)
    bar_lost_seconds: float = 3.0    # tyle sekund bez paska = pasek zniknął (pauza, nie zwycięstwo)

    def sanitize(self) -> None:
        self.bar_confirm_samples = int(_clamp(self.bar_confirm_samples, 1, 100))
        self.bar_lost_seconds = _clamp(self.bar_lost_seconds, 0.5, 60.0)


@dataclass
class TemplateInfo:
    roi: list[int]             # x, y, szerokość, wysokość w pikselach obrazu referencyjnego
    reference_size: list[int]  # szerokość, wysokość obrazu, z którego wycięto wzorzec

    @classmethod
    def from_dict(cls, data: object) -> "TemplateInfo | None":
        if not isinstance(data, dict):
            return None
        roi, ref = data.get("roi"), data.get("reference_size")
        if not (_int_list(roi, 4) and _int_list(ref, 2)):
            return None
        if roi[2] <= 0 or roi[3] <= 0 or ref[0] <= 0 or ref[1] <= 0:
            return None
        return cls(list(roi), list(ref))


@dataclass
class AppConfig:
    """Ustawienia programu wspólne dla wszystkich gier (config.json w folderze programu)."""

    detector: DetectorSettings = field(default_factory=DetectorSettings)
    capture: CaptureSettings = field(default_factory=CaptureSettings)
    overlay: OverlaySettings = field(default_factory=OverlaySettings)
    rtss: RtssSettings = field(default_factory=RtssSettings)
    bosses: BossSettings = field(default_factory=BossSettings)
    game: str = DEFAULT_GAME
    custom_games: dict[str, str] = field(default_factory=dict)  # gry dodane przez użytkownika: id → nazwa
    auto_start: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    def all_games(self) -> dict[str, str]:
        return {**GAMES, **self.custom_games}

    def game_name(self, game: str) -> str:
        return self.all_games().get(game, game)

    def add_game(self, name: str) -> str:
        """Dodaje grę użytkownika i zwraca jej id (nazwa folderu). ValueError z opisem, gdy nazwa się nie nadaje."""
        name = " ".join(name.split())
        if not name:
            raise ValueError("Podaj nazwę gry.")
        if len(name) > GAME_NAME_MAX:
            raise ValueError(f"Nazwa gry może mieć najwyżej {GAME_NAME_MAX} znaków.")
        if any(existing.casefold() == name.casefold() for existing in self.all_games().values()):
            raise ValueError(f"Gra „{name}” jest już na liście.")
        base = _slug(name) or "gra"
        game_id, number = base, 2
        while game_id in self.all_games():
            game_id, number = f"{base}-{number}", number + 1
        self.custom_games[game_id] = name
        return game_id

    def remove_game(self, game: str) -> None:
        """Usuwa grę dodaną przez użytkownika z listy (gier wbudowanych nie można usunąć)."""
        self.custom_games.pop(game, None)
        if self.game == game:
            self.game = DEFAULT_GAME


@dataclass
class Calibration:
    """Wzorce jednej gry (games/<gra>/calibration.json): obszar i rozdzielczość, z których je wycięto."""

    template: TemplateInfo | None = None           # napis śmierci
    boss_bar_template: TemplateInfo | None = None  # ramka paska zdrowia bossa
    victory_template: TemplateInfo | None = None   # komunikat zwycięstwa

    def info(self, kind: str) -> TemplateInfo | None:
        return getattr(self, TEMPLATE_FIELDS[kind][0])

    def set_info(self, kind: str, info: TemplateInfo | None) -> None:
        setattr(self, TEMPLATE_FIELDS[kind][0], info)

    @classmethod
    def from_dict(cls, data: object) -> "Calibration":
        calibration = cls()
        if isinstance(data, dict):
            for kind, (name, _) in TEMPLATE_FIELDS.items():
                calibration.set_info(kind, TemplateInfo.from_dict(data.get(name)))
        return calibration


@dataclass
class AppPaths:
    """Pliki wybranej gry (games/<gra>/) oraz wspólny config.json."""

    base: Path
    game: str
    config: Path
    game_dir: Path
    deaths: Path
    bosses: Path
    calibration: Path
    template: Path
    boss_bar_template: Path
    victory_template: Path

    @classmethod
    def for_game(cls, base: Path, game: str) -> "AppPaths":
        base = Path(base)
        game_dir = base / GAMES_DIR / game
        return cls(
            base,
            game,
            base / "config.json",
            game_dir,
            game_dir / "deaths.json",
            game_dir / "bosses.json",
            game_dir / "calibration.json",
            game_dir / "template.png",
            game_dir / "boss_bar.png",
            game_dir / "victory.png",
        )

    def template_path(self, kind: str) -> Path:
        return getattr(self, TEMPLATE_FIELDS[kind][1])

    def source_path(self, kind: str) -> Path:
        """Pełny zrzut, z którego wycięto wzorzec, np. boss_bar.png → boss_bar_source.jpg."""
        path = self.template_path(kind)
        return path.with_name(f"{path.stem}_source.jpg")


def _slug(name: str) -> str:
    """„Lies of P: Overture” → „lies-of-p-overture” (bezpieczna nazwa folderu)."""
    text = unicodedata.normalize("NFKD", name.replace("ł", "l").replace("Ł", "L"))
    text = text.encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:40].strip("-")


def load_config(path: Path) -> tuple[AppConfig, str | None]:
    """Zwraca konfigurację i ewentualne ostrzeżenie. Błędne wartości zastępuje domyślnymi."""
    config = AppConfig()
    if not path.exists():
        return config, None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            raise ValueError("oczekiwano obiektu JSON")
    except (OSError, ValueError) as exc:
        return config, f"Nie można odczytać {path.name} ({exc}). Użyto ustawień domyślnych."

    _fill(config.detector, data.get("detector"))
    _fill(config.capture, data.get("capture"))
    _fill(config.overlay, data.get("overlay"))
    _fill(config.rtss, data.get("rtss"))
    _fill(config.bosses, data.get("bosses"))
    custom = data.get("custom_games")
    if isinstance(custom, dict):
        config.custom_games = {
            game_id: " ".join(name.split())[:GAME_NAME_MAX]
            for game_id, name in custom.items()
            if isinstance(game_id, str) and _GAME_ID.match(game_id) and game_id not in GAMES
            and isinstance(name, str) and name.strip()
        }
    if data.get("game") in config.all_games():
        config.game = data["game"]
    if isinstance(data.get("auto_start"), bool):
        config.auto_start = data["auto_start"]
    for part in (config.detector, config.capture, config.overlay, config.bosses):
        part.sanitize()
    return config, None


def save_config(path: Path, config: AppConfig) -> None:
    atomic_write_text(path, json.dumps(config.to_dict(), indent=2, ensure_ascii=False) + "\n")


def load_calibration(path: Path) -> tuple[Calibration, str | None]:
    if not path.exists():
        return Calibration(), None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        return Calibration(), f"Nie można odczytać {path.name} ({exc}). Wykonaj kalibrację ponownie."
    return Calibration.from_dict(data), None


def save_calibration(path: Path, calibration: Calibration) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps(asdict(calibration), indent=2, ensure_ascii=False) + "\n")


# --- dane sprzed wyboru gry (wersja 1.2 i starsze trzymały wszystko w folderze programu) ---

LEGACY_FILES = (
    "deaths.json", "deaths.json.uszkodzony", "bosses.json", "bosses.json.uszkodzony",
    "template.png", "boss_bar.png", "victory.png",
    "template_source.jpg", "boss_bar_source.jpg", "victory_source.jpg",
)


def legacy_data_present(base: Path) -> bool:
    """Dane z wersji bez wyboru gry, których jeszcze nie przypisano do żadnej gry."""
    base = Path(base)
    return not (base / GAMES_DIR).exists() and any((base / name).exists() for name in LEGACY_FILES)


def migrate_legacy(base: Path, game: str) -> None:
    """Przenosi licznik, bossów i wzorce z folderu programu do games/<gra>/, a obszary wzorców
    z config.json do games/<gra>/calibration.json."""
    base = Path(base)
    paths = AppPaths.for_game(base, game)
    try:
        paths.game_dir.mkdir(parents=True, exist_ok=True)
        calibration = Calibration()
        config_path = base / "config.json"
        if config_path.exists():
            try:
                calibration = Calibration.from_dict(json.loads(config_path.read_text(encoding="utf-8-sig")))
            except (OSError, ValueError):
                pass
        if not paths.calibration.exists():
            save_calibration(paths.calibration, calibration)
        for name in LEGACY_FILES:
            source = base / name
            if source.exists() and not (paths.game_dir / name).exists():
                os.replace(source, paths.game_dir / name)
    except OSError as exc:
        raise StorageError(f"Nie można przenieść danych do folderu gry {paths.game_dir}: {exc}") from exc


def _fill(target: object, data: object) -> None:
    if not isinstance(data, dict):
        return
    for f in fields(target):
        if f.name not in data:
            continue
        value, current = data[f.name], getattr(target, f.name)
        is_int = isinstance(value, int) and not isinstance(value, bool)
        if isinstance(current, bool):
            ok = isinstance(value, bool)
        elif f.name == "output_index":
            ok = value is None or is_int
        elif isinstance(current, int):
            ok = is_int
        elif isinstance(current, float):
            ok = isinstance(value, (int, float)) and not isinstance(value, bool)
            value = float(value) if ok else value
        elif isinstance(current, str):
            ok = isinstance(value, str)
        else:
            ok = False
        if ok:
            setattr(target, f.name, value)


def _int_list(value: object, length: int) -> bool:
    return (
        isinstance(value, list)
        and len(value) == length
        and all(isinstance(v, int) and not isinstance(v, bool) for v in value)
    )


def _clamp(value, low, high):
    return max(low, min(high, value))


def _app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def _writable(directory: Path) -> bool:
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / f".write_test_{os.getpid()}"
        probe.write_bytes(b"")
        probe.unlink()
        return True
    except OSError:
        return False


def data_dir() -> Path:
    """Pliki leżą obok programu; gdy folder jest tylko do odczytu, trafiają do %APPDATA%."""
    directory = _app_dir()
    if _writable(directory):
        return directory
    appdata = Path(os.environ.get("APPDATA") or Path.home())
    fallback = appdata / APP_DIR_NAME
    legacy = appdata / LEGACY_APP_DIR_NAME
    if not fallback.exists() and legacy.is_dir():
        return legacy  # dane zapisane przez wersję sprzed zmiany nazwy
    try:
        fallback.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise StorageError(f"Brak folderu z prawem zapisu na dane programu: {exc}") from exc
    return fallback
