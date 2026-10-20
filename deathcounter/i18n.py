"""Język interfejsu. Teksty w kodzie są po polsku; tr() zwraca je w wybranym języku.

Kluczem tłumaczenia jest polski tekst, a zmienne części wstawia się przez nazwane pola:
tr("Śmierci: {count}", count=5). Tekst bez tłumaczenia zostaje po polsku. Język ustawia się raz
przy starcie (z config.json) – zmiana wymaga ponownego uruchomienia programu.
"""

from __future__ import annotations

LANGUAGES = {"pl": "PL", "en": "ENG"}  # kod → nazwa na liście „Język”
DEFAULT_LANGUAGE = "pl"

_language = DEFAULT_LANGUAGE


def set_language(code: str) -> None:
    global _language
    _language = code if code in LANGUAGES else DEFAULT_LANGUAGE


def language() -> str:
    return _language


def tr(text: str, /, **fields) -> str:
    """Tekst w bieżącym języku; `fields` wypełniają pola {nazwa} w tekście."""
    if _language == "en":
        from .lang_en import EN
        text = EN.get(text, text)
    return text.format(**fields) if fields else text


def N_(text: str) -> str:
    """Oznacza tekst do tłumaczenia w stałej na poziomie modułu (tłumaczy go tr() przy wyświetleniu)."""
    return text
