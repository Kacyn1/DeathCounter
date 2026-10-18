"""Panel „Walka z bossem”: śledzenie włącza się jednym polem, resztę prowadzi program."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
)

from .bosses import BossState, BossTracker, format_duration
from .storage import StorageError

STATE_COLORS = {
    BossState.WAITING: "#6b6f76",
    BossState.FIGHT: "#b8860b",
    BossState.DEATH: "#c0392b",
    BossState.DEFEATED: "#2f9e5b",
}


class BossPanel(QGroupBox):
    track_toggled = Signal(bool)
    changed = Signal()             # dane bossa zmieniły się po akcji w panelu
    save_failed = Signal(str)
    calibrate_requested = Signal()

    def __init__(self, tracker: BossTracker, parent=None) -> None:
        super().__init__("Walka z bossem", parent)
        self.tracker = tracker
        form = QFormLayout(self)

        self.track_check = QCheckBox("Śledź walkę z bossem")
        self.track_check.setChecked(tracker.enabled)
        self.track_check.setToolTip(
            "Walka zaczyna się sama, gdy na ekranie pojawi się pasek zdrowia bossa. Śmierć pauzuje timer,\n"
            "a komunikat zwycięstwa zatrzymuje go na stałe. Ty tylko zatwierdzasz wynik."
        )
        self.track_check.toggled.connect(self._on_track)
        form.addRow(self.track_check)

        self.state_label = QLabel()
        self.state_label.setStyleSheet("padding:2px 8px; border-radius:4px; color:white; font-weight:bold;")
        self.summary_label = QLabel()
        state_row = QHBoxLayout()
        state_row.addWidget(self.state_label)
        state_row.addWidget(self.summary_label, 1)
        form.addRow("Status:", state_row)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("nazwę możesz wpisać w dowolnym momencie")
        self.name_edit.editingFinished.connect(self._on_name)
        form.addRow("Boss:", self.name_edit)

        self.warning_label = QLabel()
        self.warning_label.setWordWrap(True)
        self.warning_label.setStyleSheet("background:#5a3a12; color:#ffe2b8; padding:6px; border-radius:4px;")
        form.addRow(self.warning_label)

        buttons = QHBoxLayout()
        self.save_button = QPushButton("Zapisz wynik")
        self.save_button.setToolTip("Zapisuje ostateczny wynik do bosses.json ze statusem POKONANO i czyści panel.")
        self.save_button.clicked.connect(lambda: self._act(self.tracker.confirm_defeated))
        self.continue_button = QPushButton("Kontynuuj walkę")
        self.continue_button.setToolTip("To nie było zwycięstwo – walka z tym bossem trwa dalej.")
        self.continue_button.clicked.connect(lambda: self._act(self.tracker.continue_fight))
        self.discard_button = QPushButton("Odrzuć")
        self.discard_button.setToolTip("Pomyłka (np. fałszywy start) – wpis zostanie usunięty bez zapisu wyniku.")
        self.discard_button.clicked.connect(self._confirm_discard)
        for button in (self.save_button, self.continue_button, self.discard_button):
            buttons.addWidget(button)
        form.addRow(buttons)

        self.hint_label = QLabel()
        self.hint_label.setWordWrap(True)
        self.hint_label.setStyleSheet("color:#9aa0a6;")
        calibrate_button = QPushButton("Kalibracja walki…")
        calibrate_button.setToolTip("Wzorce paska zdrowia bossa i komunikatu zwycięstwa.")
        calibrate_button.clicked.connect(self.calibrate_requested)
        hint_row = QHBoxLayout()
        hint_row.addWidget(self.hint_label, 1)
        hint_row.addWidget(calibrate_button)
        form.addRow(hint_row)
        self.refresh()

    def set_hint(self, text: str) -> None:
        self.hint_label.setText(text)

    def refresh(self) -> None:
        view = self.tracker.view()
        state = view.state if view else BossState.WAITING
        self.state_label.setText(state.value.upper())
        self.state_label.setStyleSheet(
            f"padding:2px 8px; border-radius:4px; color:white; font-weight:bold; background:{STATE_COLORS[state]};"
        )
        if view is None:
            self.summary_label.setText("brak aktywnej walki" if self.tracker.enabled else "śledzenie wyłączone")
        else:
            self.summary_label.setText(f"śmierci: {view.deaths}   czas: {format_duration(view.seconds)}")
        if not self.name_edit.hasFocus():
            self.name_edit.setText(view.name if view else "")
        self.name_edit.setEnabled(view is not None)
        self.warning_label.setText((view.uncertain or "") if view else "")
        self.warning_label.setVisible(bool(view and view.uncertain))
        self.save_button.setEnabled(view is not None and view.state is not BossState.FIGHT)
        self.continue_button.setVisible(bool(view and view.uncertain))
        self.discard_button.setEnabled(view is not None)

    def _on_track(self, checked: bool) -> None:
        self._act(lambda: self.tracker.set_enabled(checked))
        self.track_toggled.emit(checked)

    def _on_name(self) -> None:
        if self.tracker.current is not None and self.name_edit.text().strip():
            self._act(lambda: self.tracker.rename(self.name_edit.text()))
            self.name_edit.setText(self.tracker.current or "")

    def _confirm_discard(self) -> None:
        answer = QMessageBox.question(
            self,
            "Odrzuć walkę",
            f"Usunąć „{self.tracker.current}” bez zapisu wyniku?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._act(self.tracker.discard)

    def _act(self, action) -> None:
        try:
            action()
        except StorageError as exc:
            self.save_failed.emit(f"Nie zapisano danych bossa: {exc} Kolejna zmiana ponowi zapis.")
        self.refresh()
        self.changed.emit()
