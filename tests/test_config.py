import json

from deathcounter.config import AppConfig, TemplateInfo, load_config, save_config


def test_defaults_when_missing(tmp_path):
    config, warning = load_config(tmp_path / "config.json")
    assert warning is None
    assert config == AppConfig()


def test_roundtrip(tmp_path):
    config = AppConfig()
    config.detector.threshold = 0.8
    config.overlay.enabled = True
    config.capture.output_index = 1
    config.template = TemplateInfo([1, 2, 300, 60], [1920, 1080])
    save_config(tmp_path / "config.json", config)
    loaded, warning = load_config(tmp_path / "config.json")
    assert warning is None
    assert loaded == config


def test_invalid_values_fall_back(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({
        "detector": {"threshold": "wysoki", "confirm_samples": 0, "rearm_seconds": 999},
        "overlay": {"enabled": 1, "font_size": 5},
        "template": {"roi": [1, 2], "reference_size": [1, 1]},
    }), encoding="utf-8")
    config, warning = load_config(path)
    assert warning is None
    assert config.detector.threshold == 0.70
    assert config.detector.confirm_samples == 1
    assert config.detector.rearm_seconds == 60.0
    assert config.overlay.enabled is False
    assert config.overlay.font_size == 10
    assert config.template is None


def test_broken_json_gives_warning(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{", encoding="utf-8")
    config, warning = load_config(path)
    assert warning
    assert config == AppConfig()
