"""Podpis certyfikatu: kod weryfikacyjny HMAC-SHA256 z tajnym kluczem dołączanym tylko do exe.

Klucz leży w deathcounter/_signing_key.py, którego nie ma w repozytorium (kod programu jest publiczny,
więc klucz w repozytorium pozwalałby każdemu wystawiać „prawdziwe” certyfikaty). build.ps1 tworzy go
przy pierwszym budowaniu:
    python -m deathcounter.signing --init
Klucz można wydobyć z exe, więc podpis utrudnia podrabianie, ale go nie uniemożliwia.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import sys
from pathlib import Path

KEY_FILE = Path(__file__).resolve().parent / "_signing_key.py"


def load_key() -> bytes | None:
    try:
        from ._signing_key import KEY  # type: ignore[import-not-found]
    except ImportError:
        return None
    try:
        return bytes.fromhex(KEY)
    except (TypeError, ValueError):
        return None


def verification_code(payload: bytes, key: bytes) -> str:
    """16 znaków w grupach po 4, np. „K7QF-2MZD-8XBN-WC4R” (base32 bez łatwych do pomylenia znaków)."""
    digest = hmac.new(key, payload, hashlib.sha256).digest()
    text = base64.b32encode(digest).decode("ascii")[:16]
    return "-".join(text[i:i + 4] for i in range(0, 16, 4))


def matches(payload: bytes, code: str, key: bytes) -> bool:
    return hmac.compare_digest(verification_code(payload, key), code.strip().upper())


def init_key() -> bool:
    """Tworzy plik klucza, jeśli go nie ma. Zwraca True, gdy utworzono nowy klucz."""
    if KEY_FILE.exists():
        return False
    KEY_FILE.write_text(
        '"""Tajny klucz podpisu certyfikatów – NIE dodawać do repozytorium, zachować kopię."""\n'
        f'KEY = "{secrets.token_hex(32)}"\n',
        encoding="utf-8",
    )
    return True


if __name__ == "__main__":
    if "--init" in sys.argv:
        print("Utworzono nowy klucz podpisu." if init_key() else "Klucz podpisu już istnieje.")
