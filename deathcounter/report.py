"""Certyfikat PDF: gra, gracz, śmierci i pokonani bossowie – z kodem weryfikacyjnym i ukrytym znakiem wodnym.

Zabezpieczenia:
- kod weryfikacyjny (HMAC z kluczem z exe) wydrukowany na certyfikacie,
- podpisane dane zapisane w metadanych XMP pliku – „Sprawdź certyfikat…” porównuje je z kodem,
- prawie niewidoczny mikrotekst (kod, gra, gracz, śmierci) pokrywający całą stronę.
"""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from .bosses import STATUS_DEFEATED, format_duration
from .signing import matches, verification_code
from .storage import StorageError

APP_NAME = "Death Counter by MK"
CERT_VERSION = 1
MAX_BOSSES_ON_CERTIFICATE = 6
APPENDIX_ROWS_PER_PAGE = 22
_XMP_PATTERN = re.compile(rb"<dcmk:payload>([A-Za-z0-9+/=]+)</dcmk:payload>\s*<dcmk:code>([A-Z0-9-]*)</dcmk:code>")


@dataclass
class BossRow:
    name: str
    deaths: int
    seconds: float
    defeated: bool


@dataclass
class CertificateData:
    game: str
    player: str
    deaths: int
    bosses: list[BossRow]
    issued: datetime

    @property
    def defeated(self) -> list[BossRow]:
        return [b for b in self.bosses if b.defeated]

    def payload(self) -> bytes:
        """Kanoniczny zapis danych, które podpisujemy (ta sama treść zawsze daje te same bajty)."""
        data = {
            "v": CERT_VERSION,
            "app": APP_NAME,
            "game": self.game,
            "player": self.player,
            "deaths": self.deaths,
            "bosses": [[b.name, b.deaths, int(b.seconds), b.defeated] for b in self.bosses],
            "issued": self.issued.strftime("%Y-%m-%dT%H:%M"),
        }
        return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

    @classmethod
    def from_payload(cls, payload: bytes) -> "CertificateData":
        data = json.loads(payload.decode("utf-8"))
        bosses = [BossRow(str(n), int(d), float(s), bool(f)) for n, d, s, f in data["bosses"]]
        return cls(data["game"], data["player"], int(data["deaths"]), bosses,
                   datetime.strptime(data["issued"], "%Y-%m-%dT%H:%M"))


def rows_from_records(records: dict, current: str | None, current_seconds: float) -> list[BossRow]:
    """Wiersze z bosses.json; bieżący boss dostaje czas liczony na żywo (z biegnącą walką)."""
    rows = []
    for name, record in records.items():
        seconds = current_seconds if name == current else record.total_time_seconds
        rows.append(BossRow(name, record.deaths, seconds, record.status == STATUS_DEFEATED))
    return rows


# ------------------------------------------------------------------ weryfikacja

class Verdict(Enum):
    VALID = "valid"                  # dane i kod się zgadzają
    INVALID = "invalid"              # dane albo kod zmienione
    UNSIGNED = "unsigned"            # wystawiony bez klucza (wersja ze źródeł) – nie da się potwierdzić
    NOT_CERTIFICATE = "not_certificate"
    NO_KEY = "no_key"                # ten program nie ma klucza, by sprawdzić podpis


@dataclass
class Verification:
    verdict: Verdict
    data: CertificateData | None = None
    code: str = ""


def verify_pdf(path: Path, key: bytes | None) -> Verification:
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        raise StorageError(f"Nie można odczytać pliku {Path(path).name}: {exc}") from exc
    match = _XMP_PATTERN.search(raw)
    if match is None:
        return Verification(Verdict.NOT_CERTIFICATE)
    try:
        payload = base64.b64decode(match.group(1), validate=True)
        data = CertificateData.from_payload(payload)
    except (ValueError, KeyError, TypeError):
        return Verification(Verdict.INVALID)
    code = match.group(2).decode("ascii")
    if not code:
        return Verification(Verdict.UNSIGNED, data)
    if key is None:
        return Verification(Verdict.NO_KEY, data, code)
    verdict = Verdict.VALID if matches(payload, code, key) else Verdict.INVALID
    return Verification(verdict, data, code)


# ------------------------------------------------------------------ rysowanie

