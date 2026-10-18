import json

import pytest

from deathcounter import game_data
from deathcounter.audit import AuditLog, open_audit
from deathcounter.bosses import BossRecord, BossStore, BossTracker
from deathcounter.report import Adjustments

KEY = bytes(range(32))


@pytest.fixture(autouse=True)
def signing_key(monkeypatch):
    monkeypatch.setattr(game_data, "load_key", lambda: KEY)


def reopen(base, game="ds1"):
    return game_data.open_game(base, game)


def adjustments(game) -> Adjustments:
    return Adjustments.from_audit(game.audit)


def test_new_game_has_no_changes(tmp_path):
    game = reopen(tmp_path)
    assert not game.audit.changed
    assert adjustments(game).summary() == []


def test_detected_deaths_are_not_corrections(tmp_path):
    game = reopen(tmp_path)
    for _ in range(3):
        game.store.increment()
        game.audit.deaths_changed(game.store.deaths, manual=False)
    game.audit.save()
    assert not reopen(tmp_path).audit.changed


def test_manual_corrections_and_reset_are_counted(tmp_path):
    game = reopen(tmp_path)
    for value, manual in ((1, False), (2, True), (3, True), (2, True), (0, True)):  # wykryta, +1, +1, −1, reset
        game.store.set(value)
        game.audit.deaths_changed(game.store.deaths, manual=manual)
    game.audit.save()
    changes = reopen(tmp_path).audit.game
    assert (changes.manual_added, changes.manual_removed) == (2, 3)
    assert "ręczne korekty śmierci: +2 / −3" in adjustments(reopen(tmp_path)).summary()


def test_editing_deaths_file_outside_program_is_detected(tmp_path):
    game = reopen(tmp_path)
    game.store.set(5)
    game.audit.deaths_changed(5, manual=False)
    game.audit.save()
    (tmp_path / "games/ds1/deaths.json").write_text('{ "deaths": 1 }', encoding="utf-8")  # „poprawka” w Notatniku
    assert reopen(tmp_path).audit.game.external_deaths == -4
    assert reopen(tmp_path).audit.game.external_deaths == -4  # zapamiętane, nie liczone podwójnie


def test_editing_boss_time_and_status_outside_program_is_detected(tmp_path):
    game = reopen(tmp_path)
    game.boss_store.records["Smelter Demon"] = BossRecord(7, 758, "W TRAKCIE")
    game.boss_store.save()
    game.audit.bosses_saved(game.boss_store.records)
    game.audit.save()
    data = json.loads((tmp_path / "games/ds1/bosses.json").read_text(encoding="utf-8"))
    data["Smelter Demon"].update(total_time_seconds=60, status="POKONANO")  # szybszy czas i zwycięstwo
    (tmp_path / "games/ds1/bosses.json").write_text(json.dumps(data), encoding="utf-8")
    boss = reopen(tmp_path).audit.bosses["Smelter Demon"]
    assert boss.external_seconds == pytest.approx(-698)
    assert boss.external_status is True
    assert "bossowie zmienieni poza programem: 1" in adjustments(reopen(tmp_path)).summary()


def test_editing_audit_file_breaks_integrity(tmp_path):
    game = reopen(tmp_path)
    game.store.set(3)
    game.audit.deaths_changed(3, manual=True)
    game.audit.save()
    path = tmp_path / "games/ds1/audit.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["game"]["manual_added"] = 0  # ukrycie korekty
    path.write_text(json.dumps(data), encoding="utf-8")
    again = reopen(tmp_path)
    assert again.audit.intact is False
    assert any("Rejestr zmian" in w for w in again.warnings)
    assert reopen(tmp_path).audit.intact is False  # naruszenie zostaje zapamiętane


def test_deleting_audit_marks_results_as_untracked(tmp_path):
    game = reopen(tmp_path)
    game.store.set(9)
    game.audit.deaths_changed(9, manual=True)
    game.audit.save()
    (tmp_path / "games/ds1/audit.json").unlink()
    changes = reopen(tmp_path).audit.game
    assert changes.manual_added == 0
    assert changes.untracked_deaths == 9


def test_existing_data_from_older_version_is_untracked(tmp_path):
    folder = tmp_path / "games/ds2"
    folder.mkdir(parents=True)
    (folder / "deaths.json").write_text('{ "deaths": 3 }', encoding="utf-8")
    (folder / "bosses.json").write_text(json.dumps({"Demon azylu": {"deaths": 1, "total_time_seconds": 89,
                                                                    "status": "POKONANO"}}), encoding="utf-8")
    audit = reopen(tmp_path, "ds2").audit
    assert audit.game.untracked_deaths == 3
    assert (audit.bosses["Demon azylu"].untracked_deaths, audit.bosses["Demon azylu"].untracked_seconds) == (1, 89)


def test_boss_corrections_through_tracker_and_rename(tmp_path, clock):
    game = reopen(tmp_path)
    tracker = BossTracker(game.boss_store, clock, audit=game.audit)
    tracker.set_enabled(True)
    tracker.boss_bar_visible()
    clock.advance(30)
    tracker.death()            # wykryta – nie jest korektą
    tracker.manual_add()       # ręczne +1
    tracker.manual_undo()      # ręczne −1
    tracker.rename("Smelter Demon")
    boss = reopen(tmp_path).audit.bosses["Smelter Demon"]
    assert (boss.manual_added, boss.manual_removed, boss.external_deaths) == (1, 1, 0)
    assert "Boss 1" not in reopen(tmp_path).audit.bosses


def test_audit_without_key_is_saved_unsigned(tmp_path):
    audit, warning = open_audit(tmp_path / "audit.json", None, 0, {})
    assert warning is None
    assert json.loads((tmp_path / "audit.json").read_text(encoding="utf-8"))["mac"] == ""


def test_certificate_with_corrections_shows_them_and_stays_valid(tmp_path):
    import os
    from datetime import datetime

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtPdf import QPdfDocument

    from deathcounter.report import CertificateData, Verdict, verify_pdf, write_certificate

    app = QGuiApplication.instance() or QGuiApplication([])  # noqa: F841
    game = reopen(tmp_path)
    game.store.set(4)
    game.audit.deaths_changed(4, manual=True)
    data = CertificateData("Dark Souls I", "Kacyn", 4, [], datetime(2026, 10, 18, 19, 0), adjustments(game))
    path = tmp_path / "cert.pdf"
    write_certificate(path, data, KEY)
    result = verify_pdf(path, KEY)
    assert result.verdict is Verdict.VALID
    assert result.data.adjustments.game.manual_added == 4
    doc = QPdfDocument()
    doc.load(str(path))
    assert doc.pageCount() == 2  # certyfikat + załącznik „Korekty”

    clean = CertificateData("Dark Souls I", "Kacyn", 4, [], datetime(2026, 10, 18, 19, 0),
                            adjustments(reopen(tmp_path / "inna")))
    write_certificate(tmp_path / "czysty.pdf", clean, KEY)
    doc2 = QPdfDocument()
    doc2.load(str(tmp_path / "czysty.pdf"))
    assert doc2.pageCount() == 1  # bez zmian – sam certyfikat, bez adnotacji
