"""Dane jednej gry: licznik śmierci, bossowie i wzorce kalibracji z folderu games/<gra>/."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .audit import AuditLog, open_audit
from .bosses import BossStore
from .config import TEMPLATE_FIELDS, AppPaths, Calibration, load_calibration
from .storage import DeathStore, StorageError
from .signing import load_key
from .template import DeathTemplate, TemplateError

TEMPLATE_LABELS = {"death": "napisu śmierci", "boss_bar": "paska bossa", "victory": "komunikatu zwycięstwa"}


@dataclass
class GameData:
    paths: AppPaths
    store: DeathStore
    boss_store: BossStore
    calibration: Calibration
    templates: dict[str, DeathTemplate | None]
    audit: AuditLog | None = None
    warnings: list[str] = field(default_factory=list)


def counter_files(paths: AppPaths) -> list[Path]:
    """Pliki licznika gry (śmierci i bossowie) – usuwane przy „Usuń licznik” gry wbudowanej; kalibracja zostaje."""
    return [
        paths.deaths,
        paths.deaths.with_name(paths.deaths.name + ".uszkodzony"),
        paths.bosses,
        paths.bosses.with_name(paths.bosses.name + ".uszkodzony"),
        paths.audit,  # nowy licznik zaczyna też nowy rejestr zmian
    ]


def open_game(base: Path, game: str) -> GameData:
    """Wczytuje dane gry (brakujący folder tworzy). StorageError, gdy nie da się przygotować licznika."""
    paths = AppPaths.for_game(base, game)
    try:
        paths.game_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise StorageError(f"Nie można utworzyć folderu gry {paths.game_dir}: {exc}") from exc
    store = DeathStore(paths.deaths)
    store.load()
    boss_store = BossStore(paths.bosses)
    boss_store.load()
    warnings = [w for w in (store.warning, boss_store.warning) if w]
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
                warnings.append(f"Nie można wczytać wzorca {TEMPLATE_LABELS[kind]}: {exc} Wykonaj kalibrację ponownie.")
    return GameData(paths, store, boss_store, calibration, templates, audit, warnings)
