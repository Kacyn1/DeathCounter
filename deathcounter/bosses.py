"""Walka z bossem: łączny czas i śmierci na bossa, zapis w bosses.json (bez Qt, łatwe do testowania).

Program sam prowadzi walkę na podstawie zdarzeń z wykrywania:
pasek bossa widoczny → Walka (timer biegnie), napis śmierci → Śmierć (pauza),
pasek znów widoczny → Walka (ten sam boss), komunikat zwycięstwa → Boss pokonany (timer stoi).
Użytkownik tylko zatwierdza wynik („Zapisz wynik” – status POKONANO) albo odrzuca pomyłkę.
"""

from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable

from . import attempts as attempt_log
from . import recent_fights
from .attempts import Attempt, AttemptLog
from .boss_names import BossNames, is_placeholder, same_boss
from .recent_fights import RecentFights
from .storage import StorageError, atomic_write_text

Clock = Callable[[], float]

STATUS_IN_PROGRESS = "W TRAKCIE"
STATUS_DEFEATED = "POKONANO"
STATUSES = (STATUS_IN_PROGRESS, STATUS_DEFEATED)

CHECKPOINT_SECONDS = 5.0      # w trakcie walki zgromadzony czas trafia do pliku co tyle sekund
DEATH_GRACE_SECONDS = 10.0    # pasek znika przy śmierci wcześniej niż pojawia się napis śmierci
SIMULTANEOUS_SECONDS = 3.0    # śmierć i zwycięstwo tak blisko siebie = wynik niepewny
AUTO_SAVE_SECONDS = SIMULTANEOUS_SECONDS  # wynik zapisuje się sam dopiero, gdy minie czas na „prawie jednoczesną” śmierć
ABANDON_SECONDS = 15.0        # pasek zniknął i przez tyle sekund nie było śmierci ani zwycięstwa = opuszczenie areny


class BossState(Enum):
    WAITING = "Oczekiwanie"
    FIGHT = "Walka"
    DEATH = "Śmierć"
    DEFEATED = "Boss pokonany"


@dataclass
class FightEnd:
    """Walka zakończona przez program sam: wynik zapisany automatycznie albo walka przerwana."""

    view: "BossView"
    abandoned: bool


@dataclass
class RecentRow:
    """Wiersz listy ostatnich walk w panelu."""

    name: str
    outcome: str      # recent_fights.IN_PROGRESS / ABANDONED / DEFEATED
    deaths: int
    seconds: float
    time: float       # chwila ostatniej zmiany (sekundy od epoki)


@dataclass
class BossRecord:
    deaths: int = 0
    total_time_seconds: float = 0.0
    status: str = STATUS_IN_PROGRESS

    def to_dict(self) -> dict:
        return {
            "deaths": self.deaths,
            "total_time_seconds": int(self.total_time_seconds),
            "status": self.status,
        }


@dataclass
class BossView:
    """Stan bieżącej walki do pokazania w panelu i nakładce."""

    name: str
    deaths: int
    seconds: float
    state: BossState
    uncertain: str | None
    name_confident: bool = True  # nazwa wpisana ręcznie, znana albo pewnie odczytana z ekranu


