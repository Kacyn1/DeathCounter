import json

import pytest

from deathcounter.config import (
    GAMES,
    AppConfig,
    AppPaths,
    Calibration,
    TemplateInfo,
    legacy_data_present,
    load_calibration,
    load_config,
    migrate_legacy,
    save_calibration,
    save_config,
)
from deathcounter.game_data import counter_files, open_game


def test_defaults_when_missing(tmp_path):
    config, warning = load_config(tmp_path / "config.json")
    assert warning is None
    assert config == AppConfig()


def test_roundtrip(tmp_path):
    config = AppConfig()
    config.detector.threshold = 0.8
    config.overlay.enabled = True
    config.capture.output_index = 1
    config.bosses.track = True
    config.bosses.bar_lost_seconds = 5.0
    config.game = "eldenring"
    save_config(tmp_path / "config.json", config)
    loaded, warning = load_config(tmp_path / "config.json")
    assert warning is None
    assert loaded == config


def test_invalid_values_fall_back(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({
        "detector": {"threshold": "wysoki", "confirm_samples": 0, "rearm_seconds": 999},
        "overlay": {"enabled": 1, "font_size": 5},
        "game": "minecraft",
    }), encoding="utf-8")
    config, warning = load_config(path)
    assert warning is None
    assert config.detector.threshold == 0.70
    assert config.detector.confirm_samples == 1
    assert config.detector.rearm_seconds == 60.0
    assert config.overlay.enabled is False
    assert config.overlay.font_size == 10
    assert config.game == "ds1"


