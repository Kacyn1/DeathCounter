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

from .storage import StorageError, atomic_write_text

Clock = Callable[[], float]

STATUS_IN_PROGRESS = "W TRAKCIE"
STATUS_DEFEATED = "POKONANO"
STATUSES = (STATUS_IN_PROGRESS, STATUS_DEFEATED)

CHECKPOINT_SECONDS = 5.0      # w trakcie walki zgromadzony czas trafia do pliku co tyle sekund
DEATH_GRACE_SECONDS = 10.0    # pasek znika przy śmierci wcześniej niż pojawia się napis śmierci
SIMULTANEOUS_SECONDS = 3.0    # śmierć i zwycięstwo tak blisko siebie = wynik niepewny


class BossState(Enum):
    WAITING = "Oczekiwanie"
    FIGHT = "Walka"
    DEATH = "Śmierć"
    DEFEATED = "Boss pokonany"


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

    def __init__(self, store: BossStore, clock: Clock = time.monotonic, audit=None) -> None:
        self.store = store
        self.audit = audit  # rejestr zmian (audit.AuditLog) – ręczne korekty i zmiany nazw
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
        # Po restarcie wracamy do niezakończonej walki; timer nie biegnie, dopóki pasek się nie pojawi.
        pending = [name for name, r in store.records.items() if r.status == STATUS_IN_PROGRESS]
        self.current = pending[-1] if pending else None

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
        return BossView(self.current, record.deaths, self.elapsed(), self.state, self.uncertain)

    # ---------------------------------------------------- zdarzenia z gry

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        if not enabled and self.state is BossState.FIGHT:
            self._pause(BossState.WAITING)
            self._save()

    def boss_bar_visible(self) -> None:
        """Pasek zdrowia bossa potwierdzony na obrazie: start albo wznowienie walki."""
        if not self.enabled or self.uncertain or self.state in (BossState.FIGHT, BossState.DEFEATED):
            return
        if self.record is None:
            self.current = self._placeholder_name()
            self.store.records[self.current] = BossRecord()
        self.state = BossState.FIGHT
        self._fight_started = self._last_checkpoint = self._clock()
        self._bar_lost_at = None
        self._save()

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
        self._save()

    def frames_lost(self) -> None:
        """Utrata obrazu w trakcie walki: timer staje, wynik wymaga potwierdzenia."""
        if self.state is BossState.FIGHT:
            self._pause(BossState.WAITING)
            self.uncertain = "Utracono obraz w trakcie walki – kontynuuj walkę albo zatwierdź wynik."
            self._save()

    def tick(self) -> None:
        """Wywoływane co sekundę: w trakcie walki co kilka sekund zapisuje zgromadzony czas."""
        if self.state is BossState.FIGHT and self._clock() - self._last_checkpoint >= CHECKPOINT_SECONDS:
            self._checkpoint()
            self._save()

    def pause(self) -> None:
        """Zatrzymanie wykrywania lub zamknięcie programu: czas walki zostaje zapisany, a timer staje,
        bo bez analizy obrazu nikt nie zgłosi śmierci ani zniknięcia paska."""
        if self.state is BossState.FIGHT:
            self._pause(BossState.WAITING)
            self._save()

    # ------------------------------------------------------- akcje użytkownika

    def confirm_defeated(self) -> None:
        """„Zapisz wynik”: ostateczny wynik ze statusem POKONANO, bieżący boss znika z panelu."""
        record = self.record
        if record is None:
            return
        if self.state is BossState.FIGHT:
            self._pause(BossState.DEFEATED)
        record.status = STATUS_DEFEATED
        self._clear_current()
        self._save()

    def continue_fight(self) -> None:
        """Wynik niepewny okazał się zwykłą śmiercią lub przerwą – walka z tym bossem trwa dalej."""
        if self.record is None or not self.uncertain:
            return
        self.uncertain = None
        self.state = BossState.DEATH if self._death_at is not None and self._last_death_counted else BossState.WAITING
        self._victory_at = None
        self._save()

    def discard(self) -> None:
        """Pomyłka (fałszywy start): wpis znika z pliku bez zapisu wyniku."""
        if self.current is None:
            return
        self.store.records.pop(self.current, None)
        self._clear_current()
        self._save()

    def rename(self, name: str) -> str | None:
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
        self.current = name
        self._save()
        return name

    def manual_add(self) -> None:
        """Ręczne +1 (przeoczona śmierć) w trakcie walki liczy się także bossowi."""
        self._last_death_counted = False
        if self.record is not None and self.state in (BossState.FIGHT, BossState.DEATH):
            self.record.deaths += 1
            self._last_death_counted = True
            self._save(manual=True)

    def manual_undo(self) -> None:
        """Ręczne −1 cofa także śmierć bossa, jeśli ostatnia doliczona śmierć była przy bossie."""
        record = self.record
        if self._last_death_counted and record is not None and record.deaths > 0:
            record.deaths -= 1
            self._last_death_counted = False
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
            record.total_time_seconds += max(0.0, now - self._fight_started)
            self._fight_started = self._last_checkpoint = now

    def _clear_current(self) -> None:
        self.current = None
        self.state = BossState.WAITING
        self.uncertain = None
        self._fight_started = self._bar_lost_at = self._death_at = self._victory_at = None
        self._last_death_counted = False

    def _recently(self, moment: float | None, seconds: float = DEATH_GRACE_SECONDS) -> bool:
        return moment is not None and self._clock() - moment <= seconds

    def _placeholder_name(self) -> str:
        number = 1
        while f"Boss {number}" in self.store.records:
            number += 1
        return f"Boss {number}"

    def _save(self, manual: bool = False) -> None:
        self.store.save()
        if self.audit is not None:
            self.audit.bosses_saved(self.store.records, self.current if manual else None)
            self.audit.save()


def format_duration(seconds: float) -> str:
    total = int(seconds)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


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
