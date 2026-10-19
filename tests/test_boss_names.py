import json

import cv2
import numpy as np
import pytest

from deathcounter import ocr
from deathcounter.boss_names import BossNames, base_name, is_placeholder, same_boss
from deathcounter.bosses import BossState, BossStore, BossTracker
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
