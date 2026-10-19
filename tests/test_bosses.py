import json

import pytest

from deathcounter.bosses import (
    BossState,
    BossStore,
    BossTracker,
    BossView,
    format_duration,
    overlay_text,
)


@pytest.fixture
def path(tmp_path):
    return tmp_path / "bosses.json"


@pytest.fixture
def tracker(path, clock):
    store = BossStore(path)
    store.load()
    tracker = BossTracker(store, clock)
    tracker.set_enabled(True)
    return tracker


def saved(path):
    return json.loads(path.read_text(encoding="utf-8"))


def fight(tracker, clock, seconds):
    tracker.boss_bar_visible()
    clock.advance(seconds)


def test_bar_starts_fight_with_placeholder_name(tracker, clock, path):
    fight(tracker, clock, 30)
    assert tracker.state is BossState.FIGHT
    assert tracker.current == "Boss 1"
    assert tracker.elapsed() == pytest.approx(30)
    assert saved(path) == {"Boss 1": {"deaths": 0, "total_time_seconds": 0, "status": "W TRAKCIE"}}


def test_nothing_happens_when_tracking_disabled(tracker, clock, path):
    tracker.set_enabled(False)
    tracker.boss_bar_visible()
    assert tracker.current is None
    assert tracker.death() is False
    assert not path.exists()


def test_several_attempts_sum_only_fight_time(tracker, clock, path):
    fight(tracker, clock, 40)
    assert tracker.death() is True
    assert tracker.state is BossState.DEATH
    clock.advance(90)  # powrót na arenę nie wlicza się do czasu
    assert tracker.elapsed() == pytest.approx(40)
    fight(tracker, clock, 25)
    assert tracker.death() is True
    clock.advance(60)
    assert tracker.view() == BossView("Boss 1", 2, pytest.approx(65), BossState.DEATH, None, False)
    assert saved(path)["Boss 1"] == {"deaths": 2, "total_time_seconds": 65, "status": "W TRAKCIE"}


def test_death_outside_fight_counts_only_globally(tracker, clock):
    assert tracker.death() is False  # brak bossa
    fight(tracker, clock, 10)
    tracker.death()
    clock.advance(120)
    assert tracker.death() is False  # śmierć w drodze na arenę
    assert tracker.record.deaths == 1


def test_death_shortly_after_bar_disappeared_counts_for_boss(tracker, clock):
    fight(tracker, clock, 20)
    tracker.boss_bar_lost()  # pasek znika przy śmierci, napis pojawia się chwilę później
    clock.advance(3)
    assert tracker.death() is True
    assert tracker.elapsed() == pytest.approx(20)


def test_leaving_arena_pauses_timer_and_fight_continues(tracker, clock):
    fight(tracker, clock, 15)
    tracker.boss_bar_lost()
    clock.advance(200)
    assert tracker.state is BossState.WAITING
    fight(tracker, clock, 5)
    assert tracker.current == "Boss 1"
    assert tracker.elapsed() == pytest.approx(20)


def test_victory_stops_timer_and_waits_for_confirmation(tracker, clock, path):
    fight(tracker, clock, 50)
    tracker.victory()
    clock.advance(30)
    assert tracker.state is BossState.DEFEATED
    assert tracker.elapsed() == pytest.approx(50)
    tracker.boss_bar_visible()  # kolejny pasek przed zatwierdzeniem nie nadpisuje wyniku
    assert tracker.state is BossState.DEFEATED
    tracker.rename("Smelter Demon")
    tracker.confirm_defeated()
    assert tracker.current is None
    assert tracker.view() is None
    assert saved(path) == {"Smelter Demon": {"deaths": 0, "total_time_seconds": 50, "status": "POKONANO"}}


def test_victory_right_after_bar_disappears(tracker, clock):
    fight(tracker, clock, 50)
    tracker.boss_bar_lost()
    clock.advance(2)
    tracker.victory()
    assert tracker.state is BossState.DEFEATED
    assert tracker.uncertain is None


def test_victory_without_fight_is_ignored(tracker, clock):
    fight(tracker, clock, 10)
    tracker.boss_bar_lost()
    clock.advance(300)
    tracker.victory()
    assert tracker.state is BossState.WAITING


def test_next_bar_after_confirmation_is_new_boss(tracker, clock):
    fight(tracker, clock, 10)
    tracker.victory()
    tracker.confirm_defeated()
    fight(tracker, clock, 5)
    assert tracker.current == "Boss 2"
    assert tracker.record.deaths == 0
    assert tracker.elapsed() == pytest.approx(5)


def test_simultaneous_death_and_victory_is_uncertain(tracker, clock):
    fight(tracker, clock, 30)
    tracker.victory()
    clock.advance(1)
    assert tracker.death() is True
    assert tracker.uncertain
    assert tracker.state is BossState.DEFEATED
    tracker.boss_bar_visible()
    assert tracker.state is BossState.DEFEATED  # bez decyzji użytkownika nic nie rusza


def test_victory_after_death_is_uncertain_and_can_continue(tracker, clock):
    fight(tracker, clock, 30)
    tracker.death()
    clock.advance(1)
    tracker.victory()
    assert tracker.state is BossState.DEFEATED
    assert tracker.uncertain
    tracker.continue_fight()
    assert tracker.state is BossState.DEATH
    assert tracker.uncertain is None
    fight(tracker, clock, 10)
    assert tracker.elapsed() == pytest.approx(40)


