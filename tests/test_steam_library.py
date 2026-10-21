import io
import json
import urllib.error
import urllib.parse

import pytest

from deathcounter import steam_library
from deathcounter.steam_library import (
    BUILTIN,
    LIST,
    MAYBE,
    SOULSLIKE_TAG,
    TAG,
    SteamError,
    SteamGame,
    classify,
    clean_name,
    fetch_tags,
    installed_games,
    library_folders,
    parse_vdf,
    scan,
)

LIES_OF_P, HOLLOW_KNIGHT, DOTA, DS3 = 1627720, 367520, 570, 374320


def test_parse_vdf_nested_values_and_escapes():
    text = '''"libraryfolders"
{
	// komentarz
	"0"
	{
		"path"		"C:\\\\Program Files (x86)\\\\Steam"
		"label"		"say \\"hi\\""
		"apps" { "570" "123" }
	}
}'''
    data = parse_vdf(text)
    entry = data["libraryfolders"]["0"]
    assert entry["path"] == r"C:\Program Files (x86)\Steam"
    assert entry["label"] == 'say "hi"'
    assert entry["apps"] == {"570": "123"}


@pytest.mark.parametrize("text", ['"a" { "b" "c"', '"a" "b" }', '{ "b" "c" }', '"a" ?', '"a"'])
def test_parse_vdf_rejects_broken_files(text):
    with pytest.raises(ValueError):
        parse_vdf(text)


def manifest(folder, appid, name):
    steamapps = folder / "steamapps"
    steamapps.mkdir(parents=True, exist_ok=True)
    (steamapps / f"appmanifest_{appid}.acf").write_text(
        f'"AppState"\n{{\n\t"appid"\t\t"{appid}"\n\t"name"\t\t"{name}"\n\t"installdir"\t\t"x"\n}}\n', encoding="utf-8")


def steam_with_two_libraries(tmp_path):
    steam, other = tmp_path / "Steam", tmp_path / "D" / "SteamLibrary"
    manifest(steam, DS3, "DARK SOULS™ III")
    manifest(steam, DOTA, "Dota 2")
    manifest(other, LIES_OF_P, "Lies of P")
    path = str(other).replace("\\", "\\\\")
    (steam / "steamapps" / "libraryfolders.vdf").write_text(
        f'"libraryfolders"\n{{\n\t"0" {{ "path" "{str(steam).replace(chr(92), chr(92) * 2)}" }}\n'
        f'\t"1" {{ "path" "{path}" }}\n}}\n', encoding="utf-8")
    return steam


def test_installed_games_from_all_libraries(tmp_path):
    steam = steam_with_two_libraries(tmp_path)
    assert library_folders(steam) == [steam, tmp_path / "D" / "SteamLibrary"]
    assert installed_games(steam) == [
        SteamGame(DS3, "DARK SOULS III"), SteamGame(DOTA, "Dota 2"), SteamGame(LIES_OF_P, "Lies of P")]


def test_broken_manifest_is_skipped(tmp_path):
    steam = tmp_path / "Steam"
    manifest(steam, LIES_OF_P, "Lies of P")
    (steam / "steamapps" / "appmanifest_1.acf").write_text('"AppState" { "name" "Bez numeru" }', encoding="utf-8")
    (steam / "steamapps" / "appmanifest_2.acf").write_text('"AppState" {', encoding="utf-8")
    assert installed_games(steam) == [SteamGame(LIES_OF_P, "Lies of P")]


def test_clean_name():
    assert clean_name("  REMNANT  II® ") == "REMNANT II"
    assert clean_name("Sekiro™: Shadows Die Twice") == "Sekiro: Shadows Die Twice"


class FakeStore:
    """Sklep Steam: AppID → tagi; zapamiętuje zapytania."""

    def __init__(self, tags):
        self.tags = tags
        self.queries = []

    def __call__(self, request, timeout):
        query = json.loads(urllib.parse.parse_qs(urllib.parse.urlparse(request.full_url).query)["input_json"][0])
        self.queries.append([item["appid"] for item in query["ids"]])
        items = [{"appid": appid, "tagids": self.tags[appid]} if appid in self.tags else {"appid": appid, "success": 2}
                 for appid in self.queries[-1]]
        return io.BytesIO(json.dumps({"response": {"store_items": items}}).encode())


