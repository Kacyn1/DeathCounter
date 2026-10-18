import cv2
import numpy as np
import pytest

from ds2counter.config import DetectorSettings

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
    """Przyciemniona rozgrywka z czerwonym napisem pośrodku (jak ekran śmierci DS2)."""
    frame = (gameplay_frame(seed, width, height) * 0.35).astype(np.uint8)
    sx, sy = width / WIDTH, height / HEIGHT
    cv2.putText(
        frame, "NIE ZYJESZ", (int(470 * sx), int(385 * sy)), cv2.FONT_HERSHEY_DUPLEX,
        2.2 * min(sx, sy), (40, 40, 190), max(1, int(4 * min(sx, sy))), cv2.LINE_AA,
    )
    return frame
