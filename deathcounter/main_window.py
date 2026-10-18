"""Główne okno: licznik, walka z bossem, status, sterowanie wykrywaniem i nakładką."""

from __future__ import annotations

import winsound
from datetime import datetime

import numpy as np
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from . import winapi
from .boss_panel import BossPanel
from .bosses import BossTracker, overlay_text
from .calibration import CalibrationDialog, SavedCalibration
from .capture import CaptureError, grab_single_frame, list_outputs
from .config import GAMES, AppConfig, game_name, save_calibration, save_config
from .game_data import GameData, open_game
from .detector import CaptureHealth, SampleResult
from .overlay import OverlayWindow
from .report import build_report_html, rows_from_records, write_pdf
from .rtss import RtssOsd, RtssState
from .storage import StorageError
from .template import DeathTemplate, load_source_image, save_source_image
from . import rtss_setup
from .worker import (
    BOSS_BAR_LOST,
    BOSS_BAR_VISIBLE,
    BOSS_VICTORY,
    FRAMES_LOST,
    DetectionWorker,
    DetectorStatus,
    RtssSetupWorker,
)

# Skróty globalne – działają także, gdy gra jest w pełnym ekranie.
HOTKEY_SNAPSHOT, HOTKEY_PLUS, HOTKEY_MINUS = 0xD52, 0xD53, 0xD54
HOTKEYS = {
    HOTKEY_SNAPSHOT: (winapi.VK_F9, "Ctrl+Alt+F9"),
    HOTKEY_PLUS: (winapi.VK_F10, "Ctrl+Alt+F10"),
    HOTKEY_MINUS: (winapi.VK_F11, "Ctrl+Alt+F11"),
}
HOTKEY_TEXT = HOTKEYS[HOTKEY_SNAPSHOT][1]
RTSS_REFRESH_MS = 2000
BOSS_REFRESH_MS = 1000
OVERLAY_MODE_LABELS = {
    "both": "Okno + RTSS",
    "window": "Okno na wierzchu",
    "rtss": "Tylko RTSS (pełny ekran)",
}

STATUS_COLORS = {
    DetectorStatus.ACTIVE: "#2f9e5b",
    DetectorStatus.STOPPED: "#6b6f76",
    DetectorStatus.NO_IMAGE: "#c97a1e",
    DetectorStatus.NO_TEMPLATE: "#c97a1e",
    DetectorStatus.ERROR: "#c0392b",
}


