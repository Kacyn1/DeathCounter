from deathcounter import __version__, legal
from deathcounter.config import AppConfig, load_config, save_config


def test_license_files_are_available():
    text = legal.license_text()
    assert "Mateusz Kacyna" in text and "Wszelkie prawa zastrzeżone" in text
    assert "LGPL v3" in text  # wyjątek wymagany przez bibliotekę Qt
    third = legal.third_party_text()
    for library in ("Qt for Python", "OpenCV", "NumPy", "DXcam", "comtypes", "Python"):
        assert library in third
    assert "GNU LESSER GENERAL PUBLIC LICENSE" in third


def test_license_id_changes_with_text(monkeypatch):
    first = legal.license_id()
    assert len(first) == 16
    monkeypatch.setattr(legal, "license_text", lambda: "inna treść")
    assert legal.license_id() != first


def test_acceptance_is_remembered(tmp_path):
    config = AppConfig()
    config.license_accepted = legal.license_id()
    save_config(tmp_path / "config.json", config)
    assert load_config(tmp_path / "config.json")[0].license_accepted == legal.license_id()


def test_version_is_set():
    assert __version__.count(".") == 2
