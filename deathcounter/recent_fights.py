"""Ostatnie walki z bossami jednej gry (games/<gra>/recent_fights.json), pokazywane w panelu walki.

Osobny plik, a nie nowy status w bosses.json: przerwana walka zostaje w bosses.json „W TRAKCIE”,
więc starsze wersje programu i certyfikat czytają plik bez zmian.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from .storage import atomic_write_text

IN_PROGRESS = "w trakcie"
ABANDONED = "przerwano"   # pasek zniknął bez śmierci i bez zwycięstwa – gracz opuścił arenę
DEFEATED = "pokonano"
OUTCOMES = (IN_PROGRESS, ABANDONED, DEFEATED)
KEEP = 10  # tyle walk zostaje w pliku; panel pokazuje kilka ostatnich


@dataclass
class RecentFight:
    name: str
    outcome: str
    time: float  # chwila ostatniej zmiany (sekundy od epoki)


class RecentFights:
    def __init__(self, path: Path, wall: Callable[[], float] = time.time) -> None:
        self.path = Path(path)
        self._wall = wall
        self.fights: list[RecentFight] = []  # od najnowszej

    def load(self) -> str | None:
        self.fights = []
        if not self.path.exists():
            return None
        try:
            data = json.loads(self.path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            return f"Nie można odczytać {self.path.name} ({exc}); lista ostatnich walk zacznie się od nowa."
        if isinstance(data, list):
            for entry in data:
                if (isinstance(entry, dict) and isinstance(entry.get("name"), str)
                        and entry.get("outcome") in OUTCOMES and isinstance(entry.get("time"), (int, float))):
                    self.fights.append(RecentFight(entry["name"], entry["outcome"], float(entry["time"])))
        return None

    def save(self) -> None:
        atomic_write_text(self.path, json.dumps([asdict(f) for f in self.fights], indent=2, ensure_ascii=False) + "\n")

    def outcome(self, name: str) -> str | None:
        return next((f.outcome for f in self.fights if f.name == name), None)

    def touch(self, name: str, outcome: str) -> None:
        """Walka z bossem `name` jest najnowsza i ma podany wynik. Zapisuje plik, gdy coś się zmieniło."""
        if self.fights and self.fights[0].name == name and self.fights[0].outcome == outcome:
            return
        self.fights = [RecentFight(name, outcome, self._wall())] + [f for f in self.fights if f.name != name]
        del self.fights[KEEP:]
        self.save()

    def set_outcome(self, name: str, outcome: str) -> None:
        """Zmienia wynik walki bez przesuwania jej na początek listy."""
        for fight in self.fights:
            if fight.name == name and fight.outcome != outcome:
                fight.outcome = outcome
                self.save()

    def rename(self, old: str, new: str) -> None:
        """Zmiana nazwy bossa; przy scaleniu z istniejącym zostaje nowsza walka."""
        if not any(f.name == old for f in self.fights):
            return
        fights: list[RecentFight] = []
        for fight in self.fights:  # od najnowszej
            if fight.name == old:
                fight.name = new
            if not any(f.name == fight.name for f in fights):
                fights.append(fight)
        self.fights = fights
        self.save()

    def remove(self, name: str) -> None:
        if any(f.name == name for f in self.fights):
            self.fights = [f for f in self.fights if f.name != name]
            self.save()
