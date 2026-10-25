"""Biblioteki Windows API dla ctypes; poza Windowsem (tryb deweloperski na macOS, testy) – atrapy.

Atrapa przyjmuje ustawianie argtypes/restype, a każda jej funkcja nic nie robi i zwraca 0, czyli to,
co Windows API zwraca przy błędzie albo braku wyniku. Dzięki temu moduły z WinAPI dają się zaimportować,
a funkcje programu zależne od Windows (nakładka nad grą, skróty, RTSS) po prostu nie działają.
"""

from __future__ import annotations

import ctypes
import sys

IS_WINDOWS = sys.platform == "win32"


class _MissingFunction:
    argtypes = None
    restype = None

    def __call__(self, *args):
        return 0


class _MissingDll:
    def __getattr__(self, name: str) -> _MissingFunction:
        function = _MissingFunction()
        setattr(self, name, function)  # ta sama atrapa przy kolejnym odwołaniu (argtypes ustawione raz)
        return function


def load(name: str, **kwargs):
    """ctypes.WinDLL(name) na Windowsie, w innym przypadku atrapa biblioteki."""
    return ctypes.WinDLL(name, **kwargs) if IS_WINDOWS else _MissingDll()