def write_certificate(path: Path, data: CertificateData, key: bytes | None) -> str:
    """Zapisuje certyfikat (A4 poziomo) i zwraca kod weryfikacyjny („” bez klucza).
    Wymaga działającej aplikacji Qt (QGuiApplication)."""
    from PySide6.QtCore import QByteArray, QMarginsF
    from PySide6.QtGui import QPageLayout, QPageSize, QPainter, QPdfWriter

    payload = data.payload()
    code = verification_code(payload, key) if key else ""
    path = Path(path)
    writer = QPdfWriter(str(path))
    writer.setResolution(300)
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageOrientation(QPageLayout.Orientation.Landscape)
    writer.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Millimeter)
    writer.setTitle(f"Certyfikat – {data.game}")
    writer.setCreator(APP_NAME)
    writer.setDocumentXmpMetadata(QByteArray(_xmp(payload, code)))

    painter = QPainter(writer)
    if not painter.isActive():
        raise StorageError(f"Nie można zapisać pliku {path.name} (sprawdź, czy nie jest otwarty w innym programie).")
    page = _Page(painter, writer.width(), writer.height())
    page.certificate(data, code)
    appendix = data.bosses if len(data.defeated) > MAX_BOSSES_ON_CERTIFICATE or len(data.bosses) > len(data.defeated) else []
    for start in range(0, len(appendix), APPENDIX_ROWS_PER_PAGE):
        writer.newPage()
        page.appendix(data, code, appendix[start:start + APPENDIX_ROWS_PER_PAGE], start)
    painter.end()
    del writer  # zamyka plik
    if not path.exists() or path.stat().st_size == 0:
        raise StorageError(f"Nie udało się zapisać pliku {path.name}.")
    return code


def _xmp(payload: bytes, code: str) -> bytes:
    encoded = base64.b64encode(payload).decode("ascii")
    return (
        '<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description rdf:about="" xmlns:dcmk="https://github.com/Kacyn1/DeathCounter/ns/1.0/">'
        f"<dcmk:payload>{encoded}</dcmk:payload><dcmk:code>{code}</dcmk:code>"
        '</rdf:Description></rdf:RDF></x:xmpmeta><?xpacket end="w"?>'
    ).encode("utf-8")


