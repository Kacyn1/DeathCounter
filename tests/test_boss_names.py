import json

import cv2
import numpy as np
import pytest

from deathcounter import ocr
from deathcounter.attempts import AttemptLog
from deathcounter.audit import open_audit
from deathcounter.boss_names import BossNames, base_name, builtin_path, is_placeholder, same_boss
from deathcounter.bosses import BossState, BossStore, BossTracker
from deathcounter.recent_fights import RecentFights
from deathcounter.template import DeathTemplate

from .conftest import BAR_ROI, boss_frame


@pytest.fixture
def names(tmp_path):
    names = BossNames(tmp_path / "boss_names.json")
    names.load()
    return names


@pytest.fixture
def tracker(tmp_path, clock, names):
    store = BossStore(tmp_path / "bosses.json")
    store.load()
    tracker = BossTracker(store, clock, names=names)
    tracker.set_enabled(True)
    return tracker


def records(tracker):
    return {name: (r.deaths, round(r.total_time_seconds), r.status) for name, r in tracker.store.records.items()}


# --------------------------------------------------------------------- tekst OCR

def test_clean_name_skips_damage_numbers_and_noise():
    assert ocr.clean_name(["1234", "—Demon z Azylu—", "a"]) == "Demon z Azylu"
    assert ocr.clean_name(["Margit , Upadły Omen"]) == "Margit, Upadły Omen"
    assert ocr.clean_name(["Aży11.E"]) is None
    assert ocr.clean_name([]) is None


def test_normalize_ignores_case_diacritics_and_punctuation():
    assert ocr.normalize("Margit, Upadły Omen") == ocr.normalize("margit upadly omen")
    assert ocr.normalize("Demon z Ażylu") == "demon z azylu"


def test_variants_preserve_gray_letter_edges():
    band = np.full((20, 100), 25, np.uint8)
    band[5:15, 20:80] = 220
    band[5:15, 19] = 120
    images = list(ocr.variants(band))
    assert images
    assert any(np.any((im[:, :, 0] > 0) & (im[:, :, 0] < 255)) for im in images)
    assert all(im.shape[2] == 4 for im in images)


def test_naika_manual_correction_survives_reload(tracker, names, tmp_path):
    tracker.boss_bar_visible()
    tracker.boss_identified("Skorppłonłca Nałka", confident=True)
    tracker.rename("Skorpionica Naika")
    restored = BossNames(tmp_path / "boss_names.json")
    restored.load()
    assert restored.match("Skorppłonłca Nałka") == "Skorpionica Naika"
    assert tracker.current == "Skorpionica Naika"


def test_vote_prefers_most_common_reading():
    readings = ["Demon z Azylu", "Dernon z Azylu", "demon z azylu", "z Azylu", "Demon z Azylu"]
    assert ocr.vote(readings, 6) == ocr.NameReading("Demon z Azylu", True)   # 3 z 6 prób zgodne
    assert ocr.vote(readings, 18) == ocr.NameReading("Demon z Azylu", False)  # 3 z 18 – za mało
    assert ocr.vote(["Demon z Azylu"] * 2, 2) == ocr.NameReading("Demon z Azylu", False)
    assert ocr.vote([], 6) is None


def test_name_band_above_bar_clipped_to_frame():
    x0, y0, x1, y1 = ocr.name_band((2560, 1440), (795, 1173, 459, 24))
    assert (y0, y1) == (1173 - 79, 1173 - 9)
    assert x0 == 0 and x1 == 795 + 459 + 640
    assert ocr.crop_band(np.zeros((100, 100, 3), np.uint8), (10, 2, 20, 5)) is None


def test_template_locate_returns_bar_position():
    template = DeathTemplate.from_frame(boss_frame(1), BAR_ROI)
    score, rect = template.locate(boss_frame(7))
    assert score > 0.9
    assert rect == BAR_ROI


def test_windows_ocr_reads_rendered_name():
    try:
        reader = ocr.OcrReader()
    except ocr.OcrUnavailable:
        pytest.skip("brak polskiego OCR Windows")
    frame = np.full((720, 1280, 3), 25, np.uint8)
    cv2.putText(frame, "Demon z Azylu", (330, 630), cv2.FONT_HERSHEY_DUPLEX, 1.0, (225, 225, 225), 2, cv2.LINE_AA)
    assert reader.read_name([ocr.crop_band(frame, (320, 645, 400, 20))]).name == "Demon z Azylu"


