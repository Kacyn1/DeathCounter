"""Wątek wykrywania: pobiera klatki, sprawdza stan obrazu i zgłasza śmierci oraz zdarzenia walki z bossem."""

from __future__ import annotations

import copy
import queue
import threading
import time
from enum import Enum
from typing import Callable

from PySide6.QtCore import QThread, Signal

from pathlib import Path

from . import ocr, rtss_setup, updater
from .capture import DxcamSource
from .config import BossSettings, CaptureSettings, DetectorSettings
from .detector import BarEvent, CaptureHealth, DetectionSession
from .template import DeathTemplate

RETRY_SECONDS = 3.0
NAME_SAMPLES = 3            # tyle klatek z nazwą bossa trafia do OCR po pojawieniu się paska
NAME_SAMPLE_INTERVAL = 0.4  # odstęp między nimi (s) – nazwa bywa jeszcze w trakcie pojawiania się
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


class UpdateCheckWorker(QThread):
    """Pyta GitHuba o najnowsze wydanie w tle – interfejs nie czeka na sieć."""

    done = Signal(object, str)  # updater.Release | None, opis błędu

    def run(self) -> None:
        try:
            self.done.emit(updater.fetch_latest(), "")
        except updater.UpdateError as exc:
            self.done.emit(None, str(exc))


class UpdateDownloadWorker(QThread):
    """Pobiera nowy DeathCounter.exe i sprawdza jego sumę kontrolną."""

    progress = Signal(int, int)  # pobrane bajty, rozmiar
    done = Signal(str, str)      # ścieżka pobranego pliku, opis błędu

    def __init__(self, release: updater.Release, dest: Path, parent=None) -> None:
        super().__init__(parent)
        self._release = release
        self._dest = dest
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    def run(self) -> None:
        try:
            path = updater.download(self._release, self._dest, self.progress.emit, cancelled=self._cancel.is_set)
            self.done.emit(str(path), "")
        except updater.UpdateError as exc:
            self.done.emit("", str(exc))


# Zdarzenia walki z bossem przekazywane sygnałem boss_event.
BOSS_BAR_VISIBLE, BOSS_BAR_LOST, BOSS_VICTORY, FRAMES_LOST = "bar_visible", "bar_lost", "victory", "frames_lost"


