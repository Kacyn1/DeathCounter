"""Wątek wykrywania: pobiera klatki, sprawdza stan obrazu i zgłasza śmierci."""

from __future__ import annotations

import copy
import threading
import time
from enum import Enum
from typing import Callable

from PySide6.QtCore import QThread, Signal

from . import rtss_setup
from .capture import DxcamSource
from .config import CaptureSettings, DetectorSettings
from .detector import CaptureHealth, DetectionSession
from .template import DeathTemplate

RETRY_SECONDS = 3.0
SAMPLE_SIGNAL_INTERVAL = 0.2
SNAPSHOT_TIMEOUT = 2.0


class DetectorStatus(Enum):
    ACTIVE = "aktywny"
    STOPPED = "zatrzymany"
    NO_IMAGE = "brak obrazu"
    NO_TEMPLATE = "brak wzorca"
    ERROR = "błąd"


class RtssSetupWorker(QThread):
    """Instaluje (opcjonalnie) i uruchamia RTSS w tle – okna UAC i winget nie blokują interfejsu."""

    progress = Signal(str)
    done = Signal(bool, str)

    def __init__(self, install: bool, parent=None) -> None:
        super().__init__(parent)
        self._install = install

    def run(self) -> None:
        try:
            self.done.emit(True, self._setup())
        except rtss_setup.RtssSetupError as exc:
            self.done.emit(False, str(exc))
        except Exception as exc:  # noqa: BLE001 - błąd ma trafić do okna, nie do konsoli
            self.done.emit(False, f"Nieoczekiwany błąd przy uruchamianiu RTSS: {exc}")

    def _setup(self) -> str:
        path = rtss_setup.find_rtss()
        if path is None:
            if not self._install:
                raise rtss_setup.RtssSetupError("RTSS nie jest zainstalowany.")
            self.progress.emit("Instalowanie RTSS (winget)… potwierdź okno uprawnień administratora.")
            rtss_setup.install_with_winget()
            path = rtss_setup.find_rtss()
        if rtss_setup.is_running():
            return "RTSS już działa."
        if not rtss_setup.task_exists():
            self.progress.emit(
                "Potwierdź jednorazowo okno uprawnień – potem RTSS będzie startował z licznikiem bez pytania."
            )
            rtss_setup.create_start_task(path)
        self.progress.emit("Uruchamianie RTSS…")
        rtss_setup.start_rtss(path)
        return "RTSS uruchomiony."


