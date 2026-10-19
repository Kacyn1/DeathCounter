import pytest

from deathcounter import attempts as a
from deathcounter.attempts import AttemptLog, summary
from deathcounter.bosses import BossStore, BossTracker
from deathcounter.recent_fights import RecentFights


@pytest.fixture
def log(tmp_path):
    log = AttemptLog(tmp_path / "attempts.json")
    log.load()
    return log


@pytest.fixture
def tracker(tmp_path, clock, log):
    store = BossStore(tmp_path / "bosses.json")
    store.load()
    recent = RecentFights(tmp_path / "recent.json", wall=clock)
    tracker = BossTracker(store, clock, recent=recent, attempts=log, wall=clock)
    tracker.set_enabled(True)
    tracker.abandon_enabled = True
    return tracker


def history(tracker, name):
    return [(round(x.seconds), x.outcome) for x in tracker.attempts_for(name)]


def start(tracker, name=None):
    tracker.boss_bar_visible()
    if name:
        tracker.boss_identified(name, True)


def test_each_death_is_one_attempt(tracker, clock):
    start(tracker, "Margit")
    clock.advance(40)
    tracker.death()
    clock.advance(60)  # droga z ogniska nie wlicza się do próby
    start(tracker)
    clock.advance(25)
    assert history(tracker, "Margit") == [(40, a.DEATH), (25, a.IN_PROGRESS)]
    tracker.boss_bar_lost()
    tracker.victory()
    assert history(tracker, "Margit") == [(40, a.DEATH), (25, a.VICTORY)]


def test_bar_gap_without_death_is_same_attempt(tracker, clock):
    start(tracker, "Rennala")
    clock.advance(30)
    tracker.boss_bar_lost()  # przerywnik między fazami
    clock.advance(8)
    start(tracker)
    clock.advance(20)
    tracker.death()
    assert history(tracker, "Rennala") == [(50, a.DEATH)]


def test_abandon_and_stop_end_attempt(tracker, clock):
    start(tracker, "Agheel")
    clock.advance(30)
    tracker.boss_bar_lost()
    clock.advance(15)
    tracker.tick()
    start(tracker, "Agheel")
    clock.advance(10)
    tracker.pause()  # zatrzymanie wykrywania
    assert history(tracker, "Agheel") == [(30, a.ABANDONED), (10, a.STOPPED)]


def test_placeholder_attempts_follow_rename(tracker, clock):
    start(tracker)
    clock.advance(12)
    tracker.death()
    tracker.rename("Gwyn")
    assert history(tracker, "Gwyn") == [(12, a.DEATH)]


def test_switch_to_other_boss_moves_attempt(tracker, clock):
    start(tracker, "Margit")
    clock.advance(30)
    tracker.death()
    start(tracker)      # wraca Margit…
    clock.advance(4)
    tracker.boss_identified("Godrick", True)  # …ale to Godrick
    clock.advance(6)
    tracker.death()
    assert history(tracker, "Margit") == [(30, a.DEATH)]
    assert history(tracker, "Godrick") == [(10, a.DEATH)]


def test_manual_corrections(tracker, clock):
    start(tracker, "Ornstein")
    clock.advance(20)
    tracker.manual_add()  # przeoczona śmierć w trakcie walki
    clock.advance(5)
    tracker.death()
    tracker.manual_undo()  # fałszywie wykryta śmierć
    assert history(tracker, "Ornstein") == [(20, a.MANUAL_DEATH), (5, a.CANCELLED)]


def test_simultaneous_death_resolved_as_death(tracker, clock):
    start(tracker, "Gundyr")
    clock.advance(30)
    tracker.victory()
    clock.advance(1)
    tracker.death()
    tracker.continue_fight()
    assert history(tracker, "Gundyr") == [(30, a.DEATH)]


def test_abandoned_marked_defeated_from_recent(tracker, clock):
    start(tracker, "Agheel")
    clock.advance(30)
    tracker.boss_bar_lost()
    clock.advance(15)
    tracker.tick()
    tracker.mark_defeated("Agheel")
    assert history(tracker, "Agheel") == [(30, a.VICTORY)]


def test_remove_deletes_history_and_file_roundtrip(tracker, clock, tmp_path):
    start(tracker, "Margit")
    clock.advance(30)
    tracker.death()
    start(tracker)
    tracker.boss_identified("Wilk", True)
    clock.advance(3)
    tracker.pause()
    tracker.remove("Wilk")
    reloaded = AttemptLog(tmp_path / "attempts.json")
    assert reloaded.load() is None
    assert list(reloaded.bosses) == ["Margit"]
    assert reloaded.bosses["Margit"][0].outcome == a.DEATH


def test_summary():
    attempts = [a.Attempt(0, 60, a.DEATH), a.Attempt(1, 120, a.DEATH), a.Attempt(2, 90, a.VICTORY)]
    assert summary(attempts) == "Próby: 3 · średnio 00:01:30 · najdłuższa 00:02:00 · pokonany w 3. próbie"
    assert summary([]).startswith("Brak zapisanych prób")
