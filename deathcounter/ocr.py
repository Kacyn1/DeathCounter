"""Odczyt nazwy bossa z ekranu: wbudowany OCR Windows (Windows.Media.Ocr), język polski.

Nazwa jest w grach Souls tuż nad paskiem zdrowia bossa, więc czytamy pas obrazu nad miejscem,
w którym wykrywanie znalazło wzorzec paska. Napis jest najjaśniejszym elementem pasa: zostawiamy
same jasne piksele (czarny tekst na białym tle), bo tekstura tła myli OCR. Kilka progów jasności
i kilka klatek głosuje nad wynikiem.
"""

from __future__ import annotations

import asyncio
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

import cv2
import numpy as np

from .template import to_gray

OCR_LANGUAGE = "pl"
BAND_ABOVE = 0.055     # górna krawędź pasa nad paskiem (ułamek wysokości ekranu)
BAND_GAP = 0.006       # odstęp od paska – jego górna ramka myli OCR
BAND_LEFT = 0.35       # nazwa stoi nad lewym końcem paska, a wzorzec bywa wycięty z jego środka
BAND_RIGHT = 0.25      # (ułamki szerokości ekranu po obu stronach znalezionego wzorca)
SCALES = (2, 3)
BRIGHTNESS_LEVELS = (0.6, 0.72, 0.84)  # progi względem najjaśniejszych pikseli pasa
MIN_PEAK = 90          # pas bez jasnych pikseli nie zawiera napisu
MIN_LETTERS = 3
MIN_AGREEING = 3       # odczyt pewny: tyle zgodnych prób…
AGREEMENT = 0.5        # …i co najmniej taka część wszystkich prób (warianty × klatki)


@dataclass(frozen=True)
class NameReading:
    name: str
    confident: bool  # większość prób dała ten sam tekst


class OcrUnavailable(RuntimeError):
    """Brak OCR Windows albo polskiego pakietu rozpoznawania tekstu."""


def name_band(frame_size: tuple[int, int], bar: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """Obszar (x0, y0, x1, y1) nad znalezionym paskiem bossa, w którym gra wypisuje nazwę."""
    width, height = frame_size
    x, y, w, _ = bar
    x0 = max(0, x - round(width * BAND_LEFT))
    x1 = min(width, x + w + round(width * BAND_RIGHT))
    y0 = max(0, y - round(height * BAND_ABOVE))
    y1 = max(y0, y - round(height * BAND_GAP))
    return x0, y0, x1, y1


def crop_band(frame: np.ndarray, bar: tuple[int, int, int, int]) -> np.ndarray | None:
    """Szary wycinek pasa z nazwą (kopia – klatka może zostać nadpisana) albo None, gdy jest za mały."""
    height, width = frame.shape[:2]
    x0, y0, x1, y1 = name_band((width, height), bar)
    if x1 - x0 < 16 or y1 - y0 < 8:
        return None
    return to_gray(frame[y0:y1, x0:x1]).copy()


def variants(band: np.ndarray):
    """Obrazy BGRA do OCR: powiększone, z samymi jasnymi pikselami jako czarnym tekstem na białym tle."""
    peak = float(np.percentile(band, 99.5))
    if peak < MIN_PEAK:
        return
    for scale in SCALES:
        big = cv2.resize(band, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        # Zachowaj cienkie kreski i wygładzanie liter: progowanie potrafi
        # zmienić np. „i” w „ł”. Ten wariant nie odcina odcieni tekstu.
        gray = cv2.copyMakeBorder(255 - big, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)
        yield cv2.cvtColor(gray, cv2.COLOR_GRAY2BGRA)
        for level in BRIGHTNESS_LEVELS:
            binary = np.where(big >= peak * level, 0, 255).astype(np.uint8)
            binary = cv2.copyMakeBorder(binary, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)
            yield cv2.cvtColor(binary, cv2.COLOR_GRAY2BGRA)


def clean_name(lines: list[str]) -> str | None:
    """Wybiera z linii OCR tę, która wygląda na nazwę: najwięcej liter, bez samych liczb (obrażenia)."""
    best, best_letters = None, 0
    for line in lines:
        text = " ".join(line.split()).strip(" .,:;-–—|_'\"«»„”")
        text = re.sub(r"\s+([,.])", r"\1", text)
        letters = sum(c.isalpha() for c in text)
        if letters >= MIN_LETTERS and letters >= len(text.replace(" ", "")) * 0.8 and letters > best_letters:
            best, best_letters = text, letters
    return best


def normalize(name: str) -> str:
    """Klucz porównywania nazw: małe litery, bez polskich znaków i interpunkcji (OCR często je gubi)."""
    text = unicodedata.normalize("NFKD", name.replace("ł", "l").replace("Ł", "L"))
    text = "".join(c for c in text if not unicodedata.combining(c)).casefold()
    return " ".join(re.sub(r"[^\w\s]", " ", text).split())


def vote(readings: list[str], attempts: int) -> NameReading | None:
    """Najczęstszy odczyt (porównywany po normalize); remis rozstrzyga dłuższy. `attempts` – liczba prób OCR
    (także tych bez wyniku): odczyt jest pewny, gdy zgadza się większość z nich."""
    if not readings:
        return None
    groups = Counter(normalize(r) for r in readings)
    key = max(groups, key=lambda k: (groups[k], len(k)))
    name = Counter(r for r in readings if normalize(r) == key).most_common(1)[0][0]
    return NameReading(name, groups[key] >= max(MIN_AGREEING, attempts * AGREEMENT))


class OcrReader:
    """Silnik OCR tworzony raz; metody są blokujące – wywoływać poza wątkiem interfejsu."""

    def __init__(self) -> None:
        try:
            from winrt.windows.globalization import Language
            from winrt.windows.graphics.imaging import BitmapPixelFormat, SoftwareBitmap
            from winrt.windows.media.ocr import OcrEngine
            from winrt.windows.storage.streams import DataWriter
        except ImportError as exc:
            raise OcrUnavailable(f"brak modułu OCR Windows ({exc})") from exc
        engine = OcrEngine.try_create_from_language(Language(OCR_LANGUAGE))
        if engine is None:
            raise OcrUnavailable(
                "Windows nie ma polskiego pakietu rozpoznawania tekstu (Ustawienia → Czas i język → "
                "Język i region → Polski → Opcje językowe → Optyczne rozpoznawanie znaków)"
            )
        self._engine = engine
        self._bitmap = SoftwareBitmap
        self._format = BitmapPixelFormat.BGRA8
        self._writer = DataWriter

    def read_lines(self, image: np.ndarray) -> list[str]:
        """Linie tekstu z obrazu BGRA (uint8)."""
        height, width = image.shape[:2]
        writer = self._writer()
        writer.write_bytes(np.ascontiguousarray(image).tobytes())
        bitmap = self._bitmap.create_copy_from_buffer(writer.detach_buffer(), self._format, width, height)
        result = asyncio.run(self._recognize(bitmap))
        return [line.text for line in result.lines]

    async def _recognize(self, bitmap):
        return await self._engine.recognize_async(bitmap)

    def read_name(self, bands: list[np.ndarray]) -> NameReading | None:
        """Nazwa bossa z wycinków crop_band() z kilku klatek albo None, gdy nic nie wygląda na nazwę."""
        readings, attempts = [], 0
        for band in bands:
            for image in variants(band):
                attempts += 1
                name = clean_name(self.read_lines(image))
                if name:
                    readings.append(name)
        return vote(readings, attempts)
