import cv2
import numpy as np
import pytest

from deathcounter.config import DetectorSettings

WIDTH, HEIGHT = 1280, 720
TEXT_ROI = (440, 320, 400, 80)  # obszar napisu na syntetycznym ekranie śmierci


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def settings():
    return DetectorSettings()


def gameplay_frame(seed: int, width: int = WIDTH, height: int = HEIGHT) -> np.ndarray:
    """Zmienny, „zaszumiony” obraz rozgrywki."""
    rng = np.random.default_rng(seed)
    small = rng.integers(20, 200, size=(height // 16, width // 16, 3), dtype=np.uint8)
    return cv2.resize(small, (width, height), interpolation=cv2.INTER_LINEAR)


def death_frame(seed: int, width: int = WIDTH, height: int = HEIGHT) -> np.ndarray:
    """Przyciemniona rozgrywka z czerwonym napisem pośrodku (jak ekran śmierci w grach z serii Souls)."""
    frame = (gameplay_frame(seed, width, height) * 0.35).astype(np.uint8)
    sx, sy = width / WIDTH, height / HEIGHT
    cv2.putText(
        frame, "NIE ZYJESZ", (int(470 * sx), int(385 * sy)), cv2.FONT_HERSHEY_DUPLEX,
        2.2 * min(sx, sy), (40, 40, 190), max(1, int(4 * min(sx, sy))), cv2.LINE_AA,
    )
    return frame


BAR_ROI = (300, 640, 180, 40)        # lewy koniec paska bossa (ramka + początek wypełnienia)
VICTORY_ROI = (390, 300, 500, 90)    # komunikat zwycięstwa


def boss_frame(seed: int, health: float = 1.0) -> np.ndarray:
    """Rozgrywka z paskiem zdrowia bossa u dołu ekranu; `health` – ułamek wypełnienia."""
    frame = gameplay_frame(seed)
    cv2.rectangle(frame, (300, 650), (980, 670), (20, 20, 20), -1)
    cv2.rectangle(frame, (300, 650), (980, 670), (150, 190, 210), 3)
    cv2.circle(frame, (300, 660), 14, (150, 190, 210), 3)
    fill = 304 + int(672 * health)
    if fill > 304:
        cv2.rectangle(frame, (304, 654), (fill, 666), (30, 30, 170), -1)
    return frame


def victory_frame(seed: int) -> np.ndarray:
    """Komunikat zwycięstwa na tle rozgrywki."""
    frame = gameplay_frame(seed)
    cv2.rectangle(frame, (0, 300), (WIDTH, 390), (10, 10, 10), -1)
    cv2.putText(frame, "VICTORY", (450, 370), cv2.FONT_HERSHEY_DUPLEX, 2.4, (60, 170, 210), 4, cv2.LINE_AA)
    return frame


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    """Jedna aplikacja Qt na wszystkie testy. QApplication (z widżetami) musi powstać przed testami,
    które same tworzą QGuiApplication – inaczej okna, np. ResultsWindow, nie dałoby się utworzyć."""
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])
