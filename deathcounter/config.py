"""Ustawienia interfejsu i detektora (config.json) oraz ścieżki plików."""

from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from . import hotkeys
from .storage import StorageError, atomic_write_text
from .i18n import DEFAULT_LANGUAGE, LANGUAGES, tr

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

# Wzorce: napis śmierci, ramka paska zdrowia bossa, komunikat zwycięstwa, menu główne, pasek zdrowia postaci –
# (pole w Calibration, pole w AppPaths).
TEMPLATE_FIELDS = {
    "death": ("template", "template"),
    "boss_bar": ("boss_bar_template", "boss_bar_template"),
    "victory": ("victory_template", "victory_template"),
    "menu": ("menu_template", "menu_template"),
    "hud": ("hud_template", "hud_template"),
}


@dataclass
class DetectorSettings:
    threshold: float = 0.70           # minimalne dopasowanie napisu śmierci i komunikatu zwycięstwa (TM_CCOEFF_NORMED)
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


# Identyfikator aplikacji „Death Counter by MK” w Discord Developer Portal (nazwa i logo w statusie).
DEFAULT_DISCORD_CLIENT_ID = "1561403894460846100"


@dataclass
class DiscordSettings:
    enabled: bool = False   # „Status na Discordzie”
    client_id: str = ""     # puste = DEFAULT_DISCORD_CLIENT_ID

    def sanitize(self) -> None:
        self.client_id = self.client_id.strip() if self.client_id.strip().isdigit() else ""

    @property
    def effective_client_id(self) -> str:
        return self.client_id or DEFAULT_DISCORD_CLIENT_ID


@dataclass
class SessionSettings:
    track: bool = True             # „Śledź sesję” – czas i śmierci, gdy gra jest uruchomiona
    show_on_overlay: bool = False  # „Pokaż sesję na nakładce”
    auto_switch: bool = True       # „Przełączaj licznik na uruchomioną grę”

    def sanitize(self) -> None:
        pass


@dataclass
class BossSettings:
    track: bool = False              # „Śledź walkę z bossem”
    read_names: bool = True          # „Odczytuj nazwę bossa z ekranu” (OCR)
    bar_threshold: float = 0.70      # minimalne dopasowanie wzorca paska zdrowia bossa
    name_match_ratio: float = 0.60   # minimalne podobieństwo odczytu OCR do znanej nazwy bossa
    bar_confirm_samples: int = 10    # tyle kolejnych próbek z paskiem bossa = początek walki (ok. 1 s)
    bar_lost_seconds: float = 3.0    # tyle sekund bez paska = pasek zniknął (pauza, nie zwycięstwo)

    def sanitize(self) -> None:
        self.bar_threshold = _clamp(self.bar_threshold, 0.30, 0.99)
        self.name_match_ratio = _clamp(self.name_match_ratio, 0.30, 1.0)
        self.bar_confirm_samples = int(_clamp(self.bar_confirm_samples, 1, 100))
        self.bar_lost_seconds = _clamp(self.bar_lost_seconds, 0.5, 60.0)


@dataclass
class HotkeySettings:
    """Skróty globalne w zapisie „Ctrl+Alt+F9”; pusty tekst = skrót wyłączony."""

    snapshot: str = "Ctrl+Alt+F9"   # zrzut do kalibracji
    plus: str = "Ctrl+Alt+F10"      # +1
    minus: str = "Ctrl+Alt+F11"     # −1
    overlay: str = "Ctrl+Alt+F8"    # włącz/wyłącz nakładkę

    def sanitize(self) -> None:
        defaults = HotkeySettings()
        for f in fields(self):
            text = getattr(self, f.name).strip()
            try:
                text = hotkeys.parse(text).text if text else ""
            except ValueError:
                text = getattr(defaults, f.name)
            setattr(self, f.name, text)


@dataclass
class UpdateSettings:
    """Aktualizacje z GitHuba."""

    check: bool = True        # „Sprawdzaj aktualizacje raz dziennie”
    last_check: float = 0.0   # ostatnie udane sprawdzenie (sekundy od epoki)
    latest: str = ""          # najnowsza znana wersja – pasek „Dostępna wersja” od razu po starcie

    def sanitize(self) -> None:
        if not re.match(r"^\d+(\.\d+)*$", self.latest):
            self.latest = ""


