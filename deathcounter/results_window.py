"""Okno „Wyniki”: tabela bossów wybranej gry (śmierci, czas, status), odświeżana na żywo."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from .bosses import BossTracker, format_duration
from .report import rows_from_records

COLUMNS = ("Boss", "Status", "Śmierci", "Czas")
DEFEATED_COLOR = QColor("#2f9e5b")
CURRENT_COLOR = QColor("#b8860b")


class _Item(QTableWidgetItem):
    """Komórka sortowana po wartości (liczba, czas w sekundach), a nie po wyświetlanym tekście."""

    def __init__(self, text: str, key) -> None:
        super().__init__(text)
        self.key = key
        self.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)

    def __lt__(self, other: QTableWidgetItem) -> bool:
        if isinstance(other, _Item):
            return self.key < other.key
        return super().__lt__(other)


class ResultsWindow(QDialog):
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
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, len(COLUMNS)):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table, 1)
        self.empty = QLabel("Brak bossów – walki pojawią się tu, gdy włączysz „Śledź walkę z bossem”.")
        self.empty.setStyleSheet("color:#9aa0a6;")
        layout.addWidget(self.empty)
        self._names: list[str] = []
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(1, Qt.SortOrder.AscendingOrder)  # najpierw walki w trakcie

    def show_results(self, game: str, deaths: int, tracker: BossTracker) -> None:
        """Pokazuje wyniki gry; wywoływane co sekundę, gdy okno jest otwarte."""
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
        cells = [self._cells(r, r.name == tracker.current) for r in rows]
        names = [r.name for r in rows]
        self.table.setSortingEnabled(False)  # zmiana komórek przy włączonym sortowaniu przestawia wiersze w pętli
        if sorted(names) == sorted(self._names):
            # Te same wiersze – zmieniamy tylko treść, żeby nie gubić zaznaczenia i przewinięcia.
            for row in range(self.table.rowCount()):
                name = self.table.item(row, 0).text()
                for column, values in enumerate(cells[names.index(name)]):
                    self._update(self.table.item(row, column), *values)
            self.table.setSortingEnabled(True)
            return
        self._names = names
        self.table.setRowCount(len(rows))
        for row, values in enumerate(cells):
            for column, cell in enumerate(values):
                item = _Item(cell[0], cell[1])
                self._update(item, *cell)
                self.table.setItem(row, column, item)
        self.table.setSortingEnabled(True)

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
    def _update(item: _Item, text: str, key, color: QColor | None, right: bool) -> None:
        if item.text() != text:
            item.setText(text)
        item.key = key
        if right:
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        item.setData(Qt.ItemDataRole.ForegroundRole, color)
        font = QFont(item.font())
        font.setBold(color is not None)
        item.setFont(font)