# ------------------------------------------------------------------ znane nazwy

def test_helpers():
    assert base_name("Pursuer (2)") == "Pursuer"
    assert is_placeholder("Boss 3") and not is_placeholder("Boss Gundyr")
    assert same_boss("Margit", "Margit, Upadły Omen")
    assert not same_boss("Margit", "Godrick")


def test_match_corrects_ocr_typos(names):
    names.learn("Demon z Azylu")
    assert names.match("Dernon z Azylu") == "Demon z Azylu"
    assert names.match("Godrick") is None
    assert names.match("Smelter Demn", extra=["Smelter Demon (2)", "Boss 1"]) == "Smelter Demon"


def test_learn_saves_names_and_aliases(names, tmp_path):
    names.learn("Margit, Upadły Omen", reading="Mrgt Updly 0men")
    names.learn("Boss 2")  # nazwy zastępcze nie są zapamiętywane
    data = json.loads((tmp_path / "boss_names.json").read_text(encoding="utf-8"))
    assert data == {"names": ["Margit, Upadły Omen"], "aliases": {"mrgt updly 0men": "Margit, Upadły Omen"}}
    reloaded = BossNames(tmp_path / "boss_names.json")
    assert reloaded.load() is None
    assert reloaded.match("Mrgt Updly 0men") == "Margit, Upadły Omen"


@pytest.mark.parametrize("game, reading, expected", [
    ("ds1", "Dernon z Azylu", "Demon z Azylu"),
    ("ds1", "Gravel0rd Nit0", "Nito, Władca Grobów"),  # nazwa nieprzetłumaczona w grze → polska
    ("ds2", "Ostatni 0lbrzym", "Ostatni Olbrzym"),
    ("ds2", "Velstadt, Krolewska Tarcza", "Velstadt, Królewska Tarcza"),
    ("ds3", "Tancerka z Mrożnej Dolny", "Tancerka z Mroźnej Doliny"),
    ("ds3", "Midir Mrokozerca", "Midir Mrokożerca"),
    ("sekiro", "Genichiro, droga Tomo", "Genichiro, droga Tomoe"),
    ("sekiro", "Wewnetrzny Isshln", "Wewnętrzny Isshin"),
    ("eldenring", "Margit, Upadly 0men", "Margit, Upadły Omen"),
    ("eldenring", "Messmer Palovnik", "Messmer Palownik"),  # DLC
    ("eldenring", "Esgar, Krwawy Duchowy", "Esgar, Krwawy Duchowny"),
])
def test_builtin_names_match_readings_of_selected_game(tmp_path, game, reading, expected):
    names = BossNames(tmp_path / "boss_names.json", builtin_path(game))
    assert names.load() is None
    assert names.match(reading) == expected


def test_builtin_names_belong_to_their_game(tmp_path):
    names = BossNames(tmp_path / "boss_names.json", builtin_path("ds2"))
    names.load()
    assert names.match("Midir Mrokożerca") is None  # boss z DS3
    custom = BossNames(tmp_path / "boss_names.json", builtin_path("moja-gra"))
    assert custom.load() is None and custom.builtin_names == []


@pytest.mark.parametrize("game", ["ds1", "ds2", "ds3", "sekiro", "eldenring"])
def test_builtin_lists_are_valid(game):
    data = json.loads(builtin_path(game).read_text(encoding="utf-8"))
    assert len(data["names"]) == len(set(data["names"])) > 20
    assert all(key == ocr.normalize(key) and name in data["names"] for key, name in data["aliases"].items())


def test_min_ratio_decides_how_bad_reading_still_matches(tmp_path):
    names = BossNames(tmp_path / "boss_names.json", builtin_path("ds2"))
    names.load()
    reading = "Skrpnca Nka"  # podobieństwo ok. 0,7 do „Skorpionica Najka”
    assert names.match(reading) == "Skorpionica Najka"
    names.min_ratio = 0.8
    assert names.match(reading) is None
    names.min_ratio = 1.0
    assert names.match("Skorpionica Najka") == "Skorpionica Najka"
    assert names.match("Skorpionica Naika") is None


