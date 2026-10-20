"""Skróty globalne: zapis tekstowy (np. „Ctrl+Alt+F9”) ↔ modyfikatory i kod klawisza Windows (VK)."""

from __future__ import annotations

from dataclasses import dataclass

from .i18n import tr

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008

# Kolejność jak w zapisie Qt (QKeySequence.PortableText), np. „Ctrl+Alt+Shift+F9”.
MODIFIERS = {"Ctrl": MOD_CONTROL, "Alt": MOD_ALT, "Shift": MOD_SHIFT, "Meta": MOD_WIN}

KEYS: dict[str, int] = {
    **{chr(c): c for c in range(ord("A"), ord("Z") + 1)},
    **{str(d): 0x30 + d for d in range(10)},
    **{f"F{n}": 0x6F + n for n in range(1, 25)},
    "Space": 0x20, "PgUp": 0x21, "PgDown": 0x22, "End": 0x23, "Home": 0x24,
    "Left": 0x25, "Up": 0x26, "Right": 0x27, "Down": 0x28,
    "Ins": 0x2D, "Del": 0x2E, "Pause": 0x13, "ScrollLock": 0x91,
    "Backspace": 0x08, "Return": 0x0D, "Enter": 0x0D, "Tab": 0x09,
    "-": 0xBD, "=": 0xBB, "[": 0xDB, "]": 0xDD, ";": 0xBA, "'": 0xDE, ",": 0xBC, ".": 0xBE, "/": 0xBF,
    "\\": 0xDC, "`": 0xC0,
}
NUMPAD: dict[str, int] = {
    **{str(d): 0x60 + d for d in range(10)},
    "*": 0x6A, "+": 0x6B, "-": 0x6D, ".": 0x6E, "/": 0x6F,
}
# Klawisze, które bez Ctrl/Alt/Win zablokowałyby pisanie w każdym programie.
_TYPING_KEYS = {k for k in KEYS if len(k) == 1} | {"Space", "Backspace", "Return", "Enter", "Tab"}


@dataclass(frozen=True)
class Hotkey:
    modifiers: int
    vk: int
    text: str


def parse(text: str) -> Hotkey:
    """„Ctrl+Alt+F9” → Hotkey. ValueError z opisem, gdy skrótu nie da się użyć jako globalnego."""
    text = text.strip()
    if not text:
        raise ValueError(tr("Skrót jest pusty."))
    # „+” jako klawisz („Ctrl++”) nie jest obsługiwany – ostatni element to zawsze klawisz.
    *mods, key = text.split("+")
    modifiers = 0
    for mod in mods:
        if mod not in MODIFIERS and mod != "Num":
            raise ValueError(tr("Nieznany modyfikator „{mod}” w skrócie {text}.", mod=mod, text=text))
        modifiers |= MODIFIERS.get(mod, 0)
    keypad = "Num" in mods  # Qt oznacza klawisze bloku numerycznego „Num+”
    if keypad and key in NUMPAD:
        vk = NUMPAD[key]
    elif key in KEYS and not keypad:
        vk = KEYS[key]
    else:
        raise ValueError(tr("Klawisz „{value}” nie może być skrótem globalnym.", value=key or '+'))
    if not keypad and key in _TYPING_KEYS and not modifiers & (MOD_CONTROL | MOD_ALT | MOD_WIN):
        raise ValueError(tr("Skrót {text} blokowałby pisanie – dodaj Ctrl, Alt albo Win.", text=text))
    ordered = "+".join([m for m in (*MODIFIERS, "Num") if m in mods] + [key])
    return Hotkey(modifiers, vk, ordered)


def display(text: str) -> str:
    """Zapis dla użytkownika: Qt nazywa klawisz Windows „Meta”."""
    return "+".join("Win" if part == "Meta" else part for part in text.split("+")) if text else "brak"
