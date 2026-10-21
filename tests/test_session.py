"""Scenariusze od klatki do licznika (bez Qt i bez przechwytywania ekranu)."""

import cv2
import numpy as np
import pytest

from deathcounter.config import BossSettings
from deathcounter.detector import BarEvent, CaptureHealth, DetectionSession
from deathcounter.template import DeathTemplate

from .conftest import BAR_ROI, TEXT_ROI, VICTORY_ROI, boss_frame, death_frame, gameplay_frame, victory_frame

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
    deaths, _ = run(session, clock, gameplay(4) + [frozen] * 200 + gameplay(10))
    assert deaths == 1


def test_death_screen_visible_at_start_is_not_counted_again(session, clock):
    # wznowienie analizy (Start po Stop) na ekranie śmierci, która mogła już zostać policzona
    deaths, _ = run(session, clock, death_screen(4) + gameplay(10) + death_screen(4) + gameplay(5))
    assert deaths == 1


def test_resolution_change_is_detected_and_still_works(session, clock):
    big_gameplay = [gameplay_frame(3000 + i, 1920, 1080) for i in range(50)]
    big_death = [death_frame(4000 + i, 1920, 1080) for i in range(40)]
    deaths, results = run(session, clock, gameplay(3) + big_gameplay + big_death + big_gameplay)
    assert any(r.check.resolution_changed for r in results)
    assert deaths == 1


@pytest.fixture
def boss_session(clock, settings):
    return DetectionSession(
        DeathTemplate.from_frame(death_frame(1), TEXT_ROI),
        settings,
        clock,
        bar_template=DeathTemplate.from_frame(boss_frame(2), BAR_ROI),
        victory_template=DeathTemplate.from_frame(victory_frame(3), VICTORY_ROI),
    )


def fight(seconds, start=7000, health=1.0):
    return [boss_frame(start + i, health) for i in range(int(seconds / STEP))]


def victory_screen(seconds, start=8000):
    return [victory_frame(start + i) for i in range(int(seconds / STEP))]


def events(results):
    return [r.bar_event for r in results if r.bar_event]


def test_boss_bar_appears_after_confirmation_and_disappears_after_delay(boss_session, clock):
    _, results = run(boss_session, clock, gameplay(2) + fight(20) + gameplay(10))
    assert events(results) == [BarEvent.APPEARED, BarEvent.LOST]
    appeared = next(i for i, r in enumerate(results) if r.bar_event is BarEvent.APPEARED)
    lost = next(i for i, r in enumerate(results) if r.bar_event is BarEvent.LOST)
    assert appeared == 20 + 9            # 10 kolejnych próbek z paskiem
    assert 200 + 20 + 25 <= lost <= 200 + 20 + 35  # ok. 3 s bez paska


def test_boss_bar_still_detected_when_boss_loses_health(boss_session, clock):
    frames = fight(5) + fight(5, health=0.5) + fight(5, health=0.1)
    _, results = run(boss_session, clock, gameplay(2) + frames)
    assert events(results) == [BarEvent.APPEARED]
    assert results[-1].bar_visible


def test_short_glimpse_of_bar_does_not_start_fight(boss_session, clock):
    _, results = run(boss_session, clock, gameplay(2) + fight(0.5) + gameplay(5))
    assert events(results) == []


def test_victory_detected_once(boss_session, clock):
    _, results = run(boss_session, clock, gameplay(2) + fight(10) + victory_screen(4) + gameplay(10))
    assert sum(r.victory for r in results) == 1
    assert sum(r.death for r in results) == 0


def test_death_in_fight_is_not_victory(boss_session, clock):
    _, results = run(boss_session, clock, gameplay(4) + fight(10) + death_screen(4) + gameplay(5))
    assert sum(r.death for r in results) == 1
    assert sum(r.victory for r in results) == 0


def test_lost_frames_reported_once(boss_session, clock):
    _, results = run(boss_session, clock, gameplay(2) + fight(5) + [None] * 80 + fight(5))
    assert sum(r.frames_lost for r in results) == 1


def test_boss_detection_survives_resolution_change(boss_session, clock):
    big = [cv2.resize(f, (1920, 1080)) for f in fight(5, start=9000)]
    _, results = run(boss_session, clock, gameplay(2) + big)
    assert events(results) == [BarEvent.APPEARED]


def test_bar_uses_own_threshold(boss_session, clock, settings):
    bosses = BossSettings(bar_threshold=0.99)
    boss_session.apply_settings(settings, bosses)
    _, results = run(boss_session, clock, gameplay(2) + fight(20))
    assert events(results) == []                      # pasek nie przekracza progu 0.99…
    assert all(r.bar_score > settings.threshold for r in results[-10:])
    assert boss_session.detector.threshold == settings.threshold  # …a próg śmierci się nie zmienia


def test_menu_and_health_bar_presence(clock, settings):
    from deathcounter.detector import MENU_CONFIRM_SECONDS, SCREEN_EVERY_SAMPLES

    death = DeathTemplate.from_frame(death_frame(1), TEXT_ROI)
    menu = DeathTemplate.from_frame(victory_frame(2), VICTORY_ROI)   # „menu” – duży napis na środku
    hud = DeathTemplate.from_frame(boss_frame(3), BAR_ROI)          # „pasek zdrowia”
    session = DetectionSession(death, settings, clock, menu_template=menu, hud_template=hud)
    result = None
    for i in range(int((MENU_CONFIRM_SECONDS + 1) / STEP) + SCREEN_EVERY_SAMPLES):
        clock.advance(STEP)
        result = session.process(victory_frame(10 + i))
    assert result.menu_visible is True and result.hud_visible is False
    for i in range(int((MENU_CONFIRM_SECONDS + 1) / STEP) + SCREEN_EVERY_SAMPLES):
        clock.advance(STEP)
        result = session.process(boss_frame(40 + i))
    assert result.menu_visible is False and result.hud_visible is True
    plain = DetectionSession(death, settings, clock)
    clock.advance(STEP)
    result = plain.process(gameplay_frame(1))
    assert result.menu_visible is None and result.hud_visible is None   # bez wzorców – brak informacji