class _Page:
    """Rysowanie w milimetrach na stronie A4 poziomo (297 × 210 mm)."""

    CREAM = (251, 247, 239)
    RED = (155, 28, 28)
    GOLD = (185, 160, 110)
    INK = (29, 29, 31)
    MUTED = (110, 106, 100)

    def __init__(self, painter, width_px: int, height_px: int) -> None:
        from PySide6.QtGui import QPainter

        self.p = painter
        self.p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        self.p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.k = width_px / 297.0  # pikseli na mm
        self.w, self.h = 297.0, 210.0

    # --- narzędzia ---

    def _color(self, rgb, alpha: int = 255):
        from PySide6.QtGui import QColor

        return QColor(*rgb, alpha)

    def _rect(self, x, y, w, h):
        from PySide6.QtCore import QRectF

        return QRectF(x * self.k, y * self.k, w * self.k, h * self.k)

    def _font(self, family: str, size_mm: float, bold=False, italic=False, spacing: float = 0.0):
        from PySide6.QtGui import QFont

        font = QFont(family)
        font.setPixelSize(max(1, round(size_mm * self.k)))
        font.setBold(bold)
        font.setItalic(italic)
        if spacing:
            font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 100 + spacing)
        return font

    def text(self, x, y, w, h, text, family="Arial", size=4.0, bold=False, italic=False,
             color=INK, align="center", spacing=0.0, fit=True):
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QFontMetricsF

        font = self._font(family, size, bold, italic, spacing)
        if fit:  # zbyt długi napis (np. nazwa gry dodanej przez gracza) jest zmniejszany
            while QFontMetricsF(font).horizontalAdvance(text) > w * self.k and font.pixelSize() > 8:
                font.setPixelSize(int(font.pixelSize() * 0.94))
        flags = {"center": Qt.AlignmentFlag.AlignHCenter, "left": Qt.AlignmentFlag.AlignLeft,
                 "right": Qt.AlignmentFlag.AlignRight}[align] | Qt.AlignmentFlag.AlignVCenter
        self.p.setFont(font)
        self.p.setPen(self._color(color))
        self.p.drawText(self._rect(x, y, w, h), int(flags), text)

    def line(self, x1, y1, x2, y2, color=GOLD, width=0.35):
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QPen

        self.p.setPen(QPen(self._color(color), width * self.k))
        self.p.drawLine(QPointF(x1 * self.k, y1 * self.k), QPointF(x2 * self.k, y2 * self.k))

    def logo(self, cx, cy, size):
        from .icon import render

        image = render(1024)
        self.p.drawImage(self._rect(cx - size / 2, cy - size / 2, size, size), image)

    # --- elementy wspólne ---

    def background(self, data: CertificateData, code: str) -> None:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QPen

        self.p.fillRect(self._rect(0, 0, self.w, self.h), self._color(self.CREAM))
        self.watermark(data, code)
        self.p.setBrush(Qt.BrushStyle.NoBrush)
        self.p.setPen(QPen(self._color(self.RED), 2.2 * self.k))
        self.p.drawRect(self._rect(8, 8, self.w - 16, self.h - 16))
        self.p.setPen(QPen(self._color(self.GOLD), 0.5 * self.k))
        self.p.drawRect(self._rect(11.5, 11.5, self.w - 23, self.h - 23))
        for cx, cy in ((11.5, 11.5), (self.w - 11.5, 11.5), (11.5, self.h - 11.5), (self.w - 11.5, self.h - 11.5)):
            self._diamond(cx, cy, 2.2)

    def _diamond(self, cx, cy, r):
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QPolygonF

        self.p.setPen(self._color(self.GOLD))
        self.p.setBrush(self._color(self.RED))
        k = self.k
        self.p.drawPolygon(QPolygonF([QPointF(cx * k, (cy - r) * k), QPointF((cx + r) * k, cy * k),
                                      QPointF(cx * k, (cy + r) * k), QPointF((cx - r) * k, cy * k)]))

    def watermark(self, data: CertificateData, code: str) -> None:
        """Mikrotekst w kolorze prawie identycznym z tłem – niewidoczny gołym okiem, widoczny po powiększeniu."""
        mark = f"{APP_NAME} · {code or 'NIEPODPISANY'} · {data.game} · {data.player or '-'} · śmierci {data.deaths} · "
        self.p.save()
        self.p.setFont(self._font("Arial", 1.3))
        self.p.setPen(self._color(self.RED, 7))
        self.p.translate(self.w / 2 * self.k, self.h / 2 * self.k)
        self.p.rotate(-28)
        row = mark * 12
        for i in range(-60, 61):
            self.p.drawText(int(-250 * self.k), int(i * 2.6 * self.k), row)
        self.p.restore()

    def footer(self, data: CertificateData, code: str) -> None:
        y = 172
        self.line(32, y, 92, y)
        self.text(32, y + 1, 60, 6, "DATA WYSTAWIENIA", size=2.6, color=self.MUTED, spacing=12)
        self.text(32, y + 6, 60, 6, data.issued.strftime("%d.%m.%Y, %H:%M"), size=3.8, bold=True)
        self.line(self.w - 92, y, self.w - 32, y)
        self.text(self.w - 92, y + 1, 60, 6, "KOD WERYFIKACYJNY", size=2.6, color=self.MUTED, spacing=12)
        self.text(self.w - 92, y + 6, 60, 6, code or "brak – wersja bez podpisu", family="Consolas",
                  size=3.8, bold=True, color=self.RED if code else self.MUTED)
        self.seal(self.w / 2, 173)
        self.text(20, 192, self.w - 40, 5,
                  f"Autentyczność sprawdzisz w programie {APP_NAME}: przycisk „Sprawdź certyfikat…”.",
                  size=2.4, color=self.MUTED)

    def seal(self, cx, cy) -> None:
        from PySide6.QtCore import QPointF, Qt
        from PySide6.QtGui import QPen

        k = self.k
        self.p.setBrush(Qt.BrushStyle.NoBrush)
        self.p.setPen(QPen(self._color(self.RED), 1.2 * k))
        self.p.drawEllipse(QPointF(cx * k, cy * k), 15 * k, 15 * k)
        self.p.setPen(QPen(self._color(self.GOLD), 0.4 * k))
        self.p.drawEllipse(QPointF(cx * k, cy * k), 13 * k, 13 * k)
        self.logo(cx, cy, 17)

    # --- strony ---

    def certificate(self, data: CertificateData, code: str) -> None:
        self.background(data, code)
        self.logo(self.w / 2, 30, 20)
        self.text(0, 41, self.w, 6, APP_NAME.upper(), size=3.0, bold=True, color=self.MUTED, spacing=25)
        self.text(0, 47, self.w, 18, "CERTYFIKAT", family="Georgia", size=15, bold=True, spacing=8)
        self.line(self.w / 2 - 45, 66, self.w / 2 + 45, 66)
        if data.player:
            self.text(0, 69, self.w, 7, "Niniejszym poświadcza się zmagania gracza", family="Georgia", size=4.2,
                      italic=True, color=self.MUTED)
            self.text(30, 76, self.w - 60, 13, data.player, family="Georgia", size=9, bold=True, italic=True)
            self.text(0, 89, self.w, 6, "w grze", family="Georgia", size=4.2, italic=True, color=self.MUTED)
        else:
            self.text(0, 76, self.w, 13, "Niniejszym poświadcza się zmagania w grze", family="Georgia", size=5.5,
                      italic=True, color=self.MUTED)
        self.text(30, 95, self.w - 60, 13, data.game, size=8.5, bold=True, color=self.RED)
        self.stats(data, 111)
        self.boss_list(data, 135)
        self.footer(data, code)

    def stats(self, data: CertificateData, y: float) -> None:
        boss_deaths = sum(b.deaths for b in data.bosses)
        boss_time = sum(b.seconds for b in data.defeated)
        items = [
            (str(data.deaths), "ŚMIERCI ŁĄCZNIE"),
            (str(len(data.defeated)), "POKONANI BOSSOWIE"),
            (str(boss_deaths), "ŚMIERCI PRZY BOSSACH"),
            (format_duration(boss_time), "CZAS POKONANIA BOSSÓW"),
        ]
        width, gap = 50, 6
        x = (self.w - (len(items) * width + (len(items) - 1) * gap)) / 2
        for value, label in items:
            self.p.fillRect(self._rect(x, y, width, 20), self._color((243, 236, 224)))
            self.line(x, y, x + width, y, color=self.RED, width=0.6)
            self.text(x, y + 2, width, 11, value, size=7, bold=True, color=self.RED)
            self.text(x, y + 13, width, 5, label, size=2.4, color=self.MUTED, spacing=10)
            x += width + gap

    def boss_list(self, data: CertificateData, y: float) -> None:
        defeated = data.defeated
        if not defeated:
            self.text(0, y + 4, self.w, 8, "Pierwszy boss wciąż czeka na pokonanie.", family="Georgia",
                      size=4, italic=True, color=self.MUTED)
            return
        shown = defeated[:MAX_BOSSES_ON_CERTIFICATE]
        columns = 2 if len(shown) > 3 else 1
        per_column = -(-len(shown) // columns)
        col_w = 100 if columns == 2 else 130
        total_w = columns * col_w + (columns - 1) * 10
        x0 = (self.w - total_w) / 2
        self.text(0, y, self.w, 5, "POKONANI BOSSOWIE", size=2.8, bold=True, color=self.MUTED, spacing=15)
        for i, boss in enumerate(shown):
            col, row = divmod(i, per_column)
            x, ry = x0 + col * (col_w + 10), y + 7 + row * 7
            self.text(x, ry, col_w - 42, 6, boss.name, family="Georgia", size=3.6, align="left")
            self.text(x + col_w - 42, ry, 20, 6, f"{boss.deaths} †", size=3.4, color=self.RED, align="right")
            self.text(x + col_w - 22, ry, 22, 6, format_duration(boss.seconds), size=3.4, align="right")
            self.line(x, ry + 6.3, x + col_w, ry + 6.3, width=0.2)
        rest = len(defeated) - len(shown)
        if rest > 0:
            self.text(0, y + 7 + per_column * 7 + 1, self.w, 5, f"…oraz {rest} kolejnych – pełna lista w załączniku",
                      size=2.8, italic=True, color=self.MUTED)

    def appendix(self, data: CertificateData, code: str, rows: list[BossRow], start: int) -> None:
        self.background(data, code)
        self.logo(30, 27, 13)
        self.text(40, 20, 150, 8, "ZAŁĄCZNIK DO CERTYFIKATU", size=3.2, bold=True, color=self.MUTED,
                  align="left", spacing=15)
        self.text(40, 27, 200, 9, f"{data.game} – lista bossów", family="Georgia", size=6, bold=True, align="left")
        x, w, y = 30, self.w - 60, 42
        headers = (("#", 10, "left"), ("Boss", w - 105, "left"), ("Status", 35, "left"),
                   ("Śmierci", 25, "right"), ("Czas walki", 35, "right"))
        self.p.fillRect(self._rect(x, y, w, 7), self._color(self.RED))
        cx = x + 2
        for title, cw, align in headers:
            self.text(cx, y, cw - 4, 7, title, size=3.0, bold=True, color=(255, 255, 255), align=align)
            cx += cw
        for i, boss in enumerate(rows):
            ry = y + 7 + i * 5.6
            if i % 2:
                self.p.fillRect(self._rect(x, ry, w, 5.6), self._color((243, 236, 224)))
            values = (str(start + i + 1), boss.name, "pokonany" if boss.defeated else "w trakcie",
                      str(boss.deaths), format_duration(boss.seconds))
            cx = x + 2
            for (title, cw, align), value in zip(headers, values):
                self.text(cx, ry, cw - 4, 5.6, value, size=2.9, align=align,
                          color=self.RED if title == "Status" and boss.defeated else self.INK)
                cx += cw
        self.text(0, 191, self.w, 5, f"Kod weryfikacyjny: {code or 'brak – wersja bez podpisu'}",
                  family="Consolas", size=2.6, color=self.MUTED)
