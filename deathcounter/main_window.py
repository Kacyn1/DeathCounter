"""Główne okno: licznik, walka z bossem, status, sterowanie wykrywaniem i nakładką."""

from __future__ import annotations

import getpass
import time
import winsound
from pathlib import Path
from datetime import datetime

import numpy as np
from PySide6.QtCore import QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QFont, QIcon
from PySide6.QtNetwork import QLocalServer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QInputDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStyle,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

from . import game_process, hotkeys, legal, updater, winapi
from .boss_panel import BossPanel
from .collapsible import CollapsibleBox
from .bosses import BossState, BossTracker, format_duration, overlay_text
from .calibration import CalibrationDialog, SavedCalibration
from .hotkey_dialog import HotkeyDialog
from .icon import flag, render as render_icon
from .capture import CaptureError, grab_single_frame, list_outputs
from .config import DEFAULT_GAME, AppConfig, save_calibration, save_config
from .game_data import GameData, counter_files, open_game
from . import __version__
from .detector import CaptureHealth, SampleResult
from .diagnostics import DiagnosticLog
from .discord_presence import DiscordPresence, build_activity
from .overlay import OverlayWindow
from .results_window import ResultsWindow
from .session_stats import SessionStatsWindow
from .report import Adjustments, CertificateData, Verdict, rows_from_records, verify_pdf, write_certificate
from .signing import load_key
from .steam_dialog import SteamScanDialog
from .steam_library import find_steam, installed_games
from .play_session import GAP_SECONDS
from .rtss import RtssOsd, RtssState
from .storage import StorageError
from .template import DeathTemplate, load_source_image, save_source_image
from .i18n import LANGUAGES, N_, tr
from . import rtss_setup
from .worker import (
    BOSS_BAR_LOST,
    BOSS_BAR_VISIBLE,
    BOSS_VICTORY,
    FRAMES_LOST,
    DetectionWorker,
    DetectorStatus,
    RtssSetupWorker,
    UpdateCheckWorker,
    UpdateDownloadWorker,
)

# Kanał, przez który ponowne uruchomienie exe prosi działający program o pokazanie okna.
INSTANCE_SERVER = f"DeathCounterByMK-{getpass.getuser()}"
UPDATE_CHECK_TIMER_MS = 3600 * 1000  # co godzinę: czy minęła doba od ostatniego sprawdzenia
TIMEOUT_MS_ON_CLOSE = 20000          # zamknięcie czeka na wątek aktualizacji (sieć ma 15 s limitu)

# Skróty globalne (działają także w pełnym ekranie): identyfikator RegisterHotKey → pole HotkeySettings.
HOTKEY_IDS = {0xD52: "snapshot", 0xD53: "plus", 0xD54: "minus", 0xD55: "overlay"}
ADD_GAME = "__add_game__"  # pozycja „+ Dodaj grę…” na liście gier
STEAM_SCAN = "__steam_scan__"  # pozycja „Znajdź zainstalowane gry ze Steam…”
RTSS_REFRESH_MS = 2000
WINDOW_WIDTH = 640  # początkowa szerokość okna; wysokość dopasowuje się do zawartości i ekranu
PROCESS_CHECK_MS = 2000  # co tyle sprawdzamy, która gra jest uruchomiona
BOSS_REFRESH_MS = 1000
OVERLAY_MODE_LABELS = {
    "both": N_("Okno + RTSS"),
    "window": N_("Okno na wierzchu"),
    "rtss": N_("Tylko RTSS (pełny ekran)"),
}

# Znacznik stanu sesji (jak w sekcjach „Stan” i „Walka z bossem”): napis i kolor tła.
SESSION_BADGES = {
    "running": (N_("W grze"), "#2f9e5b"),
    "background": (N_("Pauza"), "#c97a1e"),
    "break": (N_("Przerwa"), "#b8860b"),
    "waiting": (N_("Oczekiwanie"), "#6b6f76"),
    "unknown": (N_("Nieznana gra"), "#c97a1e"),
    "off": (N_("Wyłączona"), "#6b6f76"),
}

# Czy licznik widać w grze (wiersz „Nakładka” w sekcji „Stan”): napis znacznika i kolor tła.
OVERLAY_BADGES = {
    "visible": (N_("Widoczna"), "#2f9e5b"),
    "partial": (N_("Częściowo"), "#c97a1e"),
    "invisible": (N_("Niewidoczna"), "#c97a1e"),
    "hidden": (N_("Ukryta"), "#6b6f76"),
}

STATUS_COLORS = {
    DetectorStatus.ACTIVE: "#2f9e5b",
    DetectorStatus.STOPPED: "#6b6f76",
    DetectorStatus.NO_IMAGE: "#c97a1e",
    DetectorStatus.NO_TEMPLATE: "#c97a1e",
    DetectorStatus.ERROR: "#c0392b",
}


