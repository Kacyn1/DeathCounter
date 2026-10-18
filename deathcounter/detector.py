"""Logika wykrywania śmierci, niezależna od Qt i od źródła obrazu (łatwa do testowania)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable

import cv2
import numpy as np

from .config import DetectorSettings
from .template import DeathTemplate, to_gray

Clock = Callable[[], float]


class DeathDetector:
    """Maszyna stanów: uzbrojony → (N kolejnych trafień) → śmierć → rozbrojony → (brak napisu) → uzbrojony.

    - Potwierdzanie: napis musi być widoczny na `confirm_samples` kolejnych próbkach.
    - Brak duplikatów: po zliczeniu detektor jest rozbrojony, dopóki napis nie zniknie.
    - Ponowne uzbrojenie: napis nieobecny przez `rearm_seconds` i minął `cooldown_seconds`.
    """

    def __init__(self, settings: DetectorSettings, clock: Clock = time.monotonic) -> None:
        self._clock = clock
        self.apply_settings(settings)
        self.armed = True
        self._hits = 0
        self._absent_since: float | None = None
        self._last_death: float | None = None

    def apply_settings(self, settings: DetectorSettings) -> None:
        self.threshold = settings.threshold
        self.hysteresis = settings.hysteresis
        self.confirm_samples = settings.confirm_samples
        self.rearm_seconds = settings.rearm_seconds
        self.cooldown_seconds = settings.cooldown_seconds

    def update(self, score: float) -> bool:
        """Przyjmuje wynik dopasowania jednej próbki; zwraca True, gdy należy doliczyć śmierć."""
        now = self._clock()
        if self.armed:
            self._hits = self._hits + 1 if score >= self.threshold else 0
            if self._hits >= self.confirm_samples:
                self.armed = False
                self._hits = 0
                self._absent_since = None
                self._last_death = now
                return True
            return False

        if score < self.threshold - self.hysteresis:
            if self._absent_since is None:
                self._absent_since = now
            cooled_down = self._last_death is None or now - self._last_death >= self.cooldown_seconds
            if now - self._absent_since >= self.rearm_seconds and cooled_down:
                self.armed = True
                self._absent_since = None
        else:
            self._absent_since = None
        return False

    def interrupt(self) -> None:
        """Przerwa w obrazie: zaczynamy liczyć potwierdzenia i nieobecność napisu od nowa."""
        self._hits = 0
        self._absent_since = None


class CaptureHealth(Enum):
    OK = "ok"
    NO_FRAMES = "no_frames"   # przechwytywanie nie dostarcza nowych klatek
    FROZEN = "frozen"         # klatki przychodzą, ale obraz się nie zmienia


@dataclass
class FrameCheck:
    health: CaptureHealth
    resolution: tuple[int, int] | None
    resolution_changed: bool
    stalled_for: float


class FrameMonitor:
    """Wykrywa brak klatek, zamrożony obraz i zmianę rozdzielczości."""

    SIGNATURE_SIZE = (32, 18)
    FROZEN_TOLERANCE = 2

    def __init__(self, timeout: float, clock: Clock = time.monotonic) -> None:
        self.timeout = timeout
        self._clock = clock
        self.reset()

    def reset(self) -> None:
        now = self._clock()
        self._last_frame = now
        self._last_change = now
        self._signature: np.ndarray | None = None
        self._resolution: tuple[int, int] | None = None

    def check(self, frame: np.ndarray | None) -> FrameCheck:
        now = self._clock()
        changed = False
        if frame is not None:
            height, width = frame.shape[:2]
            resolution = (width, height)
            if self._resolution is not None and resolution != self._resolution:
                changed = True
                self._signature = None
            self._resolution = resolution
            self._last_frame = now
            small = cv2.resize(np.ascontiguousarray(frame), self.SIGNATURE_SIZE, interpolation=cv2.INTER_AREA)
            signature = to_gray(small).astype(np.int16)
            if self._signature is None or int(np.abs(signature - self._signature).max()) > self.FROZEN_TOLERANCE:
                self._last_change = now
            self._signature = signature

        without_frames = now - self._last_frame
        without_change = now - self._last_change
        if without_frames > self.timeout:
            return FrameCheck(CaptureHealth.NO_FRAMES, self._resolution, changed, without_frames)
        if without_change > self.timeout:
            return FrameCheck(CaptureHealth.FROZEN, self._resolution, changed, without_change)
        return FrameCheck(CaptureHealth.OK, self._resolution, changed, 0.0)


@dataclass
class SampleResult:
    check: FrameCheck
    score: float | None
    death: bool
    armed: bool


class DetectionSession:
    """Łączy kontrolę obrazu, dopasowanie wzorca i detektor dla kolejnych próbek."""

    def __init__(self, template: DeathTemplate, settings: DetectorSettings, clock: Clock = time.monotonic) -> None:
        self.template = template
        self.settings = settings
        self.monitor = FrameMonitor(settings.freeze_timeout_seconds, clock)
        self.detector = DeathDetector(settings, clock)

    def apply_settings(self, settings: DetectorSettings) -> None:
        self.settings = settings
        self.monitor.timeout = settings.freeze_timeout_seconds
        self.detector.apply_settings(settings)

    def capture_restarted(self) -> None:
        self.monitor.reset()
        self.detector.interrupt()

    def process(self, frame: np.ndarray | None) -> SampleResult:
        check = self.monitor.check(frame)
        if check.resolution_changed or check.health is not CaptureHealth.OK:
            self.detector.interrupt()
        score = None
        death = False
        if check.health is CaptureHealth.OK and frame is not None:
            score = self.template.match(frame, self.settings.search_margin)
            death = self.detector.update(score)
        return SampleResult(check, score, death, self.detector.armed)
