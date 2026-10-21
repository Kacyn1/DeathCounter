"""Aktualna sesja gry (games/<gra>/session.json): śmierci i czas, w którym gra była uruchomiona (bez Qt).

Sesja zaczyna się, gdy gra zostanie uruchomiona. Czas biegnie tylko wtedy, gdy proces gry działa, a gra jest
aktywnym oknem (nie jest zminimalizowana ani w tle po Alt+Tab). Po powrocie do gry czas rusza dopiero, gdy kolejne
sprawdzenie, RESUME_CONFIRM sekund później, potwierdzi, że gra nadal jest aktywna – wtedy te sekundy też są doliczane.
Powrót do gry w ciągu GAP_SECONDS od jej zamknięcia (np. po wysypaniu się gry) kontynuuje tę samą sesję, a czas
przerwy się nie liczy; po dłuższej przerwie uruchomienie gry zaczyna nową sesję. Sesja przetrwa ponowne
uruchomienie programu.

Każda śmierć w sesji ma zapisany czas gry, w którym nastąpiła (wykres przebiegu sesji). Gdy zaczyna się nowa sesja,
poprzednia trafia do historii (games/<gra>/session_history.json) – bez sesji krótszych niż MIN_SESSION_SECONDS
i bez śmierci (np. gra włączona i od razu zamknięta).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from .storage import atomic_write_text

GAP_SECONDS = 15 * 60  # dłuższa przerwa w grze kończy sesję
MAX_STEP = 60.0        # dłuższy odstęp między sprawdzeniami (np. uśpiony komputer) nie wlicza się do czasu
SAVE_INTERVAL = 30.0   # czas sesji zapisuje się co tyle sekund (śmierci, start i koniec gry – od razu)
RESUME_CONFIRM = 2.0   # tyle sekund gra musi być na ekranie po przywróceniu, zanim czas ruszy (i zostanie doliczony)
MIN_SESSION_SECONDS = 60.0  # krótsza sesja bez śmierci nie trafia do historii


@dataclass(frozen=True)
class SessionRecord:
    """Zakończona sesja w historii."""

    started: float
    ended: float    # ostatnia chwila, w której gra działała
    seconds: float  # czas gry (bez pauz)
    deaths: int


@dataclass(frozen=True)
class SessionView:
    deaths: int
    seconds: float
    running: bool       # gra jest teraz uruchomiona
    background: bool    # uruchomiona, ale w tle (inne okno jest aktywne) – czas stoi
    continues: bool     # gra zamknięta, ale powrót w ciągu GAP_SECONDS kontynuuje sesję
    started: float | None


class PlaySession:
    def __init__(self, path: Path, history_path: Path | None = None) -> None:
        self.path = Path(path)
        self.history_path = Path(history_path) if history_path else self.path.with_name("session_history.json")
        self.started: float | None = None   # początek sesji (czas Uniksa); None – jeszcze nie było sesji
        self.last_seen = 0.0                # ostatnia chwila, w której gra działała
        self.seconds = 0.0
        self.deaths = 0
        self.death_times: list[float] = []  # czas gry w sesji (s) przy kolejnych śmierciach; wcześniejsze – bez czasu
        self.history: list[SessionRecord] = []
        self.running = False
        self.background = False
        self._counting = False                # czas biegnie od ostatniego sprawdzenia
        self._resume_at: float | None = None  # gra wróciła na ekran o tej chwili – czeka na potwierdzenie
        self._saved_at = 0.0
        self.load()
        self.history = load_history(self.history_path)

    def load(self) -> None:
        """Uszkodzony albo brakujący plik oznacza po prostu brak sesji – następna zacznie się od zera."""
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            started, last_seen = float(data["started"]), float(data["last_seen"])
            seconds, deaths = float(data["seconds"]), int(data["deaths"])
            times = sorted(float(t) for t in data.get("death_times", []) if 0 <= float(t) <= seconds)
        except (OSError, ValueError, KeyError, TypeError):
            return
        if seconds >= 0 and deaths >= 0 and started <= last_seen:
            self.started, self.last_seen, self.seconds, self.deaths = started, last_seen, seconds, deaths
            self.death_times = times[-deaths:] if deaths else []

    def save(self) -> None:
        if self.started is None:
            return
        data = {"started": self.started, "last_seen": self.last_seen, "seconds": round(self.seconds, 1),
                "deaths": self.deaths, "death_times": [round(t, 1) for t in self.death_times]}
        atomic_write_text(self.path, json.dumps(data, indent=2) + "\n")
        self._saved_at = time.monotonic()

    def tick(self, running: bool, now: float, background: bool = False) -> bool:
        """Stan gry z kolejnego sprawdzenia procesów. Zwraca True, gdy właśnie zaczęła się nowa sesja.
        StorageError, gdy nie udało się zapisać (stan w pamięci jest już zmieniony; zapis ponowi kolejne sprawdzenie)."""
        new = False
        changed = running != self.running or background != self.background
        if not running:
            self._counting, self._resume_at = False, None
        elif self.started is None or now - self.last_seen > GAP_SECONDS:
            self._archive()
            self.started, self.seconds, self.deaths, new = now, 0.0, 0, True
            self.death_times = []
            self._counting, self._resume_at = not background, None
        elif background:
            self._counting, self._resume_at = False, None
        elif self._counting:
            self.seconds += _step(now - self.last_seen)
        elif self._resume_at is None:
            # Powrót do gry (aktywne okno gry, ponowne uruchomienie gry albo programu) – czekamy na potwierdzenie.
            self._resume_at = now
        elif now - self._resume_at >= RESUME_CONFIRM:
            self.seconds += _step(now - self._resume_at)
            self._counting, self._resume_at = True, None
        if running:
            self.last_seen = now
        self.running, self.background = running, running and background
        if new or changed or (running and time.monotonic() - self._saved_at >= SAVE_INTERVAL):
            self.save()
        return new

    def stop(self, now: float) -> None:
        """Koniec śledzenia (zmiana gry, zamknięcie programu, wyłączenie opcji): czas do tej chwili zostaje zapisany."""
        if self._counting:
            self.seconds += _step(now - self.last_seen)
            self.last_seen = now
        self.running = self.background = self._counting = False
        self._resume_at = None
        self.save()

    def add_deaths(self, delta: int, now: float | None = None) -> None:
        """Zmiana ogólnego licznika: liczy się do sesji tylko przy uruchomionej grze. Śmierć dostaje czas gry
        w sesji (w chwili `now`, domyślnie ostatniego sprawdzenia gry); cofnięcie (−1) usuwa ostatnią."""
        if not (self.running and delta):
            return
        if delta > 0:
            self.death_times.extend([self.view(self.last_seen if now is None else now).seconds] * delta)
        else:
            del self.death_times[max(0, len(self.death_times) + delta):]
        self.deaths = max(0, self.deaths + delta)
        self.death_times = self.death_times[-self.deaths:] if self.deaths else []
        self.save()

    def reset_deaths(self) -> None:
        if self.started is not None and self.deaths:
            self.deaths = 0
            self.death_times = []
            self.save()

    def _archive(self) -> None:
        """Poprzednia sesja trafia do historii (zanim zacznie się nowa)."""
        if self.started is None or (self.seconds < MIN_SESSION_SECONDS and not self.deaths):
            return
        self.history.append(SessionRecord(self.started, self.last_seen, round(self.seconds, 1), self.deaths))
        data = [{"started": r.started, "ended": r.ended, "seconds": r.seconds, "deaths": r.deaths} for r in self.history]
        atomic_write_text(self.history_path, json.dumps(data, indent=2) + "\n")

    def view(self, now: float) -> SessionView:
        seconds = self.seconds + (_step(now - self.last_seen) if self._counting else 0.0)
        continues = (not self.running and self.started is not None and now - self.last_seen <= GAP_SECONDS)
        return SessionView(self.deaths, seconds, self.running, self.background, continues, self.started)


def load_history(path: Path) -> list[SessionRecord]:
    """Zakończone sesje od najstarszej. Uszkodzony plik – pusta historia (pomijane są też pojedyncze złe wpisy)."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    records = []
    for entry in data if isinstance(data, list) else []:
        try:
            record = SessionRecord(float(entry["started"]), float(entry["ended"]), float(entry["seconds"]),
                                   int(entry["deaths"]))
        except (KeyError, TypeError, ValueError):
            continue
        if record.seconds >= 0 and record.deaths >= 0:
            records.append(record)
    return sorted(records, key=lambda record: record.started)


def _step(seconds: float) -> float:
    return min(max(0.0, seconds), MAX_STEP)