class MainWindow(QMainWindow):
    def __init__(self, config: AppConfig, game: GameData, after_update: bool = False):
        super().__init__()
        self.setWindowTitle("Death Counter by MK")
        self.config = config
        self._use_game(game)
        self._pending_game: str | None = None   # zmiana gry czeka na zatrzymanie wykrywania
        self._pending_delete: str | None = None  # usunięcie licznika też
        self.diag = DiagnosticLog(self.paths.base / "diagnostyka.log")
        self.diag.write(f"=== Death Counter by MK {__version__} – gra: {self.config.game_name(self.paths.game)}, "
                        f"śmierci: {self.store.deaths}, śledzenie bossa: {self.config.bosses.track} ===")
        self.worker: DetectionWorker | None = None
        self._status = DetectorStatus.STOPPED
        self._frame_callbacks: list = []
        self._hotkey_frame: np.ndarray | None = None
        self._hotkeys: set[int] = set()  # zarejestrowane identyfikatory z HOTKEY_IDS
        self._calibration: CalibrationDialog | None = None
        self._results: ResultsWindow | None = None
        self._session_stats: SessionStatsWindow | None = None
        self._closing = False
        self._stop_requested = False
        self._rtss_setup: RtssSetupWorker | None = None
        self.discord: DiscordPresence | None = None
        self._discord_state = ""                  # ustawiany z wątku Discorda, pokazywany co sekundę
        self._session_started = int(time.time())  # „gra od…” w statusie Discorda, gdy nie śledzimy sesji
        self._matchers: dict[str, game_process.GameMatcher] = {}  # jak rozpoznać proces każdej gry
        self._steam_folders: set[str] = set()  # gry rozpoznawane po folderze instalacji Steama
        self._running_games: set[str] = set()  # gry uruchomione przy ostatnim sprawdzeniu
        self._running_exe: str | None = None   # exe wybranej gry, gdy działa
        self._auto_switched: str | None = None  # gra, na którą licznik przełączył się sam
        self._refresh_matchers()

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
        self._process_timer = QTimer(self, interval=PROCESS_CHECK_MS)
        self._process_timer.timeout.connect(self._on_process_tick)

        self._build_ui()
        self._apply_overlay()
        self._refresh_count()
        self._refresh_template_label()
        self._refresh_boss_hint()
        self._set_status(self._idle_status(), self._idle_message())
        QTimer.singleShot(0, self._report_fixed_names)  # okno najpierw się pokazuje
        QTimer.singleShot(800, self._offer_steam_scan)
        self._boss_timer.start()
        self._process_timer.start()
        QTimer.singleShot(1000, self._on_process_tick)  # gra uruchomiona przed programem
        self._apply_discord()

        if config.auto_start and self.templates["death"] is not None:
            QTimer.singleShot(0, self.start_detection)
        QTimer.singleShot(300, self._auto_start_rtss)
        self._init_updates(after_update)

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)

        self.game_combo = QComboBox()
        self._fill_games()
        self.game_combo.setToolTip(
            tr("Każda gra ma własny licznik śmierci, bossów i kalibrację.\n"
            "„+ Dodaj grę…” tworzy nowy licznik dla gry spoza listy, a „Znajdź zainstalowane gry ze Steam…”\n"
            "dodaje liczniki dla gier souls-like.")
        )
        self.game_combo.setMinimumWidth(260)
        self.game_combo.currentIndexChanged.connect(self._on_game_selected)
        self.delete_counter_button = QPushButton()
        self.delete_counter_button.clicked.connect(self.confirm_delete_counter)
        self._refresh_delete_button()
        game_row = QHBoxLayout()
        game_row.addStretch(1)
        game_row.addWidget(QLabel(tr("Gra:")))
        game_row.addWidget(self.game_combo)
        game_row.addWidget(self.delete_counter_button)
        game_row.addStretch(1)
        root.addLayout(game_row)

        title = QLabel(tr("ŚMIERCI"))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color:#b9a77f; letter-spacing:8px; font-weight:bold; font-size:20pt;")
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
        root.addWidget(self._build_update_banner())

        status_box = QGroupBox(tr("Stan"))
        status_form = QFormLayout(status_box)
        self.status_label = QLabel()
        self.status_label.setStyleSheet("padding:2px 8px; border-radius:4px; color:white; font-weight:bold;")
        self.status_message = QLabel()
        self.status_message.setWordWrap(True)
        self.image_label = QLabel("–")
        self.score_label = QLabel("–")
        self.boss_score_label = QLabel("–")
        self.overlay_badge = QLabel()
        self.overlay_status = QLabel()
        self.overlay_status.setWordWrap(True)
        self._rtss_state: RtssState | None = None  # ostatni wynik przekazania tekstu do RTSS
        self.template_label = QLabel()
        self.notice_label = QLabel()
        self.notice_label.setWordWrap(True)
        self.notice_label.setStyleSheet("color:#9aa0a6;")
        status_row = QHBoxLayout()
        status_row.addWidget(self.status_label)
        status_row.addWidget(self.status_message, 1)
        status_form.addRow(tr("Wykrywanie:"), status_row)
        overlay_row = QHBoxLayout()
        overlay_row.addWidget(self.overlay_badge)
        overlay_row.addWidget(self.overlay_status, 1)
        status_form.addRow(tr("Nakładka:"), overlay_row)
        status_form.addRow(tr("Obraz:"), self.image_label)
        status_form.addRow(tr("Dopasowanie:"), self.score_label)
        status_form.addRow(tr("Boss:"), self.boss_score_label)
        status_form.addRow(tr("Wzorce:"), self.template_label)
        status_form.addRow("", self.notice_label)
        root.addWidget(status_box)

        controls = QGridLayout()
        self.start_button = QPushButton(tr("Start"))
        self.start_button.clicked.connect(self.toggle_detection)
        self.overlay_button = QPushButton()
        self.overlay_button.setCheckable(True)  # wciśnięty, gdy nakładka jest włączona
        self.overlay_button.clicked.connect(self.toggle_overlay)
        self.plus_button = QPushButton(tr("Dodaj +1"))
        self.plus_button.clicked.connect(self._manual_plus)
        self.minus_button = QPushButton(tr("Cofnij -1"))
        self.minus_button.clicked.connect(self._manual_minus)
        self.reset_button = QPushButton(tr("Reset"))
        self.reset_button.clicked.connect(self.confirm_reset)
        self.calibrate_button = QPushButton(tr("Kalibracja…"))
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

        self.boss_panel = BossPanel(self.bosses, self.config.bosses.read_names)
        self.boss_panel.track_toggled.connect(self._on_track_bosses)
        self.boss_panel.read_names_toggled.connect(self._on_read_names)
        self.boss_panel.changed.connect(self._refresh_overlay)
        self.boss_panel.save_failed.connect(self._show_error)
        self.boss_panel.calibrate_requested.connect(lambda: self.open_calibration("boss_bar"))
        self.boss_panel.results_requested.connect(self.open_results)
        root.addWidget(self.boss_panel)
        root.addWidget(self._build_session_box())

        settings_row = QHBoxLayout()
        settings_row.addWidget(self._build_overlay_box(), 1, Qt.AlignmentFlag.AlignTop)
        settings_row.addWidget(self._build_detector_box(), 1, Qt.AlignmentFlag.AlignTop)
        root.addLayout(settings_row)
        root.addStretch(1)

        footer = self.footer_label = QLabel()
        footer.setStyleSheet("color:#7d828a;")
        footer.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        footer.setWordWrap(True)
        self._refresh_footer()
        self.report_button = QPushButton(tr("Certyfikat PDF…"))
        self.report_button.setToolTip(
            tr("Certyfikat wybranej gry: śmierci, pokonani bossowie i ich czasy, z kodem weryfikacyjnym.")
        )
        self.report_button.clicked.connect(self.generate_report)
        self.verify_button = QPushButton(tr("Sprawdź certyfikat…"))
        self.verify_button.setToolTip(tr("Sprawdza, czy plik PDF jest prawdziwym, niezmienionym certyfikatem."))
        self.verify_button.clicked.connect(self.verify_certificate)
        footer_row = QHBoxLayout()
        footer_row.addWidget(footer, 1)
        footer_row.addWidget(self.report_button)
        footer_row.addWidget(self.verify_button)
        hotkeys_button = QPushButton(tr("Skróty…"))
        hotkeys_button.setToolTip(tr("Zmiana skrótów klawiszowych działających w grze."))
        hotkeys_button.clicked.connect(self.open_hotkeys)
        footer_row.addWidget(hotkeys_button)
        about_button = QPushButton(tr("O programie"))
        about_button.clicked.connect(
            lambda: legal.show_about(self, self._build_about_updates(), self._build_about_language()))
        footer_row.addWidget(about_button)
        root.addLayout(footer_row)

        # Na mniejszych ekranach (np. Full HD, skalowanie 125–150%) okno nie mieści całej zawartości –
        # wtedy zawartość przewija się w pionie, a okno ma wysokość ekranu.
        self._content = central
        scroll = QScrollArea()
        scroll.setWidget(central)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.setCentralWidget(scroll)
        self._fitted = False
        self.resize(WINDOW_WIDTH, central.minimumSizeHint().height())

    def _collapsible(self, title: str, setting: str) -> tuple[CollapsibleBox, QFormLayout]:
        box = CollapsibleBox(title, getattr(self.config.ui, setting))
        box.collapsed_changed.connect(lambda collapsed: self._on_section_collapsed(setting, collapsed))
        return box, QFormLayout(box.content)

    def _on_section_collapsed(self, setting: str, collapsed: bool) -> None:
        setattr(self.config.ui, setting, collapsed)
        self._save_timer.start()
        self._fit_to_screen()  # okno kurczy się o zwiniętą sekcję albo rośnie o rozwiniętą, o ile jest miejsce

    def _fit_to_screen(self, move: bool = True) -> None:
        """Okno tak wysokie jak zawartość, ale nie wyższe niż ekran (resztę przewija pasek przewijania).
        `move` – także przesuwa okno, żeby nie wystawało poza ekran (nie w trakcie przeciągania na inny monitor)."""
        self._content.layout().activate()  # przelicza wysokość od razu, np. bez zwiniętej sekcji
        screen = (self.screen() or QApplication.primaryScreen()).availableGeometry()
        frame = self.frameGeometry()
        # Ramka i pasek tytułu okna (przed pierwszym pokazaniem okna Windows jeszcze ich nie podaje – wtedy 0).
        extra_w, extra_h = frame.width() - self.width(), frame.height() - self.height()
        # Okno zawsze ma miejsce na pionowy pasek przewijania: gdy pojawi się przy zmniejszaniu wysokości okna,
        # zawartość nie traci szerokości (inaczej pojawiłby się też pasek poziomy).
        bar = self.style().pixelMetric(QStyle.PixelMetric.PM_ScrollBarExtent)
        width = min(max(WINDOW_WIDTH, self._content.minimumSizeHint().width() + bar), screen.width() - extra_w)
        self.centralWidget().setMinimumWidth(width)
        needed = self._content_height(width)
        if needed > screen.height() - extra_h:
            needed = self._content_height(width - bar)  # z paskiem przewijania zawartość jest o niego węższa
        self.resize(width, min(needed, screen.height() - extra_h))
        if not move:
            return
        frame = self.frameGeometry()
        x = min(max(frame.left(), screen.left()), screen.right() + 1 - frame.width())
        y = min(max(frame.top(), screen.top()), screen.bottom() + 1 - frame.height())
        if (x, y) != (frame.left(), frame.top()):
            self.move(x, y)  # okno nie wystaje poza ekran

    def _content_height(self, width: int) -> int:
        """Wysokość zawartości przy danej szerokości (zawijane etykiety są wyższe, gdy jest węższa)."""
        content = self._content
        return content.heightForWidth(width) if content.hasHeightForWidth() else content.sizeHint().height()

    def _build_session_box(self) -> QGroupBox:
        box, form = self._collapsible(tr("Aktualna sesja"), "session_collapsed")
        s = self.config.session
        self.session_track = QCheckBox(tr("Śledź sesję"))
        self.session_track.setChecked(s.track)
        self.session_track.setToolTip(
            tr("Sesja zaczyna się, gdy uruchomisz grę, a czas biegnie tylko wtedy, gdy gra jest włączona\n"
               "i jest aktywnym oknem – stoi, gdy gra jest zminimalizowana albo w tle po Alt+Tab\n"
               "(po powrocie do gry czas rusza po ok. 2 s, które też są doliczane).\n"
               "Powrót do gry w ciągu 15 minut (np. po wysypaniu się gry) kontynuuje tę samą sesję."))
        self.session_switch = QCheckBox(tr("Przełączaj licznik na uruchomioną grę"))
        self.session_switch.setChecked(s.auto_switch)
        self.session_switch.setToolTip(
            tr("Gdy uruchomisz inną grę z listy, licznik sam się na nią przełączy.\n"
               "Ręczny wybór gry w trakcie grania nie jest cofany."))
        self.session_overlay = QCheckBox(tr("Pokaż sesję na nakładce"))
        self.session_overlay.setChecked(s.show_on_overlay)
        self.session_overlay.setToolTip(tr("Nakładka i RTSS pokazują śmierci i czas sesji, gdy gra jest uruchomiona."))
        for check in (self.session_track, self.session_switch, self.session_overlay):
            check.toggled.connect(self._on_session_settings)
        options = QHBoxLayout()
        options.addWidget(self.session_track)
        options.addWidget(self.session_switch, 1)
        form.addRow(options)
        self.session_badge = QLabel()
        self.session_state = QLabel()
        self.session_state.setWordWrap(True)
        state_row = QHBoxLayout()
        state_row.addWidget(self.session_badge)
        state_row.addWidget(self.session_state, 1)
        self.session_deaths = QLabel("–")
        self.session_time = QLabel("–")
        form.addRow(tr("Stan:"), state_row)
        form.addRow(tr("Śmierci:"), self.session_deaths)
        form.addRow(tr("Czas:"), self.session_time)
        self.session_exe_button = QPushButton()
        self.session_exe_button.clicked.connect(self._pick_game_exe)
        stats_button = QPushButton(tr("Statystyki sesji…"))
        stats_button.setToolTip(tr("Przebieg aktualnej sesji i porównanie wszystkich sesji tej gry."))
        stats_button.clicked.connect(self.open_session_stats)
        bottom = QHBoxLayout()
        bottom.addWidget(self.session_overlay, 1)
        bottom.addWidget(self.session_exe_button)
        bottom.addWidget(stats_button)
        form.addRow(bottom)
        self._refresh_session()
        return box

    def _build_overlay_box(self) -> QGroupBox:
        box, form = self._collapsible(tr("Nakładka"), "overlay_collapsed")
        s = self.config.overlay
        self.overlay_mode = QComboBox()
        for mode, label in OVERLAY_MODE_LABELS.items():
            label = tr(label)
            self.overlay_mode.addItem(label, mode)
        self.overlay_mode.setCurrentIndex(max(0, self.overlay_mode.findData(s.mode)))
        self.overlay_mode.setToolTip(
            tr("Okno na wierzchu działa w trybie okienkowym, a w pełnym ekranie tylko wtedy, gdy Windows\n"
            "stosuje optymalizacje pełnego ekranu. RTSS (RivaTuner Statistics Server) wyświetla licznik\n"
            "także w ekskluzywnym pełnym ekranie – musi być uruchomiony, a jego OSD włączone.\n"
            "Pozycję i wielkość tekstu RTSS ustawia się w samym RTSS.")
        )
        self.overlay_mode.currentIndexChanged.connect(self._on_overlay_settings)
        self.rtss_label = QLabel()
        self.rtss_label.setWordWrap(True)
        self.rtss_label.setStyleSheet("color:#9aa0a6;")
        self.overlay_x = _spin(-20000, 20000, s.x, " px")
        self.overlay_y = _spin(-20000, 20000, s.y, " px")
        self.overlay_size = _spin(10, 200, s.font_size, " px")
        self.overlay_hide = QCheckBox(tr("Niewidoczna dla nagrywania/OBS"))
        self.overlay_hide.setChecked(s.hide_from_capture)
        self.overlay_hide.setToolTip(
            tr("Nakładka będzie widoczna tylko na monitorze, a nie na zrzutach i w programach do nagrywania.")
        )
        for widget in (self.overlay_x, self.overlay_y, self.overlay_size):
            widget.valueChanged.connect(self._on_overlay_settings)
        self.overlay_hide.toggled.connect(self._on_overlay_settings)
        form.addRow(tr("Tryb:"), self.overlay_mode)
        form.addRow("RTSS:", self.rtss_label)
        self.rtss_autostart = QCheckBox(tr("Uruchamiaj RTSS razem z licznikiem"))
        self.rtss_autostart.setChecked(self.config.rtss.auto_start)
        self.rtss_autostart.toggled.connect(self._on_rtss_autostart)
        self.rtss_install_button = QPushButton(tr("Zainstaluj RTSS…"))
        self.rtss_install_button.clicked.connect(lambda: self._start_rtss_setup(install=True))
        self.rtss_install_button.setVisible(rtss_setup.find_rtss() is None)
        form.addRow(self.rtss_autostart)
        form.addRow(self.rtss_install_button)
        form.addRow(tr("Pozycja X:"), self.overlay_x)
        form.addRow(tr("Pozycja Y:"), self.overlay_y)
        form.addRow(tr("Wielkość tekstu:"), self.overlay_size)
        form.addRow(self.overlay_hide)
        self.discord_check = QCheckBox(tr("Status na Discordzie"))
        self.discord_check.setToolTip(tr("Pokazuje w Twoim statusie na Discordzie grę i liczbę śmierci."))
        self.discord_check.setChecked(self.config.discord.enabled)
        self.discord_check.toggled.connect(self._on_discord_toggled)
        self.discord_label = QLabel()
        self.discord_label.setWordWrap(True)
        self.discord_label.setStyleSheet("color:#9aa0a6;")
        form.addRow(self.discord_check)
        form.addRow(tr("Discord:"), self.discord_label)
        return box

    def _build_detector_box(self) -> QGroupBox:
        box, form = self._collapsible(tr("Wykrywanie"), "detector_collapsed")
        d = self.config.detector
        self.monitor_combo = QComboBox()
        self._fill_monitors()
        self.monitor_combo.currentIndexChanged.connect(self._on_detector_settings)
        self.threshold_spin = _threshold_spin(d.threshold)
        self.threshold_spin.setToolTip(
            tr("Minimalne dopasowanie obrazu do wzorca napisu śmierci, przy którym napis uznajemy za widoczny.\n"
            "Ten sam próg dotyczy komunikatu zwycięstwa – oba to duże napisy na środku ekranu.")
        )
        self.bar_threshold_spin = _threshold_spin(self.config.bosses.bar_threshold)
        self.bar_threshold_spin.setToolTip(
            tr("Minimalne dopasowanie obrazu do wzorca paska zdrowia bossa, przy którym walka się zaczyna.")
        )
        self.name_ratio_spin = _threshold_spin(self.config.bosses.name_match_ratio)
        self.name_ratio_spin.setRange(0.30, 1.00)
        self.name_ratio_spin.setToolTip(
            tr("Minimalne podobieństwo nazwy odczytanej z ekranu do znanej nazwy bossa wybranej gry.\n"
            "Odczyt dostaje najbardziej podobną nazwę z listy, jeśli podobieństwo jest co najmniej takie.\n"
            "Niżej – więcej poprawionych błędów OCR, ale boss spoza listy łatwiej dostanie cudzą nazwę.\n"
            "1,00 – tylko nazwy odczytane bez błędu.")
        )
        self.confirm_spin = _spin(1, 50, d.confirm_samples, tr(" próbek"))
        self.confirm_spin.setToolTip(tr("Tyle kolejnych próbek (co ok. 0,1 s) musi zawierać napis, by zliczyć śmierć."))
        self.rearm_spin = QDoubleSpinBox()
        self.rearm_spin.setRange(0.5, 60.0)
        self.rearm_spin.setSingleStep(0.5)
        self.rearm_spin.setSuffix(" s")
        self.rearm_spin.setValue(d.rearm_seconds)
        self.rearm_spin.setToolTip(tr("Tyle sekund bez napisu, zanim detektor będzie gotowy na kolejną śmierć."))
        for widget in (self.threshold_spin, self.bar_threshold_spin, self.name_ratio_spin, self.confirm_spin,
                       self.rearm_spin):
            widget.valueChanged.connect(self._on_detector_settings)
        self.autostart_check = QCheckBox(tr("Włączaj wykrywanie przy starcie"))
        self.autostart_check.setChecked(self.config.auto_start)
        self.autostart_check.toggled.connect(self._on_autostart)
        form.addRow(tr("Monitor:"), self.monitor_combo)
        form.addRow(tr("Próg śmierci i zwycięstwa:"), self.threshold_spin)
        form.addRow(tr("Próg paska bossa:"), self.bar_threshold_spin)
        form.addRow(tr("Podobieństwo nazwy bossa:"), self.name_ratio_spin)
        form.addRow(tr("Potwierdzenie:"), self.confirm_spin)
        form.addRow(tr("Ponowne uzbrojenie:"), self.rearm_spin)
        form.addRow(self.autostart_check)
        return box

    def _fill_monitors(self) -> None:
        capture = self.config.capture
        self.monitor_combo.addItem(tr("Główny monitor"), None)
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

    def _change_deaths(self, operation, manual: bool, boss_event=None, correction: bool = False) -> None:
        """Zmienia ogólny licznik (deaths.json), a potem – jeśli trzeba – licznik bossa (bosses.json).
        `correction` – ręczna korekta (przycisk, skrót, reset), zapisywana w rejestrze zmian."""
        before = self.store.deaths
        try:
            operation()
        except StorageError as exc:
            self._show_error(tr("Nie zapisano wyniku: {exc} Kolejna zmiana ponowi zapis.", exc=exc))
            if manual:
                QMessageBox.critical(self, tr("Błąd zapisu"), str(exc))
        else:
            self._clear_error()
            self._session_deaths(operation, self.store.deaths - before)
            if self.audit is not None:
                self.audit.deaths_changed(self.store.deaths, manual=correction)
                try:
                    self.audit.save()
                except StorageError as exc:
                    self._show_error(tr("Nie zapisano rejestru zmian: {exc}", exc=exc))
        if boss_event is not None:
            self._boss_event(boss_event)
        self._refresh_count()

    def _manual_plus(self, manual: bool = True) -> None:
        self.diag.write(f"RĘCZNIE +1 (było {self.store.deaths})")
        self._change_deaths(self.store.increment, manual, self.bosses.manual_add, correction=True)

    def _manual_minus(self, manual: bool = True) -> None:
        if self.store.deaths > 0:
            self.diag.write(f"RĘCZNIE −1 (było {self.store.deaths})")
            self._change_deaths(self.store.decrement, manual, self.bosses.manual_undo, correction=True)

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
            self._show_error(tr("Nie zapisano danych bossa: {exc} Kolejna zmiana ponowi zapis.", exc=exc))
        self.boss_panel.refresh()

    def _on_boss_tick(self) -> None:
        ended = None
        try:
            ended = self.bosses.tick()
        except StorageError as exc:
            self._show_error(tr("Nie zapisano danych bossa: {exc} Kolejna zmiana ponowi zapis.", exc=exc))
        self.boss_panel.refresh()
        if ended is not None:
            saved = ended.view
            what = tr("Walka przerwana (opuszczono arenę)") if ended.abandoned else tr("Automatycznie zapisany")
            text = tr("{what}: {name} – śmierci: {deaths}, czas: {seconds}", what=what, name=saved.name, deaths=saved.deaths, seconds=format_duration(saved.seconds))
            self.boss_panel.set_note(text)
            self.notice_label.setText(text)
            self.diag.write(f"BOSS: {text}")
        self._refresh_session()
        self._refresh_session_stats()
        self._refresh_overlay()
        self._refresh_discord_label()
        self._refresh_results()

    def open_results(self) -> None:
        """Okno nie blokuje programu – może zostać otwarte obok w trakcie gry."""
        if self._results is None:
            self._results = ResultsWindow(self)
            self._results.fix_names_requested.connect(self._fix_boss_names)
        self._refresh_results(force=True)
        self._results.show()
        self._results.raise_()
        self._results.activateWindow()

    def _fix_boss_names(self) -> None:
        """Przycisk „Popraw nazwy bossów” w oknie „Wyniki”: pokazuje zmiany i po potwierdzeniu je wykonuje."""
        title = tr("Popraw nazwy bossów")
        fixes = self.bosses.name_fixes()
        if not fixes:
            QMessageBox.information(self._results, title,
                                    tr("Wszystkie nazwy bossów zgadzają się z listą nazw tej gry."))
            return
        lines = "\n".join(f"• {old} → {new}" for old, new in fixes)
        answer = QMessageBox.question(
            self._results, title,
            tr("Te nazwy zostaną zamienione na nazwy z listy gry:\n\n{lines}\n\nLiczba śmierci, czas i historia prób przejdą pod nowe nazwy. Poprawić?", lines=lines))
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._fixed_names, self._fix_error = self.bosses.fix_names(force=True), None
        except StorageError as exc:
            self._fixed_names, self._fix_error = [], str(exc)
        self._report_fixed_names(dialog=False)
        self.boss_panel.refresh()
        self._refresh_overlay()
        self._refresh_results(force=True)

    def _refresh_results(self, force: bool = False) -> None:
        if self._results is not None and (force or self._results.isVisible()):
            self._results.show_results(self.config.game_name(self.paths.game), self.store.deaths, self.bosses)

    def _on_track_bosses(self, checked: bool) -> None:
        self.config.bosses.track = checked
        self._save_timer.start()
        self._refresh_overlay()
        self._refresh_boss_hint()

    def _on_read_names(self, checked: bool) -> None:
        self.config.bosses.read_names = checked
        self._save_timer.start()
        if self.worker is not None:
            self.worker.set_read_names(checked)

    def _on_boss_signal(self, event: str) -> None:
        handlers = {
            BOSS_BAR_VISIBLE: self.bosses.boss_bar_visible,
            BOSS_BAR_LOST: self.bosses.boss_bar_lost,
            BOSS_VICTORY: self.bosses.victory,
            FRAMES_LOST: self.bosses.frames_lost,
        }
        before = self.bosses.state.value
        self._boss_event(handlers[event])
        self.diag.write(f"BOSS: zdarzenie {event}, stan {before} → {self.bosses.state.value}"
                        + (f", niepewne: {self.bosses.uncertain}" if self.bosses.uncertain else ""))
        self._refresh_overlay()

    def _on_boss_name(self, reading: str, confident: bool) -> None:
        if not reading:
            self.diag.write("BOSS: nie odczytano nazwy z ekranu")
            return
        before = self.bosses.current
        try:
            name = self.bosses.boss_identified(reading, confident)
        except StorageError as exc:
            self._show_error(tr("Nie zapisano danych bossa: {exc} Kolejna zmiana ponowi zapis.", exc=exc))
            name = self.bosses.current
        self.diag.write(f"BOSS: odczyt nazwy „{reading}” ({'pewny' if confident else 'niepewny'})"
                        + (f", {before} → {name}" if name else ", bez zmian")
                        + f", nazwa {'pewna' if self.bosses.name_confident else 'do sprawdzenia'}")
        self.boss_panel.refresh()
        self._refresh_overlay()

    # ------------------------------------------------------------------ gra

    def _use_game(self, game: GameData) -> None:
        self.paths = game.paths
        self.store = game.store
        self.calibration = game.calibration
        self.templates = dict(game.templates)
        self.audit = game.audit
        self.session = game.session
        if game.boss_names is not None:
            game.boss_names.min_ratio = self.config.bosses.name_match_ratio
        self.bosses = BossTracker(game.boss_store, audit=game.audit, names=game.boss_names, recent=game.recent,
                                  attempts=game.attempts)
        self.bosses.enabled = self.config.bosses.track
        try:
            self._fixed_names = self.bosses.fix_names()
            self._fix_error = None
        except StorageError as exc:
            self._fixed_names, self._fix_error = [], str(exc)

    def _report_fixed_names(self, dialog: bool = True) -> None:
        """Pokazuje, którzy zapisani bossowie dostali nazwy z listy wbudowanej (przy wczytaniu gry
        albo po przycisku w oknie „Wyniki” – wtedy bez okna, bo zmiany były już pokazane)."""
        if self._fix_error:
            self._show_error(tr("Nie zapisano poprawionych nazw bossów: {fix_error}", fix_error=self._fix_error))
        if not self._fixed_names:
            return
        for old, new in self._fixed_names:
            self.diag.write(f"BOSS: nazwa „{old}” poprawiona na „{new}” (lista nazw gry)")
        lines = "\n".join(f"• {old} → {new}" for old, new in self._fixed_names)
        self.notice_label.setText(tr("Poprawiono nazwy bossów: {count__fixed_names}.", count__fixed_names=len(self._fixed_names)))
        if not dialog:
            return
        QMessageBox.information(
            self, tr("Poprawione nazwy bossów"),
            tr("Zapisane nazwy bossów porównano z listą nazw tej gry i poprawiono:\n\n{lines}\n\nLiczba śmierci, czas i historia prób przeszły pod nowe nazwy. Jeśli któraś zmiana jest zła, popraw tę nazwę ręcznie.", lines=lines))

    def _fill_games(self) -> None:
        """Gry wbudowane i dodane przez użytkownika, a na końcu pozycja „+ Dodaj grę…”."""
        combo = self.game_combo
        combo.blockSignals(True)
        combo.clear()
        for game_id, name in self.config.all_games().items():
            combo.addItem(name, game_id)
        combo.insertSeparator(combo.count())
        combo.addItem(tr("+ Dodaj grę…"), ADD_GAME)
        combo.addItem(tr("Znajdź zainstalowane gry ze Steam…"), STEAM_SCAN)
        combo.setCurrentIndex(max(0, combo.findData(self._pending_game or self.paths.game)))
        combo.blockSignals(False)

    def _add_game(self) -> None:
        # Lista wraca do bieżącej gry; nowa gra zostanie wybrana dopiero po podaniu nazwy.
        self._fill_games()
        name, ok = QInputDialog.getText(
            self, tr("Dodaj grę"), tr("Nazwa gry (np. Lies of P):\nGra dostanie własny licznik śmierci, bossów i kalibrację.")
        )
        if not ok:
            return
        try:
            game_id = self.config.add_game(name)
        except ValueError as exc:
            QMessageBox.warning(self, tr("Dodaj grę"), str(exc))
            return
        self._save_config()
        self._refresh_matchers()
        self._fill_games()
        self.game_combo.setCurrentIndex(self.game_combo.findData(game_id))  # przełącza na nową grę

    def _offer_steam_scan(self) -> None:
        """Raz, gdy na komputerze jest Steam: propozycja dodania liczników dla zainstalowanych gier souls-like."""
        if self.config.steam_offered or find_steam() is None:
            return
        self.config.steam_offered = True
        self._save_config()
        answer = QMessageBox.question(
            self, tr("Gry ze Steama"),
            tr("Na tym komputerze jest Steam. Sprawdzić zainstalowane gry i dodać liczniki dla gier souls-like?\n\n"
               "Później zrobisz to pozycją „Znajdź zainstalowane gry ze Steam…” na liście gier."),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._scan_steam()

    def _scan_steam(self) -> None:
        self._fill_games()  # lista wraca do bieżącej gry
        dialog = SteamScanDialog(self, self.config)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        games = dialog.selected() if accepted else []
        dialog.deleteLater()
        added = []
        for game in games:
            try:
                self.config.add_game(game.name, game.appid)
            except ValueError as exc:
                self.diag.write(f"STEAM: pominięto {game.name} ({game.appid}): {exc}")
                continue
            added.append(game.name)
        if not added:
            return
        self._save_config()
        self._refresh_matchers()
        self._fill_games()
        self.diag.write(f"STEAM: dodano gry: {', '.join(added)}")
        self.notice_label.setText(tr("Dodano gry ze Steama: {names}. Wybierz grę z listy i wykonaj kalibrację.",
                                     names=", ".join(added)))

    def _on_game_selected(self) -> None:
        game_id = self.game_combo.currentData()
        if game_id == ADD_GAME:
            self._add_game()
            return
        if game_id == STEAM_SCAN:
            self._scan_steam()
            return
        if game_id == self.paths.game and self._pending_game is None:
            return
        if self.worker is not None:
            # Wątek wykrywania używa wzorców bieżącej gry – zmiana nastąpi, gdy się zatrzyma.
            self._pending_game = game_id
            self.stop_detection()
            return
        self._switch_game(game_id, restart=False)

    def _switch_game(self, game_id: str, restart: bool, reload: bool = False) -> None:
        """Wczytuje dane gry; `reload` – ponownie tej samej (po usunięciu jej licznika, bez zapisu starych danych)."""
        auto, self._auto_switched = self._auto_switched == game_id, None
        if game_id != self.paths.game or reload:
            if not reload:
                self._boss_event(self.bosses.pause)  # czas trwającej walki zostaje zapisany
            try:
                game = open_game(self.paths.base, game_id)
            except StorageError as exc:
                QMessageBox.critical(self, tr("Zmiana gry"), tr("Nie można wczytać danych gry.\n\n{exc}", exc=exc))
                self.game_combo.blockSignals(True)
                self.game_combo.setCurrentIndex(max(0, self.game_combo.findData(self.paths.game)))
                self.game_combo.blockSignals(False)
                game = None
            if game is not None:
                if not reload:
                    self._stop_session()  # czas sesji poprzedniej gry zostaje zapisany
                self._use_game(game)
                self._session_started = int(time.time())
                self.config.game = game_id
                self._save_timer.start()
                self.boss_panel.set_tracker(self.bosses)
                self._refresh_count()
                self._refresh_template_label()
                self._refresh_footer()
                self._refresh_delete_button()
                self._set_status(self._idle_status(), self._idle_message())
                self.notice_label.setText(tr("Wybrano grę: {game_name}.", game_name=self.config.game_name(game_id)))
                self.diag.write(f"ZMIANA GRY: {self.config.game_name(game_id)}, śmierci: {self.store.deaths}")
                if auto:
                    self._report_auto_switch(game_id)
                self._refresh_session()
                for warning in game.warnings:
                    QMessageBox.warning(self, "Death Counter by MK", warning)
                self._report_fixed_names()
        self._refresh_boss_hint()
        # Wykrywanie wraca, jeśli działało przed zmianą gry albo ma się włączać samo (np. po grze bez wzorców).
        if (restart or self.config.auto_start) and self.templates["death"] is not None:
            self.start_detection()

    def _refresh_delete_button(self) -> None:
        """Grę dodaną przez użytkownika można usunąć, a grę wbudowaną (FromSoftware) tylko zresetować."""
        if self.paths.game in self.config.custom_games:
            self.delete_counter_button.setText(tr("Usuń licznik"))
            self.delete_counter_button.setToolTip(
                tr("Gra znika z listy razem z licznikiem, bossami i kalibracją. Pliki trafiają do Kosza."))
        else:
            self.delete_counter_button.setText(tr("Resetuj licznik"))
            self.delete_counter_button.setToolTip(
                tr("Gier FromSoftware nie można usunąć z listy. Reset zeruje licznik śmierci i bossów,\n"
                   "a kalibracja zostaje. Pliki trafiają do Kosza."))

    def confirm_delete_counter(self) -> None:
        game_id = self.paths.game
        name = self.config.game_name(game_id)
        custom = game_id in self.config.custom_games
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        if custom:
            box.setWindowTitle(tr("Usuń licznik"))
            box.setText(tr("Czy na pewno chcesz usunąć licznik {name}?", name=name))
            box.setInformativeText(tr("Gra zniknie z listy, a jej licznik śmierci, bossowie i kalibracja trafią do Kosza."))
        else:
            box.setWindowTitle(tr("Resetuj licznik"))
            box.setText(tr("Czy na pewno chcesz zresetować licznik {name}?", name=name))
            box.setInformativeText(tr("Licznik śmierci ({deaths}) i lista bossów trafią do Kosza. Gra zostaje na liście, a jej kalibracja się nie zmienia.", deaths=self.store.deaths))
        yes = box.addButton(tr("Tak"), QMessageBox.ButtonRole.YesRole)
        no = box.addButton(tr("Nie"), QMessageBox.ButtonRole.NoRole)
        box.setDefaultButton(no)
        box.exec()
        if box.clickedButton() is not yes:
            return
        if self.worker is not None:
            # Wątek wykrywania korzysta z danych gry – usuwamy je dopiero po jego zatrzymaniu.
            self._pending_delete = game_id
            self.stop_detection()
            return
        self._delete_counter(game_id, restart=False)

    def _delete_counter(self, game_id: str, restart: bool) -> None:
        name = self.config.game_name(game_id)
        custom = game_id in self.config.custom_games
        title = tr("Usuń licznik") if custom else tr("Resetuj licznik")
        old_paths = self.paths
        try:
            if custom:
                # Najpierw przełączenie na inną grę (zapisuje i zwalnia dane), potem usunięcie folderu.
                self._switch_game(DEFAULT_GAME, restart=False)
                winapi.send_to_recycle_bin([old_paths.game_dir])
                self.config.remove_game(game_id)
                self._save_config()
                self._fill_games()
            else:
                winapi.send_to_recycle_bin(counter_files(old_paths))
                self._switch_game(game_id, restart=False, reload=True)
        except OSError as exc:
            QMessageBox.critical(self, title, tr("Nie udało się usunąć licznika {name}.\n\n{exc}", name=name, exc=exc))
            return
        finally:
            if restart and self.worker is None and self.templates["death"] is not None:
                self.start_detection()
        self.notice_label.setText(tr("Usunięto licznik {name} (pliki są w Koszu).", name=name) if custom
                                  else tr("Zresetowano licznik {name} (pliki są w Koszu).", name=name))

    def _refresh_footer(self) -> None:
        self.footer_label.setText(tr("Dane gry: {game_dir}", game_dir=self.paths.game_dir))

    def generate_report(self) -> None:
        player, ok = QInputDialog.getText(
            self, tr("Certyfikat PDF"), tr("Nick gracza na certyfikacie (możesz zostawić puste):"), text=self.config.player_name
        )
        if not ok:
            return
        self.config.player_name = " ".join(player.split())[:60]
        self._save_timer.start()
        now = datetime.now()
        default = self.paths.base / tr("DeathCounter_certyfikat_{game}_{now:%Y-%m-%d}.pdf", game=self.paths.game, now=now)
        path, _ = QFileDialog.getSaveFileName(self, tr("Zapisz certyfikat PDF"), str(default), tr("Dokument PDF (*.pdf)"))
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        rows = rows_from_records(self.bosses.store.records, self.bosses.current, self.bosses.elapsed())
        adjustments = Adjustments.from_audit(self.audit) if self.audit is not None else None
        data = CertificateData(self.config.game_name(self.paths.game), self.config.player_name,
                               self.store.deaths, rows, now.replace(second=0, microsecond=0), adjustments)
        try:
            code = write_certificate(path, data, load_key())
        except (StorageError, OSError) as exc:
            QMessageBox.critical(self, tr("Certyfikat PDF"), tr("Nie udało się zapisać certyfikatu.\n\n{exc}", exc=exc))
            return
        signed = f" (kod {code})" if code else tr(" – bez podpisu: ta wersja programu nie ma klucza")
        self.notice_label.setText(tr("Zapisano certyfikat{signed}: {path}", signed=signed, path=path))
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def verify_certificate(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, tr("Sprawdź certyfikat"), str(self.paths.base), tr("Dokument PDF (*.pdf)"))
        if not path:
            return
        try:
            result = verify_pdf(path, load_key())
        except StorageError as exc:
            QMessageBox.critical(self, tr("Sprawdź certyfikat"), str(exc))
            return
        title, icon = {
            Verdict.VALID: (tr("Certyfikat jest prawdziwy"), QMessageBox.Icon.Information),
            Verdict.INVALID: (tr("Certyfikat został zmieniony albo podrobiony"), QMessageBox.Icon.Critical),
            Verdict.UNSIGNED: (tr("Certyfikat bez podpisu"), QMessageBox.Icon.Warning),
            Verdict.NO_KEY: (tr("Nie można sprawdzić podpisu"), QMessageBox.Icon.Warning),
            Verdict.NOT_CERTIFICATE: (tr("To nie jest certyfikat Death Counter by MK"), QMessageBox.Icon.Warning),
        }[result.verdict]
        details = {
            Verdict.VALID: tr("Dane i kod weryfikacyjny zgadzają się z podpisem. Sprawdź, czy poniższe dane są takie "
                           "same jak na certyfikacie – tylko te zostały podpisane."),
            Verdict.INVALID: tr("Dane zapisane w pliku nie pasują do kodu weryfikacyjnego."),
            Verdict.UNSIGNED: tr("Certyfikat wystawiła wersja programu bez klucza podpisu (uruchomiona ze źródeł)."),
            Verdict.NO_KEY: tr("Ta wersja programu nie ma klucza podpisu. Użyj oficjalnego DeathCounter.exe."),
            Verdict.NOT_CERTIFICATE: tr("Plik nie zawiera danych certyfikatu (to inny PDF albo zapisany ponownie "
                                     "w innym programie)."),
        }[result.verdict]
        box = QMessageBox(icon, tr("Sprawdź certyfikat"), title, parent=self)
        text = details
        if result.data is not None and result.verdict is not Verdict.INVALID:
            d = result.data
            bosses = "\n".join(tr("   • {name}: {deaths} śmierci, {seconds}", name=b.name, deaths=b.deaths, seconds=format_duration(b.seconds))
                               + ("" if b.defeated else tr(" (w trakcie)")) for b in d.bosses) or tr("   brak")
            if d.adjustments is None:
                changes = tr("brak danych (certyfikat sprzed rejestru zmian)")
            else:
                changes = "; ".join(d.adjustments.summary()) or tr("bez ręcznych zmian")
            text += (tr("\n\nGra: {game}\nGracz: {value}\nŚmierci: {deaths}\nWystawiono: {issued:%d.%m.%Y, %H:%M}\nKod: {value2}\nKorekty: {changes}\nBossowie:\n{bosses}", game=d.game, value=d.player or '–', deaths=d.deaths, issued=d.issued, value2=result.code or '–', changes=changes, bosses=bosses))
        box.setInformativeText(text)
        box.exec()

    def _refresh_boss_hint(self) -> None:
        # Bez wzorca zwycięstwa nie da się odróżnić wygranej od opuszczenia areny.
        self.bosses.abandon_enabled = self.templates["victory"] is not None
        missing = [label for kind, label in (("boss_bar", tr("pasek bossa")), ("victory", tr("komunikat zwycięstwa")))
                   if self.templates[kind] is None]
        if missing:
            hint = tr("Brak wzorca: {join}. Kliknij „Kalibracja walki…”, aby walka startowała sama.", join=', '.join(missing))
        elif self.worker is None:
            hint = tr("Wykrywanie jest wyłączone – kliknij Start, aby walka była rozpoznawana.")
        else:
            hint = tr("Walka zacznie się sama, gdy na ekranie pojawi się pasek zdrowia bossa.")
        self.boss_panel.set_hint(hint)

    def _refresh_overlay(self) -> None:
        """Ten sam tekst trafia do nakładki-okna i do RTSS, więc obie pokazują to samo."""
        boss = self.bosses.view() if self.bosses.enabled else None
        session = None
        if self.config.session.track and self.config.session.show_on_overlay:
            view = self.session.view(time.time())
            session = view if view.running else None
        self.overlay.set_text(overlay_text(self.store.deaths, boss, session))
        self._update_rtss()
        self._update_discord()

    # ------------------------------------------------------------- sesja

    def _refresh_matchers(self) -> None:
        """Jak rozpoznać proces każdej gry: exe gier wbudowanych, foldery gier ze Steama, exe wskazane ręcznie."""
        steam = find_steam()
        self._steam_games = installed_games(steam) if steam is not None else []
        self._matchers = game_process.build_matchers(self.config, self._steam_games)
        self._steam_folders = {game_id for game_id, matcher in self._matchers.items() if matcher.folders}

    def _on_process_tick(self) -> None:
        s = self.config.session
        if not (s.track or s.auto_switch):
            self._running_games = set()
            return
        processes = winapi.process_paths()
        paths = list(processes.values())
        running = game_process.running_games(paths, self._matchers)
        started, self._running_games = running - self._running_games, running
        current = self.paths.game
        for game_id in started:
            self.diag.write(f"GRA URUCHOMIONA: {self.config.game_name(game_id)}")
        if s.auto_switch and current not in running and self._pending_game is None:
            # Tylko w chwili uruchomienia gry – ręczny wybór innej gry w trakcie grania zostaje.
            target = next((game_id for game_id in self.config.all_games() if game_id in started), None)
            if target is not None:
                self._auto_switched = target
                self.diag.write(f"AUTO: przełączenie licznika na {self.config.game_name(target)}")
                self.game_combo.setCurrentIndex(self.game_combo.findData(target))
        matcher = self._matchers.get(current)
        running_exe = game_process.matching_exe(paths, matcher) if current in running else None
        if running_exe != self._running_exe:
            self._running_exe = running_exe
            self._refresh_overlay_status()  # podpowiedź o pełnym ekranie zależy od tego, czy gra działa
        # Czas sesji biegnie tylko wtedy, gdy gra jest aktywnym oknem (nie zminimalizowana ani w tle po Alt+Tab).
        background = current in running and not matcher.matches(processes.get(winapi.foreground_pid(), ""))
        if s.track:
            if background != self.session.background and current in running:
                self.diag.write("SESJA: gra w tle – czas stoi" if background
                                else "SESJA: powrót do gry – czas rusza po potwierdzeniu")
            try:
                if self.session.tick(current in running, time.time(), background):
                    self.diag.write(f"SESJA: nowa sesja {self.config.game_name(current)}")
            except StorageError as exc:
                self._show_error(tr("Nie zapisano sesji: {exc}", exc=exc))
        self._refresh_session()

    def open_session_stats(self) -> None:
        """Okno nie blokuje programu – może zostać otwarte obok w trakcie gry."""
        if self._session_stats is None:
            self._session_stats = SessionStatsWindow(self)
        self._session_stats.show()
        self._refresh_session_stats()
        self._session_stats.raise_()
        self._session_stats.activateWindow()

    def _refresh_session_stats(self) -> None:
        if self._session_stats is not None and self._session_stats.isVisible():
            self._session_stats.update_data(self.session, self.config.game_name(self.paths.game), time.time())

    def _report_auto_switch(self, game_id: str) -> None:
        text = tr("Uruchomiono grę {name} – licznik przełączył się na nią.", name=self.config.game_name(game_id))
        if self.templates["death"] is None:
            text += " " + tr("Ta gra nie ma jeszcze kalibracji – kliknij „Kalibracja…”, żeby liczyć śmierci.")
            QApplication.alert(self)  # miganie na pasku zadań: trzeba zajrzeć do programu
        self.notice_label.setText(text)
        self.diag.write(f"AUTO: {text}")

    def _session_deaths(self, operation, delta: int) -> None:
        if not self.config.session.track:
            return
        try:
            if operation == self.store.reset:
                self.session.reset_deaths()
            else:
                self.session.add_deaths(delta, time.time())
        except StorageError as exc:
            self._show_error(tr("Nie zapisano sesji: {exc}", exc=exc))

    def _stop_session(self) -> None:
        try:
            self.session.stop(time.time())
        except StorageError as exc:
            self._show_error(tr("Nie zapisano sesji: {exc}", exc=exc))

    def _on_session_settings(self) -> None:
        s = self.config.session
        if s.track and not self.session_track.isChecked():
            self._stop_session()
        s.track = self.session_track.isChecked()
        s.auto_switch = self.session_switch.isChecked()
        s.show_on_overlay = self.session_overlay.isChecked()
        self._save_timer.start()
        self._on_process_tick()
        self._refresh_overlay()

    def _pick_game_exe(self) -> None:
        game_id = self.paths.game
        path, _ = QFileDialog.getOpenFileName(
            self, tr("Wskaż exe gry"), self.config.game_exes.get(game_id, ""), tr("Programy (*.exe)"))
        if not path:
            return
        self.config.game_exes[game_id] = str(Path(path))
        self._save_config()
        self._refresh_matchers()
        self._on_process_tick()

    def _refresh_session(self) -> None:
        s = self.config.session
        game_id = self.paths.game
        known = game_id in self._matchers
        # Exe wskazuje się tylko dla gier spoza Steama – wbudowane i ze Steama program rozpoznaje sam.
        exe = self.config.game_exes.get(game_id)
        self.session_exe_button.setVisible(game_id in self.config.custom_games and game_id not in self._steam_folders)
        self.session_exe_button.setText(tr("Zmień exe gry…") if exe else tr("Wskaż exe gry…"))
        self.session_exe_button.setToolTip(exe or tr("Program nie zna exe tej gry – wskaż go, żeby śledzić sesję."))
        self.session_overlay.setEnabled(s.track)
        view = self.session.view(time.time())
        exe = self._running_exe or "?"
        if not s.track:
            badge, state = "off", tr("Śledzenie sesji jest wyłączone.")
        elif not known:
            badge, state = "unknown", tr("Program nie wie, jak rozpoznać tę grę – wskaż jej exe.")
        elif view.background:
            badge, state = "background", tr("Gra w tle ({exe}) – czas sesji stoi.", exe=exe)
        elif view.running:
            badge, state = "running", tr("{exe} – czas sesji biegnie.", exe=exe)
        elif view.continues:
            badge, state = "break", tr("Gra zamknięta – powrót w ciągu {minutes} min kontynuuje sesję.",
                                       minutes=GAP_SECONDS // 60)
        else:
            badge, state = "waiting", tr("Czekam na uruchomienie gry.")
        text, color = SESSION_BADGES[badge]
        self.session_badge.setText(tr(text).upper())
        self.session_badge.setStyleSheet(
            f"padding:2px 8px; border-radius:4px; color:white; font-weight:bold; background:{color};")
        self.session_state.setText(state)
        if not s.track or view.started is None:
            self.session_deaths.setText("–")
            self.session_time.setText("–")
            return
        ended = not (view.running or view.continues)
        suffix = f"  ({tr('ostatnia sesja')})" if ended else ""
        self.session_deaths.setText(f"{view.deaths}{suffix}")
        self.session_time.setText(f"{format_duration(view.seconds)}{suffix}")

    # ------------------------------------------------------------- Discord

    def _on_discord_toggled(self, checked: bool) -> None:
        self.config.discord.enabled = checked
        self._save_timer.start()
        self._apply_discord()

    def _apply_discord(self) -> None:
        d = self.config.discord
        if d.enabled and d.effective_client_id:
            if self.discord is None:
                self._discord_state = tr("łączenie z Discordem…")
                self.discord = DiscordPresence(d.effective_client_id, self._set_discord_state)
            self._update_discord()
        elif self.discord is not None:
            self.discord.close()  # czyści status na Discordzie
            self.discord = None
        self._refresh_discord_label()

    def _set_discord_state(self, text: str) -> None:
        self._discord_state = text  # wywoływane z wątku Discorda; etykieta odświeża się co sekundę

    def _update_discord(self) -> None:
        if self.discord is not None:
            game = self.config.game_name(self.paths.game)
            started = self._session_started
            if self.config.session.track and self.session.running and self.session.started is not None:
                started = int(self.session.started)  # „gra od…” = początek sesji
            self.discord.update(build_activity(game, self.store.deaths, started))

    def _refresh_discord_label(self) -> None:
        d = self.config.discord
        if not d.enabled:
            text = tr("wyłączony")
        elif not d.effective_client_id:
            text = tr("brak ID aplikacji Discord (patrz README)")
        else:
            text = self._discord_state
        if self.discord_label.text() != text:
            self.discord_label.setText(text)

    def confirm_reset(self) -> None:
        answer = QMessageBox.question(
            self,
            tr("Reset licznika"),
            tr("Czy na pewno wyzerować licznik? Obecna wartość ({deaths}) zostanie utracona.", deaths=self.store.deaths),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._change_deaths(self.store.reset, manual=True, correction=True)

    def _on_death_detected(self) -> None:
        before, state = self.store.deaths, self.bosses.state.value
        boss_deaths = self.bosses.record.deaths if self.bosses.record else None
        self._change_deaths(self.store.increment, manual=False, boss_event=self.bosses.death)
        after_boss = self.bosses.record.deaths if self.bosses.record else None
        self.diag.write(f"ŚMIERĆ WYKRYTA: licznik {before} → {self.store.deaths}, stan bossa {state} → "
                        f"{self.bosses.state.value}, śmierci bossa {boss_deaths} → {after_boss}")

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
            self._set_status(DetectorStatus.NO_TEMPLATE, tr("Najpierw wykonaj kalibrację (przycisk „Kalibracja…”)."))
            return
        worker = DetectionWorker(self.templates, self.config.detector, self.config.capture, self.config.bosses)
        worker.death_detected.connect(self._on_death_detected)
        worker.boss_event.connect(self._on_boss_signal)
        worker.status_changed.connect(self._set_status)
        worker.sample.connect(self._on_sample)
        worker.snapshot_ready.connect(self._on_snapshot)
        worker.notice.connect(self.notice_label.setText)
        worker.boss_name.connect(self._on_boss_name)
        worker.finished.connect(self._on_worker_finished)
        self.worker = worker
        self.diag.reset_detector_state()
        self.diag.write(f"START wykrywania (próg śmierci {self.config.detector.threshold:.2f}, "
                        f"paska {self.config.bosses.bar_threshold:.2f}, wzorce: "
                        + ", ".join(k for k, v in self.templates.items() if v is not None) + ")")
        self._stop_requested = False
        self.start_button.setText(tr("Stop"))
        self._set_status(DetectorStatus.ACTIVE, tr("Uruchamianie przechwytywania…"))
        worker.start()
        self._refresh_boss_hint()

    def stop_detection(self) -> None:
        if self.worker is not None:
            self.start_button.setEnabled(False)
            self.start_button.setText(tr("Zatrzymywanie…"))
            self._stop_requested = True
            self.worker.request_stop()

    def _on_worker_finished(self) -> None:
        worker, self.worker = self.worker, None
        if worker is not None:
            worker.deleteLater()
        self.diag.write("STOP wykrywania")
        self._flush_frame_callbacks(None, tr("Wykrywanie zostało zatrzymane przed pobraniem obrazu."))
        self.start_button.setEnabled(True)
        self.start_button.setText(tr("Start"))
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
        if self._pending_delete is not None:
            game_id, self._pending_delete = self._pending_delete, None
            self._delete_counter(game_id, restart=True)

    def _on_sample(self, result: SampleResult) -> None:
        check = result.check
        if check.resolution:
            w, h = check.resolution
            state = {
                CaptureHealth.OK: "OK",
                CaptureHealth.NO_FRAMES: tr("brak nowych klatek"),
                CaptureHealth.FROZEN: tr("zamrożony"),
            }[check.health]
            self.image_label.setText(f"{w}×{h}, {state}")
        else:
            self.image_label.setText(tr("brak klatek"))
        if result.score is None:
            self.score_label.setText("–")
        else:
            armed = "gotowy" if result.armed else tr("czeka na zniknięcie napisu")
            self.score_label.setText(
                tr("{score:.2f} (próg {threshold:.2f}) – detektor {armed}", score=result.score, threshold=self.config.detector.threshold, armed=armed)
            )
        parts = []
        if result.bar_score is not None:
            bar = "widoczny" if result.bar_visible else "niewidoczny"
            parts.append(f"pasek {result.bar_score:.2f}/{self.config.bosses.bar_threshold:.2f} ({bar})")
        if result.victory_score is not None:
            parts.append(tr("zwycięstwo {victory_score:.2f}/{threshold:.2f}", victory_score=result.victory_score, threshold=self.config.detector.threshold))
        self.boss_score_label.setText(", ".join(parts) or "–")
        self.diag.sample(result, self.config.detector.threshold, self.config.bosses.bar_threshold,
                         self.bosses.state.value)

    def _set_status(self, status: DetectorStatus, message: str) -> None:
        self._status = status
        if hasattr(self, "diag"):
            self.diag.status(f"{status.value} – {message}")
        self.status_label.setText(tr(status.value).upper())
        self.status_label.setStyleSheet(
            f"padding:2px 8px; border-radius:4px; color:white; font-weight:bold; background:{STATUS_COLORS[status]};"
        )
        self.status_message.setText(message)

    def _idle_status(self) -> DetectorStatus:
        return DetectorStatus.STOPPED if self.templates["death"] is not None else DetectorStatus.NO_TEMPLATE

    def _idle_message(self) -> str:
        if self.templates["death"] is None:
            return tr("Brak wzorca – wykonaj kalibrację, aby włączyć wykrywanie.")
        return tr("Wykrywanie wyłączone. Kliknij Start.")

    def _on_detector_settings(self) -> None:
        d = self.config.detector
        d.threshold = round(self.threshold_spin.value(), 2)
        self.config.bosses.bar_threshold = round(self.bar_threshold_spin.value(), 2)
        self.config.bosses.name_match_ratio = round(self.name_ratio_spin.value(), 2)
        if self.bosses.names is not None:
            self.bosses.names.min_ratio = self.config.bosses.name_match_ratio
        d.confirm_samples = self.confirm_spin.value()
        d.rearm_seconds = self.rearm_spin.value()
        self.config.capture.output_index = self.monitor_combo.currentData()
        if self.worker is not None:
            self.worker.update_settings(self.config.detector, self.config.capture, self.config.bosses)
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
            self._rtss_state = None
            self.rtss_label.setText(tr("nieużywany") if s.mode == "window" else tr("nakładka wyłączona"))
        # Przycisk mówi, co zrobi kliknięcie, a wciśnięty pokazuje, że nakładka jest włączona.
        self.overlay_button.setText(tr("Ukryj nakładkę") if s.enabled else tr("Pokaż nakładkę"))
        self.overlay_button.setChecked(s.enabled)
        self._refresh_overlay_status()

    def _update_rtss(self) -> None:
        if not self._rtss_timer.isActive():
            return
        state = self.rtss.show(self.overlay.text)
        if state is not self._rtss_state:
            self._rtss_state = state
            self._refresh_overlay_status()
        if state is RtssState.SHOWN:
            self.rtss_label.setText(tr("licznik przekazany do RTSS"))
        elif state is RtssState.NOT_RUNNING:
            self.rtss_label.setText(tr("RTSS nie jest uruchomiony – licznik pojawi się, gdy go włączysz"))
        else:
            self.rtss_label.setText(tr(state.value))

    def _refresh_overlay_status(self) -> None:
        """Wiersz „Nakładka” w sekcji „Stan”: czy licznik widać w grze, a jeśli nie – dlaczego."""
        s = self.config.overlay
        window, rtss = s.mode in ("window", "both"), s.mode in ("rtss", "both")
        rtss_ok = self._rtss_state is RtssState.SHOWN
        rtss_problem = tr(self._rtss_state.value) if self._rtss_state is not None else tr("RTSS nie jest uruchomiony")
        if not s.enabled:
            badge, text = "hidden", tr("Kliknij „Pokaż nakładkę”, żeby widzieć licznik w grze.")
        elif rtss and not window:
            badge, text = (("visible", tr("RTSS – licznik widać także w pełnym ekranie.")) if rtss_ok else
                           ("invisible", tr("{problem} – uruchom RTSS albo zmień tryb nakładki.",
                                            problem=_capitalized(rtss_problem))))
        elif rtss and not rtss_ok:
            badge, text = "partial", tr("Okno widoczne, ale {problem} – w pełnym ekranie licznika może nie być widać.",
                                        problem=rtss_problem)
        elif rtss:
            badge, text = "visible", tr("Okno na wierzchu i RTSS.")
        else:
            badge, text = "visible", tr("Okno na wierzchu.")
            if self._running_exe:
                # Gra działa: okno nakładki nie przebija się przez ekskluzywny pełny ekran.
                text += " " + tr("Jeśli w grze go nie widać (pełny ekran), wybierz tryb z RTSS.")
        label, color = OVERLAY_BADGES[badge]
        self.overlay_badge.setText(tr(label).upper())
        self.overlay_badge.setStyleSheet(
            f"padding:2px 8px; border-radius:4px; color:white; font-weight:bold; background:{color};")
        self.overlay_status.setText(text)

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
        self._flush_frame_callbacks(frame, None if frame is not None else tr("Brak obrazu z wybranego monitora."))

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
            thresholds={"death": self.config.detector.threshold, "victory": self.config.detector.threshold,
                        "boss_bar": self.config.bosses.bar_threshold},
            margin=self.config.detector.search_margin,
            hotkey_text=self._hotkey_text("snapshot"),
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
            self.notice_label.setText(tr("Wzorzec zapisany, ale bez zrzutu do podglądu: {exc}", exc=exc))
        self.templates[kind] = template
        self._refresh_template_label()
        self._refresh_boss_hint()
        if self.worker is not None:
            self.worker.update_template(kind, template)
        elif self._status in (DetectorStatus.NO_TEMPLATE, DetectorStatus.STOPPED):
            self._set_status(self._idle_status(), self._idle_message())
        return None

    def _refresh_template_label(self) -> None:
        names = (("death", tr("śmierć")), ("boss_bar", tr("pasek bossa")), ("victory", tr("zwycięstwo")))
        parts = [tr("{label}: {value}", label=label, value='✓' if self.templates[kind] is not None else tr('brak')) for kind, label in names]
        self.template_label.setText(", ".join(parts))

    def _on_hotkey(self, action: str) -> None:
        if action == "snapshot":
            self.request_frame(self._on_hotkey_frame)
            return
        # Akcje z gry: bez okienek, które zabrałyby fokus grze – tylko sygnał dźwiękowy.
        if action == "plus":
            self._manual_plus(manual=False)
        elif action == "minus":
            self._manual_minus(manual=False)
        else:
            self.toggle_overlay()
        off = action == "minus" or (action == "overlay" and not self.config.overlay.enabled)
        winsound.MessageBeep(winsound.MB_ICONASTERISK if off else winsound.MB_OK)

    def _on_hotkey_frame(self, frame, error) -> None:
        text = self._hotkey_text("snapshot") or tr("skrótu")
        if frame is None:
            winsound.MessageBeep(winsound.MB_ICONHAND)
            self.notice_label.setText(tr("Zrzut ze skrótu {text} nieudany: {error}", text=text, error=error))
            return
        winsound.MessageBeep(winsound.MB_OK)
        self._hotkey_frame = frame
        if self._calibration is not None:
            self._calibration.set_frame(frame)
        else:
            self.notice_label.setText(
                tr("Zapamiętano zrzut ekranu ({text}). Otwórz „Kalibracja…”, aby zaznaczyć napis.", text=text)
            )

    # --------------------------------------------------------------- skróty

    def _hotkey_text(self, action: str) -> str | None:
        """Skrót akcji do pokazania w interfejsie albo None, gdy jest wyłączony lub niezarejestrowany."""
        registered = {HOTKEY_IDS[i] for i in self._hotkeys}
        return hotkeys.display(getattr(self.config.hotkeys, action)) if action in registered else None

    def _register_hotkeys(self) -> None:
        self._unregister_hotkeys()
        failed = []
        for hotkey_id, action in HOTKEY_IDS.items():
            text = getattr(self.config.hotkeys, action)
            if not text:
                continue
            hotkey = hotkeys.parse(text)
            if winapi.register_hotkey(int(self.winId()), hotkey_id, hotkey.modifiers, hotkey.vk):
                self._hotkeys.add(hotkey_id)
            else:
                failed.append(hotkeys.display(text))
        if failed:
            self.notice_label.setText(tr("Skróty zajęte przez inny program albo system: {join}.", join=', '.join(failed)))
        self._refresh_hotkey_tooltips()

    def _unregister_hotkeys(self) -> None:
        for hotkey_id in self._hotkeys:
            winapi.unregister_hotkey(int(self.winId()), hotkey_id)
        self._hotkeys.clear()

    def _refresh_hotkey_tooltips(self) -> None:
        for button, action in ((self.plus_button, "plus"), (self.minus_button, "minus"),
                               (self.overlay_button, "overlay")):
            text = self._hotkey_text(action)
            button.setToolTip(tr("Skrót w grze: {text}", text=text) if text else "")

    def open_hotkeys(self) -> None:
        # Na czas zmiany skróty są wyrejestrowane – inaczej naciśnięcie obecnego skrótu nie dotarłoby do pola.
        self._unregister_hotkeys()
        dialog = HotkeyDialog(self, self.config.hotkeys)
        try:
            if dialog.exec() and dialog.result_settings is not None:
                self.config.hotkeys = dialog.result_settings
                self._save_timer.start()
                self.notice_label.setText(tr("Zapisano skróty klawiszowe."))
        finally:
            self._register_hotkeys()

    # ---------------------------------------------------------- okno/system

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._fitted:
            self._fitted = True
            QTimer.singleShot(0, self._fit_to_screen)  # gdy Windows poda już rozmiar ramki okna
            # Przeciągnięcie okna na monitor o innej wysokości (np. z 2K na Full HD) – nowa wysokość okna.
            self.windowHandle().screenChanged.connect(lambda _: QTimer.singleShot(0, lambda: self._fit_to_screen(move=False)))
        self._set_taskbar_icon()
        if not self._hotkeys:
            self._register_hotkeys()

    def _set_taskbar_icon(self) -> None:
        """Qt podaje Windows ikonę 32 px, a pasek zadań przy 100% skalowania ma 24 px – zmniejszona ikona
        rozmywa napis „by MK”. Dlatego ustawiamy ikonę dokładnie w rozmiarze przycisku na pasku."""
        size = round(24 * self.devicePixelRatioF())
        image = render_icon(size)
        try:
            hicon = image.toHICON()
        except (AttributeError, RuntimeError):
            return
        self._taskbar_hicon = hicon  # uchwyt musi żyć tak długo jak okno
        winapi.set_big_icon(int(self.winId()), int(hicon))

    def nativeEvent(self, event_type, message):
        if bytes(event_type) == b"windows_generic_MSG":
            msg = winapi.message_from_native(message)
            if msg.message == winapi.WM_HOTKEY and msg.wParam in self._hotkeys:
                self._on_hotkey(HOTKEY_IDS[msg.wParam])
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
            tr("Do wyświetlania licznika nad grą w pełnym ekranie potrzebny jest darmowy program "
            "RivaTuner Statistics Server (RTSS).\n\n"
            "Zainstalować go teraz? Instalacja pobierze oficjalną paczkę Guru3D przez winget, "
            "a Windows poprosi o zgodę administratora."),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._start_rtss_setup(install=True)
        else:
            r.install_declined = True
            self.notice_label.setText(tr("RTSS możesz zainstalować później przyciskiem „Zainstaluj RTSS…”."))
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

    # ---------------------------------------------------------- aktualizacje

    def _build_update_banner(self) -> QFrame:
        banner = self.update_banner = QFrame()
        banner.setStyleSheet("QFrame { background:#1d3550; border-radius:4px; } QLabel { color:#d6e6f7; }")
        row = QHBoxLayout(banner)
        row.setContentsMargins(8, 4, 8, 4)
        self.update_label = QLabel()
        self.update_label.setWordWrap(True)
        self.update_progress = QProgressBar()
        self.update_progress.setMaximumWidth(160)
        self.update_progress.hide()
        self.update_notes_button = QPushButton(tr("Co nowego"))
        self.update_notes_button.clicked.connect(self._open_release_page)
        self.update_button = QPushButton(tr("Aktualizuj"))
        self.update_button.clicked.connect(self.start_update)
        self.update_later_button = QPushButton(tr("Później"))
        self.update_later_button.setToolTip(tr("Ukrywa pasek do następnego uruchomienia programu."))
        self.update_later_button.clicked.connect(banner.hide)
        row.addWidget(self.update_label, 1)
        row.addWidget(self.update_progress)
        for button in (self.update_notes_button, self.update_button, self.update_later_button):
            row.addWidget(button)
        banner.hide()
        return banner

    def _init_updates(self, after_update: bool) -> None:
        self._release: updater.Release | None = None
        self._update_check: UpdateCheckWorker | None = None
        self._update_download: UpdateDownloadWorker | None = None
        self._update_after_check = False   # „Aktualizuj” przed sprawdzeniem – pobieranie po sprawdzeniu
        self._relaunch: str | None = None  # po zamknięciu uruchom program ponownie z tym argumentem
        self._about_update_label: QLabel | None = None
        self._instance_server = QLocalServer(self)
        QLocalServer.removeServer(INSTANCE_SERVER)
        self._instance_server.newConnection.connect(self._on_instance_wake)
        self._instance_server.listen(INSTANCE_SERVER)
        exe = updater.running_exe()
        if exe is not None:
            updater.cleanup(exe)
            QTimer.singleShot(15000, lambda: updater.cleanup(exe))  # stara wersja mogła jeszcze się zamykać
        if after_update:
            self.notice_label.setText(tr("Zaktualizowano do wersji {version}.", version=__version__))
            self.diag.write(f"AKTUALIZACJA: uruchomiono wersję {__version__}")
        if updater.is_newer(self.config.update.latest):
            self._show_update_banner(self.config.update.latest)
        self._update_timer = QTimer(self, interval=UPDATE_CHECK_TIMER_MS)
        self._update_timer.timeout.connect(self._auto_check_updates)
        self._update_timer.start()
        QTimer.singleShot(5000, self._auto_check_updates)

    def _on_instance_wake(self) -> None:
        """Ponowne kliknięcie ikony: okno wychodzi na wierzch i program sprawdza aktualizację (bez instalacji)."""
        while (connection := self._instance_server.nextPendingConnection()) is not None:
            connection.disconnected.connect(connection.deleteLater)
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()
        self.check_updates(manual=False)

    def _auto_check_updates(self) -> None:
        u = self.config.update
        if u.check and updater.due(u.last_check, time.time()):
            self.check_updates(manual=False)

    def check_updates(self, manual: bool) -> None:
        if self._update_check is not None:
            return
        self._set_about_update_status(tr("Sprawdzanie…"))
        worker = UpdateCheckWorker(self)
        worker.done.connect(lambda release, error: self._on_update_checked(release, error, manual))
        self._update_check = worker
        worker.start()

    def _on_update_checked(self, release, error: str, manual: bool) -> None:
        worker, self._update_check = self._update_check, None
        if worker is not None:
            worker.wait()
            worker.deleteLater()
        if release is None:
            self.diag.write(f"AKTUALIZACJA: {error}")
            self._set_about_update_status(error)
            if manual or self._update_after_check:
                self.notice_label.setText(error)
            self._update_after_check = False
            return
        u = self.config.update
        u.last_check, u.latest = time.time(), release.version
        self._save_timer.start()
        if not updater.is_newer(release.version):
            text = tr("Masz najnowszą wersję ({version}).", version=__version__)
            self._set_about_update_status(text)
            if manual:
                self.notice_label.setText(text)
            self.update_banner.hide()
            self._update_after_check = False
            return
        self._release = release
        self.diag.write(f"AKTUALIZACJA: dostępna wersja {release.version}")
        self._set_about_update_status(tr("Dostępna wersja {version}.", version=release.version))
        self._show_update_banner(release.version)
        if self._update_after_check:
            self._update_after_check = False
            self.start_update()

    def _show_update_banner(self, version: str) -> None:
        self.update_label.setText(tr("Dostępna nowa wersja <b>{version}</b> (masz {version2}).", version=version, version2=__version__))
        source = updater.running_exe() is None
        self.update_button.setEnabled(not source)
        self.update_button.setToolTip(tr("Program uruchomiony ze źródeł – zaktualizuj go poleceniem git pull.")
                                      if source else tr("Pobiera nową wersję, podmienia program i uruchamia go ponownie."))
        self.update_progress.hide()
        self.update_banner.show()

    def _open_release_page(self) -> None:
        url = self._release.page_url if self._release else f"{legal.REPOSITORY}/releases/latest"
        QDesktopServices.openUrl(QUrl(url))

    def start_update(self) -> None:
        exe = updater.running_exe()
        if exe is None or self._update_download is not None:
            return
        if self._release is None:
            # Pasek z zapamiętanej wersji – najpierw pobieramy dane wydania.
            self._update_after_check = True
            self.check_updates(manual=True)
            return
        if self.bosses.current is not None and self.bosses.state is not BossState.WAITING:
            answer = QMessageBox.question(
                self, tr("Aktualizacja"),
                tr("Trwa walka z bossem. Program zapisze jej czas i uruchomi się ponownie w nowej wersji. Kontynuować?"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                return
        worker = UpdateDownloadWorker(self._release, exe.with_name("DeathCounter.new.exe"), self)
        worker.progress.connect(self._on_update_progress)
        worker.done.connect(self._on_update_downloaded)
        self._update_download = worker
        for button in (self.update_button, self.update_later_button):
            button.setEnabled(False)
        self.update_label.setText(tr("Pobieranie wersji {version}…", version=self._release.version))
        self.update_progress.setRange(0, 0)
        self.update_progress.show()
        self.diag.write(f"AKTUALIZACJA: pobieranie {self._release.version}")
        worker.start()

    def _on_update_progress(self, done: int, total: int) -> None:
        if total:
            self.update_progress.setRange(0, 1000)
            self.update_progress.setValue(int(done * 1000 / total))

    def _on_update_downloaded(self, path: str, error: str) -> None:
        worker, self._update_download = self._update_download, None
        if worker is not None:
            worker.wait()
            worker.deleteLater()
        exe = updater.running_exe()
        if not error and exe is not None:
            try:
                updater.install(Path(path), exe)
            except updater.UpdateError as exc:
                error = str(exc)
        if error:
            self.diag.write(f"AKTUALIZACJA: {error}")
            self.update_progress.hide()
            self.update_label.setText(tr("Aktualizacja nieudana: {error}", error=error))
            for button in (self.update_button, self.update_later_button):
                button.setEnabled(True)
            return
        self.diag.write(f"AKTUALIZACJA: zainstalowano {self._release.version}, ponowne uruchomienie")
        self.update_label.setText(tr("Uruchamianie wersji {version}…", version=self._release.version))
        self._relaunch = updater.AFTER_UPDATE_ARG
        self.close()

    def _build_about_language(self) -> QWidget:
        """Lista „Język” w oknie „O programie”: zmiana zapisuje się i program uruchamia się ponownie."""
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        combo = QComboBox()
        combo.setIconSize(QSize(24, 16))
        for code, label in LANGUAGES.items():
            combo.addItem(QIcon(flag(code, 24, 16)), label, code)
        combo.setCurrentIndex(max(0, combo.findData(self.config.language)))
        combo.setToolTip(tr("Język programu i nazw bossów. Zmiana uruchamia program ponownie."))
        combo.currentIndexChanged.connect(lambda _: self._change_language(combo.currentData(), box))
        row.addWidget(QLabel(tr("Język:")))
        row.addWidget(combo)
        return box

    def _change_language(self, code: str, about: QWidget) -> None:
        if code == self.config.language:
            return
        self.config.language = code
        self._save_config()
        self.diag.write(f"JĘZYK: {code}, ponowne uruchomienie")
        answer = QMessageBox.question(
            about.window(), "Death Counter by MK",
            # w obu językach – program wciąż działa w poprzednim
            "Program uruchomi się ponownie w wybranym języku. Uruchomić teraz?\n\n"
            "The program will restart in the selected language. Restart now?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        about.window().accept()
        self._relaunch = updater.RESTART_ARG
        self.close()

    def _build_about_updates(self) -> QWidget:
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        auto = QCheckBox(tr("Sprawdzaj aktualizacje raz dziennie"))
        auto.setChecked(self.config.update.check)
        auto.setToolTip(tr("Program raz na dobę pyta GitHuba o najnowsze wydanie. Niczego nie instaluje bez Twojej zgody."))
        auto.toggled.connect(self._on_auto_update_check)
        check = QPushButton(tr("Sprawdź aktualizacje"))
        check.clicked.connect(lambda: self.check_updates(manual=True))
        self._about_update_label = QLabel()
        self._about_update_label.setStyleSheet("color:#9aa0a6;")
        row.addWidget(auto)
        row.addWidget(check)
        row.addWidget(self._about_update_label, 1)
        return box

    def _set_about_update_status(self, text: str) -> None:
        label = self._about_update_label
        if label is not None and isValid(label):  # okno „O programie” mogło zostać zamknięte
            label.setText(text)

    def _on_auto_update_check(self, checked: bool) -> None:
        self.config.update.check = checked
        self._save_timer.start()

    # ---------------------------------------------------------- zamykanie

    def closeEvent(self, event) -> None:
        if self._rtss_setup is not None:
            # Nie przerywamy instalacji RTSS w połowie – okno zamknie się po jej zakończeniu.
            self._closing = True
            self.notice_label.setText(tr("Kończenie konfiguracji RTSS – program zamknie się za chwilę."))
            event.ignore()
            return
        if self.worker is not None:
            # Najpierw kończymy wątek wykrywania, okno zamknie się po jego zakończeniu.
            self._closing = True
            self.stop_detection()
            event.ignore()
            return
        self._unregister_hotkeys()
        self._save_timer.stop()
        self._save_config()
        self._boss_timer.stop()
        self._boss_event(self.bosses.pause)
        self._rtss_timer.stop()
        self.rtss.clear()
        if self.discord is not None:
            self.discord.close()
            self.discord = None
        self.overlay.close()
        for thread in (self._update_check, self._update_download):
            if thread is not None:
                if isinstance(thread, UpdateDownloadWorker):
                    thread.cancel()
                thread.wait(TIMEOUT_MS_ON_CLOSE)
        self._process_timer.stop()
        self._stop_session()
        self._instance_server.close()
        super().closeEvent(event)
        if self._relaunch is not None:
            updater.restart(updater.running_exe(), self._relaunch)

    def _save_config(self) -> None:
        try:
            save_config(self.paths.config, self.config)
        except StorageError as exc:
            self._show_error(tr("Nie zapisano ustawień: {exc}", exc=exc))

    def _show_error(self, message: str) -> None:
        self.error_banner.setText(message)
        self.error_banner.show()

    def _clear_error(self) -> None:
        self.error_banner.hide()


def _capitalized(text: str) -> str:
    return text[:1].upper() + text[1:]


def _threshold_spin(value: float) -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(0.30, 0.99)
    spin.setSingleStep(0.01)
    spin.setValue(value)
    return spin


def _spin(low: int, high: int, value: int, suffix: str = "") -> QSpinBox:
    spin = QSpinBox()
    spin.setRange(low, high)
    spin.setValue(value)
    spin.setSuffix(suffix)
    return spin
