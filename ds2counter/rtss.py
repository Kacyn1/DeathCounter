"""Tekst na nakładce RivaTuner Statistics Server (RTSS) – działa także w ekskluzywnym pełnym ekranie.

Program nie dotyka gry: wpisuje tekst do pamięci współdzielonej RTSS („RTSSSharedMemoryV2”),
a rysowaniem w grze zajmuje się sam RTSS. Układ pamięci według RTSS SDK (RTSSSharedMemory.h).
"""

from __future__ import annotations

import ctypes
import struct
from ctypes import wintypes
from enum import Enum

SHARED_MEMORY_NAME = "RTSSSharedMemoryV2"
SIGNATURE = 0x52545353  # 'RTSS'
MIN_VERSION = 0x00020000
OSD_EX_VERSION = 0x00020007   # od tej wersji jest pole szOSDEx (4096 znaków)

HEADER = struct.Struct("<9I")  # signature, version, appEntrySize, appArrOffset, appArrSize,
                               # osdEntrySize, osdArrOffset, osdArrSize, osdFrame
OSD_FRAME_OFFSET = 32
OWNER_OFFSET, OWNER_SIZE = 256, 256
OSD_OFFSET, OSD_SIZE = 0, 256
OSD_EX_OFFSET, OSD_EX_SIZE = 512, 4096

FILE_MAP_ALL_ACCESS = 0xF001F

_ASCII_FALLBACK = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.OpenFileMappingW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.OpenFileMappingW.restype = wintypes.HANDLE
kernel32.MapViewOfFile.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.c_size_t]
kernel32.MapViewOfFile.restype = ctypes.c_void_p
kernel32.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
kernel32.UnmapViewOfFile.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL


class _MemoryInfo(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", wintypes.DWORD),
        ("PartitionId", wintypes.WORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", wintypes.DWORD),
        ("Protect", wintypes.DWORD),
        ("Type", wintypes.DWORD),
    ]


kernel32.VirtualQuery.argtypes = [ctypes.c_void_p, ctypes.POINTER(_MemoryInfo), ctypes.c_size_t]
kernel32.VirtualQuery.restype = ctypes.c_size_t


class RtssState(Enum):
    SHOWN = "tekst przekazany do RTSS"
    NOT_RUNNING = "RTSS nie jest uruchomiony"
    UNSUPPORTED = "nieobsługiwana wersja RTSS"
    NO_SLOT = "brak wolnego miejsca na tekst w RTSS"


class RtssOsd:
    def __init__(self, owner: str = "DS2DeathCounter", memory_name: str = SHARED_MEMORY_NAME) -> None:
        self._owner = owner.encode("ascii")
        self._memory_name = memory_name

    def show(self, text: str) -> RtssState:
        # Czcionka rastrowa RTSS nie ma polskich liter („Ś” znikało), więc przekazujemy sam ASCII.
        data = text.translate(_ASCII_FALLBACK).encode("ascii", errors="replace")
        return self._with_memory(lambda base, size: self._write(base, size, data))

    def clear(self) -> RtssState:
        return self._with_memory(self._clear)

    def _with_memory(self, action) -> RtssState:
        handle = kernel32.OpenFileMappingW(FILE_MAP_ALL_ACCESS, False, self._memory_name)
        if not handle:
            return RtssState.NOT_RUNNING
        try:
            base = kernel32.MapViewOfFile(handle, FILE_MAP_ALL_ACCESS, 0, 0, 0)
            if not base:
                return RtssState.NOT_RUNNING
            try:
                info = _MemoryInfo()
                if not kernel32.VirtualQuery(base, ctypes.byref(info), ctypes.sizeof(info)):
                    return RtssState.UNSUPPORTED
                return action(base, info.RegionSize)
            finally:
                kernel32.UnmapViewOfFile(base)
        finally:
            kernel32.CloseHandle(handle)

    def _layout(self, base: int, size: int):
        if size < HEADER.size:
            return None
        signature, version, _, _, _, entry_size, arr_offset, arr_size, _ = HEADER.unpack(
            ctypes.string_at(base, HEADER.size)
        )
        if signature != SIGNATURE or version < MIN_VERSION:
            return None
        text_offset, text_size = (OSD_EX_OFFSET, OSD_EX_SIZE) if version >= OSD_EX_VERSION else (OSD_OFFSET, OSD_SIZE)
        if entry_size < max(text_offset + text_size, OWNER_OFFSET + OWNER_SIZE):
            return None
        if arr_offset + arr_size * entry_size > size:
            return None
        return entry_size, arr_offset, arr_size, text_offset, text_size

    def _entries(self, base: int, layout):
        entry_size, arr_offset, arr_size, _, _ = layout
        # Wpis 0 jest zarezerwowany dla samego RTSS.
        for index in range(1, arr_size):
            entry = base + arr_offset + index * entry_size
            owner = ctypes.string_at(entry + OWNER_OFFSET, OWNER_SIZE).split(b"\0", 1)[0]
            yield entry, owner

    def _write(self, base: int, size: int, data: bytes) -> RtssState:
        layout = self._layout(base, size)
        if layout is None:
            return RtssState.UNSUPPORTED
        _, _, _, text_offset, text_size = layout
        payload = data[: text_size - 1] + b"\0"

        entry = next((e for e, owner in self._entries(base, layout) if owner == self._owner), None)
        if entry is None:
            entry = next((e for e, owner in self._entries(base, layout) if owner == b""), None)
            if entry is None:
                return RtssState.NO_SLOT
            ctypes.memmove(entry + OWNER_OFFSET, self._owner + b"\0", len(self._owner) + 1)
        elif ctypes.string_at(entry + text_offset, len(payload)) == payload:
            return RtssState.SHOWN  # bez zmian – nie poganiamy RTSS

        ctypes.memmove(entry + text_offset, payload, len(payload))
        self._bump_frame(base)
        return RtssState.SHOWN

    def _clear(self, base: int, size: int) -> RtssState:
        layout = self._layout(base, size)
        if layout is None:
            return RtssState.UNSUPPORTED
        entry_size = layout[0]
        for entry, owner in self._entries(base, layout):
            if owner == self._owner:
                ctypes.memset(entry, 0, entry_size)
                self._bump_frame(base)
        return RtssState.SHOWN

    @staticmethod
    def _bump_frame(base: int) -> None:
        frame = ctypes.c_uint32.from_address(base + OSD_FRAME_OFFSET)
        frame.value = (frame.value + 1) & 0xFFFFFFFF
