"""Uruchomienie aplikacji: wczytanie danych, blokada drugiej instancji, obsługa błędów w oknie."""

from __future__ import annotations

import sys
import traceback

from PySide6.QtCore import QDir, QLockFile
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QMessageBox

from .config import AppPaths, load_config
from .main_window import MainWindow
from .storage import DeathStore, StorageError
from .template import DeathTemplate, TemplateError


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
        box = QMessageBox(QMessageBox.Icon.Critical, "DS2 Death Counter – błąd", f"Wystąpił nieoczekiwany błąd:\n{exc}")
        box.setDetailedText(details)
        box.exec()

    sys.excepthook = hook


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("DS2 Death Counter")
    app.setStyle("Fusion")
    app.setPalette(_dark_palette())
    _install_excepthook()

    lock = QLockFile(QDir.temp().filePath("ds2-death-counter.lock"))
    if not lock.tryLock(100):
        QMessageBox.warning(None, "DS2 Death Counter", "Program jest już uruchomiony.")
        return 1

    try:
        paths = AppPaths.default()
        store = DeathStore(paths.deaths)
        store.load()
    except StorageError as exc:
        QMessageBox.critical(None, "DS2 Death Counter", f"Nie można przygotować pliku wyniku.\n\n{exc}")
        return 1

    warnings = [w for w in (store.warning,) if w]
    config, config_warning = load_config(paths.config)
    if config_warning:
        warnings.append(config_warning)

    template = None
    if config.template is not None:
        try:
            template = DeathTemplate.load(paths.template, config.template)
        except TemplateError as exc:
            warnings.append(f"Nie można wczytać wzorca: {exc} Wykonaj kalibrację ponownie.")

    window = MainWindow(paths, store, config, template)
    window.show()
    for warning in warnings:
        QMessageBox.warning(window, "DS2 Death Counter", warning)
    return app.exec()