def test_default_ratio_keeps_other_games_bosses_apart(tmp_path):
    names = BossNames(tmp_path / "boss_names.json", builtin_path("ds2"))
    names.load()
    assert names.match("Demon z Azylu") is None  # boss z DS1; przy 0,5 dostałby „Demon kuźni”


def test_learned_names_extend_builtin_list(tmp_path):
    names = BossNames(tmp_path / "boss_names.json", builtin_path("ds1"))
    names.load()
    names.learn("Wiatraczek", reading="Pirnvheel")
    assert names.match("Pirnvheel") == "Wiatraczek"
    assert names.match("Pinwheel") == "Wiatraczek"


def test_broken_file_gives_warning(tmp_path):
    path = tmp_path / "boss_names.json"
    path.write_text("{", encoding="utf-8")
    names = BossNames(path)
    assert names.load() is not None
    assert names.names == []


# ------------------------------------------------------------- walka i odczyt

def test_reading_names_placeholder_boss(tracker, clock):
    tracker.boss_bar_visible()
    assert tracker.current == "Boss 1"
    assert tracker.boss_identified("Demon z Azylu") == "Demon z Azylu"
    clock.advance(10)
    assert tracker.current == "Demon z Azylu"
    assert tracker.boss_identified("Demon z Azylu") is None  # ten sam boss


def test_reading_matched_to_known_name(tracker, names):
    names.learn("Demon z Azylu")
    tracker.boss_bar_visible()
    assert tracker.boss_identified("Dernon z Azylu") == "Demon z Azylu"


def test_returning_to_same_boss_merges_attempts(tracker, clock):
    tracker.boss_bar_visible()
    tracker.boss_identified("Demon z Azylu")
    clock.advance(30)
    tracker.death()
    tracker.boss_bar_visible()
    clock.advance(5)
    assert tracker.boss_identified("Demon z Azylu") is None
    assert records(tracker) == {"Demon z Azylu": (1, 30, "W TRAKCIE")}
    assert tracker.elapsed() == pytest.approx(35)


def test_other_boss_takes_over_fight_time(tracker, clock):
    tracker.boss_bar_visible()
    tracker.boss_identified("Demon z Azylu")
    clock.advance(30)
    tracker.death()
    clock.advance(60)
    tracker.boss_bar_visible()  # wraca „Demon z Azylu”, ale na ekranie jest inny boss
    clock.advance(7)            # checkpoint co 5 s zdążył dopisać czas poprzedniemu
    tracker.tick()
    assert tracker.boss_identified("Taurus Demon") == "Taurus Demon"
    clock.advance(3)
    tracker.pause()
    assert records(tracker) == {"Demon z Azylu": (1, 30, "W TRAKCIE"), "Taurus Demon": (0, 10, "W TRAKCIE")}


def test_short_manual_name_counts_as_same_boss(tracker):
    tracker.boss_bar_visible()
    tracker.rename("Margit")
    assert tracker.boss_identified("Margit, Upadły Omen") is None
    assert tracker.current == "Margit"


def test_manual_correction_teaches_alias(tracker, names, clock):
    tracker.boss_bar_visible()
    tracker.boss_identified("Gwyn Pan Pope")
    tracker.rename("Gwyn, Pan Popiołów")
    assert names.match("Gwyn Pan Pope") == "Gwyn, Pan Popiołów"
    tracker.boss_bar_lost()
    tracker.victory()
    tracker.confirm_defeated()
    tracker.boss_bar_visible()
    assert tracker.boss_identified("Gwyn Pan Pope") == "Gwyn, Pan Popiołów (2)"


def test_confirmed_ocr_name_is_learned(tracker, names):
    tracker.boss_bar_visible()
    tracker.boss_identified("Taurus Demon")
    tracker.victory()
    tracker.confirm_defeated()
    assert names.names == ["Taurus Demon"]


def test_reading_ignored_without_fight_or_when_uncertain(tracker, clock):
    assert tracker.boss_identified("Taurus Demon") is None  # brak walki
    tracker.boss_bar_visible()
    tracker.boss_identified("Demon z Azylu")
    tracker.frames_lost()
    assert tracker.boss_identified("Taurus Demon") is None
    assert tracker.state is BossState.WAITING


# ------------------------------------------------------------ automatyczny zapis

