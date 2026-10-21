from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from deathcounter import steam_dialog
from deathcounter.config import AppConfig
from deathcounter.steam_dialog import SteamScanDialog
from deathcounter.steam_library import BUILTIN, LIST, MAYBE, TAG, Found, ScanResult, SteamGame


class NoThread:
    """Zamiast wątku: wynik skanu podaje test."""

    def __init__(self, parent):
        from PySide6.QtCore import QObject, Signal

        class Signals(QObject):
            done = Signal(object, str)
            finished = Signal()

        self._signals = Signals()
        self.done, self.finished = self._signals.done, self._signals.finished

    def deleteLater(self):
        pass

    def start(self):
        pass


def make_dialog(monkeypatch, config):
    workers = []
    monkeypatch.setattr(steam_dialog, "SteamScanWorker", lambda parent: workers.append(NoThread(parent)) or workers[-1])
    parent = QWidget()
    dialog = SteamScanDialog(parent, config)
    return dialog, workers[0], parent


def test_dialog_lists_new_games_checked_and_known_games_disabled(monkeypatch):
    config = AppConfig()
    config.add_game("Nioh", appid=485510)
    dialog, worker, _parent = make_dialog(monkeypatch, config)
    assert not dialog.add_button.isEnabled()
    found = [
        Found(SteamGame(374320, "DARK SOULS III"), BUILTIN, "ds3"),
        Found(SteamGame(485510, "Nioh: Complete Edition"), LIST),
        Found(SteamGame(1627720, "Lies of P"), TAG),
        Found(SteamGame(367520, "Hollow Knight"), TAG),
        Found(SteamGame(1888160, "ARMORED CORE VI"), MAYBE),
    ]
    worker.done.emit(ScanResult(found, installed=12, online_error=""), "")
    texts = [dialog.games_list.item(row).text() for row in range(dialog.games_list.count())]
    assert texts[0] == "DARK SOULS III – wbudowana w program (Dark Souls III)"
    assert texts[1] == "Nioh: Complete Edition – już na liście"
    assert texts[2] == "Lies of P  (tag Souls-like w Steam)"
    assert texts[4].startswith("Możliwe souls-like")
    assert texts[5] == "ARMORED CORE VI  (inspirowana soulsami)"
    assert "Souls-like: 4, możliwe souls-like: 1." in dialog.status_label.text()
    assert dialog.add_button.isEnabled()
    # Możliwe souls-like nie są zaznaczone, nagłówka nie da się wybrać.
    assert dialog.selected() == [SteamGame(1627720, "Lies of P"), SteamGame(367520, "Hollow Knight")]
    dialog.games_list.item(5).setCheckState(Qt.CheckState.Checked)
    dialog.games_list.item(3).setCheckState(Qt.CheckState.Unchecked)
    assert dialog.selected() == [SteamGame(1627720, "Lies of P"), SteamGame(1888160, "ARMORED CORE VI")]
    dialog.games_list.item(2).setCheckState(Qt.CheckState.Unchecked)
    dialog.games_list.item(5).setCheckState(Qt.CheckState.Unchecked)
    assert not dialog.add_button.isEnabled()


def test_dialog_shows_errors(monkeypatch):
    dialog, worker, _parent = make_dialog(monkeypatch, AppConfig())
    worker.done.emit(None, "Nie znaleziono Steama na tym komputerze.")
    assert dialog.status_label.text() == "Nie znaleziono Steama na tym komputerze."
    assert not dialog.add_button.isEnabled()

    dialog, worker, _parent = make_dialog(monkeypatch, AppConfig())
    worker.done.emit(ScanResult([], installed=3, online_error="Brak połączenia ze sklepem Steam (x)."), "")
    assert "Użyto wbudowanej listy" in dialog.status_label.text()
    assert "Brak nowych gier do dodania." in dialog.status_label.text()