class DetectionWorker(QThread):
    death_detected = Signal()
    boss_event = Signal(str)               # BOSS_BAR_VISIBLE / BOSS_BAR_LOST / BOSS_VICTORY / FRAMES_LOST
    status_changed = Signal(object, str)   # DetectorStatus, opis
    sample = Signal(object)                # SampleResult
    snapshot_ready = Signal(object)        # np.ndarray | None
    notice = Signal(str)
    boss_name = Signal(str, bool)          # odczytana nazwa bossa ("" – nie udało się) i czy odczyt jest pewny

    def __init__(
        self,
        templates: dict[str, DeathTemplate | None],
        detector: DetectorSettings,
        capture: CaptureSettings,
        bosses: BossSettings,
        source_factory: Callable[[CaptureSettings], object] = DxcamSource,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._templates = dict(templates)
        self._detector = copy.deepcopy(detector)
        self._capture = copy.deepcopy(capture)
        self._bosses = copy.deepcopy(bosses)
        self._source_factory = source_factory
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._pending_detector: DetectorSettings | None = None
        self._pending_bosses: BossSettings | None = None
        self._ocr_failed = False  # brak OCR – do końca tego uruchomienia nie zbieramy wycinków z nazwą
        self._pending_capture: CaptureSettings | None = None
        self._pending_templates: dict[str, DeathTemplate] = {}
        self._snapshot_requested_at: float | None = None
        self._last_status: tuple | None = None
        self._name_bands: list | None = None  # wycinki z nazwą zbierane po pojawieniu się paska
        self._name_next = 0.0
        self._ocr_queue: queue.Queue | None = None

    # --- wywoływane z wątku GUI ---

    def request_stop(self) -> None:
        self._stop.set()

    def request_snapshot(self) -> None:
        with self._lock:
            if self._snapshot_requested_at is None:
                self._snapshot_requested_at = time.monotonic()

    def update_settings(self, detector: DetectorSettings, capture: CaptureSettings, bosses: BossSettings) -> None:
        with self._lock:
            self._pending_detector = copy.deepcopy(detector)
            self._pending_bosses = copy.deepcopy(bosses)
            if capture != self._capture:
                self._pending_capture = copy.deepcopy(capture)

    def set_read_names(self, enabled: bool) -> None:
        self._bosses.read_names = enabled

    def update_template(self, kind: str, template: DeathTemplate) -> None:
        with self._lock:
            self._pending_templates[kind] = template

    # --- wątek roboczy ---

    def run(self) -> None:
        try:
            self._loop()
        except Exception as exc:  # noqa: BLE001 - błąd ma trafić do okna, nie do konsoli
            self._set_status(DetectorStatus.ERROR, f"Nieoczekiwany błąd detektora: {exc}")
            self._deliver_snapshot(None)

    def _loop(self) -> None:
        session = DetectionSession(
            self._templates["death"],
            self._detector,
            bar_template=self._templates.get("boss_bar"),
            victory_template=self._templates.get("victory"),
            bosses=self._bosses,
        )
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
                    if session.capture_failed():
                        self.boss_event.emit(FRAMES_LOST)
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

                if result.frames_lost:
                    self.boss_event.emit(FRAMES_LOST)
                if result.death:
                    self.death_detected.emit()
                if result.victory:
                    self.boss_event.emit(BOSS_VICTORY)
                if result.bar_event is BarEvent.APPEARED:
                    self.boss_event.emit(BOSS_BAR_VISIBLE)
                    if self._bosses.read_names and not self._ocr_failed:
                        self._name_bands, self._name_next = [], 0.0
                elif result.bar_event is BarEvent.LOST:
                    self.boss_event.emit(BOSS_BAR_LOST)
                    self._name_bands = None
                self._collect_name(frame, result, started)
                if result.death or result.victory or result.bar_event or started - last_sample_signal >= SAMPLE_SIGNAL_INTERVAL:
                    last_sample_signal = started
                    self.sample.emit(result)

                elapsed = time.monotonic() - started
                self._stop.wait(max(0.0, self._detector.sample_interval_ms / 1000 - elapsed))
        finally:
            if source is not None:
                source.close()
            self._deliver_snapshot(None)
            if self._ocr_queue is not None:
                self._ocr_queue.put(None)

    # --- odczyt nazwy bossa ---

    def _collect_name(self, frame, result, now: float) -> None:
        """Po pojawieniu się paska zbiera kilka wycinków z nazwą i oddaje je wątkowi OCR."""
        if self._name_bands is None or frame is None or result.bar_rect is None or now < self._name_next:
            return
        band = ocr.crop_band(frame, result.bar_rect)
        if band is None:
            return
        self._name_bands.append(band)
        self._name_next = now + NAME_SAMPLE_INTERVAL
        if len(self._name_bands) >= NAME_SAMPLES:
            if self._ocr_queue is None:
                self._ocr_queue = queue.Queue()
                threading.Thread(target=self._ocr_loop, args=(self._ocr_queue,), daemon=True).start()
            self._ocr_queue.put(self._name_bands)
            self._name_bands = None

    def _ocr_loop(self, jobs: queue.Queue) -> None:
        """Osobny wątek: OCR trwa ułamek sekundy i nie może opóźniać próbek wykrywania."""
        try:
            reader = ocr.OcrReader()
        except ocr.OcrUnavailable as exc:
            self._ocr_failed = True
            self.notice.emit(f"Odczyt nazwy bossa niedostępny: {exc}.")
            return
        while (bands := jobs.get()) is not None:
            try:
                reading = reader.read_name(bands)
                self.boss_name.emit(reading.name if reading else "", bool(reading and reading.confident))
            except Exception as exc:  # noqa: BLE001 - błąd OCR nie może zatrzymać wykrywania
                self.notice.emit(f"Błąd odczytu nazwy bossa: {exc}")

    def _apply_pending(self, session: DetectionSession) -> bool:
        with self._lock:
            detector, self._pending_detector = self._pending_detector, None
            bosses, self._pending_bosses = self._pending_bosses, None
            capture, self._pending_capture = self._pending_capture, None
            templates, self._pending_templates = self._pending_templates, {}
        if detector is not None:
            self._detector = detector
            session.apply_settings(detector, bosses)
        if bosses is not None:
            self._bosses = bosses
        for kind, template in templates.items():
            session.set_template(kind, template)
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
