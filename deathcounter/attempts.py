"""Historia pojedynczych prób walki z bossem (games/<gra>/attempts.json), pokazywana w oknie „Wyniki”.

Próba trwa od pojawienia się paska do śmierci, zwycięstwa albo przerwania. Pasek, który zniknie na chwilę
i wróci bez śmierci (np. przerywnik między fazami), to wciąż ta sama próba. Czas próby to czas walki
(tak jak łączny czas bossa) – bez przerw, gdy paska nie było.
Osobny plik, a nie część bosses.json: starsze wersje programu i certyfikat czytają bosses.json bez zmian.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from .storage import atomic_write_text

DEATH = "death"
MANUAL_DEATH = "manual_death"   # ręczne +1 w trakcie walki (przeoczona śmierć)
VICTORY = "victory"
ABANDONED = "abandoned"         # opuszczenie areny
STOPPED = "stopped"             # zatrzymanie wykrywania albo zamknięcie programu w trakcie próby
CANCELLED = "cancelled"         # śmierć cofnięta ręcznym −1
IN_PROGRESS = "in_progress"     # trwająca próba (tylko w pamięci, nie w pliku)
OUTCOMES = (DEATH, MANUAL_DEATH, VICTORY, ABANDONED, STOPPED, CANCELLED)

LABELS = {
    DEATH: "Śmierć",
    MANUAL_DEATH: "Śmierć (ręcznie)",
    VICTORY: "Zwycięstwo",
    ABANDONED: "Przerwano (opuszczono arenę)",
    STOPPED: "Przerwano (zatrzymano wykrywanie)",
    CANCELLED: "Cofnięto (−1)",
    IN_PROGRESS: "W toku",
}


@dataclass
class Attempt:
    start: float     # początek próby (sekundy od epoki)
    seconds: float   # czas walki w tej próbie
    outcome: str


class AttemptLog:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.bosses: dict[str, list[Attempt]] = {}  # boss → próby od najstarszej

    def load(self) -> str | None:
        self.bosses = {}
        if not self.path.exists():
            return None
        try:
            data = json.loads(self.path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            return f"Nie można odczytać {self.path.name} ({exc}); historia prób zacznie się od nowa."
        if isinstance(data, dict):
            for name, entries in data.items():
                if not isinstance(name, str) or not isinstance(entries, list):
                    continue
                attempts = [
                    Attempt(float(e["start"]), float(e["seconds"]), e["outcome"])
                    for e in entries
                    if isinstance(e, dict) and e.get("outcome") in OUTCOMES
                    and all(isinstance(e.get(k), (int, float)) and not isinstance(e.get(k), bool)
                            for k in ("start", "seconds"))
                ]
                if attempts:
                    self.bosses[name] = attempts
        return None

    def save(self) -> None:
        data = {name: [asdict(a) for a in attempts] for name, attempts in self.bosses.items()}
        atomic_write_text(self.path, json.dumps(data, indent=1, ensure_ascii=False) + "\n")

    def add(self, name: str, attempt: Attempt) -> None:
        self.bosses.setdefault(name, []).append(attempt)
        self.save()

    def last(self, name: str) -> Attempt | None:
        attempts = self.bosses.get(name)
        return attempts[-1] if attempts else None

    def set_last_outcome(self, name: str, outcome: str, only_if: tuple[str, ...]) -> None:
        """Poprawia wynik ostatniej próby bossa, jeśli jest jednym z `only_if` (np. przerwana okazała się wygraną)."""
        last = self.last(name)
        if last is not None and last.outcome in only_if and last.outcome != outcome:
            last.outcome = outcome
            self.save()

    def rename(self, old: str, new: str) -> None:
        """Zmiana nazwy bossa; przy scaleniu z istniejącym bossem próby łączą się w kolejności czasu."""
        attempts = self.bosses.pop(old, None)
        if attempts is None:
            return
        self.bosses[new] = sorted(self.bosses.get(new, []) + attempts, key=lambda a: a.start)
        self.save()

    def remove(self, name: str) -> None:
        if self.bosses.pop(name, None) is not None:
            self.save()


def format_when(timestamp: float) -> str:
    """„dziś 19:42” albo „18.10 21:05”."""
    moment = datetime.fromtimestamp(timestamp)
    return f"dziś {moment:%H:%M}" if moment.date() == datetime.now().date() else f"{moment:%d.%m %H:%M}"


def summary(attempts: list[Attempt]) -> str:
    """„Próby: 23 · średnio 01:42 · najdłuższa 04:10 · pokonany w 23. próbie” (czas w GG:MM:SS)."""
    from .bosses import format_duration

    if not attempts:
        return "Brak zapisanych prób – historia prób zbiera się od wersji 1.8.0."
    times = [a.seconds for a in attempts]
    parts = [f"Próby: {len(attempts)}", f"średnio {format_duration(sum(times) / len(times))}",
             f"najdłuższa {format_duration(max(times))}"]
    won = next((i for i, a in enumerate(attempts, 1) if a.outcome == VICTORY), None)
    if won is not None:
        parts.append(f"pokonany w {won}. próbie")
    return " · ".join(parts)
