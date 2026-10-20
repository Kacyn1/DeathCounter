"""Znane nazwy bossów jednej gry (games/<gra>/boss_names.json), uzupełniane z każdą walką.

OCR myli pojedyncze litery, więc odczyt dopasowujemy do najbliższej znanej nazwy. Gry wbudowane mają
od początku listę nazw z plików gry w parach polska–angielska (data/boss_names/<gra>.json): odczyt
w dowolnym z tych języków daje nazwę w języku programu. Lista rośnie sama:
nazwa zatwierdzona wynikiem albo poprawiona ręcznie trafia do pliku, a błędny odczyt, który
poprawiłeś, zostaje zapamiętany jako jej odmiana (alias) – następnym razem od razu da właściwą nazwę.
"""

from __future__ import annotations

import hashlib
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

from .ocr import normalize
from .storage import atomic_write_text
from . import i18n
from .i18n import tr

MATCH_RATIO = 0.6  # domyślne minimalne podobieństwo odczytu do znanej nazwy (ustawienie name_match_ratio)
BUILTIN_DIR = Path(__file__).resolve().parent / "data" / "boss_names"
_NUMBERED = re.compile(r"^(.*) \(\d+\)$")
_PLACEHOLDER = re.compile(r"^Boss \d+$")


def builtin_path(game: str) -> Path:
    """Wbudowana lista nazw bossów gry (dla gier dodanych przez użytkownika plik nie istnieje)."""
    return BUILTIN_DIR / f"{game}.json"


def _read(path: Path) -> tuple[list[str], dict[str, str]]:
    """Nazwy i aliasy z pliku; OSError/ValueError, gdy nie da się go odczytać."""
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    names: list[str] = []
    aliases: dict[str, str] = {}
    if isinstance(data, dict):
        if isinstance(data.get("names"), list):
            names = [n for n in data["names"] if isinstance(n, str) and n.strip()]
        if isinstance(data.get("aliases"), dict):
            aliases = {k: v for k, v in data["aliases"].items() if isinstance(k, str) and isinstance(v, str)}
    return names, aliases


def _read_builtin(path: Path, language: str) -> tuple[list[str], dict[str, str]]:
    """Lista wbudowana w języku `language`: nazwy oraz aliasy – nazwy w drugim języku i teksty z gry
    (znormalizowane) → nazwa w `language`. OSError/ValueError, gdy nie da się jej odczytać."""
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    other = "en" if language == "pl" else "pl"
    names: list[str] = []
    aliases: dict[str, str] = {}
    by_polish: dict[str, str] = {}
    for boss in data["bosses"]:
        name = boss[language]
        if name not in names:
            names.append(name)
        aliases.setdefault(normalize(boss[other]), name)
        by_polish.setdefault(boss["pl"], name)
    for key, polish in data.get("aliases", {}).items():
        aliases.setdefault(key, by_polish.get(polish, polish))
    own = {normalize(n) for n in names}
    return names, {k: v for k, v in aliases.items() if k not in own}


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
    def __init__(self, path: Path, builtin: Path | None = None, min_ratio: float = MATCH_RATIO,
                 language: str | None = None) -> None:
        self.path = Path(path)
        self.builtin = builtin  # wbudowana lista gry – tylko do odczytu
        self.language = language or i18n.language()  # język nazw na liście wbudowanej
        self.min_ratio = min_ratio
        self.names: list[str] = []
        self.aliases: dict[str, str] = {}  # znormalizowany błędny odczyt → nazwa
        self.builtin_names: list[str] = []
        self.builtin_aliases: dict[str, str] = {}
        self.builtin_version: str | None = None  # skrót listy wbudowanej
        self.checked: str | None = None          # wersja listy, z którą porównano już zapisane nazwy

    def load(self) -> str | None:
        """Wczytuje listę wbudowaną i plik gry; uszkodzony plik pomija (lista zbuduje się od nowa)
        i zwraca ostrzeżenie."""
        self.names, self.aliases, self.checked = [], {}, None
        self.builtin_names, self.builtin_aliases, self.builtin_version = [], {}, None
        if self.builtin is not None and self.builtin.exists():
            try:
                self.builtin_names, self.builtin_aliases = _read_builtin(self.builtin, self.language)
                # Inna lista albo inny język – zapisane nazwy trzeba porównać (przetłumaczyć) jeszcze raz.
                digest = hashlib.sha256(self.builtin.read_bytes() + self.language.encode())
                self.builtin_version = digest.hexdigest()[:12]
            except (OSError, ValueError, KeyError, TypeError):
                pass  # bez listy wbudowanej program i tak działa – uczy się nazw z walk
        if not self.path.exists():
            return None
        try:
            self.names, self.aliases = _read(self.path)
            checked = json.loads(self.path.read_text(encoding="utf-8-sig")).get("builtin_checked")
            self.checked = checked if isinstance(checked, str) else None
        except (OSError, ValueError, AttributeError) as exc:
            return tr("Nie można odczytać {name} ({exc}); lista znanych bossów zacznie się od nowa.", name=self.path.name, exc=exc)
        return None

    def save(self) -> None:
        data = {"names": self.names, "aliases": self.aliases}
        if self.checked:
            data["builtin_checked"] = self.checked
        atomic_write_text(self.path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    def match(self, text: str, extra: list[str] = ()) -> str | None:
        """Znana nazwa najbliższa odczytowi OCR albo None. `extra` – np. nazwy z bosses.json."""
        key = normalize(text)
        if not key:
            return None
        if key in self.aliases:
            return self.aliases[key]
        if key in self.builtin_aliases:
            return self.builtin_aliases[key]
        candidates = {normalize(n): n for n in (*self.builtin_names, *extra, *self.names) if not is_placeholder(n)}
        candidates.update(self.builtin_aliases)
        candidates.update(self.aliases)
        return self._closest(key, candidates)

    def canonical(self, name: str) -> str | None:
        """Nazwa z listy wbudowanej najbliższa podanej (np. zapisanej kiedyś z błędem OCR) albo None."""
        key = normalize(base_name(name))
        if not key or is_placeholder(name):
            return None
        if key in self.builtin_aliases:
            return self.builtin_aliases[key]
        candidates = {normalize(n): n for n in self.builtin_names}
        candidates.update(self.builtin_aliases)
        return self._closest(key, candidates)

    @property
    def needs_check(self) -> bool:
        """Lista wbudowana jest nowa dla tej gry – zapisane nazwy trzeba z nią porównać."""
        return self.builtin_version is not None and self.checked != self.builtin_version

    def fix_learned(self) -> None:
        """Zapamiętane nazwy i aliasy zamienia na nazwy z listy wbudowanej, a zapamiętaną błędną nazwę
        zostawia jako alias – ten sam odczyt OCR da od razu właściwą nazwę. Oznacza listę jako sprawdzoną.
        StorageError przy błędzie zapisu."""
        names: list[str] = []
        for name in self.names:
            fixed = self.canonical(name) or name
            if fixed != name:
                self.aliases[normalize(name)] = fixed
            if not any(normalize(n) == normalize(fixed) for n in names):
                names.append(fixed)
        self.names = names
        self.aliases = {key: self.canonical(name) or name for key, name in self.aliases.items()
                        if key != normalize(self.canonical(name) or name)}
        self.checked = self.builtin_version
        self.save()

    def _closest(self, key: str, candidates: dict[str, str]) -> str | None:
        best, best_ratio = None, self.min_ratio
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
