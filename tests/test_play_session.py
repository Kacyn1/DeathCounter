import json

from deathcounter.bosses import overlay_text
from deathcounter.play_session import (
    GAP_SECONDS,
    LOADING,
    LOADING_FALLBACK,
    MAX_STEP,
    MENU,
    PLAYING,
    GamePhase,
    PlaySession,
)

START = 1_800_000_000.0


def play(session, start, seconds, step=2.0):
    """Gra uruchomiona przez `seconds` sekund, sprawdzana co `step`; zwraca chwilę końca."""
    now = start
    while now < start + seconds:
        session.tick(True, now)
        now += step
    session.tick(True, now)
    return now


def test_session_starts_with_game_and_counts_only_running_time(tmp_path):
    session = PlaySession(tmp_path / "session.json")
    assert session.started is None
    session.tick(False, START)              # program włączony, gra jeszcze nie
    assert session.started is None
    assert session.tick(True, START + 100)  # gra uruchomiona – nowa sesja
    end = play(session, START + 100, 600)
    assert session.seconds == 600
    session.tick(False, end + 2)            # gra zamknięta
    assert session.view(end + 300).seconds == 600
    assert session.view(end + 300).continues


def test_short_break_continues_session_without_counting_it(tmp_path):
    session = PlaySession(tmp_path / "session.json")
    end = play(session, START, 60)
    session.add_deaths(3)
    session.tick(False, end + 2)
    assert not session.tick(True, end + 10 * 60)  # wysypana gra, powrót po 10 min
    assert session.seconds == 60 and session.deaths == 3
    play(session, end + 10 * 60, 30)
    assert session.seconds == 90


def test_long_break_starts_new_session(tmp_path):
    session = PlaySession(tmp_path / "session.json")
    end = play(session, START, 60)
    session.add_deaths(2)
    session.tick(False, end + 2)
    assert not session.view(end + GAP_SECONDS + 1).continues
    assert session.tick(True, end + GAP_SECONDS + 1)
    assert session.seconds == 0 and session.deaths == 0


def test_sleeping_computer_does_not_add_hours(tmp_path):
    session = PlaySession(tmp_path / "session.json")
    session.tick(True, START)
    session.tick(True, START + 10)
    session.tick(True, START + 10 + 600)  # 10 min bez sprawdzenia (uśpienie) – gra „działa” dalej
    assert session.seconds == 10 + MAX_STEP


def test_background_game_pauses_time_and_restore_is_confirmed(tmp_path):
    session = PlaySession(tmp_path / "session.json")
    end = play(session, START, 100)                  # 100 s gry
    session.tick(True, end + 2, background=True)      # zminimalizowana albo Alt+Tab
    assert session.view(end + 2).background
    session.tick(True, end + 300, background=True)    # 5 min na pulpicie – nie liczy się
    assert session.view(end + 300).seconds == 100
    session.tick(True, end + 302)                    # przywrócona – czeka na potwierdzenie
    assert session.view(end + 303).seconds == 100
    session.tick(True, end + 304)                    # po 2 s nadal na ekranie: czas rusza, te 2 s są doliczone
    assert session.seconds == 102
    session.tick(True, end + 306)
    assert session.seconds == 104


def test_restore_without_confirmation_adds_nothing(tmp_path):
    session = PlaySession(tmp_path / "session.json")
    end = play(session, START, 100)
    session.tick(True, end + 2, background=True)
    session.tick(True, end + 4)                      # przywrócona na chwilę…
    session.tick(True, end + 6, background=True)      # …i znowu w tle przed potwierdzeniem
    session.tick(True, end + 8)
    assert session.seconds == 100


def test_long_background_game_keeps_session(tmp_path):
    session = PlaySession(tmp_path / "session.json")
    end = play(session, START, 100)
    session.add_deaths(2)
    for now in range(int(end) + 2, int(end) + GAP_SECONDS * 2, 2):  # pół godziny w tle – gra działa
        assert not session.tick(True, now, background=True)
    assert session.deaths == 2 and session.seconds == 100


