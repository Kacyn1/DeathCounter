"""Logika wykrywania (śmierć, pasek bossa, zwycięstwo), niezależna od Qt i od źródła obrazu (łatwa do testowania)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable

import cv2
import numpy as np

from .config import BossSettings, DetectorSettings
from .template import DeathTemplate, to_gray

Clock = Callable[[], float]


class DeathDetector:
    """Maszyna stanów: uzbrojony → (N kolejnych trafień) → śmierć → rozbrojony → (brak napisu) → uzbrojony.

    - Potwierdzanie: napis musi być widoczny na `confirm_samples` kolejnych próbkach.
    - Brak duplikatów: po zliczeniu detektor jest rozbrojony, dopóki napis nie zniknie.
    - Ponowne uzbrojenie: napis nieobecny przez `rearm_seconds` i minął `cooldown_seconds`.
    """

    def __init__(self, settings: DetectorSettings, clock: Clock = time.monotonic, armed: bool = True) -> None:
        self._clock = clock
        self.apply_settings(settings)
        self.armed = armed
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


class BarEvent(Enum):
    APPEARED = "appeared"
    LOST = "lost"


class PresenceDetector:
    """Obecność elementu widocznego przez dłuższy czas (pasek zdrowia bossa).

    - Pojawienie: element widoczny na `bar_confirm_samples` kolejnych próbkach.
    - Zniknięcie: element nieobecny (poniżej progu minus histereza) przez `bar_lost_seconds`.
    """

    def __init__(self, settings: DetectorSettings, bosses: BossSettings, clock: Clock = time.monotonic) -> None:
        self._clock = clock
        self.apply_settings(settings, bosses)
        self.visible = False
        self._hits = 0
        self._absent_since: float | None = None

    def apply_settings(self, settings: DetectorSettings, bosses: BossSettings) -> None:
        self.threshold = settings.threshold
        self.hysteresis = settings.hysteresis
        self.confirm_samples = bosses.bar_confirm_samples
        self.lost_seconds = bosses.bar_lost_seconds

    def update(self, score: float) -> BarEvent | None:
        now = self._clock()
        if not self.visible:
            self._hits = self._hits + 1 if score >= self.threshold else 0
            if self._hits >= self.confirm_samples:
                self.visible = True
                self._hits = 0
                self._absent_since = None
                return BarEvent.APPEARED
            return None
        if score < self.threshold - self.hysteresis:
            if self._absent_since is None:
                self._absent_since = now
            if now - self._absent_since >= self.lost_seconds:
                self.visible = False
                self._absent_since = None
                return BarEvent.LOST
        else:
            self._absent_since = None
        return None

    def interrupt(self) -> None:
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
    bar_score: float | None = None
    bar_event: BarEvent | None = None
    bar_visible: bool = False
    victory_score: float | None = None
    victory: bool = False
    frames_lost: bool = False  # obraz właśnie przestał docierać (zgłaszane raz, przy przejściu z OK)


class DetectionSession:
    """Łączy kontrolę obrazu, dopasowanie wzorców i detektory dla kolejnych próbek.

    Detektory śmierci i zwycięstwa startują rozbrojone: napis widoczny w chwili startu
    (lub wznowienia) analizy mógł już zostać policzony, więc najpierw musi zniknąć.
    """

    def __init__(
        self,
        template: DeathTemplate,
        settings: DetectorSettings,
        clock: Clock = time.monotonic,
        bar_template: DeathTemplate | None = None,
        victory_template: DeathTemplate | None = None,
        bosses: BossSettings | None = None,
    ) -> None:
        self.template = template
        self.bar_template = bar_template
        self.victory_template = victory_template
        self.settings = settings
        self.bosses = bosses or BossSettings()
        self.monitor = FrameMonitor(settings.freeze_timeout_seconds, clock)
        self.detector = DeathDetector(settings, clock, armed=False)
        self.victory_detector = DeathDetector(settings, clock, armed=False)
        self.bar_detector = PresenceDetector(settings, self.bosses, clock)
        self._healthy = True

    def apply_settings(self, settings: DetectorSettings, bosses: BossSettings | None = None) -> None:
        self.settings = settings
        self.bosses = bosses or self.bosses
        self.monitor.timeout = settings.freeze_timeout_seconds
        self.detector.apply_settings(settings)
        self.victory_detector.apply_settings(settings)
        self.bar_detector.apply_settings(settings, self.bosses)

    def set_template(self, kind: str, template: DeathTemplate) -> None:
        if kind == "boss_bar":
            self.bar_template = template
            self.bar_detector.interrupt()
        elif kind == "victory":
            self.victory_template = template
            self.victory_detector.interrupt()
        else:
            self.template = template
            self.detector.interrupt()

    def interrupt(self) -> None:
        self.detector.interrupt()
        self.victory_detector.interrupt()
        self.bar_detector.interrupt()

    def capture_restarted(self) -> None:
        self.monitor.reset()
        self.interrupt()

    def capture_failed(self) -> bool:
        """Błąd przechwytywania. Zwraca True, gdy wcześniej obraz docierał (utratę zgłaszamy raz)."""
        self.interrupt()
        lost, self._healthy = self._healthy, False
        return lost

    def process(self, frame: np.ndarray | None) -> SampleResult:
        check = self.monitor.check(frame)
        healthy = check.health is CaptureHealth.OK
        frames_lost = self._healthy and not healthy
        self._healthy = healthy
        if check.resolution_changed or not healthy:
            self.interrupt()
        result = SampleResult(check, None, False, self.detector.armed, frames_lost=frames_lost)
        if healthy and frame is not None:
            margin = self.settings.search_margin
            result.score = self.template.match(frame, margin)
            result.death = self.detector.update(result.score)
            result.armed = self.detector.armed
            if self.bar_template is not None:
                result.bar_score = self.bar_template.match(frame, margin)
                result.bar_event = self.bar_detector.update(result.bar_score)
            if self.victory_template is not None:
                result.victory_score = self.victory_template.match(frame, margin)
                result.victory = self.victory_detector.update(result.victory_score)
        result.bar_visible = self.bar_detector.visible
        return result
