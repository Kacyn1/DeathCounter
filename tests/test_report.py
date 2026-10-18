from datetime import datetime

import pytest

from deathcounter.bosses import STATUS_DEFEATED, STATUS_IN_PROGRESS, BossRecord
from deathcounter.report import BossRow, build_report_html, rows_from_records, write_pdf

WHEN = datetime(2026, 10, 18, 14, 45)


def test_report_lists_defeated_and_pending_bosses():
    rows = [
        BossRow("Demon z Azylu", 2, 151, True),
        BossRow("Taurus <Demon>", 5, 758, True),
        BossRow("Boss 3", 1, 42, False),
    ]
    html = build_report_html(42, rows, WHEN)
    assert "18.10.2026, 14:45" in html
    assert ">42<" in html                       # śmierci łącznie
    assert "Pokonani bossowie" in html and ">2<" in html
    assert "Taurus &lt;Demon&gt;" in html       # nazwa bezpiecznie wstawiona do HTML
    assert "12:38" in html and "02:31" in html  # czasy pokonania
    assert "Niepokonani" in html and "Boss 3" in html
    assert "15:51" in html                      # łączny czas walk z bossami


def test_report_without_bosses():
    html = build_report_html(3, [], WHEN)
    assert "Jeszcze żaden boss nie został pokonany." in html
    assert "Niepokonani" not in html


def test_rows_use_live_time_for_current_boss():
    records = {
        "A": BossRecord(1, 100, STATUS_DEFEATED),
        "B": BossRecord(2, 50, STATUS_IN_PROGRESS),
    }
    rows = rows_from_records(records, "B", 61.5)
    assert rows == [BossRow("A", 1, 100, True), BossRow("B", 2, 61.5, False)]


@pytest.fixture(scope="module")
def qt_app():
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QGuiApplication

    return QGuiApplication.instance() or QGuiApplication([])


def test_write_pdf_creates_pdf_file(qt_app, tmp_path):
    path = tmp_path / "raport ąę.pdf"
    write_pdf(path, build_report_html(1, [BossRow("Demon z Azylu", 1, 60, True)], WHEN))
    assert path.read_bytes().startswith(b"%PDF")
