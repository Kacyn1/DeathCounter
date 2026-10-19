import json

import pytest

from deathcounter import hotkeys
from deathcounter.config import HotkeySettings, load_config


def test_parse_default_shortcuts():
    hotkey = hotkeys.parse("Ctrl+Alt+F9")
    assert hotkey == hotkeys.Hotkey(hotkeys.MOD_CONTROL | hotkeys.MOD_ALT, 0x78, "Ctrl+Alt+F9")
    assert hotkeys.parse("Ctrl+Alt+F8").vk == 0x77


def test_parse_normalizes_modifier_order():
    assert hotkeys.parse("Shift+Alt+Ctrl+K").text == "Ctrl+Alt+Shift+K"
    assert hotkeys.parse("Meta+Ctrl+1").modifiers == hotkeys.MOD_CONTROL | hotkeys.MOD_WIN


def test_parse_single_keys_and_keypad():
    assert hotkeys.parse("Pause").vk == 0x13
    assert hotkeys.parse("F13").vk == 0x7C
    assert hotkeys.parse("Num+5").vk == 0x65
    assert hotkeys.parse("Ctrl+Num+-").vk == 0x6D


@pytest.mark.parametrize("text", ["", "K", "Shift+K", "Space", "Ctrl+Hyper+K", "Ctrl+Alt+Esc", "Ctrl+"])
def test_parse_rejects_unusable(text):
    with pytest.raises(ValueError):
        hotkeys.parse(text)


def test_display_uses_win():
    assert hotkeys.display("Meta+Ctrl+F1") == "Win+Ctrl+F1"
    assert hotkeys.display("") == "brak"


def test_config_hotkeys(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"hotkeys": {"plus": "Alt+Ctrl+P", "minus": "", "overlay": "Q", "snapshot": 5}}),
                    encoding="utf-8")
    config, _ = load_config(path)
    assert config.hotkeys.plus == "Ctrl+Alt+P"
    assert config.hotkeys.minus == ""                          # wyłączony
    assert config.hotkeys.overlay == HotkeySettings().overlay  # błędny → domyślny
    assert config.hotkeys.snapshot == "Ctrl+Alt+F9"
