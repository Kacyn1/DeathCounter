import json

from PySide6.QtCore import QPointF

from deathcounter.play_session import PlaySession
from deathcounter.session_stats import (
    SessionStatsWindow,
    clock,
    longest_without_death,
    nice_ticks,
    per_hour,
    sessions,
    time_ticks,
)

NOW = 1_800_000_000.0


def make_session(tmp_path, history, current=None):
    (tmp_path / "session_history.json").write_text(json.dumps(history), encoding="utf-8")
    if current:
        (tmp_path / "session.json").write_text(json.dumps(current), encoding="utf-8")
    return PlaySession(tmp_path / "session.json")


def test_helpers():
    assert nice_ticks(16) == [0, 5, 10, 15, 20]
    assert nice_ticks(3) == [0, 1, 2, 3]
    assert nice_ticks(0) == [0, 1]
    assert time_ticks(4150) == [0, 900, 1800, 2700, 3600]
    assert clock(3900) == "1:05"
    assert per_hour(14, 3600) == "14,0" and per_hour(3, 30) == "–"
    assert longest_without_death([100, 150], 400) == 250
    assert longest_without_death([100, 150], 400, early=2) == 250   # od pierwszej śmierci z czasem
    assert longest_without_death([], 400) == 400


def test_sessions_list_history_then_current(tmp_path):
    session = make_session(tmp_path, [{"started": NOW - 9000, "ended": NOW - 5000, "seconds": 3600, "deaths": 20}],
                           {"started": NOW - 600, "last_seen": NOW, "seconds": 500, "deaths": 3, "death_times": [10, 20, 30]})
    rows = sessions(session, NOW)
    assert [(r.number, r.deaths, r.current) for r in rows] == [(1, 20, False), (2, 3, True)]


def test_window_shows_both_tabs(tmp_path):
    session = make_session(tmp_path, [{"started": NOW - 9000, "ended": NOW - 5000, "seconds": 3600, "deaths": 20}],
                           {"started": NOW - 600, "last_seen": NOW, "seconds": 500, "deaths": 4, "death_times": [100, 200, 300]})
    window = SessionStatsWindow()
    window.update_data(session, "Dark Souls II", NOW)
    assert window.windowTitle() == "Statystyki sesji – Dark Souls II"
    assert [label.text() for label in window.current_tiles.values] == ["4", "00:08:20", "28,8", "00:03:20", "00:03:20"]
    assert "1 śmierci" in window.current_note.text()                  # jedna śmierć bez czasu
    assert [label.text() for label in window.all_tiles.values] == ["2", "24", "01:08:20", "12,0", "21,1"]
    assert window.table.item(0, 0).text() == "2 (bieżąca)" and window.table.item(1, 3).text() == "20"
    window.timeline._mouse = QPointF(200, 100)   # rysowanie z dymkiem nie rzuca wyjątków
    window.bars._mouse = QPointF(100, 150)
    window.resize(600, 500)
    window.grab()


def test_window_without_sessions(tmp_path):
    window = SessionStatsWindow()
    window.update_data(PlaySession(tmp_path / "session.json"), "Sekiro", NOW)
    assert window.timeline.empty_text and window.bars.empty_text
    assert window.table.rowCount() == 0
    window.grab()
