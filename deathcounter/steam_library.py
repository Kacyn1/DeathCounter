"""Gry souls-like z biblioteki Steam (bez Qt, łatwe do testowania).

Zainstalowane gry program czyta z plików Steama na dysku (libraryfolders.vdf i appmanifest_*.acf),
bez logowania i klucza API. Czy gra jest souls-like, sprawdza tag „Souls-like” w sklepie Steam:
jedno zapytanie o tagi wszystkich zainstalowanych gier (wysyła tylko ich numery AppID). Bez internetu
zostaje wbudowana lista znanych gier souls-like.

Tag mają też gry tylko inspirowane soulsami (np. Armored Core VI, Dead Cells – tag na 8. miejscu),
dlatego liczy się jego miejsce: na 1–3 to souls-like, na 4–10 – „możliwe souls-like” do decyzji gracza.
Prawdziwe souls-like z tagiem dalej (Nioh 2, Black Myth: Wukong – 4. miejsce) są na wbudowanej liście.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import __version__
from .i18n import tr

TAGS_URL = "https://api.steampowered.com/IStoreBrowseService/GetItems/v1/"
SOULSLIKE_TAG = 29482  # tag „Souls-like” w sklepie Steam
SURE_TAGS = 3          # tag wśród tylu głównych tagów gry = souls-like (Steam podaje je od najczęstszego)
TOP_TAGS = 10          # wśród tylu = możliwe souls-like; dalej gra nie jest pokazywana
BATCH = 100            # tyle gier w jednym zapytaniu o tagi
TIMEOUT = 15
DEFAULT_STEAM = Path(r"C:\Program Files (x86)\Steam")

# Gry wbudowane w program: AppID → id gry (wydania Prepare to Die / Remastered i DS2 / Scholar mają wspólny licznik).
BUILTIN_APPS = {
    211420: "ds1", 570940: "ds1",
    236430: "ds2", 335300: "ds2",
    374320: "ds3",
    814380: "sekiro",
    1245620: "eldenring",
}

# Znane gry souls-like, gdy sklep Steam nie odpowiada (tag „Souls-like” sprawdzony w sklepie).
KNOWN_SOULSLIKE = frozenset({
    2622380,   # Elden Ring Nightreign
    1627720,   # Lies of P
    485510,    # Nioh: Complete Edition
    1325200,   # Nioh 2 – The Complete Edition
    1110910,   # Mortal Shell
    1501750,   # Lords of the Fallen
    265300,    # Lords of the Fallen (2014)
    617290,    # Remnant: From the Ashes
    1282100,   # Remnant II
    367520,    # Hollow Knight
    1030300,   # Hollow Knight: Silksong
    774361,    # Blasphemous
    2114740,   # Blasphemous 2
    283640,    # Salt and Sanctuary
    1343240,   # Thymesia
    1448440,   # Wo Long: Fallen Dynasty
    2358720,   # Black Myth: Wukong
    678960,    # Code Vein
    378540,    # The Surge
    644830,    # The Surge 2
    649950,    # Ashen
    356650,    # Death's Gambit: Afterlife
    628670,    # Hellpoint
    1369630,   # Ender Lilies: Quietus of the Knights
    2680010,   # The First Berserker: Khazan
})

TAG = "tag"          # tag „Souls-like” wśród głównych tagów gry (SURE_TAGS)
MAYBE = "maybe"      # tag dalej, ale w TOP_TAGS – możliwe souls-like
LIST = "list"        # z wbudowanej listy znanych gier souls-like
BUILTIN = "builtin"  # gra wbudowana w program


class SteamError(RuntimeError):
    pass


@dataclass(frozen=True)
class SteamGame:
    appid: int
    name: str
    install_dir: Path | None = field(default=None, compare=False)  # steamapps/common/<gra>


@dataclass(frozen=True)
class Found:
    game: SteamGame
    source: str               # TAG, MAYBE, LIST albo BUILTIN
    builtin: str | None = None  # id gry wbudowanej, gdy source == BUILTIN


@dataclass
class ScanResult:
    found: list[Found]
    installed: int            # ile gier jest zainstalowanych
    online_error: str = ""    # dlaczego nie sprawdzono tagów (wtedy użyto wbudowanej listy)


# --- pliki Steama ---

_TOKEN = re.compile(r'"((?:[^"\\]|\\.)*)"|([{}])|//[^\n]*|\s+')
_ESCAPES = {"n": "\n", "t": "\t", "\\": "\\", '"': '"'}


def parse_vdf(text: str) -> dict:
    """Format KeyValues Steama („klucz” „wartość” albo „klucz” { … }) → zagnieżdżony słownik."""
    root: dict = {}
    stack = [root]
    key: str | None = None
    pos = 0
    while pos < len(text):
        match = _TOKEN.match(text, pos)
        if match is None:
            raise ValueError(f"nieoczekiwany znak na pozycji {pos}")
        pos = match.end()
        string, brace = match.group(1), match.group(2)
        if brace == "{":
            if key is None:
                raise ValueError("„{” bez klucza")
            child: dict = {}
            stack[-1][key] = child
            stack.append(child)
            key = None
        elif brace == "}":
            if len(stack) == 1:
                raise ValueError("nadmiarowe „}”")
            stack.pop()
            key = None
        elif string is not None:
            value = re.sub(r"\\(.)", lambda m: _ESCAPES.get(m.group(1), m.group(0)), string)
            if key is None:
                key = value
            else:
                stack[-1][key] = value
                key = None
    if len(stack) > 1 or key is not None:
        raise ValueError("niekompletny plik")
    return root


def find_steam() -> Path | None:
    """Folder Steama z rejestru (albo domyślny), None, gdy Steama nie ma."""
    candidates = []
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            candidates.append(Path(winreg.QueryValueEx(key, "SteamPath")[0]))
    except (ImportError, OSError):
        pass
    candidates.append(DEFAULT_STEAM)
    return next((path for path in candidates if (path / "steamapps").is_dir()), None)


def library_folders(steam: Path) -> list[Path]:
    """Wszystkie biblioteki Steama (także na innych dyskach); zawsze co najmniej folder samego Steama."""
    folders = [Path(steam)]
    try:
        data = parse_vdf((Path(steam) / "steamapps" / "libraryfolders.vdf").read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return folders
    for entry in data.get("libraryfolders", {}).values():
        path = entry.get("path") if isinstance(entry, dict) else None
        if isinstance(path, str) and path and Path(path) not in folders:
            folders.append(Path(path))
    return folders


def installed_games(steam: Path) -> list[SteamGame]:
    """Zainstalowane gry ze wszystkich bibliotek (appmanifest_<appid>.acf), posortowane po nazwie."""
    games: dict[int, SteamGame] = {}
    for folder in library_folders(steam):
        for manifest in sorted((folder / "steamapps").glob("appmanifest_*.acf")):
            try:
                state = parse_vdf(manifest.read_text(encoding="utf-8", errors="replace")).get("AppState", {})
                appid, name = int(state["appid"]), clean_name(state["name"])
                install_dir = folder / "steamapps" / "common" / str(state["installdir"]) if state.get("installdir") else None
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                continue  # uszkodzony albo niepełny manifest – pomijamy tę grę
            if name:
                games.setdefault(appid, SteamGame(appid, name, install_dir))
    return sorted(games.values(), key=lambda game: game.name.casefold())


def clean_name(name: str) -> str:
    """„DARK SOULS™ III” → „DARK SOULS III” (bez znaków towarowych, pojedyncze spacje)."""
    return " ".join(re.sub("[™®©]", "", str(name)).split())


# --- tagi ze sklepu Steam ---

def fetch_tags(appids: list[int], opener: Callable = urllib.request.urlopen) -> dict[int, list[int]]:
    """AppID → tagi gry od najczęstszego. Wysyła do sklepu Steam tylko numery AppID."""
    tags: dict[int, list[int]] = {}
    for start in range(0, len(appids), BATCH):
        query = {
            "ids": [{"appid": appid} for appid in appids[start:start + BATCH]],
            "context": {"language": "english", "country_code": "US"},
            "data_request": {"include_tag_count": 20},
        }
        url = TAGS_URL + "?" + urllib.parse.urlencode({"input_json": json.dumps(query)})
        request = urllib.request.Request(url, headers={"User-Agent": f"DeathCounter/{__version__}"})
        try:
            with opener(request, timeout=TIMEOUT) as response:
                items = json.loads(response.read())["response"].get("store_items", [])
        except (OSError, urllib.error.URLError) as exc:
            raise SteamError(tr("Brak połączenia ze sklepem Steam ({exc}).", exc=exc)) from exc
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise SteamError(tr("Nieczytelna odpowiedź sklepu Steam ({exc}).", exc=exc)) from exc
        for item in items:
            if isinstance(item, dict) and isinstance(item.get("appid"), int):
                tags[item["appid"]] = [tag for tag in item.get("tagids", []) if isinstance(tag, int)]
    return tags


def tag_source(tagids: list[int]) -> str | None:
    """TAG, MAYBE albo None (tagu „Souls-like” nie ma wśród głównych tagów gry)."""
    if SOULSLIKE_TAG in tagids[:SURE_TAGS]:
        return TAG
    return MAYBE if SOULSLIKE_TAG in tagids[:TOP_TAGS] else None


def classify(games: list[SteamGame], tags: dict[int, list[int]] | None) -> list[Found]:
    """Gry wbudowane w program i gry souls-like, a na końcu możliwe souls-like (MAYBE).
    `tags` None – sklep nie odpowiedział, zostaje lista znanych gier."""
    found = []
    for game in games:
        if game.appid in BUILTIN_APPS:
            found.append(Found(game, BUILTIN, BUILTIN_APPS[game.appid]))
        elif game.appid in KNOWN_SOULSLIKE:
            found.append(Found(game, LIST))
        elif tags is not None and (source := tag_source(tags.get(game.appid, []))):
            found.append(Found(game, source))
    return sorted(found, key=lambda item: item.source == MAYBE)  # sortowanie stabilne: nazwy zostają po kolei


def scan(steam: Path | None = None, opener: Callable = urllib.request.urlopen) -> ScanResult:
    """Zainstalowane gry souls-like. SteamError, gdy na komputerze nie ma Steama."""
    steam = steam or find_steam()
    if steam is None:
        raise SteamError(tr("Nie znaleziono Steama na tym komputerze."))
    games = installed_games(steam)
    others = [game.appid for game in games if game.appid not in BUILTIN_APPS]
    tags, error = None, ""
    if others:
        try:
            tags = fetch_tags(others, opener)
        except SteamError as exc:
            error = str(exc)
    return ScanResult(classify(games, tags), len(games), error)
