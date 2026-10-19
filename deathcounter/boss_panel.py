"""Panel „Walka z bossem”: śledzenie włącza się jednym polem, resztę prowadzi program."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
)

from . import recent_fights
from .attempts import format_when
from .bosses import BossState, BossTracker, RecentRow, format_duration
from .storage import StorageError

RECENT_ROWS = 3
OUTCOME_LABELS = {
    recent_fights.IN_PROGRESS: ("W TRAKCIE", "#9aa0a6"),
    recent_fights.ABANDONED: ("PRZERWANO", "#c97a1e"),
    recent_fights.DEFEATED: ("POKONANO", "#2f9e5b"),
}

STATE_COLORS = {
    BossState.WAITING: "#6b6f76",
    BossState.FIGHT: "#b8860b",
    BossState.DEATH: "#c0392b",
    BossState.DEFEATED: "#2f9e5b",
}


class BossPanel(QGroupBox):
    track_toggled = Signal(bool)
    read_names_toggled = Signal(bool)
    changed = Signal()             # dane bossa zmieniły się po akcji w panelu
    save_failed = Signal(str)
    calibrate_requested = Signal()
    results_requested = Signal()

    def __init__(self, tracker: BossTracker, read_names: bool = True, parent=None) -> None:
        super().__init__("Walka z bossem", parent)
        self.tracker = tracker
        self._note = ""
        form = QFormLayout(self)

        self.track_check = QCheckBox("Śledź walkę z bossem")
        self.track_check.setChecked(tracker.enabled)
        self.track_check.setToolTip(
            "Walka zaczyna się sama, gdy na ekranie pojawi się pasek zdrowia bossa. Śmierć pauzuje timer,\n"
            "a komunikat zwycięstwa zatrzymuje go na stałe. Ty tylko zatwierdzasz wynik."
        )
        self.track_check.toggled.connect(self._on_track)
        self.read_names_check = QCheckBox("Odczytuj nazwę bossa z ekranu")
        self.read_names_check.setChecked(read_names)
        self.read_names_check.setToolTip(
            "Po pojawieniu się paska program czyta nazwę nad nim (OCR Windows, język polski).\n"
            "Poprawiona ręcznie nazwa zostaje zapamiętana – następnym razem boss zostanie rozpoznany od razu.\n"
            "Gdy w trakcie walki pojawi się inny boss, walka przechodzi na niego."
        )
        self.read_names_check.toggled.connect(self.read_names_toggled)
        track_row = QHBoxLayout()
        track_row.addWidget(self.track_check)
        track_row.addWidget(self.read_names_check, 1)
        form.addRow(track_row)

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

        # Ostatnie walki: stałe wiersze, odświeżane co sekundę bez przebudowy widżetów.
        recent_grid = QGridLayout()
        recent_grid.setColumnStretch(0, 1)
        self.recent_title = QLabel("Ostatnie walki:")
        self.recent_title.setStyleSheet("color:#9aa0a6;")
        recent_grid.addWidget(self.recent_title, 0, 0, 1, 3)
        self._recent: list[tuple[QLabel, QPushButton, QPushButton]] = []
        for index in range(RECENT_ROWS):
            label = QLabel()
            defeated = QPushButton("Pokonany")
            defeated.setToolTip("To była wygrana, której program nie wykrył – zapisz wynik jako POKONANO.")
            defeated.clicked.connect(lambda _=False, i=index: self._recent_action(i, defeated=True))
            remove = QPushButton("Usuń")
            remove.setToolTip("Pomyłka (np. przebiegnięcie obok bossa) – usuwa bossa razem z wynikiem.")
            remove.clicked.connect(lambda _=False, i=index: self._recent_action(i, defeated=False))
            recent_grid.addWidget(label, index + 1, 0)
            recent_grid.addWidget(defeated, index + 1, 1)
            recent_grid.addWidget(remove, index + 1, 2)
            self._recent.append((label, defeated, remove))
        self._recent_rows: list[RecentRow] = []
        form.addRow(recent_grid)

        self.hint_label = QLabel()
        self.hint_label.setWordWrap(True)
        self.hint_label.setStyleSheet("color:#9aa0a6;")
        calibrate_button = QPushButton("Kalibracja walki…")
        calibrate_button.setToolTip("Wzorce paska zdrowia bossa i komunikatu zwycięstwa.")
        calibrate_button.clicked.connect(self.calibrate_requested)
        hint_row = QHBoxLayout()
        hint_row.addWidget(self.hint_label, 1)
        results_button = QPushButton("Wyniki…")
        results_button.setToolTip("Tabela wszystkich bossów tej gry: śmierci, czas i status.")
        results_button.clicked.connect(self.results_requested)
        hint_row.addWidget(results_button)
        hint_row.addWidget(calibrate_button)
        form.addRow(hint_row)
        self.refresh()

    def set_tracker(self, tracker: BossTracker) -> None:
        """Po zmianie gry panel pokazuje bossów tej gry."""
        self.tracker = tracker
        self._note = ""
        self.name_edit.clear()
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
        warning = view.uncertain if view else None
        if view is not None and not warning and view.state is BossState.DEFEATED and not view.name_confident:
            warning = "Nazwa bossa jest niepewna – sprawdź ją (możesz poprawić) i kliknij „Zapisz wynik”."
        self.warning_label.setText(warning or "")
        self.warning_label.setVisible(bool(warning))
        self.save_button.setEnabled(view is not None and view.state is not BossState.FIGHT)
        self.continue_button.setVisible(bool(view and view.uncertain))
        self.discard_button.setEnabled(view is not None)
        if view is not None:
            self._note = ""
        if view is None and self._note:
            self.summary_label.setText(self._note)
        self._refresh_recent()

    def _refresh_recent(self) -> None:
        rows = self._recent_rows = self.tracker.recent_rows(RECENT_ROWS)
        self.recent_title.setVisible(bool(rows))
        for index, (label, defeated, remove) in enumerate(self._recent):
            row = rows[index] if index < len(rows) else None
            for widget in (label, defeated, remove):
                widget.setVisible(row is not None)
            if row is None:
                continue
            status, color = OUTCOME_LABELS[row.outcome]
            text = (f"{row.name} · <b style='color:{color}'>{status}</b> · śmierci: {row.deaths} · "
                    f"{format_duration(row.seconds)} · <span style='color:#7d828a'>{format_when(row.time)}</span>")
            if label.text() != text:
                label.setText(text)
            open_fight = row.outcome != recent_fights.DEFEATED
            defeated.setVisible(open_fight)
            remove.setVisible(open_fight)

    def _recent_action(self, index: int, defeated: bool) -> None:
        if index >= len(self._recent_rows):
            return
        row = self._recent_rows[index]
        if defeated:
            self._act(lambda: self.tracker.mark_defeated(row.name))
            return
        answer = QMessageBox.question(
            self,
            "Usuń walkę",
            f"Usunąć „{row.name}” razem z wynikiem (śmierci: {row.deaths}, czas: {format_duration(row.seconds)})?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._act(lambda: self.tracker.remove(row.name))

    def set_note(self, text: str) -> None:
        """Komunikat po zakończonej walce (np. automatyczny zapis), widoczny do początku kolejnej walki."""
        self._note = text
        self.refresh()

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