def test_lost_frames_stop_timer_and_require_decision(tracker, clock):
    fight(tracker, clock, 30)
    tracker.frames_lost()
    clock.advance(20)
    assert tracker.elapsed() == pytest.approx(30)
    assert tracker.uncertain
    tracker.boss_bar_visible()
    assert tracker.state is BossState.WAITING  # brak automatycznego wznowienia
    tracker.victory()
    assert tracker.state is BossState.DEFEATED  # zwycięstwo nie jest uznawane bez zatwierdzenia
    assert tracker.uncertain
    tracker.continue_fight()
    fight(tracker, clock, 10)
    assert tracker.elapsed() == pytest.approx(40)


def test_restart_keeps_time_and_does_not_run_timer(tracker, clock, path):
    fight(tracker, clock, 42)
    tracker.death()
    fight(tracker, clock, 18)
    tracker.pause()
    clock.advance(3600)  # aplikacja wyłączona

    store = BossStore(path)
    store.load()
    restored = BossTracker(store, clock)
    restored.set_enabled(True)
    assert restored.current == "Boss 1"
    assert restored.state is BossState.WAITING
    clock.advance(100)
    assert restored.elapsed() == pytest.approx(60)
    assert restored.record.deaths == 1
    fight(restored, clock, 5)
    assert restored.elapsed() == pytest.approx(65)


def test_checkpoint_saves_time_during_fight(tracker, clock, path):
    tracker.boss_bar_visible()
    clock.advance(3)
    tracker.tick()
    assert saved(path)["Boss 1"]["total_time_seconds"] == 0
    clock.advance(3)
    tracker.tick()
    assert saved(path)["Boss 1"]["total_time_seconds"] == 6
    assert tracker.elapsed() == pytest.approx(6)


def test_rename_keeps_running_timer(tracker, clock, path):
    fight(tracker, clock, 10)
    assert tracker.rename("  Smelter   Demon ") == "Smelter Demon"
    clock.advance(5)
    tracker.death()
    assert saved(path) == {"Smelter Demon": {"deaths": 1, "total_time_seconds": 15, "status": "W TRAKCIE"}}


def test_rename_to_unfinished_boss_merges(path, clock):
    path.write_text(json.dumps({
        "Smelter Demon": {"deaths": 5, "total_time_seconds": 300, "status": "W TRAKCIE"},
        "Boss 1": {"deaths": 2, "total_time_seconds": 60, "status": "W TRAKCIE"},
    }), encoding="utf-8")
    store = BossStore(path)
    store.load()
    tracker = BossTracker(store, clock)
    assert tracker.current == "Boss 1"
    tracker.rename("Smelter Demon")
    assert saved(path) == {"Smelter Demon": {"deaths": 7, "total_time_seconds": 360, "status": "W TRAKCIE"}}


def test_rename_to_defeated_boss_gets_number(tracker, clock, path):
    fight(tracker, clock, 10)
    tracker.victory()
    tracker.rename("Pursuer")
    tracker.confirm_defeated()
    fight(tracker, clock, 20)  # np. NG+
    assert tracker.rename("Pursuer") == "Pursuer (2)"
    assert list(saved(path)) == ["Pursuer", "Pursuer (2)"]


def test_discard_removes_false_start(tracker, clock, path):
    fight(tracker, clock, 2)
    tracker.discard()
    assert tracker.current is None
    assert saved(path) == {}


def test_manual_corrections(tracker, clock):
    fight(tracker, clock, 10)
    tracker.death()
    tracker.manual_undo()
    assert tracker.record.deaths == 0
    tracker.manual_undo()  # tylko jedna śmierć do cofnięcia
    assert tracker.record.deaths == 0
    tracker.manual_add()
    assert tracker.record.deaths == 1
    fight(tracker, clock, 5)
    tracker.boss_bar_lost()
    clock.advance(100)
    tracker.manual_add()  # poza walką liczy się tylko ogólnie
    assert tracker.record.deaths == 1


def test_disabling_tracking_pauses_fight(tracker, clock):
    fight(tracker, clock, 10)
    tracker.set_enabled(False)
    clock.advance(50)
    assert tracker.elapsed() == pytest.approx(10)


def test_corrupted_file_is_backed_up(path):
    path.write_text("{ zepsute", encoding="utf-8")
    store = BossStore(path)
    store.load()
    assert store.records == {}
    assert store.warning
    assert path.with_name("bosses.json.uszkodzony").exists()


@pytest.mark.parametrize("entry", [
    {"deaths": -1, "total_time_seconds": 0, "status": "W TRAKCIE"},
    {"deaths": 1, "total_time_seconds": "dużo", "status": "W TRAKCIE"},
    {"deaths": 1, "total_time_seconds": 5, "status": "?"},
])
def test_invalid_entry_is_rejected(path, entry):
    path.write_text(json.dumps({"X": entry}), encoding="utf-8")
    store = BossStore(path)
    store.load()
    assert store.warning


def test_format_duration():
    assert format_duration(758) == "00:12:38"
    assert format_duration(5) == "00:00:05"
    assert format_duration(3725.9) == "01:02:05"
    assert format_duration(360000) == "100:00:00"


def test_overlay_text():
    boss = BossView("Smelter Demon", 7, 758, BossState.FIGHT, None)
    assert overlay_text(42, boss) == "DEATHS: 42\nSmelter Demon — deaths: 7\nCzas: 00:12:38"
    assert overlay_text(42, None) == "DEATHS: 42"
    defeated = BossView("Smelter Demon", 7, 758, BossState.DEFEATED, None)
    assert overlay_text(42, defeated) == "DEATHS: 42"