def win(tracker, clock, reading, confident):
    tracker.boss_bar_visible()
    tracker.boss_identified(reading, confident)
    clock.advance(60)
    tracker.victory()


def test_confident_name_saved_automatically_after_victory(tracker, clock):
    win(tracker, clock, "Demon z Azylu", confident=True)
    clock.advance(1)
    assert tracker.tick() is None  # czas na „prawie jednoczesną” śmierć
    clock.advance(3)
    saved = tracker.tick().view
    assert (saved.name, saved.deaths, round(saved.seconds)) == ("Demon z Azylu", 0, 60)
    assert tracker.current is None
    assert records(tracker) == {"Demon z Azylu": (0, 60, "POKONANO")}


def test_uncertain_name_waits_for_user(tracker, clock):
    win(tracker, clock, "Den-łon z Azylu", confident=False)
    clock.advance(10)
    assert tracker.tick() is None
    assert tracker.state is BossState.DEFEATED
    assert tracker.view().name_confident is False


def test_known_name_is_confident(tracker, clock, names):
    names.learn("Demon z Azylu")
    win(tracker, clock, "Dernon z Azylu", confident=False)
    clock.advance(4)
    assert tracker.tick().view.name == "Demon z Azylu"


def test_manual_name_is_confident(tracker, clock):
    tracker.boss_bar_visible()
    tracker.rename("Gwyn")
    clock.advance(30)
    tracker.victory()
    clock.advance(4)
    assert tracker.tick().view.name == "Gwyn"


def test_placeholder_never_saved_automatically(tracker, clock):
    tracker.boss_bar_visible()
    clock.advance(30)
    tracker.victory()
    clock.advance(10)
    assert tracker.tick() is None


def test_death_right_after_victory_blocks_auto_save(tracker, clock):
    win(tracker, clock, "Demon z Azylu", confident=True)
    clock.advance(2)
    tracker.death()
    clock.advance(10)
    assert tracker.tick() is None
    assert tracker.uncertain


def test_victory_after_death_blocks_auto_save(tracker, clock):
    tracker.boss_bar_visible()
    tracker.boss_identified("Demon z Azylu", True)
    clock.advance(30)
    tracker.death()
    tracker.victory()
    clock.advance(10)
    assert tracker.tick() is None


# ------------------------------------------------ poprawianie zapisanych nazw

