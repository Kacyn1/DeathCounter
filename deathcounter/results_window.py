"""Okno „Wyniki”: tabela bossów wybranej gry (śmierci, czas, status), odświeżana na żywo.
Dwuklik w bossa rozwija pod nim historię jego prób."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import attempts as attempt_log
from .attempts import format_when, summary
from .bosses import BossTracker, format_duration
from .report import rows_from_records

COLUMNS = ("Boss", "Status", "Śmierci", "Czas")
ATTEMPT_COLUMNS = ("Nr", "Początek", "Czas", "Wynik")
VISIBLE_ATTEMPTS = 15  # wysokość listy prób; dalsze przewija się
DEFEATED_COLOR = QColor("#2f9e5b")
CURRENT_COLOR = QColor("#b8860b")
OUTCOME_COLORS = {
    attempt_log.VICTORY: DEFEATED_COLOR,
    attempt_log.DEATH: QColor("#d9534f"),
    attempt_log.MANUAL_DEATH: QColor("#d9534f"),
    attempt_log.ABANDONED: QColor("#c97a1e"),
    attempt_log.STOPPED: QColor("#c97a1e"),
    attempt_log.IN_PROGRESS: CURRENT_COLOR,
    attempt_log.CANCELLED: QColor("#7d828a"),
}


class AttemptsView(QWidget):
    """Próby jednego bossa (najnowsze na górze) z podsumowaniem; lista na 15 wierszy z przewijaniem."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 4, 4, 8)
        self.summary = QLabel()
        self.summary.setStyleSheet("color:#9aa0a6;")
        layout.addWidget(self.summary)
        self.table = QTableWidget(0, len(ATTEMPT_COLUMNS))
        self.table.setHorizontalHeaderLabels(ATTEMPT_COLUMNS)
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        header = self.table.horizontalHeader()
        for column in range(len(ATTEMPT_COLUMNS) - 1):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(len(ATTEMPT_COLUMNS) - 1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

    def show_attempts(self, attempts: list[attempt_log.Attempt]) -> None:
        """`attempts` od najstarszej; tabela pokazuje najnowsze na górze, z numerem kolejnym próby."""
        self.summary.setText(summary(attempts))
        self.table.setVisible(bool(attempts))
        self.table.setRowCount(len(attempts))
        for row, (number, attempt) in enumerate(reversed(list(enumerate(attempts, 1)))):
            values = (str(number), format_when(attempt.start), format_duration(attempt.seconds),
                      attempt_log.LABELS[attempt.outcome])
            for column, text in enumerate(values):
                item = self.table.item(row, column)
                if item is None:
                    item = QTableWidgetItem()
                    self.table.setItem(row, column, item)
                if item.text() != text:
                    item.setText(text)
                if column in (0, 2):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.item(row, 3).setData(Qt.ItemDataRole.ForegroundRole, OUTCOME_COLORS[attempt.outcome])
        rows = min(len(attempts), VISIBLE_ATTEMPTS)
        height = self.table.horizontalHeader().height() + 2 * self.table.frameWidth()
        height += sum(self.table.rowHeight(r) for r in range(rows))
        self.table.setFixedHeight(height)


class ResultsWindow(QDialog):
    """Tabela bossów; dwuklik w bossa wstawia pod nim wiersz z historią jego prób."""

    fix_names_requested = Signal()  # „Popraw nazwy bossów” – porównanie z listą nazw gry

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.resize(560, 480)
        layout = QVBoxLayout(self)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, len(COLUMNS)):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        # Sortowanie własne zamiast wbudowanego: wiersz z próbami musi zostać pod swoim bossem.
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        header.setSortIndicator(1, Qt.SortOrder.AscendingOrder)  # najpierw walki w trakcie
        header.sortIndicatorChanged.connect(lambda *_: self._render())
        self.table.cellDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self.table, 1)
        hint = QLabel("Kliknij dwukrotnie bossa, aby zobaczyć historię jego prób.")
        hint.setStyleSheet("color:#7d828a;")
        self.fix_names_button = QPushButton("Popraw nazwy bossów")
        self.fix_names_button.setToolTip(
            "Porównuje nazwy bossów w tabeli z listą nazw tej gry i zamienia podobne\n"
            "(np. odczytane z błędem) na nazwy z listy. Przed zmianą pokazuje, co się zmieni."
        )
        self.fix_names_button.clicked.connect(self.fix_names_requested)
        footer = QHBoxLayout()
        footer.addWidget(hint, 1)
        footer.addWidget(self.fix_names_button)
        layout.addLayout(footer)
        self.empty = QLabel("Brak bossów – walki pojawią się tu, gdy włączysz „Śledź walkę z bossem”.")
        self.empty.setStyleSheet("color:#9aa0a6;")
        layout.addWidget(self.empty)
        self._tracker: BossTracker | None = None
        self._rows: list = []
        self._expanded: set[str] = set()
        self._layout: list[tuple[str, bool]] = []  # (boss, czy to wiersz z próbami) dla kolejnych wierszy

    def show_results(self, game: str, deaths: int, tracker: BossTracker) -> None:
        """Pokazuje wyniki gry; wywoływane co sekundę, gdy okno jest otwarte."""
        self._tracker = tracker
        self.setWindowTitle(f"Wyniki – {game}")
        rows = rows_from_records(tracker.store.records, tracker.current, tracker.elapsed())
        defeated = [r for r in rows if r.defeated]
        boss_deaths = sum(r.deaths for r in rows)
        total_time = sum(r.seconds for r in rows)
        self.summary.setText(
            f"<b>Śmierci łącznie: {deaths}</b> &nbsp;·&nbsp; pokonani bossowie: {len(defeated)} z {len(rows)}"
            f" &nbsp;·&nbsp; śmierci przy bossach: {boss_deaths} &nbsp;·&nbsp; czas walk: {format_duration(total_time)}"
        )
        self.empty.setVisible(not rows)
        # Tylko gry z wbudowaną listą nazw (Dark Souls I–III, Sekiro, Elden Ring).
        self.fix_names_button.setVisible(tracker.names is not None and bool(tracker.names.builtin_names))
        self.fix_names_button.setEnabled(bool(rows))
        self._rows = rows
        self._expanded &= {r.name for r in rows}
        self._render()

    def toggle(self, name: str) -> None:
        """Rozwija albo zwija historię prób bossa."""
        self._expanded ^= {name}
        self._render()

    def _on_double_click(self, row: int, _column: int) -> None:
        if row < len(self._layout) and not self._layout[row][1]:
            self.toggle(self._layout[row][0])

    def _render(self) -> None:
        if self._tracker is None:
            return
        current = self._tracker.current
        header = self.table.horizontalHeader()
        column, order = header.sortIndicatorSection(), header.sortIndicatorOrder()
        cells = {r.name: self._cells(r, r.name == current) for r in self._rows}
        names = sorted(cells, key=lambda n: cells[n][column][1], reverse=order == Qt.SortOrder.DescendingOrder)
        layout = [(name, detail) for name in names for detail in (False, True)
                  if not detail or name in self._expanded]
        if layout != self._layout:
            # Inna kolejność albo rozwinięcie – wiersze od nowa (przewinięcie zostaje).
            scroll = self.table.verticalScrollBar().value()
            self.table.clearSpans()
            self.table.setRowCount(0)
            self.table.setRowCount(len(layout))
            for row, (_name, detail) in enumerate(layout):
                if detail:
                    self.table.setSpan(row, 0, 1, len(COLUMNS))
                    self.table.setCellWidget(row, 0, AttemptsView())
                    continue
                for col in range(len(COLUMNS)):
                    item = QTableWidgetItem()
                    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                    self.table.setItem(row, col, item)
            self._layout = layout
            self.table.verticalScrollBar().setValue(scroll)
        for row, (name, detail) in enumerate(layout):
            if detail:
                view = self.table.cellWidget(row, 0)
                view.show_attempts(self._tracker.attempts_for(name))
                height = view.sizeHint().height()
                if self.table.rowHeight(row) != height:
                    self.table.setRowHeight(row, height)
                continue
            for col, (text, _key, color, right) in enumerate(cells[name]):
                self._update(self.table.item(row, col), text, color, right)

    @staticmethod
    def _cells(row, current: bool) -> list[tuple]:
        """(tekst, klucz sortowania, kolor, do prawej) dla kolejnych kolumn."""
        if row.defeated:
            status, order, color = "POKONANO", 2, DEFEATED_COLOR
        elif current:
            status, order, color = "W TRAKCIE (bieżąca walka)", 0, CURRENT_COLOR
        else:
            status, order, color = "W TRAKCIE", 1, None
        return [
            (row.name, row.name.casefold(), CURRENT_COLOR if current else None, False),
            (status, order, color, False),
            (str(row.deaths), row.deaths, None, True),
            (format_duration(row.seconds), row.seconds, None, True),
        ]

    @staticmethod
    def _update(item: QTableWidgetItem, text: str, color: QColor | None, right: bool) -> None:
        if item.text() != text:
            item.setText(text)
        if right:
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        item.setData(Qt.ItemDataRole.ForegroundRole, color)
        font = QFont(item.font())
        font.setBold(color is not None)
        item.setFont(font)