class DetectionWorker(QThread):
    death_detected = Signal()
    status_changed = Signal(object, str)   # DetectorStatus, opis
    sample = Signal(object)                # SampleResult
    snapshot_ready = Signal(object)        # np.ndarray | None
    notice = Signal(str)

    def __init__(
        self,
        template: DeathTemplate,
        detector: DetectorSettings,
        capture: CaptureSettings,
        source_factory: Callable[[CaptureSettings], object] = DxcamSource,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._template = template
        self._detector = copy.deepcopy(detector)
        self._capture = copy.deepcopy(capture)
        self._source_factory = source_factory
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._pending_detector: DetectorSettings | None = None
        self._pending_capture: CaptureSettings | None = None
        self._pending_template: DeathTemplate | None = None
        self._snapshot_requested_at: float | None = None
        self._last_status: tuple | None = None

    # --- wywoływane z wątku GUI ---

    def request_stop(self) -> None:
        self._stop.set()

    def request_snapshot(self) -> None:
        with self._lock:
            if self._snapshot_requested_at is None:
                self._snapshot_requested_at = time.monotonic()

    def update_settings(self, detector: DetectorSettings, capture: CaptureSettings) -> None:
        with self._lock:
            self._pending_detector = copy.deepcopy(detector)
            if capture != self._capture:
                self._pending_capture = copy.deepcopy(capture)

    def update_template(self, template: DeathTemplate) -> None:
        with self._lock:
            self._pending_template = template

    # --- wątek roboczy ---

    def run(self) -> None:
        try:
            self._loop()
        except Exception as exc:  # noqa: BLE001 - błąd ma trafić do okna, nie do konsoli
            self._set_status(DetectorStatus.ERROR, f"Nieoczekiwany błąd detektora: {exc}")
            self._deliver_snapshot(None)

    def _loop(self) -> None:
        session = DetectionSession(self._template, self._detector)
        source = None
        retry_at = 0.0
        last_frame = None
        last_sample_signal = 0.0

        try:
            while not self._stop.is_set():
                started = time.monotonic()
                reopen = self._apply_pending(session)
                if reopen and source is not None:
                    source.close()
                    source = None
                    retry_at = 0.0

                if source is None:
                    if started >= retry_at:
                        source = self._source_factory(self._capture)
                        try:
                            source.open()
                            session.capture_restarted()
                            last_frame = None
                            self._set_status(DetectorStatus.ACTIVE, "Przechwytywanie uruchomione.")
                        except Exception as exc:  # noqa: BLE001
                            source.close()
                            source = None
                            retry_at = started + RETRY_SECONDS
                            self._set_status(DetectorStatus.ERROR, f"{exc} Ponowna próba za kilka sekund.")
                    if source is None:
                        self._deliver_snapshot(None)
                        self._stop.wait(self._detector.sample_interval_ms / 1000)
                        continue

                try:
                    frame = source.grab()
                except Exception as exc:  # noqa: BLE001
                    source.close()
                    source = None
                    retry_at = started + RETRY_SECONDS
                    session.detector.interrupt()
                    self._set_status(DetectorStatus.ERROR, f"Błąd przechwytywania obrazu: {exc}")
                    continue

                if frame is not None:
                    last_frame = frame
                result = session.process(frame)
                self._serve_snapshot(last_frame)

                check = result.check
                if check.resolution_changed and check.resolution:
                    w, h = check.resolution
                    self.notice.emit(f"Rozdzielczość obrazu zmieniła się na {w}×{h}; wzorzec został przeskalowany.")
                if check.health is CaptureHealth.NO_FRAMES:
                    self._set_status(
                        DetectorStatus.NO_IMAGE,
                        f"Brak nowych klatek od {int(check.stalled_for)} s. "
                        "Sprawdź, czy gra działa na wybranym monitorze.",
                    )
                elif check.health is CaptureHealth.FROZEN:
                    self._set_status(DetectorStatus.NO_IMAGE, f"Obraz zamrożony od {int(check.stalled_for)} s.")
                else:
                    self._set_status(DetectorStatus.ACTIVE, "Wykrywanie działa.")

                if result.death:
                    self.death_detected.emit()
                if result.death or started - last_sample_signal >= SAMPLE_SIGNAL_INTERVAL:
                    last_sample_signal = started
                    self.sample.emit(result)

                elapsed = time.monotonic() - started
                self._stop.wait(max(0.0, self._detector.sample_interval_ms / 1000 - elapsed))
        finally:
            if source is not None:
                source.close()
            self._deliver_snapshot(None)

    def _apply_pending(self, session: DetectionSession) -> bool:
        with self._lock:
            detector, self._pending_detector = self._pending_detector, None
            capture, self._pending_capture = self._pending_capture, None
            template, self._pending_template = self._pending_template, None
        if detector is not None:
            self._detector = detector
            session.apply_settings(detector)
        if template is not None:
            session.template = template
            session.detector.interrupt()
        if capture is not None:
            self._capture = capture
            return True
        return False

    def _serve_snapshot(self, frame) -> None:
        with self._lock:
            requested = self._snapshot_requested_at
        if requested is None:
            return
        if frame is not None:
            self._deliver_snapshot(frame.copy())
        elif time.monotonic() - requested > SNAPSHOT_TIMEOUT:
            self._deliver_snapshot(None)

    def _deliver_snapshot(self, frame) -> None:
        with self._lock:
            if self._snapshot_requested_at is None:
                return
            self._snapshot_requested_at = None
        self.snapshot_ready.emit(frame)

    def _set_status(self, status: DetectorStatus, message: str) -> None:
        if self._last_status != (status, message):
            self._last_status = (status, message)
            self.status_changed.emit(status, message)
