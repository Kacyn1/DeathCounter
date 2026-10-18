"""Raport PDF: ogólna liczba śmierci oraz bossowie pokonani i niepokonani (śmierci, łączny czas walki)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from html import escape
from pathlib import Path

from .bosses import STATUS_DEFEATED, format_duration
from .storage import StorageError

ACCENT = "#9b1c1c"


@dataclass
class BossRow:
    name: str
    deaths: int
    seconds: float
    defeated: bool


def build_report_html(game: str, deaths: int, bosses: list[BossRow], generated_at: datetime) -> str:
    defeated = [b for b in bosses if b.defeated]
    pending = [b for b in bosses if not b.defeated]
    boss_deaths = sum(b.deaths for b in bosses)
    boss_time = sum(b.seconds for b in bosses)

    parts = [
        "<html><body style='font-family:\"Segoe UI\"; color:#1d1d1f;'>",
        f"<h1 style='color:{ACCENT}; margin-bottom:0;'>{escape(game)}</h1>",
        f"<p style='color:#6b6f76; margin-top:2px;'>Death Counter by MK – raport · "
        f"wygenerowano {generated_at:%d.%m.%Y, %H:%M}</p>",
        "<table width='100%' cellspacing='0' cellpadding='10' style='margin-top:12px;'><tr>",
        _stat("Śmierci łącznie", str(deaths)),
        _stat("Pokonani bossowie", str(len(defeated))),
        _stat("Śmierci przy bossach", str(boss_deaths)),
        _stat("Czas walk z bossami", format_duration(boss_time)),
        "</tr></table>",
        "<h2 style='margin-top:24px;'>Pokonani bossowie</h2>",
    ]
    if defeated:
        parts.append(_boss_table(defeated, "Czas pokonania"))
    else:
        parts.append("<p style='color:#6b6f76;'>Jeszcze żaden boss nie został pokonany.</p>")
    if pending:
        parts.append("<h2 style='margin-top:24px;'>Niepokonani (walka w trakcie)</h2>")
        parts.append(_boss_table(pending, "Czas walki"))
    parts.append(
        "<p style='color:#9aa0a6; font-size:8pt; margin-top:24px;'>Czas walki to łączny czas aktywnej walki "
        "z bossem ze wszystkich podejść, bez powrotów na arenę.</p>"
    )
    parts.append("</body></html>")
    return "".join(parts)


def write_pdf(path: Path, html: str) -> None:
    """Zapisuje raport jako PDF (A4). Wymaga działającej aplikacji Qt (QGuiApplication)."""
    from PySide6.QtCore import QMarginsF
    from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter, QTextDocument

    path = Path(path)
    writer = QPdfWriter(str(path))
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageMargins(QMarginsF(18, 18, 18, 18), QPageLayout.Unit.Millimeter)
    writer.setTitle("Death Counter by MK – raport")
    writer.setCreator("Death Counter by MK")
    document = QTextDocument()
    document.setDocumentMargin(0)  # marginesy strony ustawia już QPdfWriter
    document.setHtml(html)
    document.print_(writer)
    del writer  # zamyka plik
    if not path.exists() or path.stat().st_size == 0:
        raise StorageError(f"Nie udało się zapisać raportu {path.name} (sprawdź, czy plik nie jest otwarty).")


def rows_from_records(records: dict, current: str | None, current_seconds: float) -> list[BossRow]:
    """Wiersze raportu z bosses.json; bieżący boss dostaje czas liczony na żywo (z biegnącą walką)."""
    rows = []
    for name, record in records.items():
        seconds = current_seconds if name == current else record.total_time_seconds
        rows.append(BossRow(name, record.deaths, seconds, record.status == STATUS_DEFEATED))
    return rows


def _stat(label: str, value: str) -> str:
    return (
        "<td align='center' style='background:#f3f1ee; border:1px solid #e2ded8;'>"
        f"<div style='font-size:22pt; font-weight:bold; color:{ACCENT};'>{escape(value)}</div>"
        f"<div style='color:#6b6f76;'>{escape(label)}</div></td>"
    )


def _boss_table(rows: list[BossRow], time_label: str) -> str:
    header = (
        "<tr style='background:#2b2c30; color:white;'>"
        "<th align='left' width='6%'>#</th><th align='left' width='56%'>Boss</th>"
        f"<th align='right' width='16%'>Śmierci</th><th align='right' width='22%'>{escape(time_label)}</th></tr>"
    )
    body = []
    for i, row in enumerate(rows, 1):
        shade = "#ffffff" if i % 2 else "#f6f5f3"
        body.append(
            f"<tr style='background:{shade};'><td>{i}</td><td>{escape(row.name)}</td>"
            f"<td align='right'>{row.deaths}</td><td align='right'>{format_duration(row.seconds)}</td></tr>"
        )
    return (
        "<table width='100%' cellspacing='0' cellpadding='6' style='border:1px solid #e2ded8;'>"
        + header + "".join(body) + "</table>"
    )
