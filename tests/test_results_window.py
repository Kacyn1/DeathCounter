from PySide6.QtCore import Qt

from deathcounter.attempts import AttemptLog
from deathcounter.boss_names import BossNames, builtin_path
from deathcounter.bosses import BossRecord, BossStore, BossTracker
from deathcounter.results_window import ResultsWindow


def rows(window):
    table = window.table
    return {table.item(r, 0).text(): [table.item(r, c).text() for c in range(4)]
            for r in range(table.rowCount()) if table.item(r, 0) is not None}


def test_table_shows_bosses_and_live_time(tmp_path, clock):
    store = BossStore(tmp_path / "bosses.json")
    store.records = {"Margit": BossRecord(7, 600, "W TRAKCIE"), "Godrick": BossRecord(3, 900, "POKONANO")}
    tracker = BossTracker(store, clock)
    tracker.set_enabled(True)
    window = ResultsWindow()
    window.show_results("Elden Ring", 15, tracker)
    assert rows(window)["Margit"] == ["Margit", "W TRAKCIE (bieżąca walka)", "7", "00:10:00"]
    assert rows(window)["Godrick"] == ["Godrick", "POKONANO", "3", "00:15:00"]
    assert "pokonani bossowie: 1 z 2" in window.summary.text()

    tracker.boss_bar_visible()
    clock.advance(65)
    window.show_results("Elden Ring", 15, tracker)
    assert rows(window)["Margit"][3] == "00:11:05"


def test_double_click_shows_attempts_newest_first(tmp_path, clock):
    store = BossStore(tmp_path / "bosses.json")
    log = AttemptLog(tmp_path / "attempts.json")
    tracker = BossTracker(store, clock, attempts=log, wall=lambda: 1_700_000_000.0)
    tracker.set_enabled(True)
    for seconds in range(1, 21):  # 20 prób – lista pokazuje 15 wierszy, resztę przewija
        tracker.boss_bar_visible()
        clock.advance(seconds)
        tracker.death()
    tracker.boss_bar_visible()
    clock.advance(7)
    window = ResultsWindow()
    window.show_results("Elden Ring", 20, tracker)
    window.table.cellDoubleClicked.emit(0, 0)  # dwuklik w bossa
    assert window.table.rowCount() == 2 and window.table.columnSpan(1, 0) == 4
    view = window.table.cellWidget(1, 0)
    table = view.table
    assert table.rowCount() == 21
    assert [table.item(0, c).text() for c in (0, 2, 3)] == ["21", "00:00:07", "W toku"]
    assert [table.item(1, c).text() for c in (0, 2, 3)] == ["20", "00:00:20", "Śmierć"]
    assert view.summary.text().startswith("Próby: 21")
    visible = table.height() - table.horizontalHeader().height() - 2 * table.frameWidth()
    assert visible == sum(table.rowHeight(r) for r in range(15))
    window.table.cellDoubleClicked.emit(0, 2)  # ponowny dwuklik zwija
    assert window.table.rowCount() == 1


def test_sorting_keeps_attempts_under_boss(tmp_path, clock):
    store = BossStore(tmp_path / "bosses.json")
    store.records = {"Margit": BossRecord(7, 600, "POKONANO"), "Godrick": BossRecord(3, 900, "POKONANO")}
    window = ResultsWindow()
    window.show_results("Elden Ring", 10, BossTracker(store, clock))
    window.toggle("Margit")
    header = window.table.horizontalHeader()
    expected = {Qt.SortOrder.AscendingOrder: ["Godrick", "Margit", "próby"],
                Qt.SortOrder.DescendingOrder: ["Margit", "próby", "Godrick"]}
    for order, names in expected.items():
        header.setSortIndicator(2, order)  # po liczbie śmierci
        shown = [window.table.item(r, 0).text() if window.table.item(r, 0) else "próby"
                 for r in range(window.table.rowCount())]
        assert shown == names


def test_fix_names_button_only_for_games_with_name_list(tmp_path, clock):
    store = BossStore(tmp_path / "bosses.json")
    store.records = {"Ostatni 0lbrzym": BossRecord(2, 60, "W TRAKCIE")}
    names = BossNames(tmp_path / "boss_names.json", builtin_path("ds2"))
    names.load()
    window = ResultsWindow()
    window.show_results("Dark Souls II", 2, BossTracker(store, clock, names=names))
    assert not window.fix_names_button.isHidden() and window.fix_names_button.isEnabled()
    requested = []
    window.fix_names_requested.connect(lambda: requested.append(True))
    window.fix_names_button.click()
    assert requested == [True]

    custom = BossNames(tmp_path / "custom.json", builtin_path("moja-gra"))
    custom.load()
    window.show_results("Moja gra", 2, BossTracker(store, clock, names=custom))
    assert window.fix_names_button.isHidden()
