import json

import pytest

from deathcounter.storage import DeathStore


def test_creates_file_with_zero(tmp_path):
    store = DeathStore(tmp_path / "deaths.json")
    assert store.load() == 0
    assert json.loads((tmp_path / "deaths.json").read_text(encoding="utf-8")) == {"deaths": 0}


def test_file_contains_only_deaths(tmp_path):
    store = DeathStore(tmp_path / "deaths.json")
    store.load()
    store.set(127)
    assert (tmp_path / "deaths.json").read_text(encoding="utf-8") == '{ "deaths": 127 }\n'


def test_value_survives_restart(tmp_path):
    store = DeathStore(tmp_path / "deaths.json")
    store.load()
    store.increment()
    store.increment()
    assert DeathStore(tmp_path / "deaths.json").load() == 2


def test_never_below_zero(tmp_path):
    store = DeathStore(tmp_path / "deaths.json")
    store.load()
    assert store.decrement() == 0
    store.increment()
    assert store.decrement() == 0
    assert store.decrement() == 0


def test_reset(tmp_path):
    store = DeathStore(tmp_path / "deaths.json")
    store.load()
    store.set(5)
    assert store.reset() == 0
    assert DeathStore(tmp_path / "deaths.json").load() == 0


def test_no_temp_files_left(tmp_path):
    store = DeathStore(tmp_path / "deaths.json")
    store.load()
    for _ in range(5):
        store.increment()
    assert [p.name for p in tmp_path.iterdir()] == ["deaths.json"]


def test_reads_existing_value_with_any_formatting(tmp_path):
    (tmp_path / "deaths.json").write_text('{"deaths":42}', encoding="utf-8")
    assert DeathStore(tmp_path / "deaths.json").load() == 42


@pytest.mark.parametrize("content", ["nie json", "[]", '{"deaths": -3}', '{"deaths": "7"}', '{"deaths": true}', "{}"])
def test_corrupted_file_is_backed_up(tmp_path, content):
    path = tmp_path / "deaths.json"
    path.write_text(content, encoding="utf-8")
    store = DeathStore(path)
    assert store.load() == 0
    assert store.warning
    assert (tmp_path / "deaths.json.uszkodzony").read_text(encoding="utf-8") == content
    assert json.loads(path.read_text(encoding="utf-8")) == {"deaths": 0}
