"""Licencja programu (GNU GPL v3) i licencje bibliotek: odczyt plików i okno „O programie”."""

from __future__ import annotations

import sys
from pathlib import Path

from . import __version__

AUTHOR = "Mateusz Kacyna"
REPOSITORY = "https://github.com/Kacyn1/DeathCounter"
COPYRIGHT = f"Copyright © 2026 {AUTHOR}"
LICENSE_NOTICE = (
    "Ten program jest wolnym oprogramowaniem: możesz go rozpowszechniać i/lub modyfikować na warunkach "
    "Powszechnej Licencji Publicznej GNU (GNU GPL) w wersji 3, opublikowanej przez Free Software Foundation. "
    "Program jest rozpowszechniany bez jakiejkolwiek gwarancji – szczegóły w treści licencji."
)


def _resource(name: str) -> Path:
    """Pliki dołączone do exe (PyInstaller) albo leżące w katalogu głównym projektu."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / name


def _read(name: str) -> str:
    try:
        return _resource(name).read_text(encoding="utf-8")
    except OSError:
        return f"Brak pliku {name}. Pełny tekst jest dostępny na {REPOSITORY}."


def license_text() -> str:
    return _read("LICENSE")


def third_party_text() -> str:
    return _read("THIRD_PARTY_LICENSES.txt")


def show_text(parent, title: str, text: str) -> None:
    from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTextBrowser, QVBoxLayout

    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.resize(760, 640)
    layout = QVBoxLayout(dialog)
    browser = QTextBrowser()
    browser.setPlainText(text)
    layout.addWidget(browser, 1)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    buttons.button(QDialogButtonBox.StandardButton.Close).setText("Zamknij")
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    dialog.exec()


def show_about(parent) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPixmap
    from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

    from .icon import render

    dialog = QDialog(parent)
    dialog.setWindowTitle("O programie")
    layout = QHBoxLayout(dialog)
    logo = QLabel()
    logo.setPixmap(QPixmap.fromImage(render(128)))
    logo.setAlignment(Qt.AlignmentFlag.AlignTop)
    layout.addWidget(logo)
    column = QVBoxLayout()
    info = QLabel(
        f"<h2 style='margin:0'>Death Counter by MK</h2>"
        f"<p>Wersja {__version__}</p>"
        f"<p>{COPYRIGHT}</p>"
        f"<p>{LICENSE_NOTICE}</p>"
        f"<p>Kod źródłowy: <a href='{REPOSITORY}'>{REPOSITORY}</a></p>"
        "<p style='color:#9aa0a6'>Program korzysta z bibliotek Qt for Python (LGPL v3), OpenCV (Apache 2.0), "
        "NumPy (BSD), DXcam i comtypes (MIT) oraz Pythona (PSF).</p>"
    )
    info.setWordWrap(True)
    info.setOpenExternalLinks(True)
    info.setTextFormat(Qt.TextFormat.RichText)
    info.setMinimumWidth(440)
    column.addWidget(info)
    buttons = QHBoxLayout()
    for label, action in (
        ("Licencja (GNU GPL v3)…", lambda: show_text(dialog, "GNU General Public License v3", license_text())),
        ("Licencje bibliotek…", lambda: show_text(dialog, "Licencje bibliotek osób trzecich", third_party_text())),
        ("Zamknij", dialog.accept),
    ):
        button = QPushButton(label)
        button.clicked.connect(action)
        buttons.addWidget(button)
    column.addLayout(buttons)
    layout.addLayout(column)
    dialog.exec()
