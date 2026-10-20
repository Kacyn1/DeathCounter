"""Uruchomienie aplikacji: wczytanie danych, blokada drugiej instancji, obsługa błędów w oknie."""

from __future__ import annotations

import ctypes
import sys
import traceback

from PySide6.QtCore import QDir, QLockFile
from PySide6.QtNetwork import QLocalSocket
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox

from .config import GAMES, data_dir, legacy_data_present, load_config, migrate_legacy, save_config
from .game_data import open_game
from .icon import app_icon
from .main_window import INSTANCE_SERVER, MainWindow
from .updater import AFTER_UPDATE_ARG, RESTART_ARG
from . import i18n
from .storage import StorageError
from .i18n import tr


def _dark_palette() -> QPalette:
    palette = QPalette()
    base, window, text = QColor(24, 25, 28), QColor(32, 33, 37), QColor(225, 225, 225)
    palette.setColor(QPalette.ColorRole.Window, window)
    palette.setColor(QPalette.ColorRole.WindowText, text)
    palette.setColor(QPalette.ColorRole.Base, base)
    palette.setColor(QPalette.ColorRole.AlternateBase, window)
    palette.setColor(QPalette.ColorRole.Text, text)
    palette.setColor(QPalette.ColorRole.Button, QColor(45, 46, 51))
    palette.setColor(QPalette.ColorRole.ButtonText, text)
    palette.setColor(QPalette.ColorRole.ToolTipBase, window)
    palette.setColor(QPalette.ColorRole.ToolTipText, text)
    palette.setColor(QPalette.ColorRole.Highlight, QColor(150, 40, 40))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(110, 110, 110))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(110, 110, 110))
    return palette


def _install_excepthook() -> None:
    def hook(exc_type, exc, tb):
        details = "".join(traceback.format_exception(exc_type, exc, tb))
        box = QMessageBox(QMessageBox.Icon.Critical, tr("Death Counter by MK – błąd"), tr("Wystąpił nieoczekiwany błąd:\n{exc}", exc=exc))
        box.setDetailedText(details)
        box.exec()

    sys.excepthook = hook


def _set_app_user_model_id() -> None:
    # Bez tego pasek zadań grupuje okno pod pythonw.exe i pokazuje ikonę Pythona.
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("DeathCounter")
    except (AttributeError, OSError):
        pass


def _wake_running() -> bool:
    """Program już działa: prosi go o pokazanie okna (i sprawdzenie aktualizacji). False, gdy nie odpowiada."""
    try:
        ctypes.windll.user32.AllowSetForegroundWindow(-1)  # działająca kopia może wyjść na wierzch
    except (AttributeError, OSError):
        pass
    socket = QLocalSocket()
    socket.connectToServer(INSTANCE_SERVER)
    if not socket.waitForConnected(1000):
        return False
    socket.write(b"show")
    socket.waitForBytesWritten(1000)
    socket.disconnectFromServer()
    return True


def _ask_legacy_game(default: str) -> str:
    """Jednorazowo po aktualizacji: do której gry należą dotychczasowy licznik, bossowie i kalibracja."""
    ids = list(GAMES)
    name, ok = QInputDialog.getItem(
        None,
        tr("Death Counter by MK – wybór gry"),
        tr("Program zapisuje teraz licznik śmierci, bossów i kalibrację osobno dla każdej gry.\n"
        "Do której gry należą dotychczasowe dane?"),
        [GAMES[g] for g in ids],
        ids.index(default) if default in ids else 0,
        False,
    )
    return ids[[GAMES[g] for g in ids].index(name)] if ok else default


def main() -> int:
    _set_app_user_model_id()
    app = QApplication(sys.argv)
    app.setApplicationName("Death Counter by MK")
    app.setWindowIcon(app_icon())
    app.setStyle("Fusion")
    app.setPalette(_dark_palette())
    _install_excepthook()

    # Po aktualizacji (albo zmianie języka) nowa kopia czeka, aż stara się zamknie i zwolni blokadę.
    after_update = AFTER_UPDATE_ARG in sys.argv
    restarted = after_update or RESTART_ARG in sys.argv
    lock = QLockFile(QDir.temp().filePath("death-counter.lock"))
    if not lock.tryLock(30000 if restarted else 100):
        if not restarted and _wake_running():
            return 0  # ponowne kliknięcie ikony – działające okno wychodzi na wierzch
        QMessageBox.warning(None, "Death Counter by MK", tr("Program jest już uruchomiony."))
        return 1

    try:
        base = data_dir()
        config, config_warning = load_config(base / "config.json")
        i18n.set_language(config.language)
        if legacy_data_present(base):
            config.game = _ask_legacy_game(config.game)
            migrate_legacy(base, config.game)
            save_config(base / "config.json", config)
        game = open_game(base, config.game)
    except StorageError as exc:
        QMessageBox.critical(None, "Death Counter by MK", tr("Nie można przygotować pliku wyniku.\n\n{exc}", exc=exc))
        return 1

    warnings = ([config_warning] if config_warning else []) + game.warnings
    window = MainWindow(config, game, after_update=after_update)
    window.show()
    for warning in warnings:
        QMessageBox.warning(window, "Death Counter by MK", warning)
    return app.exec()
