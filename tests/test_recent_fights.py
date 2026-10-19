import json

import pytest

from deathcounter import recent_fights
from deathcounter.bosses import BossState, BossStore, BossTracker
from deathcounter.recent_fights import RecentFights


@pytest.fixture
def recent(tmp_path, clock):
    recent = RecentFights(tmp_path / "recent_fights.json", wall=clock)
    recent.load()
    return recent


@pytest.fixture
def tracker(tmp_path, clock, recent):
    store = BossStore(tmp_path / "bosses.json")
    store.load()
    tracker = BossTracker(store, clock, recent=recent)
    tracker.set_enabled(True)
    tracker.abandon_enabled = True
    return tracker


def fight(tracker, clock, name, seconds):
    tracker.boss_bar_visible()
    tracker.rename(name)
    clock.advance(seconds)


def leave_arena(tracker, clock, seconds=15):
    tracker.boss_bar_lost()
    clock.advance(seconds)
    return tracker.tick()


def outcomes(tracker):
    return [(r.name, r.outcome, r.deaths, round(r.seconds)) for r in tracker.recent_rows()]


def test_leaving_arena_abandons_fight_but_keeps_record(tracker, clock):
    fight(tracker, clock, "Margit", 40)
    tracker.death()
    fight(tracker, clock, "Margit", 30)
    assert leave_arena(tracker, clock, 14) is None  # jeszcze za wcześnie
    clock.advance(1)
    ended = tracker.tick()
    assert ended.abandoned and (ended.view.name, ended.view.deaths) == ("Margit", 1)
    assert tracker.current is None and tracker.state is BossState.WAITING
    assert tracker.store.records["Margit"].status == "W TRAKCIE"
    assert outcomes(tracker) == [("Margit", recent_fights.ABANDONED, 1, 70)]


def test_death_or_victory_after_bar_lost_is_not_leaving(tracker, clock):
    fight(tracker, clock, "Margit", 40)
    tracker.boss_bar_lost()
    clock.advance(5)
    tracker.death()
    clock.advance(30)
    assert tracker.tick() is None
    assert tracker.current == "Margit"


def test_no_abandon_without_victory_template(tracker, clock):
    tracker.abandon_enabled = False
    fight(tracker, clock, "Margit", 40)
    assert leave_arena(tracker, clock, 60) is None
    assert tracker.current == "Margit"


def test_stopping_detection_does_not_abandon(tracker, clock):
    fight(tracker, clock, "Margit", 40)
    tracker.boss_bar_lost()
    tracker.pause()
    clock.advance(60)
    assert tracker.tick() is None


def test_returning_to_abandoned_boss_continues(tracker, clock):
    fight(tracker, clock, "Margit", 40)
    leave_arena(tracker, clock)
    tracker.boss_bar_visible()
    assert tracker.current == "Boss 1"
    tracker.boss_identified("Margit")  # odczyt nazwy podłącza walkę do przerwanego bossa
    clock.advance(20)
    tracker.pause()
    assert tracker.current == "Margit"
    assert round(tracker.store.records["Margit"].total_time_seconds) == 60
    assert tracker.recent_rows() == []  # bieżąca walka nie jest na liście ostatnich


def test_recent_list_newest_first_with_outcomes(tracker, clock):
    fight(tracker, clock, "Margit", 40)
    leave_arena(tracker, clock)
    fight(tracker, clock, "Agheel", 30)
    tracker.victory()
    tracker.confirm_defeated()
    fight(tracker, clock, "Godrick", 10)
    tracker.death()
    tracker.boss_bar_visible()          # inny boss: walka wraca do Godricka, dopóki odczyt nazwy jej nie przełączy
    tracker.boss_identified("Ogar")
    assert [r[:2] for r in outcomes(tracker)] == [
        ("Godrick", recent_fights.IN_PROGRESS), ("Agheel", recent_fights.DEFEATED),
        ("Margit", recent_fights.ABANDONED)]


def test_mark_defeated_and_remove(tracker, clock, tmp_path):
    fight(tracker, clock, "Margit", 40)
    leave_arena(tracker, clock)
    fight(tracker, clock, "Wilk", 5)
    leave_arena(tracker, clock)
    tracker.mark_defeated("Margit")
    tracker.remove("Wilk")
    assert outcomes(tracker) == [("Margit", recent_fights.DEFEATED, 0, 40)]
    assert json.loads((tmp_path / "bosses.json").read_text(encoding="utf-8")) == {
        "Margit": {"deaths": 0, "total_time_seconds": 40, "status": "POKONANO"}}


def test_abandoned_fight_not_resumed_after_restart(tracker, clock, tmp_path, recent):
    fight(tracker, clock, "Margit", 40)
    leave_arena(tracker, clock)
    reloaded = RecentFights(tmp_path / "recent_fights.json")
    assert reloaded.load() is None
    restored = BossTracker(tracker.store, clock, recent=reloaded)
    assert restored.current is None
    assert restored.recent_rows()[0].outcome == recent_fights.ABANDONED


def test_recent_file_keeps_last_fights(recent, clock):
    for number in range(15):
        recent.touch(f"Boss {number}", recent_fights.IN_PROGRESS)
        clock.advance(1)
    assert len(recent.fights) == recent_fights.KEEP
    assert recent.fights[0].name == "Boss 14"
