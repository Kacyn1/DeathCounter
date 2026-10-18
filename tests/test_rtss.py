"""RtssOsd na sztucznej pamięci współdzielonej o układzie zgodnym z RTSS SDK."""

import ctypes
import os
import struct
from ctypes import wintypes

import pytest

from deathcounter.rtss import HEADER, OSD_EX_OFFSET, OWNER_OFFSET, SIGNATURE, RtssOsd, RtssState

ENTRY_SIZE = 4096 + 512 + 262144  # szOSD + szOSDOwner + szOSDEx + bufor (RTSS 7.x)
ENTRIES = 4
ARR_OFFSET = 256
SIZE = ARR_OFFSET + ENTRIES * ENTRY_SIZE

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.CreateFileMappingW.argtypes = [
    wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.LPCWSTR
]
kernel32.CreateFileMappingW.restype = wintypes.HANDLE
kernel32.MapViewOfFile.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.c_size_t]
kernel32.MapViewOfFile.restype = ctypes.c_void_p


@pytest.fixture
def fake_rtss():
    name = f"DeathCounterTestRTSS_{os.getpid()}"
    handle = kernel32.CreateFileMappingW(wintypes.HANDLE(-1), None, 0x04, 0, SIZE, name)
    base = kernel32.MapViewOfFile(handle, 0xF001F, 0, 0, 0)
    header = HEADER.pack(SIGNATURE, 0x0002000E, 0, 0, 0, ENTRY_SIZE, ARR_OFFSET, ENTRIES, 0)
    ctypes.memmove(base, header, len(header))
    yield name, base
    kernel32.UnmapViewOfFile(ctypes.c_void_p(base))
    kernel32.CloseHandle(handle)


def entry(base, index):
    return base + ARR_OFFSET + index * ENTRY_SIZE


def owner(base, index):
    return ctypes.string_at(entry(base, index) + OWNER_OFFSET, 256).split(b"\0")[0]


def text(base, index):
    return ctypes.string_at(entry(base, index) + OSD_EX_OFFSET, 4096).split(b"\0")[0]


def frame(base):
    return struct.unpack_from("<I", ctypes.string_at(base + 32, 4))[0]


def test_not_running():
    assert RtssOsd(memory_name="NieIstniejeTakaPamiec123").show("x") is RtssState.NOT_RUNNING


def test_claims_first_free_slot_skipping_entry_zero(fake_rtss):
    name, base = fake_rtss
    assert RtssOsd(memory_name=name).show("ŚMIERCI: 5") is RtssState.SHOWN
    assert owner(base, 0) == b""
    assert owner(base, 1) == b"DeathCounter"
    assert text(base, 1) == b"SMIERCI: 5"
    assert frame(base) == 1


def test_respects_other_owners_and_updates_own_slot(fake_rtss):
    name, base = fake_rtss
    ctypes.memmove(entry(base, 1) + OWNER_OFFSET, b"Afterburner\0", 12)
    osd = RtssOsd(memory_name=name)
    osd.show("ŚMIERCI: 1")
    osd.show("ŚMIERCI: 1")  # bez zmian – bez nowej klatki
    osd.show("ŚMIERCI: 2")
    assert owner(base, 1) == b"Afterburner"
    assert owner(base, 2) == b"DeathCounter"
    assert text(base, 2).endswith(b"2")
    assert frame(base) == 2


def test_clear_frees_slot(fake_rtss):
    name, base = fake_rtss
    osd = RtssOsd(memory_name=name)
    osd.show("ŚMIERCI: 3")
    osd.clear()
    assert owner(base, 1) == b""
    assert text(base, 1) == b""


def test_no_free_slot(fake_rtss):
    name, base = fake_rtss
    for i in range(1, ENTRIES):
        ctypes.memmove(entry(base, i) + OWNER_OFFSET, b"inny\0", 5)
    assert RtssOsd(memory_name=name).show("x") is RtssState.NO_SLOT


def test_rejects_wrong_signature(fake_rtss):
    name, base = fake_rtss
    ctypes.memmove(base, b"\0\0\0\0", 4)
    assert RtssOsd(memory_name=name).show("x") is RtssState.UNSUPPORTED
