"""Okno „Skróty klawiszowe”: zmiana skrótów globalnych."""

from __future__ import annotations

from dataclasses import fields

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QKeySequenceEdit,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from . import hotkeys
from .config import HotkeySettings
from .i18n import tr, N_

LABELS = {
    "snapshot": N_("Zrzut do kalibracji:"),
    "plus": N_("Dodaj +1:"),
    "minus": N_("Cofnij −1:"),
    "overlay": N_("Nakładka włącz/wyłącz:"),
}


class HotkeyDialog(QDialog):
    def __init__(self, parent, settings: HotkeySettings):
        super().__init__(parent)
        self.setWindowTitle(tr("Skróty klawiszowe"))
        self.result_settings: HotkeySettings | None = None
        layout = QVBoxLayout(self)
        info = QLabel(
            tr("Skróty działają globalnie – także w grze na pełnym ekranie. Kliknij pole i naciśnij nową "
            "kombinację klawiszy; przycisk ✕ w polu wyłącza skrót.")
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QFormLayout()
        self.edits: dict[str, QKeySequenceEdit] = {}
        for f in fields(HotkeySettings):
            edit = QKeySequenceEdit()
            edit.setMaximumSequenceLength(1)
            edit.setClearButtonEnabled(True)
            edit.setKeySequence(_sequence(getattr(settings, f.name)))
            edit.keySequenceChanged.connect(self._validate)
            self.edits[f.name] = edit
            form.addRow(tr(LABELS[f.name]), edit)
        layout.addLayout(form)

        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color:#e06c5a;")
        layout.addWidget(self.error_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        defaults = QPushButton(tr("Przywróć domyślne"))
        defaults.clicked.connect(self._restore_defaults)
        buttons.addButton(defaults, QDialogButtonBox.ButtonRole.ResetRole)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        self.ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        layout.addWidget(buttons)
        self.resize(420, self.sizeHint().height())

    def _restore_defaults(self) -> None:
        defaults = HotkeySettings()
        for name, edit in self.edits.items():
            edit.setKeySequence(_sequence(getattr(defaults, name)))

    def _collect(self) -> tuple[HotkeySettings, list[str]]:
        settings, errors, used = HotkeySettings(), [], {}
        for name, edit in self.edits.items():
            text = edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
            if text:
                try:
                    hotkey = hotkeys.parse(text)
                except ValueError as exc:
                    errors.append(f"{tr(LABELS[name])[:-1]}: {exc}")
                    text = ""
                else:
                    text = hotkey.text
                    key = (hotkey.modifiers, hotkey.vk)
                    if key in used:
                        errors.append(tr("{display} jest już przypisany do „{item}”.", display=hotkeys.display(text), item=tr(LABELS[used[key]])[:-1]))
                    used.setdefault(key, name)
            setattr(settings, name, text)
        return settings, errors

    def _validate(self) -> None:
        _, errors = self._collect()
        self.error_label.setText("\n".join(errors))
        self.ok_button.setEnabled(not errors)

    def _accept(self) -> None:
        settings, errors = self._collect()
        if errors:
            return
        self.result_settings = settings
        self.accept()


def _sequence(text: str) -> QKeySequence:
    return QKeySequence.fromString(text, QKeySequence.SequenceFormat.PortableText)
