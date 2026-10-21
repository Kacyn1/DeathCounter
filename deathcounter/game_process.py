"""Która gra z listy jest uruchomiona: działające procesy dopasowane do gier (bez Qt, łatwe do testowania).

Gry wbudowane rozpoznaje nazwa exe. Gry ze Steama – każdy exe z ich folderu instalacji (steamapps/common/<gra>);
gry dodane ręcznie dostają folder gry ze Steama o tej samej nazwie albo exe wskazany przez gracza.
"""

from __future__ import annotations

import ntpath
from dataclasses import dataclass
from pathlib import Path

from .config import AppConfig
from .steam_library import SteamGame, clean_name

# Exe gier wbudowanych (małymi literami); DS1 – Prepare to Die i Remastered, DS2 – obie wersje mają ten sam exe.
BUILTIN_EXES = {
    "ds1": ("darksouls.exe", "darksoulsremastered.exe"),
    "ds2": ("darksoulsii.exe",),
    "ds3": ("darksoulsiii.exe",),
    "sekiro": ("sekiro.exe",),
    "eldenring": ("eldenring.exe",),
}


@dataclass(frozen=True)
class GameMatcher:
    exe_names: frozenset[str] = frozenset()  # nazwy exe, małymi literami
    folders: tuple[str, ...] = ()            # foldery gry, małymi literami, zakończone „\”
    exe_paths: frozenset[str] = frozenset()  # pełne ścieżki exe, małymi literami

    def matches(self, path: str) -> bool:
        path = ntpath.normcase(ntpath.normpath(path))
        return (ntpath.basename(path) in self.exe_names or path in self.exe_paths
                or any(path.startswith(folder) for folder in self.folders))


def _folder(path: Path) -> str:
    return ntpath.normcase(ntpath.normpath(str(path))).rstrip("\\") + "\\"


def build_matchers(config: AppConfig, steam_games: list[SteamGame]) -> dict[str, GameMatcher]:
    """Gra → sposób rozpoznania jej procesu; gry, których nie da się rozpoznać, nie mają wpisu."""
    by_appid = {game.appid: game for game in steam_games if game.install_dir is not None}
    by_name = {clean_name(game.name).casefold(): game for game in by_appid.values()}
    matchers = {game_id: GameMatcher(exe_names=frozenset(names)) for game_id, names in BUILTIN_EXES.items()}
    for game_id, name in config.custom_games.items():
        steam = by_appid.get(config.steam_appids.get(game_id)) or by_name.get(clean_name(name).casefold())
        exe = config.game_exes.get(game_id)
        if steam is None and exe is None:
            continue
        matchers[game_id] = GameMatcher(
            folders=(_folder(steam.install_dir),) if steam else (),
            exe_paths=frozenset({ntpath.normcase(ntpath.normpath(exe))}) if exe else frozenset(),
        )
    return matchers


def running_games(processes: list[str], matchers: dict[str, GameMatcher]) -> set[str]:
    return {game_id for game_id, matcher in matchers.items() if any(matcher.matches(path) for path in processes)}


def matching_exe(processes: list[str], matcher: GameMatcher) -> str | None:
    """Nazwa exe gry, który działa (do pokazania w oknie)."""
    return next((ntpath.basename(path) for path in processes if matcher.matches(path)), None)