def test_fetch_tags_in_batches():
    store = FakeStore({appid: [SOULSLIKE_TAG] for appid in range(1, 151)})
    tags = fetch_tags(list(range(1, 151)), store)
    assert [len(query) for query in store.queries] == [100, 50]
    assert tags[150] == [SOULSLIKE_TAG]


def test_fetch_tags_errors():
    def offline(request, timeout):
        raise urllib.error.URLError("brak sieci")

    with pytest.raises(SteamError, match="Brak połączenia"):
        fetch_tags([1], offline)
    with pytest.raises(SteamError, match="Nieczytelna"):
        fetch_tags([1], lambda request, timeout: io.BytesIO(b"<html>"))


ARMORED_CORE, DEAD_CELLS, RONIN, TAILS_OF_IRON = 1888160, 588650, 1340990, 1283410


def test_classify_by_tag_position():
    # Miejsca tagu „Souls-like” jak w sklepie Steam (październik 2026).
    games = [SteamGame(ARMORED_CORE, "ARMORED CORE VI"), SteamGame(DS3, "DARK SOULS III"),
             SteamGame(DEAD_CELLS, "Dead Cells"), SteamGame(DOTA, "Dota 2"),
             SteamGame(HOLLOW_KNIGHT, "Hollow Knight"), SteamGame(RONIN, "Rise of the Ronin"),
             SteamGame(TAILS_OF_IRON, "Tails of Iron")]
    tags = {ARMORED_CORE: [1] * 7 + [SOULSLIKE_TAG], DEAD_CELLS: [1] * 7 + [SOULSLIKE_TAG],
            DOTA: [1, 2], RONIN: [1] * 10 + [SOULSLIKE_TAG], TAILS_OF_IRON: [1, 2, SOULSLIKE_TAG],
            HOLLOW_KNIGHT: [1] * 10 + [SOULSLIKE_TAG]}  # znana gra: wbudowana lista ma pierwszeństwo przed tagiem
    found = classify(games, tags)
    assert [(item.game.name, item.source) for item in found] == [
        ("DARK SOULS III", BUILTIN), ("Hollow Knight", LIST), ("Tails of Iron", TAG),
        ("ARMORED CORE VI", MAYBE), ("Dead Cells", MAYBE)]


def test_classify_offline_uses_known_list():
    games = [SteamGame(LIES_OF_P, "Lies of P"), SteamGame(DOTA, "Dota 2")]
    assert [(item.game.appid, item.source) for item in classify(games, None)] == [(LIES_OF_P, LIST)]


def test_scan_asks_store_only_about_other_games(tmp_path):
    steam = steam_with_two_libraries(tmp_path)
    store = FakeStore({LIES_OF_P: [SOULSLIKE_TAG], DOTA: [1]})
    result = scan(steam, store)
    assert store.queries == [[DOTA, LIES_OF_P]]  # DS3 jest wbudowana – bez pytania sklepu
    assert result.installed == 3
    assert [(item.game.name, item.source) for item in result.found] == [("DARK SOULS III", BUILTIN), ("Lies of P", LIST)]
    assert result.online_error == ""


def test_scan_offline_falls_back_to_known_list(tmp_path):
    steam = steam_with_two_libraries(tmp_path)

    def offline(request, timeout):
        raise OSError("brak sieci")

    result = scan(steam, offline)
    assert [item.source for item in result.found] == [BUILTIN, LIST]
    assert "Brak połączenia" in result.online_error


def test_scan_without_steam(monkeypatch):
    monkeypatch.setattr(steam_library, "find_steam", lambda: None)
    with pytest.raises(SteamError, match="Nie znaleziono Steama"):
        scan()