@dataclass
class UiSettings:
    """Wygląd okna: zwinięte sekcje."""

    overlay_collapsed: bool = False
    detector_collapsed: bool = False
    session_collapsed: bool = False

    def sanitize(self) -> None:
        pass


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
    session: SessionSettings = field(default_factory=SessionSettings)
    discord: DiscordSettings = field(default_factory=DiscordSettings)
    hotkeys: HotkeySettings = field(default_factory=HotkeySettings)
    ui: UiSettings = field(default_factory=UiSettings)
    update: UpdateSettings = field(default_factory=UpdateSettings)
    game: str = DEFAULT_GAME
    player_name: str = ""  # nick gracza na certyfikacie
    custom_games: dict[str, str] = field(default_factory=dict)  # gry dodane przez użytkownika: id → nazwa
    steam_appids: dict[str, int] = field(default_factory=dict)  # gry dodane ze Steama: id → AppID
    steam_offered: bool = False  # jednorazowa propozycja wyszukania gier w bibliotece Steam
    game_exes: dict[str, str] = field(default_factory=dict)  # exe wskazany dla gry spoza Steama: id → ścieżka
    auto_start: bool = False
    language: str = DEFAULT_LANGUAGE  # język interfejsu i nazw bossów (i18n.LANGUAGES)

    def to_dict(self) -> dict:
        return asdict(self)

    def all_games(self) -> dict[str, str]:
        return {**GAMES, **self.custom_games}

    def game_name(self, game: str) -> str:
        return self.all_games().get(game, game)

    def add_game(self, name: str, appid: int | None = None) -> str:
        """Dodaje grę użytkownika i zwraca jej id (nazwa folderu). ValueError z opisem, gdy nazwa się nie nadaje.
        `appid` – numer gry w Steam (gra znaleziona w bibliotece Steam)."""
        name = " ".join(name.split())
        if not name:
            raise ValueError(tr("Podaj nazwę gry."))
        if len(name) > GAME_NAME_MAX:
            raise ValueError(tr("Nazwa gry może mieć najwyżej {GAME_NAME_MAX} znaków.", GAME_NAME_MAX=GAME_NAME_MAX))
        if self.has_game_named(name):
            raise ValueError(tr("Gra „{name}” jest już na liście.", name=name))
        base = _slug(name) or "gra"
        game_id, number = base, 2
        while game_id in self.all_games():
            game_id, number = f"{base}-{number}", number + 1
        self.custom_games[game_id] = name
        if appid is not None:
            self.steam_appids[game_id] = appid
        return game_id

    def steam_game(self, appid: int) -> str | None:
        """Id gry dodanej wcześniej ze Steama pod tym AppID."""
        return next((game_id for game_id, known in self.steam_appids.items() if known == appid), None)

    def has_game_named(self, name: str) -> bool:
        name = " ".join(name.split()).casefold()
        return any(existing.casefold() == name for existing in self.all_games().values())

    def remove_game(self, game: str) -> None:
        """Usuwa grę dodaną przez użytkownika z listy (gier wbudowanych nie można usunąć)."""
        self.custom_games.pop(game, None)
        self.steam_appids.pop(game, None)
        self.game_exes.pop(game, None)
        if self.game == game:
            self.game = DEFAULT_GAME


@dataclass
class Calibration:
    """Wzorce jednej gry (games/<gra>/calibration.json): obszar i rozdzielczość, z których je wycięto."""

    template: TemplateInfo | None = None           # napis śmierci
    boss_bar_template: TemplateInfo | None = None  # ramka paska zdrowia bossa
    victory_template: TemplateInfo | None = None   # komunikat zwycięstwa
    menu_template: TemplateInfo | None = None      # menu główne gry (czas w menu nie jest czasem gry)
    hud_template: TemplateInfo | None = None       # pasek zdrowia postaci (początek rozgrywki po wyjściu z menu)

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
    audit: Path
    calibration: Path
    template: Path
    boss_bar_template: Path
    victory_template: Path
    boss_names: Path
    recent_fights: Path
    attempts: Path
    session: Path
    session_history: Path
    menu_template: Path
    hud_template: Path

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
            game_dir / "audit.json",
            game_dir / "calibration.json",
            game_dir / "template.png",
            game_dir / "boss_bar.png",
            game_dir / "victory.png",
            game_dir / "boss_names.json",
            game_dir / "recent_fights.json",
            game_dir / "attempts.json",
            game_dir / "session.json",
            game_dir / "session_history.json",
            game_dir / "menu.png",
            game_dir / "hud.png",
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


