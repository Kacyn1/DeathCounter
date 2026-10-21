"""Aktualna sesja gry (games/<gra>/session.json): śmierci i czas, w którym gra była uruchomiona (bez Qt).

Sesja zaczyna się, gdy gra zostanie uruchomiona. Czas biegnie tylko wtedy, gdy proces gry działa, a gra jest
aktywnym oknem (nie jest zminimalizowana ani w tle po Alt+Tab). Po powrocie do gry czas rusza dopiero, gdy kolejne
sprawdzenie, RESUME_CONFIRM sekund później, potwierdzi, że gra nadal jest aktywna – wtedy te sekundy też są doliczane.
Powrót do gry w ciągu GAP_SECONDS od jej zamknięcia (np. po wysypaniu się gry) kontynuuje tę samą sesję, a czas
przerwy się nie liczy; po dłuższej przerwie uruchomienie gry zaczyna nową sesję. Sesja przetrwa ponowne
uruchomienie programu.
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


@dataclass(frozen=True)
class SessionView:
    deaths: int
    seconds: float
    running: bool       # gra jest teraz uruchomiona
    background: bool    # uruchomiona, ale w tle (inne okno jest aktywne) – czas stoi
    continues: bool     # gra zamknięta, ale powrót w ciągu GAP_SECONDS kontynuuje sesję
    started: float | None


class PlaySession:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.started: float | None = None   # początek sesji (czas Uniksa); None – jeszcze nie było sesji
        self.last_seen = 0.0                # ostatnia chwila, w której gra działała
        self.seconds = 0.0
        self.deaths = 0
        self.running = False
        self.background = False
        self._counting = False                # czas biegnie od ostatniego sprawdzenia
        self._resume_at: float | None = None  # gra wróciła na ekran o tej chwili – czeka na potwierdzenie
        self._saved_at = 0.0
        self.load()

    def load(self) -> None:
        """Uszkodzony albo brakujący plik oznacza po prostu brak sesji – następna zacznie się od zera."""
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            started, last_seen = float(data["started"]), float(data["last_seen"])
            seconds, deaths = float(data["seconds"]), int(data["deaths"])
        except (OSError, ValueError, KeyError, TypeError):
            return
        if seconds >= 0 and deaths >= 0 and started <= last_seen:
            self.started, self.last_seen, self.seconds, self.deaths = started, last_seen, seconds, deaths

    def save(self) -> None:
        if self.started is None:
            return
        data = {"started": self.started, "last_seen": self.last_seen, "seconds": round(self.seconds, 1),
                "deaths": self.deaths}
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
            self.started, self.seconds, self.deaths, new = now, 0.0, 0, True
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

    def add_deaths(self, delta: int) -> None:
        """Zmiana ogólnego licznika: liczy się do sesji tylko przy uruchomionej grze."""
        if self.running and delta:
            self.deaths = max(0, self.deaths + delta)
            self.save()

    def reset_deaths(self) -> None:
        if self.started is not None and self.deaths:
            self.deaths = 0
            self.save()

    def view(self, now: float) -> SessionView:
        seconds = self.seconds + (_step(now - self.last_seen) if self._counting else 0.0)
        continues = (not self.running and self.started is not None and now - self.last_seen <= GAP_SECONDS)
        return SessionView(self.deaths, seconds, self.running, self.background, continues, self.started)


def _step(seconds: float) -> float:
    return min(max(0.0, seconds), MAX_STEP)

