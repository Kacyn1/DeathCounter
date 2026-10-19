"""Wzorzec fragmentu ekranu (napis śmierci, ramka paska bossa, komunikat zwycięstwa) i dopasowanie do klatek."""

from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np

from .config import TemplateInfo
from .storage import StorageError, atomic_write_bytes

MIN_WIDTH = 24
MIN_HEIGHT = 8
MIN_CONTRAST = 6.0  # odchylenie standardowe jasności; płaski obszar nie nadaje się na wzorzec


class TemplateError(ValueError):
    """Wzorzec nie istnieje, jest uszkodzony albo się nie nadaje."""


def to_gray(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return image
    image = np.ascontiguousarray(image)
    if image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def read_image(path: Path) -> np.ndarray:
    """Wczytuje obraz jako BGR. cv2.imread nie obsługuje polskich znaków w ścieżce na Windows."""
    try:
        data = np.fromfile(str(path), dtype=np.uint8)
    except OSError as exc:
        raise TemplateError(f"Nie można odczytać pliku {Path(path).name}: {exc}") from exc
    image = cv2.imdecode(data, cv2.IMREAD_COLOR) if data.size else None
    if image is None:
        raise TemplateError(f"Plik {Path(path).name} nie jest obsługiwanym obrazem.")
    return image


def save_source_image(path: Path, frame: np.ndarray) -> None:
    """Pełny zrzut, z którego wycięto wzorzec – pokazywany potem w oknie kalibracji (JPEG, by nie zajmował dużo)."""
    if frame.ndim == 3 and frame.shape[2] == 4:
        frame = frame[:, :, :3]
    ok, encoded = cv2.imencode(".jpg", np.ascontiguousarray(frame), [cv2.IMWRITE_JPEG_QUALITY, 92])
    if not ok:
        raise StorageError("Nie można zakodować zrzutu kalibracji.")
    atomic_write_bytes(Path(path), encoded.tobytes())


def load_source_image(path: Path, reference_size: tuple[int, int]) -> np.ndarray | None:
    """Zapisany zrzut kalibracji albo None, gdy go brak lub nie pasuje do wzorca (inny rozmiar)."""
    if not Path(path).exists():
        return None
    try:
        image = read_image(path)
    except TemplateError:
        return None
    height, width = image.shape[:2]
    return image if (width, height) == tuple(reference_size) else None


class DeathTemplate:
    def __init__(self, image: np.ndarray, roi: tuple[int, int, int, int], reference_size: tuple[int, int]):
        image = to_gray(image)
        x, y, w, h = roi
        if image.shape != (h, w):
            raise TemplateError("Rozmiar obrazu wzorca nie zgadza się z zapisanym obszarem.")
        self.image = np.ascontiguousarray(image)
        self.roi = (int(x), int(y), int(w), int(h))
        self.reference_size = (int(reference_size[0]), int(reference_size[1]))
        # (klucz, wzorzec, obszar) w jednym atrybucie, bo wzorzec bywa używany z dwóch wątków.
        self._cache: tuple | None = None

    @classmethod
    def from_frame(cls, frame: np.ndarray, roi: tuple[int, int, int, int]) -> "DeathTemplate":
        height, width = frame.shape[:2]
        x, y, w, h = (int(v) for v in roi)
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(width, x + w), min(height, y + h)
        if x1 - x0 < MIN_WIDTH or y1 - y0 < MIN_HEIGHT:
            raise TemplateError(
                f"Zaznaczony obszar jest za mały (minimum {MIN_WIDTH}×{MIN_HEIGHT} px). "
                "Zaznacz cały napis lub cały fragment ramki paska."
            )
        crop = to_gray(frame[y0:y1, x0:x1]).copy()
        if float(crop.std()) < MIN_CONTRAST:
            raise TemplateError(
                "Zaznaczony obszar jest prawie jednolity. Zaznacz napis lub ramkę paska, a nie samo tło."
            )
        return cls(crop, (x0, y0, x1 - x0, y1 - y0), (width, height))

    @classmethod
    def load(cls, path: Path, info: TemplateInfo) -> "DeathTemplate":
        if not Path(path).exists():
            raise TemplateError(f"Brak pliku wzorca {Path(path).name}. Wykonaj kalibrację.")
        image = read_image(path)
        return cls(image, tuple(info.roi), tuple(info.reference_size))

    def save(self, path: Path) -> TemplateInfo:
        ok, encoded = cv2.imencode(".png", self.image)
        if not ok:
            raise StorageError("Nie można zakodować obrazu wzorca.")
        atomic_write_bytes(Path(path), encoded.tobytes())
        return TemplateInfo(list(self.roi), list(self.reference_size))

    def preview_frame(self) -> np.ndarray:
        """Zastępczy obraz kalibracji, gdy brak zapisanego zrzutu: sam wzorzec na czarnym tle w swoim miejscu."""
        width, height = self.reference_size
        canvas = np.zeros((height, width, 3), np.uint8)
        x, y, w, h = self.roi
        canvas[y:y + h, x:x + w] = cv2.cvtColor(self.image, cv2.COLOR_GRAY2BGR)
        return canvas

    def match(self, frame: np.ndarray, margin: float = 0.5) -> float:
        """Zwraca najlepsze dopasowanie (0–1) w okolicy miejsca, z którego pochodzi wzorzec.

        Gdy rozdzielczość klatki różni się od referencyjnej, wzorzec i obszar są skalowane.
        """
        return self.locate(frame, margin)[0]

    def locate(self, frame: np.ndarray, margin: float = 0.5) -> tuple[float, tuple[int, int, int, int] | None]:
        """Jak match(), a do tego miejsce najlepszego dopasowania (x, y, szerokość, wysokość) w klatce."""
        height, width = frame.shape[:2]
        template, (x0, y0, x1, y1) = self._prepared(width, height, margin)
        th, tw = template.shape
        if x1 - x0 < tw or y1 - y0 < th:
            return 0.0, None
        region = to_gray(frame[y0:y1, x0:x1])
        result = cv2.matchTemplate(region, template, cv2.TM_CCOEFF_NORMED)
        _, best, _, (bx, by) = cv2.minMaxLoc(result)
        if not math.isfinite(best):
            return 0.0, None
        return float(best), (x0 + bx, y0 + by, tw, th)

    def _prepared(self, width: int, height: int, margin: float):
        key = (width, height, margin)
        cache = self._cache
        if cache is None or cache[0] != key:
            ref_w, ref_h = self.reference_size
            sx, sy = width / ref_w, height / ref_h
            x, y, w, h = self.roi
            tw, th = max(1, round(w * sx)), max(1, round(h * sy))
            if (tw, th) == (w, h):
                template = self.image
            else:
                interpolation = cv2.INTER_AREA if tw < w else cv2.INTER_LINEAR
                template = cv2.resize(self.image, (tw, th), interpolation=interpolation)
            left, top = round(x * sx), round(y * sy)
            mx, my = round(tw * margin), round(th * margin)
            area = (
                max(0, left - mx),
                max(0, top - my),
                min(width, left + tw + mx),
                min(height, top + th + my),
            )
            cache = self._cache = (key, template, area)
        return cache[1], cache[2]