def test_session_started_in_background_waits_for_game_on_screen(tmp_path):
    session = PlaySession(tmp_path / "session.json")
    assert session.tick(True, START, background=True)
    session.tick(True, START + 10, background=True)
    session.tick(True, START + 12)
    session.tick(True, START + 14)
    assert session.seconds == 2


def test_deaths_count_only_while_game_runs(tmp_path):
    session = PlaySession(tmp_path / "session.json")
    session.add_deaths(1)                 # ręczne +1 przed uruchomieniem gry
    assert session.deaths == 0
    session.tick(True, START)
    session.add_deaths(1)
    session.add_deaths(1)
    session.add_deaths(-1)
    session.add_deaths(-5)                # nie schodzi poniżej zera
    assert session.deaths == 0
    session.add_deaths(4)
    session.reset_deaths()
    assert session.deaths == 0


def test_session_survives_program_restart(tmp_path):
    path = tmp_path / "session.json"
    session = PlaySession(path)
    end = play(session, START, 120)
    session.add_deaths(5)
    session.stop(end + 1)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["deaths"] == 5 and saved["seconds"] == 121

    again = PlaySession(path)               # program uruchomiony ponownie, gra działa dalej
    assert not again.tick(True, end + 30)
    play(again, end + 30, 10)
    assert again.deaths == 5 and again.seconds == 131


def test_broken_file_means_no_session(tmp_path):
    path = tmp_path / "session.json"
    for text in ("{", '{"started": 5, "last_seen": 1, "seconds": 0, "deaths": 0}', '{"deaths": -1}', "[]"):
        path.write_text(text, encoding="utf-8")
        assert PlaySession(path).started is None


def test_overlay_shows_session_line(tmp_path):
    session = PlaySession(tmp_path / "session.json")
    end = play(session, START, 3724)
    session.add_deaths(12)
    assert overlay_text(40, None, session.view(end)) == "DEATHS: 40\nSesja: 12 · 01:02:04"
    assert overlay_text(40, None) == "DEATHS: 40"


def test_death_times_follow_play_time(tmp_path):
    session = PlaySession(tmp_path / "session.json")
    end = play(session, START, 100)
    session.add_deaths(1, end)
    end = play(session, end, 50)
    session.add_deaths(2, end)
    assert session.death_times == [100, 150, 150]
    session.add_deaths(-1, end)                      # cofnięcie usuwa ostatnią
    assert session.death_times == [100, 150] and session.deaths == 2
    session.stop(end)
    again = PlaySession(tmp_path / "session.json")  # czasy przetrwają ponowne uruchomienie programu
    assert again.death_times == [100, 150]
    again.reset_deaths()
    assert again.death_times == []


def test_old_session_file_without_death_times(tmp_path):
    path = tmp_path / "session.json"
    path.write_text('{"started": 1, "last_seen": 100, "seconds": 90, "deaths": 4}', encoding="utf-8")
    session = PlaySession(path)
    assert session.deaths == 4 and session.death_times == []


def test_finished_session_goes_to_history(tmp_path):
    session = PlaySession(tmp_path / "session.json")
    end = play(session, START, 600)
    session.add_deaths(5)
    session.tick(False, end + 2)
    assert session.tick(True, end + GAP_SECONDS + 10)  # nowa sesja – poprzednia trafia do historii
    assert [(r.started, r.seconds, r.deaths) for r in session.history] == [(START, 600, 5)]
    assert session.death_times == []
    reloaded = PlaySession(tmp_path / "session.json")
    assert [(r.started, r.ended, r.deaths) for r in reloaded.history] == [(START, end, 5)]


def test_short_empty_session_is_not_kept(tmp_path):
    session = PlaySession(tmp_path / "session.json")
    end = play(session, START, 30)                     # gra włączona na pół minuty, bez śmierci
    session.tick(False, end + 2)
    session.tick(True, end + GAP_SECONDS + 10)
    assert session.history == []
    end = play(session, end + GAP_SECONDS + 10, 30)  # krótka, ale ze śmiercią – zostaje
    session.add_deaths(1)
    session.tick(False, end + 2)
    session.tick(True, end + GAP_SECONDS + 10)
    assert len(session.history) == 1


