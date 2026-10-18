"""Scenariusze od klatki do licznika (bez Qt i bez przechwytywania ekranu)."""

import numpy as np
import pytest

from deathcounter.detector import CaptureHealth, DetectionSession
from deathcounter.template import DeathTemplate

from .conftest import TEXT_ROI, death_frame, gameplay_frame

STEP = 0.1


@pytest.fixture
def session(clock, settings):
    template = DeathTemplate.from_frame(death_frame(1), TEXT_ROI)
    return DetectionSession(template, settings, clock)


def run(session, clock, frames):
    deaths, results = 0, []
    for frame in frames:
        clock.advance(STEP)
        result = session.process(frame)
        deaths += result.death
        results.append(result)
    return deaths, results


def gameplay(seconds, start=1000):
    return [gameplay_frame(start + i) for i in range(int(seconds / STEP))]


def death_screen(seconds, start=5000):
    return [death_frame(start + i) for i in range(int(seconds / STEP))]


def black(seconds):
    return [np.full((720, 1280, 3), i % 3, np.uint8) for i in range(int(seconds / STEP))]


def test_control_test_one_death_is_exactly_plus_one(session, clock):
    deaths, _ = run(session, clock, gameplay(5) + death_screen(4) + black(2) + gameplay(10))
    assert deaths == 1


def test_several_deaths(session, clock):
    one_life = gameplay(15)
    frames = []
    for i in range(3):
        frames += one_life + death_screen(4, start=6000 + i * 100) + black(2)
    deaths, _ = run(session, clock, frames + gameplay(5))
    assert deaths == 3


def test_missing_frames_are_reported_and_not_counted(session, clock):
    deaths, results = run(session, clock, gameplay(2) + [None] * 80 + gameplay(2))
    assert deaths == 0
    assert any(r.check.health is CaptureHealth.NO_FRAMES for r in results)
    assert results[-1].check.health is CaptureHealth.OK


def test_frozen_image_is_reported(session, clock):
    frozen = gameplay_frame(7)
    deaths, results = run(session, clock, [frozen] * 80)
    assert deaths == 0
    assert results[-1].check.health is CaptureHealth.FROZEN


def test_frozen_death_screen_counts_only_once(session, clock):
    frozen = death_frame(8)
    deaths, _ = run(session, clock, [frozen] * 200 + gameplay(10))
    assert deaths == 1


def test_resolution_change_is_detected_and_still_works(session, clock):
    big_gameplay = [gameplay_frame(3000 + i, 1920, 1080) for i in range(50)]
    big_death = [death_frame(4000 + i, 1920, 1080) for i in range(40)]
    deaths, results = run(session, clock, gameplay(3) + big_gameplay + big_death + big_gameplay)
    assert any(r.check.resolution_changed for r in results)
    assert deaths == 1
