from deathcounter.bosses import BossRecord, BossStore, BossTracker
from deathcounter.results_window import ResultsWindow


def test_table_shows_bosses_and_live_time(tmp_path, clock):
    store = BossStore(tmp_path / "bosses.json")
    store.records = {"Margit": BossRecord(7, 600, "W TRAKCIE"), "Godrick": BossRecord(3, 900, "POKONANO")}
    tracker = BossTracker(store, clock)
    tracker.set_enabled(True)
    window = ResultsWindow()
    window.show_results("Elden Ring", 15, tracker)
    table = window.table
    rows = {table.item(r, 0).text(): [table.item(r, c).text() for c in range(4)] for r in range(table.rowCount())}
    assert rows["Margit"] == ["Margit", "W TRAKCIE (bieżąca walka)", "7", "00:10:00"]
    assert rows["Godrick"] == ["Godrick", "POKONANO", "3", "00:15:00"]
    assert "pokonani bossowie: 1 z 2" in window.summary.text()

    tracker.boss_bar_visible()
    clock.advance(65)
    window.show_results("Elden Ring", 15, tracker)
    row = next(r for r in range(table.rowCount()) if table.item(r, 0).text() == "Margit")
    assert table.item(row, 3).text() == "00:11:05"