def test_broken_history_file(tmp_path):
    history = tmp_path / "session_history.json"
    history.write_text('[{"started": 1, "ended": 2, "seconds": 60, "deaths": 3}, {"started": "x"}, 5]', encoding="utf-8")
    assert [r.deaths for r in PlaySession(tmp_path / "session.json").history] == [3]
    history.write_text("{", encoding="utf-8")
    assert PlaySession(tmp_path / "session.json").history == []



def test_phase_menu_loading_then_health_bar():
    phase = GamePhase()
    phase.restart(0)
    assert phase.phase == LOADING                         # logo wydawcy po uruchomieniu gry
    assert phase.update(False, False, 5) is None
    assert phase.update(True, False, 20) == "discard"    # menu: logo nie było grą
    assert phase.phase == MENU
    assert phase.update(False, False, 60) is None         # „Kontynuuj” – wczytywanie
    assert phase.phase == LOADING
    assert phase.update(False, True, 75) == "discard"    # pasek zdrowia: rozgrywka, wczytywanie się nie liczy
    assert phase.phase == PLAYING
    assert phase.update(False, False, 300) is None        # pasek znika (ukryty interfejs) – gra trwa
    assert phase.phase == PLAYING
    assert phase.update(True, False, 400) is None         # powrót do menu
    assert phase.phase == MENU


def test_phase_without_health_bar_starts_after_menu():
    phase = GamePhase()
    phase.restart(0)
    phase.update(True, None, 10)
    assert phase.update(False, None, 30) == "credit"      # bez wzorca paska: gra zaraz po menu
    assert phase.phase == PLAYING


def test_phase_fallback_when_health_bar_never_shows():
    phase = GamePhase()
    phase.restart(0)                                      # program uruchomiony w trakcie gry, interfejs ukryty
    assert phase.update(False, False, LOADING_FALLBACK - 1) is None
    assert phase.update(False, False, LOADING_FALLBACK) == "credit"
    assert phase.phase == PLAYING


def test_phase_without_menu_template_is_always_play():
    phase = GamePhase()
    phase.restart(0)
    phase.update(None, True, 1)
    assert phase.phase == PLAYING


def test_game_time_excludes_menu_and_loading(tmp_path):
    session = PlaySession(tmp_path / "session.json")
    session.tick(True, START, phase=MENU)
    now = START
    for _ in range(30):                                   # minuta w menu
        now += 2
        session.tick(True, now, phase=MENU)
    for _ in range(10):                                   # 20 s wczytywania
        now += 2
        session.tick(True, now, phase=LOADING)
    session.resolve_loading(False)                        # pasek zdrowia – to było wczytywanie
    for _ in range(50):                                   # 100 s gry
        now += 2
        session.tick(True, now, phase=PLAYING)
    view = session.view(now)
    assert view.seconds == 180 and view.game_seconds == 98   # pierwsze 2 s gry przypadają jeszcze wczytywaniu
    session.stop(now)
    again = PlaySession(tmp_path / "session.json")
    assert again.game_seconds == 98


def test_loading_credited_when_gameplay_confirmed_late(tmp_path):
    session = PlaySession(tmp_path / "session.json")
    session.tick(True, START, phase=LOADING)
    session.tick(True, START + 2, phase=LOADING)
    session.tick(True, START + 4, phase=LOADING)
    session.resolve_loading(True)
    assert session.game_seconds == 4


def test_old_files_count_whole_session_as_game_time(tmp_path):
    (tmp_path / "session.json").write_text('{"started": 1, "last_seen": 900, "seconds": 600, "deaths": 2}',
                                           encoding="utf-8")
    (tmp_path / "session_history.json").write_text('[{"started": 1, "ended": 2, "seconds": 300, "deaths": 1}]',
                                                   encoding="utf-8")
    session = PlaySession(tmp_path / "session.json")
    assert session.game_seconds == 600 and session.history[0].game_seconds == 300