def test_broken_json_gives_warning(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{", encoding="utf-8")
    config, warning = load_config(path)
    assert warning
    assert config == AppConfig()


def test_games_list():
    assert list(GAMES.values()) == [
        "Dark Souls I", "Dark Souls II", "Dark Souls III", "Sekiro: Shadows Die Twice", "Elden Ring",
    ]


def test_each_game_has_own_folder(tmp_path):
    ds1, er = AppPaths.for_game(tmp_path, "ds1"), AppPaths.for_game(tmp_path, "eldenring")
    assert ds1.config == er.config == tmp_path / "config.json"
    assert ds1.deaths == tmp_path / "games" / "ds1" / "deaths.json"
    assert er.source_path("boss_bar") == tmp_path / "games" / "eldenring" / "boss_bar_source.jpg"


def test_calibration_roundtrip(tmp_path):
    path = tmp_path / "games" / "ds3" / "calibration.json"
    calibration = Calibration()
    calibration.set_info("death", TemplateInfo([1, 2, 300, 60], [1920, 1080]))
    calibration.set_info("victory", TemplateInfo([300, 300, 500, 90], [1280, 720]))
    save_calibration(path, calibration)
    loaded, warning = load_calibration(path)
    assert warning is None
    assert loaded == calibration
    assert loaded.info("boss_bar") is None


def test_invalid_calibration_entries_are_dropped(tmp_path):
    path = tmp_path / "calibration.json"
    path.write_text(json.dumps({"template": {"roi": [1, 2], "reference_size": [1, 1]}}), encoding="utf-8")
    loaded, warning = load_calibration(path)
    assert warning is None
    assert loaded.info("death") is None


def test_games_keep_separate_counters(tmp_path):
    ds1 = open_game(tmp_path, "ds1")
    ds1.store.set(7)
    sekiro = open_game(tmp_path, "sekiro")
    assert sekiro.store.deaths == 0
    assert open_game(tmp_path, "ds1").store.deaths == 7


def test_legacy_data_is_moved_to_chosen_game(tmp_path):
    (tmp_path / "deaths.json").write_text('{ "deaths": 3 }\n', encoding="utf-8")
    (tmp_path / "bosses.json").write_text(
        json.dumps({"Demon azylu": {"deaths": 1, "total_time_seconds": 89, "status": "POKONANO"}}), encoding="utf-8"
    )
    (tmp_path / "template.png").write_bytes(b"png")
    (tmp_path / "boss_bar_source.jpg").write_bytes(b"jpg")
    (tmp_path / "config.json").write_text(json.dumps({
        "detector": {"threshold": 0.75},
        "template": {"roi": [773, 629, 1017, 260], "reference_size": [2560, 1440]},
        "boss_bar_template": {"roi": [790, 1171, 476, 30], "reference_size": [2560, 1440]},
    }), encoding="utf-8")
    assert legacy_data_present(tmp_path)

    migrate_legacy(tmp_path, "ds1")

    game = tmp_path / "games" / "ds1"
    assert not (tmp_path / "deaths.json").exists()
    assert (game / "deaths.json").read_text(encoding="utf-8") == '{ "deaths": 3 }\n'
    assert (game / "template.png").read_bytes() == b"png"
    assert (game / "boss_bar_source.jpg").exists()
    calibration, _ = load_calibration(game / "calibration.json")
    assert calibration.info("death") == TemplateInfo([773, 629, 1017, 260], [2560, 1440])
    assert calibration.info("boss_bar") == TemplateInfo([790, 1171, 476, 30], [2560, 1440])
    assert calibration.info("victory") is None
    assert not legacy_data_present(tmp_path)  # pytanie o grę pojawia się tylko raz
    config, _ = load_config(tmp_path / "config.json")
    assert config.detector.threshold == 0.75  # wspólne ustawienia zostają


def test_no_legacy_data_on_fresh_install(tmp_path):
    assert not legacy_data_present(tmp_path)
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")
    assert not legacy_data_present(tmp_path)


def test_add_game_creates_unique_folder_name():
    config = AppConfig()
    assert config.add_game("  Lies of   P ") == "lies-of-p"
    assert config.add_game("Łowcy Dusz: Zażółć") == "lowcy-dusz-zazolc"
    assert config.add_game("Lies of P!") == "lies-of-p-2"   # inna nazwa, ten sam folder bazowy
    assert config.add_game("???") == "gra"
    assert config.game_name("lies-of-p") == "Lies of P"
    assert list(config.all_games())[:5] == list(GAMES)       # wbudowane zostają na początku


@pytest.mark.parametrize("name, message", [
    ("", "Podaj nazwę"),
    ("   ", "Podaj nazwę"),
    ("elden ring", "już na liście"),
    ("x" * 61, "najwyżej 60"),
])
def test_add_game_rejects_bad_names(name, message):
    with pytest.raises(ValueError, match=message):
        AppConfig().add_game(name)


def test_custom_games_survive_restart(tmp_path):
    config = AppConfig()
    config.game = config.add_game("Lies of P")
    save_config(tmp_path / "config.json", config)
    loaded, _ = load_config(tmp_path / "config.json")
    assert loaded.custom_games == {"lies-of-p": "Lies of P"}
    assert loaded.game == "lies-of-p"
    assert AppPaths.for_game(tmp_path, loaded.game).game_dir == tmp_path / "games" / "lies-of-p"


def test_invalid_custom_games_are_dropped(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({
        "custom_games": {"../hack": "Zła", "ds1": "Podmiana", "ok-game": "Dobra", "bad": 5},
        "game": "../hack",
    }), encoding="utf-8")
    loaded, _ = load_config(path)
    assert loaded.custom_games == {"ok-game": "Dobra"}
    assert loaded.game == "ds1"


def test_remove_custom_game():
    config = AppConfig()
    config.game = config.add_game("Lies of P")
    config.remove_game("lies-of-p")
    assert "lies-of-p" not in config.all_games()
    assert config.game == "ds1"
    config.remove_game("ds3")  # gry wbudowanej nie da się usunąć z listy
    assert "ds3" in config.all_games()


def test_counter_files_keep_calibration(tmp_path):
    paths = AppPaths.for_game(tmp_path, "ds1")
    names = {p.name for p in counter_files(paths)}
    assert names == {"deaths.json", "deaths.json.uszkodzony", "bosses.json", "bosses.json.uszkodzony", "audit.json"}