def system_language() -> str:
    """„pl” przy polskim Windows, w innym przypadku „en”."""
    try:
        import ctypes
        return "pl" if ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF == 0x15 else "en"
    except (AttributeError, OSError):
        return DEFAULT_LANGUAGE


def load_config(path: Path) -> tuple[AppConfig, str | None]:
    """Zwraca konfigurację i ewentualne ostrzeżenie. Błędne wartości zastępuje domyślnymi."""
    config = AppConfig()
    if not path.exists():
        config.language = system_language()  # pierwsze uruchomienie: język Windows
        return config, None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            raise ValueError(tr("oczekiwano obiektu JSON"))
    except (OSError, ValueError) as exc:
        return config, tr("Nie można odczytać {name} ({exc}). Użyto ustawień domyślnych.", name=path.name, exc=exc)

    _fill(config.detector, data.get("detector"))
    _fill(config.capture, data.get("capture"))
    _fill(config.overlay, data.get("overlay"))
    _fill(config.rtss, data.get("rtss"))
    _fill(config.bosses, data.get("bosses"))
    bosses = data.get("bosses")
    if not (isinstance(bosses, dict) and "bar_threshold" in bosses):
        # Wcześniej pasek bossa używał wspólnego progu – zostaje taki, jaki był ustawiony.
        config.bosses.bar_threshold = config.detector.threshold
    _fill(config.session, data.get("session"))
    _fill(config.discord, data.get("discord"))
    _fill(config.hotkeys, data.get("hotkeys"))
    _fill(config.ui, data.get("ui"))
    _fill(config.update, data.get("update"))
    custom = data.get("custom_games")
    if isinstance(custom, dict):
        config.custom_games = {
            game_id: " ".join(name.split())[:GAME_NAME_MAX]
            for game_id, name in custom.items()
            if isinstance(game_id, str) and _GAME_ID.match(game_id) and game_id not in GAMES
            and isinstance(name, str) and name.strip()
        }
    appids = data.get("steam_appids")
    if isinstance(appids, dict):
        config.steam_appids = {
            game_id: appid for game_id, appid in appids.items()
            if game_id in config.custom_games and isinstance(appid, int) and not isinstance(appid, bool) and appid > 0
        }
    exes = data.get("game_exes")
    if isinstance(exes, dict):
        config.game_exes = {
            game_id: exe for game_id, exe in exes.items()
            if game_id in config.custom_games and isinstance(exe, str) and exe.lower().endswith(".exe")
        }
    if data.get("game") in config.all_games():
        config.game = data["game"]
    if isinstance(data.get("player_name"), str):
        config.player_name = " ".join(data["player_name"].split())[:GAME_NAME_MAX]
    if isinstance(data.get("auto_start"), bool):
        config.auto_start = data["auto_start"]
    if isinstance(data.get("steam_offered"), bool):
        config.steam_offered = data["steam_offered"]
    if data.get("language") in LANGUAGES:
        config.language = data["language"]
    for part in (config.detector, config.capture, config.overlay, config.bosses, config.discord, config.hotkeys,
                 config.update):
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
        return Calibration(), tr("Nie można odczytać {name} ({exc}). Wykonaj kalibrację ponownie.", name=path.name, exc=exc)
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
        raise StorageError(tr("Nie można przenieść danych do folderu gry {game_dir}: {exc}", game_dir=paths.game_dir, exc=exc)) from exc


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
        raise StorageError(tr("Brak folderu z prawem zapisu na dane programu: {exc}", exc=exc)) from exc
    return fallback
