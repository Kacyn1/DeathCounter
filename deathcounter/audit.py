"""Rejestr zmian licznika (games/<gra>/audit.json): ręczne korekty i zmiany w plikach poza programem.

Program zapisuje tu, ile śmierci dodano lub odjęto ręcznie (przyciski, skróty, reset) oraz jakie
wartości sam ostatnio zapisał w deaths.json i bosses.json. Przy uruchomieniu porównuje pliki z tymi
wartościami – różnica to zmiana poza programem (np. edycja pliku w Notatniku). Rejestr jest podpisany
kluczem certyfikatów: jego edycja zostaje wykryta, a usunięcie sprawia, że istniejące wyniki są
oznaczane jako „bez historii zmian”.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from .storage import StorageError, atomic_write_text
from .i18n import tr

AUDIT_VERSION = 1


@dataclass
class Changes:
    """Historia jednego licznika (całej gry albo jednego bossa)."""

    manual_added: int = 0           # śmierci dodane ręcznie w programie
    manual_removed: int = 0         # śmierci odjęte ręcznie w programie (także reset)
    external_deaths: int = 0        # suma zmian liczby śmierci poza programem
    external_seconds: float = 0.0   # suma zmian czasu walki poza programem (boss)
    external_status: bool = False   # boss: status zmieniony poza programem; gra: lista bossów zmieniona
    untracked_deaths: int = 0       # śmierci, które istniały przed rejestrem (bez historii)
    untracked_seconds: float = 0.0
    last_deaths: int = 0            # ostatnio zapisane przez program
    last_seconds: float = 0.0
    last_status: str = ""

    @property
    def changed(self) -> bool:
        return bool(self.manual_added or self.manual_removed or self.external_deaths
                    or round(self.external_seconds) or self.external_status
                    or self.untracked_deaths or round(self.untracked_seconds))

    @classmethod
    def from_dict(cls, data: object) -> "Changes":
        changes = cls()
        if isinstance(data, dict):
            for f in fields(cls):
                value = data.get(f.name)
                if isinstance(value, type(getattr(changes, f.name))) and not (
                    isinstance(value, bool) and f.type != "bool"
                ):
                    setattr(changes, f.name, value)
                elif f.type == "float" and isinstance(value, int) and not isinstance(value, bool):
                    setattr(changes, f.name, float(value))
        return changes


@dataclass
class AuditLog:
    path: Path
    key: bytes | None
    game: Changes = field(default_factory=Changes)
    bosses: dict[str, Changes] = field(default_factory=dict)
    intact: bool = True             # False: rejestr był edytowany lub uszkodzony – wyniki niewiarygodne
    existed: bool = False

    # ---------------------------------------------------------------- plik

    def load(self) -> str | None:
        """Wczytuje rejestr; zwraca ostrzeżenie, gdy podpis się nie zgadza."""
        self.existed = self.path.exists()
        if not self.existed:
            return None
        try:
            data = json.loads(self.path.read_text(encoding="utf-8-sig"))
            if not isinstance(data, dict):
                raise ValueError(tr("oczekiwano obiektu JSON"))
        except (OSError, ValueError):
            self.intact = False
            return tr("Rejestr zmian {name} jest uszkodzony – wynik tej gry będzie oznaczony jako niepewny.", name=self.path.name)
        self.game = Changes.from_dict(data.get("game"))
        bosses = data.get("bosses")
        self.bosses = {str(k): Changes.from_dict(v) for k, v in bosses.items()} if isinstance(bosses, dict) else {}
        self.intact = data.get("intact") is True
        if self.key is not None and data.get("mac") != self._mac():
            self.intact = False
            return tr("Rejestr zmian {name} został zmieniony poza programem – wynik tej gry będzie oznaczony jako niepewny.", name=self.path.name)
        return None

    def save(self) -> None:
        data = self._content()
        data["mac"] = self._mac()
        atomic_write_text(self.path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    def _content(self) -> dict:
        return {
            "v": AUDIT_VERSION,
            "game": asdict(self.game),
            "bosses": {name: asdict(c) for name, c in self.bosses.items()},
            "intact": self.intact,
        }

    def _mac(self) -> str:
        if self.key is None:
            return ""
        canonical = json.dumps(self._content(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hmac.new(self.key, canonical.encode("utf-8"), hashlib.sha256).hexdigest()

    # ---------------------------------------------------------------- zdarzenia

    def reconcile(self, deaths: int, records: dict) -> None:
        """Przy wczytaniu gry: różnice między plikami a ostatnim zapisem programu to zmiany poza programem.
        Bez rejestru (pierwsze uruchomienie albo usunięty plik) istniejące wyniki są „bez historii”."""
        fresh = not self.existed
        if fresh:
            self.game.untracked_deaths = deaths
        elif deaths != self.game.last_deaths:
            self.game.external_deaths += deaths - self.game.last_deaths
        self.game.last_deaths = deaths
        for name in list(self.bosses):
            if name not in records:  # boss usunięty z pliku poza programem
                self.game.external_status = True
                del self.bosses[name]
        for name, record in records.items():
            entry = self.bosses.get(name)
            if entry is None:
                entry = self.bosses[name] = Changes()
                if fresh:
                    entry.untracked_deaths, entry.untracked_seconds = record.deaths, float(record.total_time_seconds)
                else:  # boss dopisany do pliku ręcznie
                    entry.external_deaths, entry.external_seconds = record.deaths, float(record.total_time_seconds)
                    entry.external_status = record.status != "W TRAKCIE"
            else:
                entry.external_deaths += record.deaths - entry.last_deaths
                if abs(record.total_time_seconds - entry.last_seconds) >= 1:
                    entry.external_seconds += record.total_time_seconds - entry.last_seconds
                if entry.last_status and record.status != entry.last_status:
                    entry.external_status = True
            entry.last_deaths, entry.last_seconds, entry.last_status = (
                record.deaths, float(record.total_time_seconds), record.status)
        self.existed = True

    def deaths_changed(self, deaths: int, manual: bool) -> None:
        delta = deaths - self.game.last_deaths
        if manual and delta > 0:
            self.game.manual_added += delta
        elif manual and delta < 0:
            self.game.manual_removed -= delta
        self.game.last_deaths = deaths

    def bosses_saved(self, records: dict, manual_boss: str | None = None) -> None:
        """Po każdym zapisie bosses.json przez program; zmiana śmierci `manual_boss` to ręczna korekta."""
        for name in list(self.bosses):
            if name not in records:
                del self.bosses[name]  # odrzucony fałszywy start
        for name, record in records.items():
            entry = self.bosses.setdefault(name, Changes())
            delta = record.deaths - entry.last_deaths
            if name == manual_boss and delta > 0:
                entry.manual_added += delta
            elif name == manual_boss and delta < 0:
                entry.manual_removed -= delta
            entry.last_deaths, entry.last_seconds, entry.last_status = (
                record.deaths, float(record.total_time_seconds), record.status)

    def boss_renamed(self, old: str, new: str) -> None:
        """Zmiana nazwy bossa; przy scaleniu z istniejącym bossem historia się sumuje."""
        entry = self.bosses.pop(old, None)
        if entry is None:
            return
        target = self.bosses.get(new)
        if target is None:
            self.bosses[new] = entry
            return
        for name in ("manual_added", "manual_removed", "external_deaths", "untracked_deaths",
                     "last_deaths"):
            setattr(target, name, getattr(target, name) + getattr(entry, name))
        for name in ("external_seconds", "untracked_seconds", "last_seconds"):
            setattr(target, name, getattr(target, name) + getattr(entry, name))
        target.external_status = target.external_status or entry.external_status

    @property
    def changed(self) -> bool:
        return not self.intact or self.game.changed or any(c.changed for c in self.bosses.values())


def open_audit(path: Path, key: bytes | None, deaths: int, records: dict) -> tuple[AuditLog, str | None]:
    audit = AuditLog(Path(path), key)
    warning = audit.load()
    audit.reconcile(deaths, records)
    try:
        audit.save()
    except StorageError as exc:
        warning = tr("Nie można zapisać rejestru zmian: {exc}", exc=exc)
    return audit, warning
