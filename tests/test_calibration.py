"""Okno kalibracji: zakładka paska głównego bossa tylko dla gier, które ją mają."""

import pytest

from deathcounter.calibration import CalibrationDialog
from deathcounter.config import GAMES, MAIN_BOSS_BAR_GAMES


def dialog(main_boss_bar: bool, kind: str = "death") -> CalibrationDialog:
    thresholds = dict.fromkeys(("death", "boss_bar", "boss_bar_main", "victory", "menu", "hud"), 0.7)
    return CalibrationDialog(None, lambda *_: None, lambda *_: None, {}, {}, thresholds, 0.5, None,
                             initial_kind=kind, main_boss_bar=main_boss_bar)


def tab_titles(window: CalibrationDialog) -> list[str]:
    return [window.boss_tabs.tabText(i) for i in range(window.boss_tabs.count())]


def test_main_boss_bar_tab_in_sekiro_only():
    assert MAIN_BOSS_BAR_GAMES == {"sekiro"} and MAIN_BOSS_BAR_GAMES <= set(GAMES)
    window = dialog(True, "boss_bar_main")
    assert tab_titles(window) == ["Pasek bossa", "Pasek głównego bossa", "Komunikat zwycięstwa"]
    assert window.current_page() is window.pages["boss_bar_main"]


def test_other_games_have_no_main_boss_bar_tab():
    window = dialog(False)
    assert tab_titles(window) == ["Pasek bossa", "Komunikat zwycięstwa"]
    assert "boss_bar_main" not in window.pages
    with pytest.raises(KeyError):
        window.show_kind("boss_bar_main")
