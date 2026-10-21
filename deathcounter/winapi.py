"""Cienkie opakowania funkcji Windows API (ctypes): nakładka, skróty klawiszowe, Kosz i lista procesów."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from pathlib import Path

from .i18n import tr

user32 = ctypes.WinDLL("user32", use_last_error=True)

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000

HWND_TOPMOST = wintypes.HWND(-1)
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010

WDA_NONE = 0x00
WDA_EXCLUDEFROMCAPTURE = 0x11

WM_HOTKEY = 0x0312
MOD_NOREPEAT = 0x4000  # pozostałe modyfikatory: deathcounter.hotkeys

user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowPos.argtypes = [
    wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT
]
user32.SetWindowPos.restype = wintypes.BOOL
user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
user32.SetWindowDisplayAffinity.restype = wintypes.BOOL
user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
user32.RegisterHotKey.restype = wintypes.BOOL
user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
user32.UnregisterHotKey.restype = wintypes.BOOL


def make_click_through(hwnd: int) -> None:
    """Okno nie przechwytuje kliknięć, nie zabiera fokusu i nie pojawia się na pasku zadań."""
    style = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
    style |= WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
    user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, style)


def set_topmost(hwnd: int) -> None:
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)


def exclude_from_capture(hwnd: int, exclude: bool) -> bool:
    """Ukrywa okno przed przechwytywaniem ekranu (Windows 10 2004+). Zwraca False przy błędzie."""
    return bool(user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE if exclude else WDA_NONE))


def register_hotkey(hwnd: int, hotkey_id: int, modifiers: int, vk: int) -> bool:
    return bool(user32.RegisterHotKey(hwnd, hotkey_id, modifiers | MOD_NOREPEAT, vk))


def unregister_hotkey(hwnd: int, hotkey_id: int) -> None:
    user32.UnregisterHotKey(hwnd, hotkey_id)


def message_from_native(message) -> wintypes.MSG:
    return wintypes.MSG.from_address(int(message))


class _SHFILEOPSTRUCTW(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("wFunc", wintypes.UINT),
        ("pFrom", wintypes.LPCWSTR),
        ("pTo", wintypes.LPCWSTR),
        ("fFlags", wintypes.WORD),
        ("fAnyOperationsAborted", wintypes.BOOL),
        ("hNameMappings", wintypes.LPVOID),
        ("lpszProgressTitle", wintypes.LPCWSTR),
    ]


FO_DELETE = 0x0003
FOF_SILENT, FOF_NOCONFIRMATION, FOF_ALLOWUNDO, FOF_NOERRORUI = 0x0004, 0x0010, 0x0040, 0x0400

shell32 = ctypes.WinDLL("shell32", use_last_error=True)
shell32.SHFileOperationW.argtypes = [ctypes.POINTER(_SHFILEOPSTRUCTW)]
shell32.SHFileOperationW.restype = ctypes.c_int


def send_to_recycle_bin(paths) -> None:
    """Przenosi pliki lub foldery do Kosza (można je stamtąd przywrócić). OSError przy niepowodzeniu."""
    existing = [str(Path(p).resolve()) for p in paths if Path(p).exists()]
    if not existing:
        return
    op = _SHFILEOPSTRUCTW()
    op.wFunc = FO_DELETE
    op.pFrom = "\0".join(existing) + "\0\0"  # lista ścieżek zakończona podwójnym zerem
    op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI
    code = shell32.SHFileOperationW(ctypes.byref(op))
    if code != 0 or op.fAnyOperationsAborted:
        raise OSError(tr("Nie udało się przenieść do Kosza (kod {code:#x}). Sprawdź, czy pliki nie są otwarte.", code=code))


WM_SETICON = 0x0080
ICON_BIG = 1
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.SendMessageW.restype = wintypes.LPARAM


def set_big_icon(hwnd: int, hicon: int) -> None:
    """Duża ikona okna – z niej Windows rysuje przycisk na pasku zadań."""
    user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon)


PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
MAX_PROCESSES = 8192
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.K32EnumProcesses.argtypes = [ctypes.POINTER(wintypes.DWORD), wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
kernel32.K32EnumProcesses.restype = wintypes.BOOL
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                ctypes.POINTER(wintypes.DWORD)]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL


def process_paths() -> dict[int, str]:
    """PID → pełna ścieżka exe działających procesów. Tylko odczyt – procesy (w tym gra) nie są w żaden sposób
    zmieniane; procesy, do których Windows nie daje dostępu, są pomijane."""
    pids = (wintypes.DWORD * MAX_PROCESSES)()
    needed = wintypes.DWORD()
    if not kernel32.K32EnumProcesses(pids, ctypes.sizeof(pids), ctypes.byref(needed)):
        return {}
    paths = {}
    buffer = ctypes.create_unicode_buffer(1024)
    for pid in pids[:needed.value // ctypes.sizeof(wintypes.DWORD)]:
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            continue
        try:
            size = wintypes.DWORD(len(buffer))
            if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                paths[pid] = buffer.value
        finally:
            kernel32.CloseHandle(handle)
    return paths



user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD


def foreground_pid() -> int | None:
    """PID procesu, do którego należy aktywne okno (None – brak, np. zablokowany ekran)."""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value or None
