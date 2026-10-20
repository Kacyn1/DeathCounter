"""Zapis licznika śmierci w deaths.json (zawsze atomowo)."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from .i18n import tr


class StorageError(Exception):
    """Błąd odczytu lub zapisu pliku z danymi."""


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Zapisuje plik przez plik tymczasowy i podmianę (os.replace).

    Podmiana jest ponawiana przez chwilę, bo na Windows plik może być
    na moment zablokowany przez inny program (np. OBS czytający wynik).
    """
    path = Path(path)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with open(tmp, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        for attempt in range(20):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                if attempt == 19:
                    raise
                time.sleep(0.05)
    except OSError as exc:
        raise StorageError(tr("Nie można zapisać pliku {name}: {exc}", name=path.name, exc=exc)) from exc
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


def atomic_write_text(path: Path, text: str) -> None:
    atomic_write_bytes(path, text.encode("utf-8"))


def format_deaths(deaths: int) -> str:
    return f'{{ "deaths": {deaths} }}\n'


class DeathStore:
    """Przechowuje wyłącznie liczbę śmierci: { "deaths": N }."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._deaths = 0
        self.warning: str | None = None

    @property
    def deaths(self) -> int:
        return self._deaths

    def load(self) -> int:
        """Wczytuje wynik; brakujący plik tworzy z wartością 0.

        Uszkodzony plik jest odkładany jako kopia (deaths.json.uszkodzony),
        żeby nie stracić danych bez wiedzy użytkownika.
        """
        self.warning = None
        if not self.path.exists():
            self._deaths = 0
            self._save()
            return self._deaths
        try:
            raw = self.path.read_text(encoding="utf-8-sig")
        except OSError as exc:
            raise StorageError(tr("Nie można odczytać pliku {name}: {exc}", name=self.path.name, exc=exc)) from exc
        try:
            self._deaths = _parse_deaths(raw)
        except ValueError as exc:
            backup = self.path.with_name(self.path.name + ".uszkodzony")
            try:
                os.replace(self.path, backup)
            except OSError as move_exc:
                raise StorageError(
                    tr("Plik {name} jest uszkodzony ({exc}) i nie można go odłożyć: {move_exc}", name=self.path.name, exc=exc, move_exc=move_exc)
                ) from move_exc
            self.warning = (
                tr("Plik {name} był uszkodzony ({exc}). Jego kopię zapisano jako {name2}, a licznik zaczyna od 0.", name=self.path.name, exc=exc, name2=backup.name)
            )
            self._deaths = 0
            self._save()
        return self._deaths

    def set(self, value: int) -> int:
        value = max(0, int(value))
        if value != self._deaths:
            self._deaths = value
            # Wartość w pamięci zostaje nawet przy błędzie zapisu; kolejna zmiana ponowi zapis.
            self._save()
        return self._deaths

    def increment(self) -> int:
        return self.set(self._deaths + 1)

    def decrement(self) -> int:
        return self.set(self._deaths - 1)

    def reset(self) -> int:
        return self.set(0)

    def save(self) -> None:
        self._save()

    def _save(self) -> None:
        atomic_write_text(self.path, format_deaths(self._deaths))


def _parse_deaths(raw: str) -> int:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(tr("niepoprawny JSON")) from exc
    if not isinstance(data, dict) or "deaths" not in data:
        raise ValueError(tr('brak pola "deaths"'))
    value = data["deaths"]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(tr('pole "deaths" nie jest liczbą całkowitą'))
    if value < 0:
        raise ValueError(tr('pole "deaths" jest ujemne'))
    return value
