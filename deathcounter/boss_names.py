"""Znane nazwy bossów jednej gry (games/<gra>/boss_names.json), uzupełniane z każdą walką.

OCR myli pojedyncze litery, więc odczyt dopasowujemy do najbliższej znanej nazwy. Lista rośnie sama:
nazwa zatwierdzona wynikiem albo poprawiona ręcznie trafia do pliku, a błędny odczyt, który
poprawiłeś, zostaje zapamiętany jako jej odmiana (alias) – następnym razem od razu da właściwą nazwę.
"""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from pathlib import Path

from .ocr import normalize
from .storage import atomic_write_text

MATCH_RATIO = 0.8  # minimalne podobieństwo odczytu do znanej nazwy
_NUMBERED = re.compile(r"^(.*) \(\d+\)$")
_PLACEHOLDER = re.compile(r"^Boss \d+$")


def base_name(name: str) -> str:
    """„Pursuer (2)” → „Pursuer” – kolejne podejście do pokonanego bossa to wciąż ten sam boss."""
    match = _NUMBERED.match(name)
    return match.group(1) if match else name


def is_placeholder(name: str) -> bool:
    """Nazwa nadana przez program, zanim poznał prawdziwą („Boss 1”)."""
    return bool(_PLACEHOLDER.match(name))


def same_boss(a: str, b: str) -> bool:
    """Ta sama nazwa po normalizacji, także gdy jedna jest skrótem drugiej („Margit” i „Margit, Upadły Omen”)."""
    a, b = normalize(base_name(a)), normalize(base_name(b))
    return bool(a and b) and (a == b or a in b or b in a)


class BossNames:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.names: list[str] = []
        self.aliases: dict[str, str] = {}  # znormalizowany błędny odczyt → nazwa

    def load(self) -> str | None:
        """Wczytuje plik; uszkodzony pomija (lista zbuduje się od nowa) i zwraca ostrzeżenie."""
        self.names, self.aliases = [], {}
        if not self.path.exists():
            return None
        try:
            data = json.loads(self.path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            return f"Nie można odczytać {self.path.name} ({exc}); lista znanych bossów zacznie się od nowa."
        if isinstance(data, dict):
            names = data.get("names")
            aliases = data.get("aliases")
            if isinstance(names, list):
                self.names = [n for n in names if isinstance(n, str) and n.strip()]
            if isinstance(aliases, dict):
                self.aliases = {k: v for k, v in aliases.items() if isinstance(k, str) and isinstance(v, str)}
        return None

    def save(self) -> None:
        data = {"names": self.names, "aliases": self.aliases}
        atomic_write_text(self.path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    def match(self, text: str, extra: list[str] = ()) -> str | None:
        """Znana nazwa najbliższa odczytowi OCR albo None. `extra` – np. nazwy z bosses.json."""
        key = normalize(text)
        if not key:
            return None
        if key in self.aliases:
            return self.aliases[key]
        candidates = {normalize(n): n for n in (*extra, *self.names) if not is_placeholder(n)}
        candidates.update(self.aliases)
        best, best_ratio = None, MATCH_RATIO
        for known, name in candidates.items():
            ratio = SequenceMatcher(None, key, known).ratio()
            if ratio >= best_ratio:
                best, best_ratio = base_name(name), ratio
        return best

    def learn(self, name: str, reading: str | None = None) -> None:
        """Zapamiętuje nazwę i – gdy różni się od odczytu OCR – ten odczyt jako jej odmianę.
        StorageError przy błędzie zapisu."""
        name = base_name(" ".join(name.split()))
        if not name or is_placeholder(name):
            return
        changed = False
        if not any(normalize(n) == normalize(name) for n in self.names):
            self.names.append(name)
            changed = True
        if reading and normalize(reading) and normalize(reading) != normalize(name):
            if self.aliases.get(normalize(reading)) != name:
                self.aliases[normalize(reading)] = name
                changed = True
        if changed:
            self.save()