def _saved_game(tmp_path, game, bosses, learned=None, recent=(), attempts=None):
    """Zapisane dane gry z wcześniejszej wersji, wczytane jak przy starcie programu."""
    (tmp_path / "bosses.json").write_text(json.dumps(bosses, ensure_ascii=False), encoding="utf-8")
    if learned is not None:
        (tmp_path / "boss_names.json").write_text(json.dumps(learned, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "recent_fights.json").write_text(json.dumps(
        [{"name": n, "outcome": o, "time": 100.0 - i} for i, (n, o) in enumerate(recent)], ensure_ascii=False),
        encoding="utf-8")
    (tmp_path / "attempts.json").write_text(json.dumps(attempts or {}, ensure_ascii=False), encoding="utf-8")
    return _open_saved(tmp_path, game)


def _open_saved(tmp_path, game):
    store = BossStore(tmp_path / "bosses.json")
    store.load()
    names = BossNames(tmp_path / "boss_names.json", builtin_path(game))
    names.load()
    recent = RecentFights(tmp_path / "recent_fights.json")
    recent.load()
    attempts = AttemptLog(tmp_path / "attempts.json")
    attempts.load()
    audit, _ = open_audit(tmp_path / "audit.json", None, 0, store.records)
    return BossTracker(store, names=names, recent=recent, attempts=attempts, audit=audit)


def _entry(deaths, seconds=60, status="W TRAKCIE"):
    return {"deaths": deaths, "total_time_seconds": seconds, "status": status}


def test_saved_misread_name_gets_builtin_name_with_history(tmp_path):
    tracker = _saved_game(
        tmp_path, "ds2",
        {"Skorppłonłca Nałka": _entry(7, 300), "Ostatni Olbrzym": _entry(2, 90, "POKONANO")},
        recent=[("Skorppłonłca Nałka", "w trakcie")],
        attempts={"Skorppłonłca Nałka": [{"start": 1.0, "seconds": 40.0, "outcome": "death"}]})
    assert tracker.current == "Skorppłonłca Nałka"
    assert tracker.fix_names() == [("Skorppłonłca Nałka", "Skorpionica Najka")]
    assert tracker.current == "Skorpionica Najka"
    assert records(tracker) == {"Skorpionica Najka": (7, 300, "W TRAKCIE"), "Ostatni Olbrzym": (2, 90, "POKONANO")}
    reopened = _open_saved(tmp_path, "ds2")
    assert list(reopened.store.records) == ["Skorpionica Najka", "Ostatni Olbrzym"]
    assert [f.name for f in reopened.recent.fights] == ["Skorpionica Najka"]
    assert list(reopened.attempts.bosses) == ["Skorpionica Najka"]
    assert reopened.audit.bosses.keys() == {"Skorpionica Najka", "Ostatni Olbrzym"}
    reopened.names.min_ratio = 1.0  # stary błędny odczyt rozpoznany wprost, bez podobieństwa
    assert reopened.names.match("Skorppłonłca Nałka") == "Skorpionica Najka"


def test_two_entries_of_same_boss_are_merged_or_numbered(tmp_path):
    tracker = _saved_game(tmp_path, "ds3", {
        "Midir Mrokozerca": _entry(3, 100),
        "Midir Mrokożerca": _entry(4, 200),
        "Tancerka z Mroznej Dolny": _entry(5, 50, "POKONANO"),
        "Tancerka z Mroźnej Doliny": _entry(1, 10, "POKONANO"),
    })
    tracker.fix_names()
    assert records(tracker) == {
        "Midir Mrokożerca": (7, 300, "W TRAKCIE"),
        "Tancerka z Mroźnej Doliny (2)": (5, 50, "POKONANO"),
        "Tancerka z Mroźnej Doliny": (1, 10, "POKONANO"),
    }


def test_learned_names_are_fixed_and_old_reading_kept_as_alias(tmp_path):
    tracker = _saved_game(tmp_path, "ds2", {}, learned={
        "names": ["Skorpionica Naika", "Mój własny boss"],
        "aliases": {"skorpplonlca nalka": "Skorpionica Naika"},
    })
    tracker.fix_names()
    names = tracker.names
    assert names.names == ["Skorpionica Najka", "Mój własny boss"]
    assert names.match("Skorppłonłca Nałka") == "Skorpionica Najka"
    assert names.match("Skorpionica Naika") == "Skorpionica Najka"


def test_names_are_checked_once_per_builtin_list(tmp_path):
    tracker = _saved_game(tmp_path, "ds1", {"Gravelord Nito": _entry(1)})
    assert tracker.fix_names() == [("Gravelord Nito", "Nito, Władca Grobów")]
    tracker.rename("Gravelord Nito")  # użytkownik woli nazwę z gry
    reopened = _open_saved(tmp_path, "ds1")
    assert reopened.fix_names() == []
    assert list(reopened.store.records) == ["Gravelord Nito"]


def test_placeholders_unknown_and_correct_names_stay(tmp_path):
    tracker = _saved_game(tmp_path, "ds1", {
        "Boss 1": _entry(1), "Wiatraczek": _entry(1, status="POKONANO"), "Margit, Upadły Omen": _entry(1),
    })
    assert tracker.fix_names() == []
    custom = _saved_game(tmp_path, "moja-gra", {"Dernon z Azylu": _entry(1)})
    assert custom.fix_names() == []


def test_fix_on_demand_after_names_were_checked(tmp_path):
    tracker = _saved_game(tmp_path, "ds2", {"Ostatni Olbrzym": _entry(1)})
    assert tracker.fix_names() == []  # sprawdzenie przy wczytaniu gry – nic do poprawy
    tracker.store.records["Przeg1ly"] = tracker.store.records.pop("Ostatni Olbrzym")  # nowy błędny odczyt
    tracker.current = "Przeg1ly"
    assert tracker.fix_names() == []  # lista już sprawdzona – automatycznie nic się nie dzieje
    assert tracker.name_fixes() == [("Przeg1ly", "Przegniły")]
    assert list(tracker.store.records) == ["Przeg1ly"]  # podgląd niczego nie zmienia
    assert tracker.fix_names(force=True) == [("Przeg1ly", "Przegniły")]
    assert tracker.current == "Przegniły"
    assert tracker.name_fixes() == []
