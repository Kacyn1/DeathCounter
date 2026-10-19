"""Aktualizacja do najnowszego wydania z GitHuba (bez Qt, łatwe do testowania).

Program pyta API GitHuba o najnowszy release, pobiera DeathCounter.exe, sprawdza jego sumę SHA-256
(podawaną przez GitHub dla każdego pliku) i podmienia działający exe: działającego pliku nie da się
nadpisać, ale da się zmienić jego nazwę – stary zostaje jako DeathCounter.old.exe i znika przy
następnym starcie. Dane (licznik, bossowie, kalibracja) leżą obok exe i zostają nietknięte.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import __version__

LATEST_URL = "https://api.github.com/repos/Kacyn1/DeathCounter/releases/latest"
ASSET_NAME = "DeathCounter.exe"
CHECK_INTERVAL = 24 * 3600  # automatyczne sprawdzanie raz dziennie
TIMEOUT = 15
AFTER_UPDATE_ARG = "--after-update"  # nowa wersja czeka, aż stara zwolni blokadę drugiej kopii


class UpdateError(RuntimeError):
    pass


@dataclass
class Release:
    version: str
    page_url: str
    download_url: str | None  # None, gdy release nie ma DeathCounter.exe z sumą kontrolną
    size: int
    sha256: str


def parse_version(text: str) -> tuple[int, ...]:
    """„v1.10.2” → (1, 10, 2); nieczytelna wersja → ()."""
    match = re.match(r"^v?(\d+(?:\.\d+)*)$", text.strip())
    return tuple(int(part) for part in match.group(1).split(".")) if match else ()


def is_newer(version: str, current: str = __version__) -> bool:
    new, old = parse_version(version), parse_version(current)
    return bool(new) and bool(old) and new > old


def due(last_check: float, now: float) -> bool:
    """Czy minęła doba od ostatniego sprawdzenia (zegar cofnięty też liczy się jako „pora”)."""
    return not (0 <= now - last_check < CHECK_INTERVAL)


def release_from_json(data: dict) -> Release:
    version = str(data.get("tag_name", "")).lstrip("v")
    if not parse_version(version):
        raise UpdateError(f"Nieczytelny numer wersji w wydaniu: {data.get('tag_name')!r}.")
    asset = next((a for a in data.get("assets", []) if a.get("name") == ASSET_NAME), None)
    digest = str(asset.get("digest") or "") if asset else ""
    if asset and digest.startswith("sha256:"):
        return Release(version, data.get("html_url", ""), asset["browser_download_url"], int(asset["size"]),
                       digest.split(":", 1)[1].lower())
    return Release(version, data.get("html_url", ""), None, 0, "")


def fetch_latest(opener: Callable = urllib.request.urlopen) -> Release:
    request = urllib.request.Request(LATEST_URL, headers={
        "Accept": "application/vnd.github+json", "User-Agent": f"DeathCounter/{__version__}"})
    try:
        with opener(request, timeout=TIMEOUT) as response:
            return release_from_json(json.loads(response.read()))
    except UpdateError:
        raise
    except (OSError, ValueError, KeyError) as exc:
        raise UpdateError(f"Nie udało się sprawdzić aktualizacji: {exc}") from exc


def download(release: Release, dest: Path, progress: Callable[[int, int], None] | None = None,
             opener: Callable = urllib.request.urlopen, cancelled: Callable[[], bool] = lambda: False) -> Path:
    """Pobiera exe do `dest` i sprawdza sumę SHA-256. Przy błędzie plik częściowy jest usuwany."""
    if release.download_url is None:
        raise UpdateError("To wydanie nie ma pliku DeathCounter.exe z sumą kontrolną – pobierz je ręcznie.")
    part = dest.with_name(dest.name + ".part")
    digest = hashlib.sha256()
    done = 0
    request = urllib.request.Request(release.download_url, headers={"User-Agent": f"DeathCounter/{__version__}"})
    try:
        with opener(request, timeout=TIMEOUT) as response, open(part, "wb") as out:
            while chunk := response.read(256 * 1024):
                if cancelled():
                    raise UpdateError("Pobieranie przerwane.")
                out.write(chunk)
                digest.update(chunk)
                done += len(chunk)
                if progress is not None:
                    progress(done, release.size)
        if release.size and done != release.size:
            raise UpdateError(f"Pobrano {done} z {release.size} bajtów – połączenie zostało przerwane.")
        if digest.hexdigest() != release.sha256:
            raise UpdateError("Suma kontrolna pobranego pliku się nie zgadza – plik jest uszkodzony albo podmieniony.")
        os.replace(part, dest)
        return dest
    except OSError as exc:
        raise UpdateError(f"Nie udało się pobrać aktualizacji: {exc}") from exc
    finally:
        part.unlink(missing_ok=True)


def old_path(exe: Path) -> Path:
    return exe.with_name(f"{exe.stem}.old{exe.suffix}")


def install(new_exe: Path, exe: Path) -> None:
    """Podmienia exe: działający plik dostaje nazwę *.old.exe, nowy wchodzi na jego miejsce."""
    old = old_path(exe)
    try:
        old.unlink(missing_ok=True)
        os.replace(exe, old)
    except OSError as exc:
        raise UpdateError(f"Nie można podmienić {exe.name}: {exc}") from exc
    try:
        os.replace(new_exe, exe)
    except OSError as exc:
        os.replace(old, exe)  # przywrócenie działającej wersji
        raise UpdateError(f"Nie można zapisać nowej wersji: {exc}") from exc


def cleanup(exe: Path) -> None:
    """Po aktualizacji: usuwa starą wersję i pozostałości pobierania (zablokowany plik zostaje na później)."""
    for path in (old_path(exe), exe.with_name("DeathCounter.new.exe"), exe.with_name("DeathCounter.new.exe.part")):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def running_exe() -> Path | None:
    """Ścieżka DeathCounter.exe albo None przy uruchomieniu ze źródeł (tam aktualizuje się przez git pull)."""
    return Path(sys.executable).resolve() if getattr(sys, "frozen", False) else None


def restart(exe: Path) -> None:
    """Uruchamia nową wersję jako niezależny proces. PYINSTALLER_RESET_ENVIRONMENT – nowy exe nie może
    korzystać z folderu tymczasowego bieżącego procesu (jednoplikowy exe sam się w nim rozpakowuje)."""
    env = dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1")
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen([str(exe), AFTER_UPDATE_ARG], cwd=str(exe.parent), env=env, creationflags=flags, close_fds=True)
