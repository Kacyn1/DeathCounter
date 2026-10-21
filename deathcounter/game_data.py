"""Dane jednej gry: licznik śmierci, bossowie i wzorce kalibracji z folderu games/<gra>/."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .audit import AuditLog, open_audit
from .boss_names import BossNames, builtin_path
from .bosses import BossStore
from .attempts import AttemptLog
from .recent_fights import RecentFights
from .play_session import PlaySession
from .config import TEMPLATE_FIELDS, AppPaths, Calibration, load_calibration
from .storage import DeathStore, StorageError
from .signing import load_key
from .template import DeathTemplate, TemplateError
from .i18n import tr, N_

TEMPLATE_LABELS = {"death": N_("napisu śmierci"), "boss_bar": N_("paska bossa"), "victory": N_("komunikatu zwycięstwa"),
                   "menu": N_("menu głównego"), "hud": N_("paska zdrowia postaci")}


@dataclass
class GameData:
    paths: AppPaths
    store: DeathStore
    boss_store: BossStore
    calibration: Calibration
    templates: dict[str, DeathTemplate | None]
    audit: AuditLog | None = None
    boss_names: BossNames | None = None
    recent: RecentFights | None = None
    attempts: AttemptLog | None = None
    session: PlaySession | None = None
    warnings: list[str] = field(default_factory=list)


def counter_files(paths: AppPaths) -> list[Path]:
    """Pliki licznika gry (śmierci i bossowie) – usuwane przy „Usuń licznik” gry wbudowanej; kalibracja zostaje."""
    return [
        paths.deaths,
        paths.deaths.with_name(paths.deaths.name + ".uszkodzony"),
        paths.bosses,
        paths.bosses.with_name(paths.bosses.name + ".uszkodzony"),
        paths.audit,  # nowy licznik zaczyna też nowy rejestr zmian
        paths.session,
        paths.session_history,
    ]


def open_game(base: Path, game: str) -> GameData:
    """Wczytuje dane gry (brakujący folder tworzy). StorageError, gdy nie da się przygotować licznika."""
    paths = AppPaths.for_game(base, game)
    try:
        paths.game_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise StorageError(tr("Nie można utworzyć folderu gry {game_dir}: {exc}", game_dir=paths.game_dir, exc=exc)) from exc
    store = DeathStore(paths.deaths)
    store.load()
    boss_store = BossStore(paths.bosses)
    boss_store.load()
    boss_names = BossNames(paths.boss_names, builtin_path(game))
    recent = RecentFights(paths.recent_fights)
    attempts = AttemptLog(paths.attempts)
    warnings = [w for w in (store.warning, boss_store.warning, boss_names.load(), recent.load(), attempts.load())
                if w]
    audit, warning = open_audit(paths.audit, load_key(), store.deaths, boss_store.records)
    if warning:
        warnings.append(warning)

    calibration, warning = load_calibration(paths.calibration)
    if warning:
        warnings.append(warning)
    templates: dict[str, DeathTemplate | None] = {}
    for kind in TEMPLATE_FIELDS:
        info = calibration.info(kind)
        templates[kind] = None
        if info is not None:
            try:
                templates[kind] = DeathTemplate.load(paths.template_path(kind), info)
            except TemplateError as exc:
                warnings.append(tr("Nie można wczytać wzorca {item}: {exc} Wykonaj kalibrację ponownie.", item=tr(TEMPLATE_LABELS[kind]), exc=exc))
    return GameData(paths, store, boss_store, calibration, templates, audit, boss_names, recent, attempts,
                    PlaySession(paths.session, paths.session_history), warnings)
