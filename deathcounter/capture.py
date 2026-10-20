"""Przechwytywanie obrazu przez DXCam (DXGI Desktop Duplication)."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass

import numpy as np

from .config import CaptureSettings
from .i18n import tr


class CaptureError(Exception):
    """Nie udało się uruchomić przechwytywania lub pobrać obrazu."""


@dataclass
class OutputInfo:
    device_index: int
    output_index: int
    width: int
    height: int
    primary: bool

    @property
    def label(self) -> str:
        primary = tr(" (główny)") if self.primary else ""
        return tr("Monitor {value}: {width}×{height}{primary}", value=self.output_index + 1, width=self.width, height=self.height, primary=primary)


def _dxcam():
    # Import dopiero przy użyciu: dxcam przy imporcie odpytuje karty graficzne,
    # a ewentualny błąd ma trafić do okna programu, a nie zatrzymać start aplikacji.
    try:
        import dxcam
    except Exception as exc:  # noqa: BLE001 - każdy błąd biblioteki pokazujemy użytkownikowi
        raise CaptureError(tr("Nie można załadować biblioteki DXCam: {exc}", exc=exc)) from exc
    return dxcam


_OUTPUT_LINE = re.compile(r"Device\[(\d+)\] Output\[(\d+)\]: Res:\((\d+), (\d+)\).*Primary:(\w+)")


def list_outputs() -> list[OutputInfo]:
    info = _dxcam().output_info()
    return [
        OutputInfo(int(m[1]), int(m[2]), int(m[3]), int(m[4]), m[5] == "True")
        for m in _OUTPUT_LINE.finditer(info)
    ]


class DxcamSource:
    """Pojedyncze źródło klatek. grab() zwraca None, gdy od ostatniego razu nie ma nowej klatki."""

    def __init__(self, settings: CaptureSettings) -> None:
        self._settings = settings
        self._camera = None

    def open(self) -> None:
        dxcam = _dxcam()
        try:
            self._camera = dxcam.create(
                device_idx=self._settings.device_index,
                output_idx=self._settings.output_index,
                output_color="BGR",
            )
        except Exception as exc:  # noqa: BLE001
            raise CaptureError(tr("Nie można uruchomić przechwytywania obrazu: {exc}", exc=exc)) from exc
        if self._camera is None:
            raise CaptureError(tr("DXCam nie zwrócił źródła obrazu dla wybranego monitora."))

    def grab(self) -> np.ndarray | None:
        if self._camera is None:
            raise CaptureError(tr("Przechwytywanie nie jest uruchomione."))
        return self._camera.grab()

    def close(self) -> None:
        camera, self._camera = self._camera, None
        if camera is not None:
            try:
                camera.release()
            except Exception:  # noqa: BLE001 - zamykanie nie może przerwać pracy programu
                pass


def grab_single_frame(settings: CaptureSettings, timeout: float = 2.0) -> np.ndarray:
    """Jednorazowy zrzut ekranu (używany przy kalibracji, gdy wykrywanie jest zatrzymane)."""
    source = DxcamSource(settings)
    source.open()
    try:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            frame = source.grab()
            if frame is not None:
                return frame
            time.sleep(0.03)
    finally:
        source.close()
    raise CaptureError(tr("Brak obrazu: nie udało się pobrać klatki z wybranego monitora."))
