import sys
from pathlib import Path

import pytest

from deathcounter.config import AppConfig, load_config, save_config
from deathcounter.game_process import build_matchers, matching_exe, running_games
from deathcounter.steam_library import SteamGame

LIBRARY = Path(r"D:\SteamLibrary\steamapps\common")
STEAM_GAMES = [
    SteamGame(1627720, "Lies of P", LIBRARY / "Lies of P"),
    SteamGame(485510, "Nioh: Complete Edition", LIBRARY / "NIOH"),
]


def test_builtin_games_by_exe_name():
    matchers = build_matchers(AppConfig(), [])
    processes = [r"C:\Windows\explorer.exe", r"E:\Gry\Dark Souls II Scholar\Game\DarkSoulsII.exe"]
    assert running_games(processes, matchers) == {"ds2"}
    assert running_games([r"C:\x\DarkSoulsRemastered.exe"], matchers) == {"ds1"}
    assert running_games([r"C:\x\ELDENRING.EXE"], matchers) == {"eldenring"}
    assert matching_exe(processes, matchers["ds2"]) == "DarkSoulsII.exe"


def test_steam_game_by_install_folder():
    config = AppConfig()
    config.add_game("Lies of P", appid=1627720)
    matchers = build_matchers(config, STEAM_GAMES)
    exe = str(LIBRARY / "Lies of P" / "LiesofP" / "Binaries" / "Win64" / "LOP-Win64-Shipping.exe")
    assert running_games([exe], matchers) == {"lies-of-p"}
    # Inny folder o podobnym początku nazwy to nie ta gra.
    assert running_games([str(LIBRARY / "Lies of Pinocchio" / "game.exe")], matchers) == set()


@pytest.mark.skipif(sys.platform != "win32", reason="ścieżki Windows (D:\\...) poza Windowsem łączą się przez /")
def test_manually_added_game_matched_to_steam_by_name():
    config = AppConfig()
    config.add_game("nioh:  complete edition")  # dodana ręcznie, przed wyszukiwaniem w Steamie
    config.add_game("Hollow Knight")             # nie ma jej w Steamie
    matchers = build_matchers(config, STEAM_GAMES)
    assert matchers["nioh-complete-edition"].folders == (str(LIBRARY / "NIOH").lower() + "\\",)
    assert "hollow-knight" not in matchers


def test_chosen_exe_for_game_outside_steam(tmp_path):
    config = AppConfig()
    game_id = config.add_game("Hollow Knight")
    config.game_exes[game_id] = r"C:\GOG Games\Hollow Knight\hollow_knight.exe"
    save_config(tmp_path / "config.json", config)
    loaded, _ = load_config(tmp_path / "config.json")
    assert loaded.game_exes == {game_id: r"C:\GOG Games\Hollow Knight\hollow_knight.exe"}
    matchers = build_matchers(loaded, [])
    assert running_games([r"c:\gog games\hollow knight\HOLLOW_KNIGHT.exe"], matchers) == {game_id}
    assert running_games([r"C:\Inne\hollow_knight.exe"], matchers) == set()
    loaded.remove_game(game_id)
    assert loaded.game_exes == {}


def test_invalid_game_exes_are_dropped(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"custom_games": {"a": "A"}, "game_exes": {"a": "C:/a.txt", "ds1": "C:/x.exe", "b": "C:/b.exe"}}',
                    encoding="utf-8")
    loaded, _ = load_config(path)
    assert loaded.game_exes == {}