class MainWindow(QMainWindow):
    def __init__(self, config: AppConfig, game: GameData):
        super().__init__()
        self.setWindowTitle("Death Counter")
        self.config = config
        self._use_game(game)
        self._pending_game: str | None = None   # zmiana gry czeka na zatrzymanie wykrywania
        self.worker: DetectionWorker | None = None
        self._status = DetectorStatus.STOPPED
        self._frame_callbacks: list = []
        self._hotkey_frame: np.ndarray | None = None
        self._hotkeys: set[int] = set()
        self._calibration: CalibrationDialog | None = None
        self._closing = False
        self._stop_requested = False
        self._rtss_setup: RtssSetupWorker | None = None

        self.overlay = OverlayWindow(config.overlay)
        self.rtss = RtssOsd()
        # RTSS może zostać uruchomiony (lub zrestartowany) po naszym programie – ponawiamy wpis.
        self._rtss_timer = QTimer(self, interval=RTSS_REFRESH_MS)
        self._rtss_timer.timeout.connect(self._update_rtss)

        self._save_timer = QTimer(self, singleShot=True, interval=500)
        self._save_timer.timeout.connect(self._save_config)
        # Timer walki: odświeża czas w panelu i nakładce oraz co kilka sekund zapisuje go do pliku.
        self._boss_timer = QTimer(self, interval=BOSS_REFRESH_MS)
        self._boss_timer.timeout.connect(self._on_boss_tick)

        self._build_ui()
        self._apply_overlay()
        self._refresh_count()
        self._refresh_template_label()
        self._refresh_boss_hint()
        self._set_status(self._idle_status(), self._idle_message())
        self._boss_timer.start()

        if config.auto_start and self.templates["death"] is not None:
            QTimer.singleShot(0, self.start_detection)
        QTimer.singleShot(300, self._auto_start_rtss)

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)

        self.game_combo = QComboBox()
        for game_id, name in GAMES.items():
            self.game_combo.addItem(name, game_id)
        self.game_combo.setCurrentIndex(max(0, self.game_combo.findData(self.paths.game)))
        self.game_combo.setToolTip("Każda gra ma własny licznik śmierci, bossów i kalibrację.")
        self.game_combo.setMinimumWidth(260)
        self.game_combo.currentIndexChanged.connect(self._on_game_selected)
        game_row = QHBoxLayout()
        game_row.addStretch(1)
        game_row.addWidget(QLabel("Gra:"))
        game_row.addWidget(self.game_combo)
        game_row.addStretch(1)
        root.addLayout(game_row)

        title = QLabel("ŚMIERCI")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color:#b9a77f; letter-spacing:4px; font-weight:bold;")
        self.count_label = QLabel("0")
        self.count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        count_font = QFont("Segoe UI", 54)
        count_font.setBold(True)
        self.count_label.setFont(count_font)
        root.addWidget(title)
        root.addWidget(self.count_label)

        self.error_banner = QLabel()
        self.error_banner.setWordWrap(True)
        self.error_banner.setStyleSheet("background:#5a1d1d; color:#ffd7d7; padding:6px; border-radius:4px;")
        self.error_banner.hide()
        root.addWidget(self.error_banner)

        status_box = QGroupBox("Stan")
        status_form = QFormLayout(status_box)
        self.status_label = QLabel()
        self.status_label.setStyleSheet("padding:2px 8px; border-radius:4px; color:white; font-weight:bold;")
        self.status_message = QLabel()
        self.status_message.setWordWrap(True)
        self.image_label = QLabel("–")
        self.score_label = QLabel("–")
        self.boss_score_label = QLabel("–")
        self.template_label = QLabel()
        self.notice_label = QLabel()
        self.notice_label.setWordWrap(True)
        self.notice_label.setStyleSheet("color:#9aa0a6;")
        status_row = QHBoxLayout()
        status_row.addWidget(self.status_label)
        status_row.addWidget(self.status_message, 1)
        status_form.addRow("Wykrywanie:", status_row)
        status_form.addRow("Obraz:", self.image_label)
        status_form.addRow("Dopasowanie:", self.score_label)
        status_form.addRow("Boss:", self.boss_score_label)
        status_form.addRow("Wzorce:", self.template_label)
        status_form.addRow("", self.notice_label)
        root.addWidget(status_box)

        controls = QGridLayout()
        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self.toggle_detection)
        self.overlay_button = QPushButton()
        self.overlay_button.clicked.connect(self.toggle_overlay)
        self.plus_button = QPushButton("Dodaj +1")
        self.plus_button.clicked.connect(self._manual_plus)
        self.minus_button = QPushButton("Cofnij -1")
        self.minus_button.clicked.connect(self._manual_minus)
        self.reset_button = QPushButton("Reset")
        self.reset_button.clicked.connect(self.confirm_reset)
        self.calibrate_button = QPushButton("Kalibracja…")
        self.calibrate_button.clicked.connect(lambda: self.open_calibration())
        for button in (self.start_button, self.overlay_button):
            button.setMinimumHeight(36)
        controls.addWidget(self.start_button, 0, 0, 1, 2)
        controls.addWidget(self.overlay_button, 0, 2, 1, 2)
        controls.addWidget(self.plus_button, 1, 0)
        controls.addWidget(self.minus_button, 1, 1)
        controls.addWidget(self.reset_button, 1, 2)
        controls.addWidget(self.calibrate_button, 1, 3)
        root.addLayout(controls)

        self.boss_panel = BossPanel(self.bosses)
        self.boss_panel.track_toggled.connect(self._on_track_bosses)
        self.boss_panel.changed.connect(self._refresh_overlay)
        self.boss_panel.save_failed.connect(self._show_error)
        self.boss_panel.calibrate_requested.connect(lambda: self.open_calibration("boss_bar"))
        root.addWidget(self.boss_panel)

        settings_row = QHBoxLayout()
        settings_row.addWidget(self._build_overlay_box())
        settings_row.addWidget(self._build_detector_box())
        root.addLayout(settings_row)

        footer = self.footer_label = QLabel()
        footer.setStyleSheet("color:#7d828a;")
        footer.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        footer.setWordWrap(True)
        self._refresh_footer()
        self.report_button = QPushButton("Raport PDF…")
        self.report_button.setToolTip("Raport: śmierci łącznie oraz bossowie pokonani i niepokonani (śmierci, czas walki).")
        self.report_button.clicked.connect(self.generate_report)
        footer_row = QHBoxLayout()
        footer_row.addWidget(footer, 1)
        footer_row.addWidget(self.report_button)
        root.addLayout(footer_row)

        self.setCentralWidget(central)
        self.resize(640, 860)

    def _build_overlay_box(self) -> QGroupBox:
        box = QGroupBox("Nakładka")
        form = QFormLayout(box)
        s = self.config.overlay
        self.overlay_mode = QComboBox()
        for mode, label in OVERLAY_MODE_LABELS.items():
            self.overlay_mode.addItem(label, mode)
        self.overlay_mode.setCurrentIndex(max(0, self.overlay_mode.findData(s.mode)))
        self.overlay_mode.setToolTip(
            "Okno na wierzchu działa w trybie okienkowym, a w pełnym ekranie tylko wtedy, gdy Windows\n"
            "stosuje optymalizacje pełnego ekranu. RTSS (RivaTuner Statistics Server) wyświetla licznik\n"
            "także w ekskluzywnym pełnym ekranie – musi być uruchomiony, a jego OSD włączone.\n"
            "Pozycję i wielkość tekstu RTSS ustawia się w samym RTSS."
        )
        self.overlay_mode.currentIndexChanged.connect(self._on_overlay_settings)
        self.rtss_label = QLabel()
        self.rtss_label.setWordWrap(True)
        self.rtss_label.setStyleSheet("color:#9aa0a6;")
        self.overlay_x = _spin(-20000, 20000, s.x, " px")
        self.overlay_y = _spin(-20000, 20000, s.y, " px")
        self.overlay_size = _spin(10, 200, s.font_size, " px")
        self.overlay_hide = QCheckBox("Niewidoczna dla nagrywania/OBS")
        self.overlay_hide.setChecked(s.hide_from_capture)
        self.overlay_hide.setToolTip(
            "Nakładka będzie widoczna tylko na monitorze, a nie na zrzutach i w programach do nagrywania."
        )
        for widget in (self.overlay_x, self.overlay_y, self.overlay_size):
            widget.valueChanged.connect(self._on_overlay_settings)
        self.overlay_hide.toggled.connect(self._on_overlay_settings)
        form.addRow("Tryb:", self.overlay_mode)
        form.addRow("RTSS:", self.rtss_label)
        self.rtss_autostart = QCheckBox("Uruchamiaj RTSS razem z licznikiem")
        self.rtss_autostart.setChecked(self.config.rtss.auto_start)
        self.rtss_autostart.toggled.connect(self._on_rtss_autostart)
        self.rtss_install_button = QPushButton("Zainstaluj RTSS…")
        self.rtss_install_button.clicked.connect(lambda: self._start_rtss_setup(install=True))
        self.rtss_install_button.setVisible(rtss_setup.find_rtss() is None)
        form.addRow(self.rtss_autostart)
        form.addRow(self.rtss_install_button)
        form.addRow("Pozycja X:", self.overlay_x)
        form.addRow("Pozycja Y:", self.overlay_y)
        form.addRow("Wielkość tekstu:", self.overlay_size)
        form.addRow(self.overlay_hide)
        return box

    def _build_detector_box(self) -> QGroupBox:
        box = QGroupBox("Wykrywanie")
        form = QFormLayout(box)
        d = self.config.detector
        self.monitor_combo = QComboBox()
        self._fill_monitors()
        self.monitor_combo.currentIndexChanged.connect(self._on_detector_settings)
        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(0.30, 0.99)
        self.threshold_spin.setSingleStep(0.01)
        self.threshold_spin.setValue(d.threshold)
        self.threshold_spin.setToolTip("Minimalne dopasowanie obrazu do wzorca, przy którym napis uznajemy za widoczny.")
        self.confirm_spin = _spin(1, 50, d.confirm_samples, " próbek")
        self.confirm_spin.setToolTip("Tyle kolejnych próbek (co ok. 0,1 s) musi zawierać napis, by zliczyć śmierć.")
        self.rearm_spin = QDoubleSpinBox()
        self.rearm_spin.setRange(0.5, 60.0)
        self.rearm_spin.setSingleStep(0.5)
        self.rearm_spin.setSuffix(" s")
        self.rearm_spin.setValue(d.rearm_seconds)
        self.rearm_spin.setToolTip("Tyle sekund bez napisu, zanim detektor będzie gotowy na kolejną śmierć.")
        for widget in (self.threshold_spin, self.confirm_spin, self.rearm_spin):
            widget.valueChanged.connect(self._on_detector_settings)
        self.autostart_check = QCheckBox("Włączaj wykrywanie przy starcie")
        self.autostart_check.setChecked(self.config.auto_start)
        self.autostart_check.toggled.connect(self._on_autostart)
        form.addRow("Monitor:", self.monitor_combo)
        form.addRow("Próg:", self.threshold_spin)
        form.addRow("Potwierdzenie:", self.confirm_spin)
        form.addRow("Ponowne uzbrojenie:", self.rearm_spin)
        form.addRow(self.autostart_check)
        return box

    def _fill_monitors(self) -> None:
        capture = self.config.capture
        self.monitor_combo.addItem("Główny monitor", None)
        try:
            outputs = list_outputs()
        except CaptureError as exc:
            outputs = []
            self._show_error(str(exc))
        for out in outputs:
            if out.device_index == capture.device_index:
                self.monitor_combo.addItem(out.label, out.output_index)
        index = self.monitor_combo.findData(capture.output_index)
        self.monitor_combo.setCurrentIndex(max(0, index))

    # ------------------------------------------------------------ licznik

    def _change_deaths(self, operation, manual: bool, boss_event=None) -> None:
        """Zmienia ogólny licznik (deaths.json), a potem – jeśli trzeba – licznik bossa (bosses.json)."""
        try:
            operation()
        except StorageError as exc:
            self._show_error(f"Nie zapisano wyniku: {exc} Kolejna zmiana ponowi zapis.")
            if manual:
                QMessageBox.critical(self, "Błąd zapisu", str(exc))
        else:
            self._clear_error()
        if boss_event is not None:
            self._boss_event(boss_event)
        self._refresh_count()

    def _manual_plus(self, manual: bool = True) -> None:
        self._change_deaths(self.store.increment, manual, self.bosses.manual_add)

    def _manual_minus(self, manual: bool = True) -> None:
        if self.store.deaths > 0:
            self._change_deaths(self.store.decrement, manual, self.bosses.manual_undo)

    def _refresh_count(self) -> None:
        deaths = self.store.deaths
        self.count_label.setText(str(deaths))
        self.minus_button.setEnabled(deaths > 0)
        self._refresh_overlay()

    # ------------------------------------------------------- walka z bossem

    def _boss_event(self, event) -> None:
        try:
            event()
        except StorageError as exc:
            self._show_error(f"Nie zapisano danych bossa: {exc} Kolejna zmiana ponowi zapis.")
        self.boss_panel.refresh()

    def _on_boss_tick(self) -> None:
        self._boss_event(self.bosses.tick)
        self._refresh_overlay()

    def _on_track_bosses(self, checked: bool) -> None:
        self.config.bosses.track = checked
        self._save_timer.start()
        self._refresh_overlay()
        self._refresh_boss_hint()

    def _on_boss_signal(self, event: str) -> None:
        handlers = {
            BOSS_BAR_VISIBLE: self.bosses.boss_bar_visible,
            BOSS_BAR_LOST: self.bosses.boss_bar_lost,
            BOSS_VICTORY: self.bosses.victory,
            FRAMES_LOST: self.bosses.frames_lost,
        }
        self._boss_event(handlers[event])
        self._refresh_overlay()

    # ------------------------------------------------------------------ gra

    def _use_game(self, game: GameData) -> None:
        self.paths = game.paths
        self.store = game.store
        self.calibration = game.calibration
        self.templates = dict(game.templates)
        self.bosses = BossTracker(game.boss_store)
        self.bosses.enabled = self.config.bosses.track

    def _on_game_selected(self) -> None:
        game_id = self.game_combo.currentData()
        if game_id == self.paths.game and self._pending_game is None:
            return
        if self.worker is not None:
            # Wątek wykrywania używa wzorców bieżącej gry – zmiana nastąpi, gdy się zatrzyma.
            self._pending_game = game_id
            self.stop_detection()
            return
        self._switch_game(game_id, restart=False)

    def _switch_game(self, game_id: str, restart: bool) -> None:
        if game_id != self.paths.game:
            self._boss_event(self.bosses.pause)  # czas trwającej walki zostaje zapisany
            try:
                game = open_game(self.paths.base, game_id)
            except StorageError as exc:
                QMessageBox.critical(self, "Zmiana gry", f"Nie można wczytać danych gry.\n\n{exc}")
                self.game_combo.blockSignals(True)
                self.game_combo.setCurrentIndex(max(0, self.game_combo.findData(self.paths.game)))
                self.game_combo.blockSignals(False)
                game = None
            if game is not None:
                self._use_game(game)
                self.config.game = game_id
                self._save_timer.start()
                self.boss_panel.set_tracker(self.bosses)
                self._refresh_count()
                self._refresh_template_label()
                self._refresh_footer()
                self._set_status(self._idle_status(), self._idle_message())
                self.notice_label.setText(f"Wybrano grę: {game_name(game_id)}.")
                for warning in game.warnings:
                    QMessageBox.warning(self, "Death Counter", warning)
        self._refresh_boss_hint()
        # Wykrywanie wraca, jeśli działało przed zmianą gry albo ma się włączać samo (np. po grze bez wzorców).
        if (restart or self.config.auto_start) and self.templates["death"] is not None:
            self.start_detection()

    def _refresh_footer(self) -> None:
        self.footer_label.setText(f"Dane gry: {self.paths.game_dir}")

    def generate_report(self) -> None:
        now = datetime.now()
        default = self.paths.base / f"DeathCounter_raport_{self.paths.game}_{now:%Y-%m-%d}.pdf"
        path, _ = QFileDialog.getSaveFileName(self, "Zapisz raport PDF", str(default), "Dokument PDF (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        rows = rows_from_records(self.bosses.store.records, self.bosses.current, self.bosses.elapsed())
        try:
            write_pdf(path, build_report_html(game_name(self.paths.game), self.store.deaths, rows, now))
        except (StorageError, OSError) as exc:
            QMessageBox.critical(self, "Raport PDF", f"Nie udało się zapisać raportu.\n\n{exc}")
            return
        self.notice_label.setText(f"Zapisano raport: {path}")
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _refresh_boss_hint(self) -> None:
        missing = [label for kind, label in (("boss_bar", "pasek bossa"), ("victory", "komunikat zwycięstwa"))
                   if self.templates[kind] is None]
        if missing:
            hint = f"Brak wzorca: {', '.join(missing)}. Kliknij „Kalibracja walki…”, aby walka startowała sama."
        elif self.worker is None:
            hint = "Wykrywanie jest wyłączone – kliknij Start, aby walka była rozpoznawana."
        else:
            hint = "Walka zacznie się sama, gdy na ekranie pojawi się pasek zdrowia bossa."
        self.boss_panel.set_hint(hint)

    def _refresh_overlay(self) -> None:
        """Ten sam tekst trafia do nakładki-okna i do RTSS, więc obie pokazują to samo."""
        boss = self.bosses.view() if self.bosses.enabled else None
        self.overlay.set_text(overlay_text(self.store.deaths, boss))
        self._update_rtss()

    def confirm_reset(self) -> None:
        answer = QMessageBox.question(
            self,
            "Reset licznika",
            f"Czy na pewno wyzerować licznik? Obecna wartość ({self.store.deaths}) zostanie utracona.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._change_deaths(self.store.reset, manual=True)

    def _on_death_detected(self) -> None:
        self._change_deaths(self.store.increment, manual=False, boss_event=self.bosses.death)

    # ---------------------------------------------------------- wykrywanie

    def toggle_detection(self) -> None:
        if self.worker is None:
            self.start_detection()
        else:
            self.stop_detection()

    def start_detection(self) -> None:
        if self.worker is not None:
            return
        if self.templates["death"] is None:
            self._set_status(DetectorStatus.NO_TEMPLATE, "Najpierw wykonaj kalibrację (przycisk „Kalibracja…”).")
            return
        worker = DetectionWorker(self.templates, self.config.detector, self.config.capture, self.config.bosses)
        worker.death_detected.connect(self._on_death_detected)
        worker.boss_event.connect(self._on_boss_signal)
        worker.status_changed.connect(self._set_status)
        worker.sample.connect(self._on_sample)
        worker.snapshot_ready.connect(self._on_snapshot)
        worker.notice.connect(self.notice_label.setText)
        worker.finished.connect(self._on_worker_finished)
        self.worker = worker
        self._stop_requested = False
        self.start_button.setText("Stop")
        self._set_status(DetectorStatus.ACTIVE, "Uruchamianie przechwytywania…")
        worker.start()
        self._refresh_boss_hint()

    def stop_detection(self) -> None:
        if self.worker is not None:
            self.start_button.setEnabled(False)
            self.start_button.setText("Zatrzymywanie…")
            self._stop_requested = True
            self.worker.request_stop()

    def _on_worker_finished(self) -> None:
        worker, self.worker = self.worker, None
        if worker is not None:
            worker.deleteLater()
        self._flush_frame_callbacks(None, "Wykrywanie zostało zatrzymane przed pobraniem obrazu.")
        self.start_button.setEnabled(True)
        self.start_button.setText("Start")
        self.score_label.setText("–")
        self.boss_score_label.setText("–")
        # Bez wykrywania nikt nie zgłosi śmierci ani zniknięcia paska – timer walki staje.
        self._boss_event(self.bosses.pause)
        self._refresh_overlay()
        self._refresh_boss_hint()
        # Błąd, który sam zakończył wątek, zostaje widoczny; zwykłe zatrzymanie pokazuje stan spoczynku.
        if self._stop_requested or self._status is not DetectorStatus.ERROR:
            self._set_status(self._idle_status(), self._idle_message())
        if self._closing:
            self.close()
            return
        if self._pending_game is not None:
            game_id, self._pending_game = self._pending_game, None
            self._switch_game(game_id, restart=True)

    def _on_sample(self, result: SampleResult) -> None:
        check = result.check
        if check.resolution:
            w, h = check.resolution
            state = {
                CaptureHealth.OK: "OK",
                CaptureHealth.NO_FRAMES: "brak nowych klatek",
                CaptureHealth.FROZEN: "zamrożony",
            }[check.health]
            self.image_label.setText(f"{w}×{h}, {state}")
        else:
            self.image_label.setText("brak klatek")
        if result.score is None:
            self.score_label.setText("–")
        else:
            armed = "gotowy" if result.armed else "czeka na zniknięcie napisu"
            self.score_label.setText(
                f"{result.score:.2f} (próg {self.config.detector.threshold:.2f}) – detektor {armed}"
            )
        parts = []
        if result.bar_score is not None:
            bar = "widoczny" if result.bar_visible else "niewidoczny"
            parts.append(f"pasek {result.bar_score:.2f} ({bar})")
        if result.victory_score is not None:
            parts.append(f"zwycięstwo {result.victory_score:.2f}")
        self.boss_score_label.setText(", ".join(parts) or "–")

    def _set_status(self, status: DetectorStatus, message: str) -> None:
        self._status = status
        self.status_label.setText(status.value.upper())
        self.status_label.setStyleSheet(
            f"padding:2px 8px; border-radius:4px; color:white; font-weight:bold; background:{STATUS_COLORS[status]};"
        )
        self.status_message.setText(message)

    def _idle_status(self) -> DetectorStatus:
        return DetectorStatus.STOPPED if self.templates["death"] is not None else DetectorStatus.NO_TEMPLATE

    def _idle_message(self) -> str:
        if self.templates["death"] is None:
            return "Brak wzorca – wykonaj kalibrację, aby włączyć wykrywanie."
        return "Wykrywanie wyłączone. Kliknij Start."

    def _on_detector_settings(self) -> None:
        d = self.config.detector
        d.threshold = round(self.threshold_spin.value(), 2)
        d.confirm_samples = self.confirm_spin.value()
        d.rearm_seconds = self.rearm_spin.value()
        self.config.capture.output_index = self.monitor_combo.currentData()
        if self.worker is not None:
            self.worker.update_settings(self.config.detector, self.config.capture)
        self._save_timer.start()

    def _on_autostart(self, checked: bool) -> None:
        self.config.auto_start = checked
        self._save_timer.start()

    # ------------------------------------------------------------- nakładka

    def toggle_overlay(self) -> None:
        self.config.overlay.enabled = not self.config.overlay.enabled
        self._apply_overlay()
        self._save_timer.start()

    def _apply_overlay(self) -> None:
        s = self.config.overlay
        self.overlay.setVisible(s.enabled and s.mode in ("window", "both"))
        if s.enabled and s.mode in ("rtss", "both"):
            self._rtss_timer.start()
            self._update_rtss()
        else:
            self._rtss_timer.stop()
            self.rtss.clear()
            self.rtss_label.setText("nieużywany" if s.mode == "window" else "nakładka wyłączona")
        self.overlay_button.setText("Nakładka: Wyłącz" if s.enabled else "Nakładka: Włącz")

    def _update_rtss(self) -> None:
        if not self._rtss_timer.isActive():
            return
        state = self.rtss.show(self.overlay.text)
        if state is RtssState.SHOWN:
            self.rtss_label.setText("licznik przekazany do RTSS")
        elif state is RtssState.NOT_RUNNING:
            self.rtss_label.setText("RTSS nie jest uruchomiony – licznik pojawi się, gdy go włączysz")
        else:
            self.rtss_label.setText(state.value)

    def _on_overlay_settings(self) -> None:
        s = self.config.overlay
        if s.mode == "window" and self.overlay_mode.currentData() != "window":
            QTimer.singleShot(0, self._auto_start_rtss)
        s.mode = self.overlay_mode.currentData()
        s.x = self.overlay_x.value()
        s.y = self.overlay_y.value()
        s.font_size = self.overlay_size.value()
        s.hide_from_capture = self.overlay_hide.isChecked()
        self.overlay.apply_settings(s)
        self._apply_overlay()
        self._save_timer.start()

    # ------------------------------------------------------------ kalibracja

    def request_frame(self, callback) -> None:
        """Pobiera aktualny obraz ekranu; callback(frame | None, komunikat_błędu | None)."""
        if self.worker is not None:
            self._frame_callbacks.append(callback)
            self.worker.request_snapshot()
            return
        try:
            frame = grab_single_frame(self.config.capture)
        except CaptureError as exc:
            callback(None, str(exc))
        else:
            callback(frame, None)

    def _on_snapshot(self, frame) -> None:
        self._flush_frame_callbacks(frame, None if frame is not None else "Brak obrazu z wybranego monitora.")

    def _flush_frame_callbacks(self, frame, error) -> None:
        callbacks, self._frame_callbacks = self._frame_callbacks, []
        for callback in callbacks:
            callback(frame, error)

    def open_calibration(self, kind: str = "death") -> None:
        # Zrzut ze skrótu trafia do otwieranej zakładki tylko raz; potem kalibracja pokazuje zapisane wzorce.
        hotkey_frame, self._hotkey_frame = self._hotkey_frame, None
        dialog = CalibrationDialog(
            self,
            frame_provider=self.request_frame,
            saver=self._save_template,
            templates=self.templates,
            saved={k: self._saved_calibration(k) for k in self.templates},
            threshold=self.config.detector.threshold,
            margin=self.config.detector.search_margin,
            hotkey_text=HOTKEY_TEXT if HOTKEY_SNAPSHOT in self._hotkeys else None,
            initial_frame=hotkey_frame,
            initial_kind=kind,
        )
        self._calibration = dialog
        try:
            dialog.exec()
        finally:
            self._calibration = None

    def _saved_calibration(self, kind: str) -> SavedCalibration | None:
        template = self.templates[kind]
        if template is None:
            return None
        frame = load_source_image(self.paths.source_path(kind), template.reference_size)
        if frame is not None:
            return SavedCalibration(frame, full=True)
        return SavedCalibration(template.preview_frame(), full=False)

    def _save_template(self, kind: str, template: DeathTemplate, frame: np.ndarray) -> str | None:
        """Zapis wzorca z okna kalibracji: wzorzec PNG, pełny zrzut (do podglądu) i config.json.
        Wzorzec jest od razu używany przez wykrywanie."""
        try:
            self.calibration.set_info(kind, template.save(self.paths.template_path(kind)))
            save_calibration(self.paths.calibration, self.calibration)
        except StorageError as exc:
            return str(exc)
        try:
            save_source_image(self.paths.source_path(kind), frame)
        except StorageError as exc:
            # Wzorzec działa także bez podglądu – zgłaszamy, ale nie przerywamy.
            self.notice_label.setText(f"Wzorzec zapisany, ale bez zrzutu do podglądu: {exc}")
        self.templates[kind] = template
        self._refresh_template_label()
        self._refresh_boss_hint()
        if self.worker is not None:
            self.worker.update_template(kind, template)
        elif self._status in (DetectorStatus.NO_TEMPLATE, DetectorStatus.STOPPED):
            self._set_status(self._idle_status(), self._idle_message())
        return None

    def _refresh_template_label(self) -> None:
        names = (("death", "śmierć"), ("boss_bar", "pasek bossa"), ("victory", "zwycięstwo"))
        parts = [f"{label}: {'✓' if self.templates[kind] is not None else 'brak'}" for kind, label in names]
        self.template_label.setText(", ".join(parts))

    def _on_hotkey(self, hotkey_id: int) -> None:
        if hotkey_id == HOTKEY_SNAPSHOT:
            self.request_frame(self._on_hotkey_frame)
            return
        # Korekta z gry: bez okienek, które zabrałyby fokus grze – tylko sygnał dźwiękowy.
        if hotkey_id == HOTKEY_PLUS:
            self._manual_plus(manual=False)
        else:
            self._manual_minus(manual=False)
        winsound.MessageBeep(winsound.MB_OK if hotkey_id == HOTKEY_PLUS else winsound.MB_ICONASTERISK)

    def _on_hotkey_frame(self, frame, error) -> None:
        if frame is None:
            winsound.MessageBeep(winsound.MB_ICONHAND)
            self.notice_label.setText(f"Zrzut ze skrótu {HOTKEY_TEXT} nieudany: {error}")
            return
        winsound.MessageBeep(winsound.MB_OK)
        self._hotkey_frame = frame
        if self._calibration is not None:
            self._calibration.set_frame(frame)
        else:
            self.notice_label.setText(
                f"Zapamiętano zrzut ekranu ({HOTKEY_TEXT}). Otwórz „Kalibracja…”, aby zaznaczyć napis."
            )

    # ---------------------------------------------------------- okno/system

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._hotkeys:
            return
        failed = []
        for hotkey_id, (vk, text) in HOTKEYS.items():
            if winapi.register_hotkey(int(self.winId()), hotkey_id, winapi.MOD_CONTROL | winapi.MOD_ALT, vk):
                self._hotkeys.add(hotkey_id)
            else:
                failed.append(text)
        if failed:
            self.notice_label.setText(f"Skróty zajęte przez inny program: {', '.join(failed)}.")

    def nativeEvent(self, event_type, message):
        if bytes(event_type) == b"windows_generic_MSG":
            msg = winapi.message_from_native(message)
            if msg.message == winapi.WM_HOTKEY and msg.wParam in self._hotkeys:
                self._on_hotkey(msg.wParam)
                return True, 0
        return super().nativeEvent(event_type, message)

    # ------------------------------------------------------------------ RTSS

    def _auto_start_rtss(self) -> None:
        r = self.config.rtss
        if not r.auto_start or self.config.overlay.mode == "window":
            return
        if rtss_setup.find_rtss() is not None:
            self._start_rtss_setup(install=False)
            return
        if r.install_declined:
            return
        answer = QMessageBox.question(
            self,
            "RivaTuner Statistics Server",
            "Do wyświetlania licznika nad grą w pełnym ekranie potrzebny jest darmowy program "
            "RivaTuner Statistics Server (RTSS).\n\n"
            "Zainstalować go teraz? Instalacja pobierze oficjalną paczkę Guru3D przez winget, "
            "a Windows poprosi o zgodę administratora.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._start_rtss_setup(install=True)
        else:
            r.install_declined = True
            self.notice_label.setText("RTSS możesz zainstalować później przyciskiem „Zainstaluj RTSS…”.")
            self._save_timer.start()

    def _start_rtss_setup(self, install: bool) -> None:
        if self._rtss_setup is not None:
            return
        worker = RtssSetupWorker(install, self)
        worker.progress.connect(self.notice_label.setText)
        worker.done.connect(lambda ok, message: self._on_rtss_setup_done(ok, message, install))
        self._rtss_setup = worker
        self.rtss_install_button.setEnabled(False)
        worker.start()

    def _on_rtss_setup_done(self, ok: bool, message: str, install: bool) -> None:
        worker, self._rtss_setup = self._rtss_setup, None
        if worker is not None:
            worker.wait()
            worker.deleteLater()
        self.rtss_install_button.setEnabled(True)
        self.rtss_install_button.setVisible(rtss_setup.find_rtss() is None)
        self.notice_label.setText(message)
        if ok:
            # Licznik trafi do świeżo uruchomionego RTSS przy najbliższym odświeżeniu.
            QTimer.singleShot(1500, self._update_rtss)
        elif install:
            QMessageBox.warning(self, "RivaTuner Statistics Server", message)
        if self._closing:
            self.close()

    def _on_rtss_autostart(self, checked: bool) -> None:
        self.config.rtss.auto_start = checked
        self._save_timer.start()
        if checked:
            self._auto_start_rtss()

    # ---------------------------------------------------------- zamykanie

    def closeEvent(self, event) -> None:
        if self._rtss_setup is not None:
            # Nie przerywamy instalacji RTSS w połowie – okno zamknie się po jej zakończeniu.
            self._closing = True
            self.notice_label.setText("Kończenie konfiguracji RTSS – program zamknie się za chwilę.")
            event.ignore()
            return
        if self.worker is not None:
            # Najpierw kończymy wątek wykrywania, okno zamknie się po jego zakończeniu.
            self._closing = True
            self.stop_detection()
            event.ignore()
            return
        for hotkey_id in self._hotkeys:
            winapi.unregister_hotkey(int(self.winId()), hotkey_id)
        self._hotkeys.clear()
        self._save_timer.stop()
        self._save_config()
        self._boss_timer.stop()
        self._boss_event(self.bosses.pause)
        self._rtss_timer.stop()
        self.rtss.clear()
        self.overlay.close()
        super().closeEvent(event)

    def _save_config(self) -> None:
        try:
            save_config(self.paths.config, self.config)
        except StorageError as exc:
            self._show_error(f"Nie zapisano ustawień: {exc}")

    def _show_error(self, message: str) -> None:
        self.error_banner.setText(message)
        self.error_banner.show()

    def _clear_error(self) -> None:
        self.error_banner.hide()


def _spin(low: int, high: int, value: int, suffix: str = "") -> QSpinBox:
    spin = QSpinBox()
    spin.setRange(low, high)
    spin.setValue(value)
    spin.setSuffix(suffix)
    return spin
