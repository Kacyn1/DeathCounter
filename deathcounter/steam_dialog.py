"""Okno „Znajdź zainstalowane gry ze Steam”: gry souls-like z biblioteki Steam do zaznaczenia i dodania na listę gier."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import steam_library
from .config import AppConfig
from .i18n import N_, tr
from .steam_library import Found, ScanResult, SteamGame
from .worker import SteamScanWorker

SOURCE_LABELS = {
    steam_library.TAG: N_("tag Souls-like w Steam"),
    steam_library.LIST: N_("znana gra souls-like"),
    steam_library.MAYBE: N_("inspirowana soulsami"),
}


class SteamScanDialog(QDialog):
    def __init__(self, parent: QWidget, config: AppConfig) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Gry ze Steama"))
        self.setMinimumWidth(460)
        self._config = config
        layout = QVBoxLayout(self)
        info = QLabel(tr("Program czyta listę zainstalowanych gier z plików Steama na tym komputerze. "
                         "Do sklepu Steam wysyła tylko ich numery (AppID), żeby sprawdzić tag „Souls-like”."))
        info.setWordWrap(True)
        info.setStyleSheet("color:#9aa0a6;")
        self.status_label = QLabel(tr("Sprawdzanie biblioteki Steam…"))
        self.status_label.setWordWrap(True)
        self.games_list = QListWidget()
        self.games_list.itemChanged.connect(self._refresh_add_button)
        self.buttons = QDialogButtonBox()
        self.add_button = self.buttons.addButton(tr("Dodaj zaznaczone"), QDialogButtonBox.ButtonRole.AcceptRole)
        self.buttons.addButton(tr("Anuluj"), QDialogButtonBox.ButtonRole.RejectRole)
        self.add_button.setEnabled(False)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(info)
        layout.addWidget(self.status_label)
        layout.addWidget(self.games_list, 1)
        layout.addWidget(self.buttons)

        # Wątek należy do okna głównego: zamknięcie tego okna w trakcie zapytania go nie przerywa,
        # a sygnał do usuniętego okna Qt rozłącza sam.
        worker = SteamScanWorker(parent)
        worker.done.connect(self._on_scanned)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def selected(self) -> list[SteamGame]:
        items = (self.games_list.item(row) for row in range(self.games_list.count()))
        return [item.data(Qt.ItemDataRole.UserRole) for item in items
                if item.flags() & Qt.ItemFlag.ItemIsEnabled and item.checkState() == Qt.CheckState.Checked]

    def _on_scanned(self, result: ScanResult | None, error: str) -> None:
        if result is None:
            self.status_label.setText(error)
            return
        maybe = [found for found in result.found if found.source == steam_library.MAYBE]
        self.games_list.blockSignals(True)
        for found in result.found:
            if maybe and found is maybe[0]:
                self.games_list.addItem(self._header(tr(
                    "Możliwe souls-like – tag „Souls-like” jest dalej wśród tagów gry. "
                    "Zaznacz, jeśli gra ma ekran śmierci:")))
            self.games_list.addItem(self._item(found))
        self.games_list.blockSignals(False)
        new = sum(1 for row in range(self.games_list.count())
                  if self.games_list.item(row).flags() & Qt.ItemFlag.ItemIsEnabled)
        lines = [tr("Zainstalowane gry: {installed}. Souls-like: {sure}, możliwe souls-like: {maybe}.",
                    installed=result.installed, sure=len(result.found) - len(maybe), maybe=len(maybe))]
        if result.online_error:
            lines.append(tr("Nie udało się sprawdzić tagów: {error} Użyto wbudowanej listy znanych gier.",
                            error=result.online_error))
        lines.append(tr("Zaznacz gry, które mają dostać licznik.") if new else tr("Brak nowych gier do dodania."))
        self.status_label.setText("\n".join(lines))
        self._refresh_add_button()

    def _item(self, found: Found) -> QListWidgetItem:
        game = found.game
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, game)
        if found.source == steam_library.BUILTIN:
            text = tr("{name} – wbudowana w program ({game})", name=game.name,
                      game=self._config.game_name(found.builtin))
            enabled = False
        elif self._config.steam_game(game.appid) or self._config.has_game_named(game.name):
            text, enabled = tr("{name} – już na liście", name=game.name), False
        else:
            text, enabled = f"{game.name}  ({tr(SOURCE_LABELS[found.source])})", True
        item.setText(text)
        flags = Qt.ItemFlag.ItemIsUserCheckable
        item.setFlags(flags | Qt.ItemFlag.ItemIsEnabled if enabled else flags)
        # Nowe souls-like są zaznaczone, możliwe – nie; nieaktywne pozycje pokazują, że gra już jest.
        maybe = enabled and found.source == steam_library.MAYBE
        item.setCheckState(Qt.CheckState.Unchecked if maybe else Qt.CheckState.Checked)
        return item

    @staticmethod
    def _header(text: str) -> QListWidgetItem:
        item = QListWidgetItem(text)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        font = item.font()
        font.setBold(True)
        item.setFont(font)
        return item

    def _refresh_add_button(self, *_) -> None:
        self.add_button.setEnabled(bool(self.selected()))
