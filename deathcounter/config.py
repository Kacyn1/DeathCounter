"""Ustawienia interfejsu i detektora (config.json) oraz ścieżki plików."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from .storage import StorageError, atomic_write_text

APP_DIR_NAME = "DeathCounter"
LEGACY_APP_DIR_NAME = "DS2DeathCounter"


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
    detector: DetectorSettings = field(default_factory=DetectorSettings)
    capture: CaptureSettings = field(default_factory=CaptureSettings)
    overlay: OverlaySettings = field(default_factory=OverlaySettings)
    rtss: RtssSettings = field(default_factory=RtssSettings)
    template: TemplateInfo | None = None
    auto_start: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AppPaths:
    base: Path
    deaths: Path
    config: Path
    template: Path

    @classmethod
    def in_dir(cls, base: Path) -> "AppPaths":
        base = Path(base)
        return cls(base, base / "deaths.json", base / "config.json", base / "template.png")

    @classmethod
    def default(cls) -> "AppPaths":
        return cls.in_dir(_data_dir())


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
    config.template = TemplateInfo.from_dict(data.get("template"))
    if isinstance(data.get("auto_start"), bool):
        config.auto_start = data["auto_start"]
    for part in (config.detector, config.capture, config.overlay):
        part.sanitize()
    return config, None


def save_config(path: Path, config: AppConfig) -> None:
    atomic_write_text(path, json.dumps(config.to_dict(), indent=2, ensure_ascii=False) + "\n")


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


def _data_dir() -> Path:
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