class BossStore:
    """bosses.json: { "Nazwa": { "deaths": N, "total_time_seconds": S, "status": "W TRAKCIE" | "POKONANO" } }."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.records: dict[str, BossRecord] = {}
        self.warning: str | None = None

    def load(self) -> None:
        """Brakujący plik oznacza brak bossów. Uszkodzony plik jest odkładany jako bosses.json.uszkodzony."""
        self.warning = None
        self.records = {}
        if not self.path.exists():
            return
        try:
            raw = self.path.read_text(encoding="utf-8-sig")
        except OSError as exc:
            raise StorageError(f"Nie można odczytać pliku {self.path.name}: {exc}") from exc
        try:
            self.records = _parse_bosses(raw)
        except ValueError as exc:
            backup = self.path.with_name(self.path.name + ".uszkodzony")
            try:
                os.replace(self.path, backup)
            except OSError as move_exc:
                raise StorageError(
                    f"Plik {self.path.name} jest uszkodzony ({exc}) i nie można go odłożyć: {move_exc}"
                ) from move_exc
            self.warning = (
                f"Plik {self.path.name} był uszkodzony ({exc}). Jego kopię zapisano jako "
                f"{backup.name}, a lista bossów zaczyna się od nowa."
            )

    def save(self) -> None:
        data = {name: record.to_dict() for name, record in self.records.items()}
        atomic_write_text(self.path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


class BossTracker:
    """Maszyna stanów walki z bossem. Każda metoda zdarzenia zapisuje plik, gdy coś się zmieniło.

    Błąd zapisu (StorageError) przechodzi do wywołującego; stan w pamięci zostaje,
    a kolejna zmiana ponowi zapis.
    """

    def __init__(self, store: BossStore, clock: Clock = time.monotonic, audit=None,
                 names: BossNames | None = None, recent: RecentFights | None = None,
                 attempts: AttemptLog | None = None, wall: Clock = time.time) -> None:
        self.store = store
        self.attempts = attempts  # historia pojedynczych prób (okno „Wyniki”)
        self._wall = wall         # zegar ścienny – godzina rozpoczęcia próby
        self._attempt: Attempt | None = None  # trwająca próba bieżącego bossa (zapisywana po zakończeniu)
        self.audit = audit  # rejestr zmian (audit.AuditLog) – ręczne korekty i zmiany nazw
        self.names = names  # znane nazwy bossów gry – do dopasowania odczytu OCR
        self.recent = recent  # ostatnie walki pokazywane w panelu
        self.abandon_enabled = False  # przerywanie walki po opuszczeniu areny (wymaga wzorca zwycięstwa)
        self._clock = clock
        self.enabled = False
        self.state = BossState.WAITING
        self.current: str | None = None
        self.uncertain: str | None = None
        self._fight_started: float | None = None
        self._last_checkpoint = 0.0
        self._bar_lost_at: float | None = None
        self._death_at: float | None = None
        self._victory_at: float | None = None
        self._last_death_counted = False
        self._segment_started: float | None = None  # początek bieżącego odcinka walki (od pojawienia się paska)
        self._reading: str | None = None            # ostatni odczyt OCR nazwy bieżącego bossa
        # Po restarcie wracamy do niezakończonej walki; timer nie biegnie, dopóki pasek się nie pojawi.
        # Przerwana walka (opuszczona arena) nie wraca – boss wróci, gdy pasek pojawi się znowu.
        pending = [name for name, r in store.records.items() if r.status == STATUS_IN_PROGRESS
                   and (recent is None or recent.outcome(name) != recent_fights.ABANDONED)]
        self.current = pending[-1] if pending else None
        self.name_confident = self.current is not None and not is_placeholder(self.current)

    # ------------------------------------------------------------- odczyt

    @property
    def record(self) -> BossRecord | None:
        return self.store.records.get(self.current) if self.current is not None else None

    def elapsed(self) -> float:
        record = self.record
        if record is None:
            return 0.0
        running = self._clock() - self._fight_started if self._fight_started is not None else 0.0
        return record.total_time_seconds + running

    def view(self) -> BossView | None:
        record = self.record
        if record is None:
            return None
        return BossView(self.current, record.deaths, self.elapsed(), self.state, self.uncertain, self.name_confident)

    def attempts_for(self, name: str) -> list[Attempt]:
        """Próby bossa od najstarszej; trwająca próba bieżącego bossa (W toku) na końcu, z czasem na żywo."""
        attempts = list(self.attempts.bosses.get(name, [])) if self.attempts is not None else []
        if name == self.current and self._attempt is not None:
            running = self._clock() - self._fight_started if self._fight_started is not None else 0.0
            attempts.append(Attempt(self._attempt.start, self._attempt.seconds + running, attempt_log.IN_PROGRESS))
        return attempts

    def recent_rows(self, limit: int = 3) -> list[RecentRow]:
        """Ostatnie walki poza bieżącą (ta jest pokazywana osobno), od najnowszej."""
        rows = []
        for fight in self.recent.fights if self.recent is not None else []:
            record = self.store.records.get(fight.name)
            if record is None or fight.name == self.current:
                continue  # boss usunięty albo przemianowany
            outcome = recent_fights.DEFEATED if record.status == STATUS_DEFEATED else fight.outcome
            rows.append(RecentRow(fight.name, outcome, record.deaths, record.total_time_seconds, fight.time))
            if len(rows) == limit:
                break
        return rows

    # ---------------------------------------------------- zdarzenia z gry

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        if not enabled and self.state is BossState.FIGHT:
            self._pause(BossState.WAITING)
            self._end_attempt(attempt_log.STOPPED)
            self._save()

    def boss_bar_visible(self) -> None:
        """Pasek zdrowia bossa potwierdzony na obrazie: start albo wznowienie walki."""
        if not self.enabled or self.uncertain or self.state in (BossState.FIGHT, BossState.DEFEATED):
            return
        if self.record is None:
            self.current = self._placeholder_name()
            self.store.records[self.current] = BossRecord()
            self.name_confident = False
        if self._attempt is None:  # pasek wrócił bez śmierci (np. po przerywniku) – ta sama próba trwa dalej
            self._attempt = Attempt(self._wall(), 0.0, attempt_log.IN_PROGRESS)
        self.state = BossState.FIGHT
        self._fight_started = self._last_checkpoint = self._segment_started = self._clock()
        self._bar_lost_at = None
        self._save()

    def boss_identified(self, reading: str, confident: bool = False) -> str | None:
        """Nazwa odczytana z ekranu (OCR) chwilę po pojawieniu się paska. Zwraca nową nazwę bieżącego
        bossa albo None, gdy nic się nie zmieniło. `confident` – większość prób OCR dała ten sam tekst;
        pewna jest też nazwa dopasowana do znanej i zgodna z nazwą bieżącego bossa.

        - boss bez nazwy („Boss 1”) dostaje odczytaną nazwę (dopasowaną do znanych nazw gry);
        - ten sam boss – bez zmian;
        - inny boss w trakcie walki – walka przechodzi na niego razem z czasem od pojawienia się paska,
          a poprzedni zostaje w pliku jako niepokonany.
        """
        reading = " ".join(reading.split())
        if not reading or not self.enabled or self.record is None or self.uncertain:
            return None
        known = self.names.match(reading, list(self.store.records)) if self.names is not None else None
        name = known or reading
        if same_boss(name, self.current):
            self._reading = reading
            self.name_confident = True  # odczyt potwierdza nazwę, którą boss już ma
            return None
        if is_placeholder(self.current):
            self._reading = reading
            self.name_confident = confident or known is not None
            return self._rename(name)
        if self.state is not BossState.FIGHT or self._segment_started is None:
            return None
        self._switch_to(name)
        self._reading = reading
        self.name_confident = confident or known is not None
        return self.current

    def boss_bar_lost(self) -> None:
        """Pasek zniknął bez śmierci i bez zwycięstwa (np. ucieczka z areny) – sama pauza."""
        if self.state is BossState.FIGHT:
            self._pause(BossState.WAITING)
            self._bar_lost_at = self._clock()
            self._save()

    def death(self) -> bool:
        """Napis śmierci. Zwraca True, gdy śmierć doliczono także bossowi (ogólny licznik rośnie zawsze)."""
        self._last_death_counted = False
        if not self.enabled or self.record is None:
            return False
        now = self._clock()
        if self.state is BossState.FIGHT:
            self._pause(BossState.DEATH)
        elif self.state is BossState.WAITING and self._recently(self._bar_lost_at):
            self.state = BossState.DEATH
        elif self.state is BossState.DEFEATED and self._recently(self._victory_at, SIMULTANEOUS_SECONDS):
            self.uncertain = "Śmierć i komunikat zwycięstwa prawie jednocześnie – zatwierdź wynik."
        else:
            return False
        self._death_at = now
        self.record.deaths += 1
        self._last_death_counted = True
        self._end_attempt(attempt_log.DEATH)
        self._save()
        return True

    def victory(self) -> None:
        """Komunikat zwycięstwa potwierdzony: timer staje na stałe, wynik czeka na zatwierdzenie."""
        if not self.enabled or self.record is None:
            return
        if self.state is BossState.FIGHT:
            self._pause(BossState.DEFEATED)
        elif self.state is BossState.DEATH:
            self.uncertain = "Komunikat zwycięstwa po śmierci – zatwierdź wynik albo kontynuuj walkę."
        elif not (self.state is BossState.WAITING and (self._recently(self._bar_lost_at) or self.uncertain)):
            return
        self.state = BossState.DEFEATED
        self._victory_at = self._clock()
        self._end_attempt(attempt_log.VICTORY)
        self._save()

    def frames_lost(self) -> None:
        """Utrata obrazu w trakcie walki: timer staje, wynik wymaga potwierdzenia."""
        if self.state is BossState.FIGHT:
            self._pause(BossState.WAITING)
            self.uncertain = "Utracono obraz w trakcie walki – kontynuuj walkę albo zatwierdź wynik."
            self._save()

    def tick(self) -> FightEnd | None:
        """Wywoływane co sekundę: w trakcie walki co kilka sekund zapisuje zgromadzony czas.

        - Po zwycięstwie zapisuje wynik sam, gdy nic nie budzi wątpliwości: nazwa jest pewna, wynik nie czeka
          na decyzję, a od komunikatu zwycięstwa minął czas na „prawie jednoczesną” śmierć.
        - Gdy pasek zniknął i przez ABANDON_SECONDS nie było ani śmierci, ani zwycięstwa, gracz opuścił arenę:
          walka jest przerwana, a boss zostaje w pliku „W TRAKCIE” (z dotychczasowymi śmierciami i czasem).
        Zwraca zakończoną walkę albo None."""
        now = self._clock()
        if self.state is BossState.FIGHT and now - self._last_checkpoint >= CHECKPOINT_SECONDS:
            self._checkpoint()
            self._save()
        if (self.state is BossState.DEFEATED and self.name_confident and not self.uncertain
                and self._victory_at is not None and now - self._victory_at > AUTO_SAVE_SECONDS):
            view = self.view()
            self.confirm_defeated()
            return FightEnd(view, abandoned=False)
        if (self.abandon_enabled and self.state is BossState.WAITING and self.record is not None
                and not self.uncertain and self._bar_lost_at is not None
                and now - self._bar_lost_at >= ABANDON_SECONDS):
            view = self.view()
            if self.recent is not None:
                self.recent.touch(self.current, recent_fights.ABANDONED)
            self._end_attempt(attempt_log.ABANDONED)
            self._clear_current()
            self._save()
            return FightEnd(view, abandoned=True)
        return None

    def pause(self) -> None:
        """Zatrzymanie wykrywania lub zamknięcie programu: czas walki zostaje zapisany, a timer staje,
        bo bez analizy obrazu nikt nie zgłosi śmierci ani zniknięcia paska."""
        if self.state is BossState.FIGHT:
            self._pause(BossState.WAITING)
            self._save()
        self._end_attempt(attempt_log.STOPPED)  # nie wiadomo, co działo się dalej
        self._bar_lost_at = None  # bez wykrywania nie da się stwierdzić, że gracz opuścił arenę

    # ------------------------------------------------------- akcje użytkownika

    def confirm_defeated(self) -> None:
        """„Zapisz wynik”: ostateczny wynik ze statusem POKONANO, bieżący boss znika z panelu."""
        record = self.record
        if record is None:
            return
        if self.state is BossState.FIGHT:
            self._pause(BossState.DEFEATED)
        if self._attempt is not None:
            self._end_attempt(attempt_log.VICTORY)
        elif self.uncertain and self.attempts is not None:
            # „Komunikat zwycięstwa po śmierci” zatwierdzony jako wygrana – ostatnia próba to zwycięstwo.
            self.attempts.set_last_outcome(self.current, attempt_log.VICTORY, only_if=(attempt_log.DEATH,))
        record.status = STATUS_DEFEATED
        if self.names is not None:
            self.names.learn(self.current)  # zatwierdzona nazwa – także ta odczytana z ekranu
        if self.recent is not None:
            self.recent.touch(self.current, recent_fights.DEFEATED)
        self._clear_current()
        self._save()

    def continue_fight(self) -> None:
        """Wynik niepewny okazał się zwykłą śmiercią lub przerwą – walka z tym bossem trwa dalej."""
        if self.record is None or not self.uncertain:
            return
        self.uncertain = None
        died = self._death_at is not None and self._last_death_counted
        if died and self.attempts is not None:
            # Śmierć tuż po komunikacie zwycięstwa – próba skończyła się śmiercią, nie wygraną.
            self.attempts.set_last_outcome(self.current, attempt_log.DEATH, only_if=(attempt_log.VICTORY,))
        self.state = BossState.DEATH if died else BossState.WAITING
        self._victory_at = None
        self._save()

    def discard(self) -> None:
        """Pomyłka (fałszywy start): wpis znika z pliku bez zapisu wyniku."""
        if self.current is None:
            return
        self.store.records.pop(self.current, None)
        if self.recent is not None:
            self.recent.remove(self.current)
        if self.attempts is not None:
            self.attempts.remove(self.current)
        self._clear_current()
        self._save()

    def mark_defeated(self, name: str) -> None:
        """Walka z listy ostatnich (np. przerwana) była w rzeczywistości wygraną, której program nie wykrył."""
        record = self.store.records.get(name)
        if record is None or name == self.current:
            return
        record.status = STATUS_DEFEATED
        if self.names is not None:
            self.names.learn(name)
        if self.recent is not None:
            self.recent.set_outcome(name, recent_fights.DEFEATED)
        if self.attempts is not None:
            self.attempts.set_last_outcome(name, attempt_log.VICTORY,
                                           only_if=(attempt_log.ABANDONED, attempt_log.STOPPED))
        self._save()

    def remove(self, name: str) -> None:
        """Usuwa bossa z listy ostatnich walk i z pliku (np. fałszywy start przy bossie w otwartym świecie)."""
        if name == self.current:
            self.discard()
            return
        if self.store.records.pop(name, None) is None:
            return
        if self.recent is not None:
            self.recent.remove(name)
        if self.attempts is not None:
            self.attempts.remove(name)
        self._save()

    def rename(self, name: str) -> str | None:
        """Nazwa wpisana ręcznie. Program ją zapamiętuje, a ostatni odczyt OCR – jako jej odmianę,
        żeby następnym razem od razu rozpoznać bossa. Zwraca nazwę po zmianie."""
        name = " ".join(name.split())
        if self.names is not None and self.record is not None and name:
            self.names.learn(name, self._reading)
        if self.record is not None and name:
            self.name_confident = True
        return self._rename(name)

    def _rename(self, name: str) -> str | None:
        """Nadaje nazwę bieżącemu bossowi. Istniejący niepokonany boss o tej nazwie jest scalany z bieżącym,
        a pokonany dostaje nowy wpis z numerem, np. „Smelter Demon (2)”. Zwraca nazwę po zmianie."""
        name = " ".join(name.split())
        record = self.record
        if record is None or not name or name == self.current:
            return self.current
        records = self.store.records
        existing = records.get(name)
        if existing is not None and existing.status == STATUS_IN_PROGRESS:
            existing.deaths += record.deaths
            existing.total_time_seconds += record.total_time_seconds
            del records[self.current]
        else:
            if existing is not None:
                name = _numbered(name, records)
            self.store.records = {(name if key == self.current else key): value for key, value in records.items()}
        if self.audit is not None:
            self.audit.boss_renamed(self.current, name)
        if self.attempts is not None:
            self.attempts.rename(self.current, name)
        self.current = name
        self._save()
        return name

    def manual_add(self) -> None:
        """Ręczne +1 (przeoczona śmierć) w trakcie walki liczy się także bossowi."""
        self._last_death_counted = False
        if self.record is not None and self.state in (BossState.FIGHT, BossState.DEATH):
            self.record.deaths += 1
            self._last_death_counted = True
            if self._attempt is not None:
                self._checkpoint()
                self._end_attempt(attempt_log.MANUAL_DEATH)
                if self.state is BossState.FIGHT:  # walka trwa – liczy się kolejna próba
                    self._attempt = Attempt(self._wall(), 0.0, attempt_log.IN_PROGRESS)
            self._save(manual=True)

    def manual_undo(self) -> None:
        """Ręczne −1 cofa także śmierć bossa, jeśli ostatnia doliczona śmierć była przy bossie."""
        record = self.record
        if self._last_death_counted and record is not None and record.deaths > 0:
            record.deaths -= 1
            self._last_death_counted = False
            if self.attempts is not None:
                self.attempts.set_last_outcome(self.current, attempt_log.CANCELLED,
                                               only_if=(attempt_log.DEATH, attempt_log.MANUAL_DEATH))
            self._save(manual=True)

    # ------------------------------------------------------------ wewnętrzne

    def _pause(self, state: BossState) -> None:
        self._checkpoint()
        self._fight_started = None
        self.state = state

    def _checkpoint(self) -> None:
        record = self.record
        if record is not None and self._fight_started is not None:
            now = self._clock()
            delta = max(0.0, now - self._fight_started)
            record.total_time_seconds += delta
            if self._attempt is not None:
                self._attempt.seconds += delta
            self._fight_started = self._last_checkpoint = now

    def _switch_to(self, name: str) -> None:
        """Bieżąca walka to inny boss: czas od pojawienia się paska przechodzi na niego."""
        self._checkpoint()
        moved = max(0.0, self._clock() - self._segment_started)
        old = self.record
        old.total_time_seconds = max(0.0, old.total_time_seconds - moved)
        if self._attempt is not None:
            # Część próby sprzed pojawienia się paska (gdy pasek wrócił bez śmierci) należy do poprzedniego bossa.
            earlier = self._attempt.seconds - moved
            if earlier >= 1.0 and self.attempts is not None:
                self.attempts.add(self.current, Attempt(self._attempt.start, round(earlier, 1),
                                                        attempt_log.ABANDONED))
            self._attempt = Attempt(self._wall() - moved, moved, attempt_log.IN_PROGRESS)
        records = self.store.records
        existing = records.get(name)
        if existing is None or existing.status != STATUS_IN_PROGRESS:
            if existing is not None:
                name = _numbered(name, records)
            records[name] = BossRecord()
        self.current = name
        self.record.total_time_seconds += moved
        self._last_death_counted = False
        self._death_at = None
        self._save()

    def _clear_current(self) -> None:
        self.current = None
        self.state = BossState.WAITING
        self.uncertain = None
        self._fight_started = self._bar_lost_at = self._death_at = self._victory_at = None
        self._segment_started = self._reading = None
        self._last_death_counted = False
        self.name_confident = False
        self._attempt = None

    def _end_attempt(self, outcome: str) -> None:
        """Kończy trwającą próbę bieżącego bossa i zapisuje ją w historii."""
        attempt, self._attempt = self._attempt, None
        if attempt is not None and self.attempts is not None and self.current is not None:
            self.attempts.add(self.current, Attempt(attempt.start, round(attempt.seconds, 1), outcome))

    def _recently(self, moment: float | None, seconds: float = DEATH_GRACE_SECONDS) -> bool:
        return moment is not None and self._clock() - moment <= seconds

    def _placeholder_name(self) -> str:
        number = 1
        while f"Boss {number}" in self.store.records:
            number += 1
        return f"Boss {number}"

    def _save(self, manual: bool = False) -> None:
        self.store.save()
        if self.recent is not None and self.current is not None:
            self.recent.touch(self.current, recent_fights.IN_PROGRESS)
        if self.audit is not None:
            self.audit.bosses_saved(self.store.records, self.current if manual else None)
            self.audit.save()


def format_duration(seconds: float) -> str:
    """Czas zawsze jako GG:MM:SS, np. 00:12:38 (powyżej 99 godzin godzin jest więcej cyfr)."""
    total = int(seconds)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def overlay_text(deaths: int, boss: BossView | None) -> str:
    """Wspólny tekst nakładki-okna i RTSS. Po zwycięstwie zostaje sam ogólny licznik."""
    lines = [f"DEATHS: {deaths}"]
    if boss is not None and boss.state is not BossState.DEFEATED:
        lines.append(f"{boss.name} — deaths: {boss.deaths}")
        lines.append(f"Czas: {format_duration(boss.seconds)}")
    return "\n".join(lines)


def _numbered(name: str, records: dict[str, BossRecord]) -> str:
    number = 2
    while f"{name} ({number})" in records:
        number += 1
    return f"{name} ({number})"


def _parse_bosses(raw: str) -> dict[str, BossRecord]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("niepoprawny JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("oczekiwano obiektu JSON")
    records = {}
    for name, entry in data.items():
        if not isinstance(entry, dict):
            raise ValueError(f"wpis „{name}” nie jest obiektem")
        deaths, seconds, status = entry.get("deaths"), entry.get("total_time_seconds"), entry.get("status")
        if isinstance(deaths, bool) or not isinstance(deaths, int) or deaths < 0:
            raise ValueError(f"„{name}”: pole \"deaths\" nie jest liczbą nieujemną")
        if (
            isinstance(seconds, bool)
            or not isinstance(seconds, (int, float))
            or not math.isfinite(seconds)
            or seconds < 0
        ):
            raise ValueError(f"„{name}”: pole \"total_time_seconds\" nie jest liczbą nieujemną")
        if status not in STATUSES:
            raise ValueError(f"„{name}”: nieznany status {status!r}")
        records[name] = BossRecord(deaths, float(seconds), status)
    return records
