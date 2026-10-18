"""Ikona aplikacji: logo „DC by MK” – czerwony Arial Bold na czarnym, zaokrąglonym kwadracie z czerwoną ramką.

Każdy rozmiar jest rysowany osobno (nie zmniejszany z dużego obrazu), żeby napisy były wyraźne
także na pasku zadań (24–32 px). build.ps1 zapisuje z tego plik .ico dla PyInstallera:
    python -m deathcounter.icon build\\DeathCounter.ico
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QIcon, QImage, QPainter, QPainterPath, QPen, QPixmap

ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)
BACKGROUND = QColor(0, 0, 0)
RED = QColor(237, 28, 36)


def _text_path(text: str) -> QPainterPath:
    font = QFont("Arial")
    font.setBold(True)
    font.setPixelSize(200)
    path = QPainterPath()
    path.addText(QPointF(0, 0), font, text)
    return path


def _fill_text(painter: QPainter, text: str, box: QRectF) -> None:
    """Napis jak największy w ramach `box`, wyśrodkowany."""
    path = _text_path(text)
    bounds = path.boundingRect()
    scale = min(box.width() / bounds.width(), box.height() / bounds.height())
    painter.save()
    painter.translate(box.center())
    painter.scale(scale, scale)
    painter.translate(-bounds.center())
    painter.fillPath(path, RED)
    painter.restore()


def _draw_text_crisp(painter: QPainter, text: str, box: QRectF) -> None:
    """Małe ikony: największy całkowity rozmiar Arial, który mieści się w `box`, z hintingiem
    i położeniem wyrównanym do pikseli – litery są ostre zamiast rozmytych."""
    font = QFont("Arial")
    font.setBold(True)
    font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    # Bez wygładzania: Arial ma ręcznie dopracowany hinting dla małych rozmiarów, więc litery
    # składają się z pełnych pikseli (wygładzanie dawało rozmyte i kolorowe krawędzie).
    font.setStyleStrategy(QFont.StyleStrategy.NoAntialias)
    for pixels in range(int(box.height() * 2), 3, -1):
        font.setPixelSize(pixels)
        tight = QFontMetrics(font).tightBoundingRect(text)
        if tight.width() <= box.width() + 0.5 and tight.height() <= box.height() + 0.5:
            break
    x = round(box.center().x() - tight.width() / 2) - tight.left()
    y = round(box.center().y() - tight.height() / 2) - tight.top()
    painter.setFont(font)
    painter.setPen(RED)
    painter.drawText(x, y, text)


# Najmniejsze rozmiary (pasek zadań 24/32 px, pasek tytułu 16/20 px) są narysowane ręcznie piksel
# po pikselu w kształcie Arial Bold – automatyczne rysowanie czcionki daje tu nieczytelne „by MK”.
# (x, y, wiersze) – „X” to czerwony piksel. Przy 16 i 20 px na „by MK” nie ma miejsca: samo „DC” z linią.
PIXEL_ART = {
    16: [
        (3, 3, ["XXXX.", "XX.XX", "XX.XX", "XX.XX", "XX.XX", "XX.XX", "XX.XX", "XXXX."]),
        (9, 3, [".XXXX", "XX...", "XX...", "XX...", "XX...", "XX...", "XX...", ".XXXX"]),
        (3, 12, ["X" * 11]),
    ],
    20: [
        (3, 3, ["XXXXX.", "XXXXXX", "XX..XX", "XX..XX", "XX..XX", "XX..XX", "XX..XX", "XX..XX", "XXXXXX", "XXXXX."]),
        (11, 3, [".XXXXX", "XXXXXX", "XX....", "XX....", "XX....", "XX....", "XX....", "XX....", "XXXXXX", ".XXXXX"]),
        (3, 15, ["X" * 14]),
    ],
    24: [
        (4, 3, ["XXXXX..", "XXXXXX.", "XX..XXX", "XX...XX", "XX...XX", "XX..XXX", "XXXXXX.", "XXXXX.."]),
        (13, 3, ["..XXXXX", ".XXXXXX", "XXX....", "XX.....", "XX.....", "XXX....", ".XXXXXX", "..XXXXX"]),
        (4, 12, ["X" * 16]),
        (3, 14, ["X..", "X..", "XXX", "X.X", "X.X", "XXX"]),                       # b
        (7, 16, ["X.X", "X.X", "X.X", "XXX", "..X", "XX."]),                        # y
        (12, 14, ["X...X", "XX.XX", "X.X.X", "X...X", "X...X", "X...X"]),           # M
        (18, 14, ["X..X", "X.X.", "XX..", "XX..", "X.X.", "X..X"]),                 # K
    ],
    32: [
        (5, 4, ["XXXXXXX...", "XXXXXXXX..", "XXX...XXX.", "XXX....XXX", "XXX....XXX", "XXX....XXX",
                "XXX....XXX", "XXX....XXX", "XXX...XXX.", "XXXXXXXX..", "XXXXXXX..."]),
        (18, 4, ["..XXXXXX..", ".XXXXXXXXX", "XXX.....XX", "XXX.......", "XXX.......", "XXX.......",
                 "XXX.......", "XXX.......", "XXX.....XX", ".XXXXXXXXX", "..XXXXXX.."]),
        (5, 16, ["X" * 22, "X" * 22]),
        (2, 19, ["XX...", "XX...", "XXXX.", "XXXXX", "XX.XX", "XX.XX", "XXXXX"]),            # b
        (8, 21, ["XX.XX", "XX.XX", "XX.XX", "XXXXX", ".XXXX", "...XX", "XXXX."]),            # y
        (15, 19, ["XX....XX", "XXX..XXX", "XXXXXXXX", "XX.XX.XX", "XX....XX", "XX....XX", "XX....XX"]),  # M
        (24, 19, ["XX..XX", "XX.XX.", "XXXX..", "XXX...", "XXXX..", "XX.XX.", "XX..XX"]),     # K
    ],
}


def _render_pixel_art(size: int) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)  # bez wygładzania – każdy piksel ramki jest pełny
    # Zaokrąglona ramka 1 px, symetryczna: wcięcie krawędzi w kolejnych wierszach od góry (i od dołu).
    insets = [3, 2, 1] if size >= 32 else [2, 1]
    last = size - 1
    for y in range(size):
        inset = insets[min(y, last - y)] if min(y, last - y) < len(insets) else 0
        left, right = inset, last - inset
        if y in (0, last):
            painter.fillRect(left, y, right - left + 1, 1, RED)
            continue
        painter.fillRect(left + 1, y, right - left - 1, 1, BACKGROUND)
        painter.fillRect(left, y, 1, 1, RED)
        painter.fillRect(right, y, 1, 1, RED)
    for x0, y0, rows in PIXEL_ART[size]:
        for dy, row in enumerate(rows):
            for dx, cell in enumerate(row):
                if cell == "X":
                    painter.fillRect(x0 + dx, y0 + dy, 1, 1, RED)
    painter.end()
    return image


def render(size: int) -> QImage:
    if size in PIXEL_ART:
        return _render_pixel_art(size)
    s = float(size)
    small = size <= 64
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

    if small:
        # Pasek zadań: układ liczony w całych pikselach – ramka i linia po 1–2 px, reszta na napisy.
        border = 1 if size <= 32 else 2
        pad = 1 if size <= 24 else 2
        radius = s * 0.12
    else:
        border = max(1, round(s * 0.04))
        pad = round(s * 0.07)
        radius = s * 0.16
    frame = QRectF(border / 2, border / 2, s - border, s - border)
    painter.setPen(QPen(RED, border))
    painter.setBrush(BACKGROUND)
    painter.drawRoundedRect(frame, radius, radius)

    inner = border + pad
    top, bottom, width = inner, size - inner, size - 2 * inner
    line = max(1, round(s * 0.03))
    gap = max(1, round(s * 0.04))
    text_space = bottom - top - line - 2 * gap
    dc_height = round(text_space * 0.52)
    line_y = top + dc_height + gap
    draw = _draw_text_crisp if small else _fill_text
    draw(painter, "DC", QRectF(inner, top, width, dc_height))
    painter.fillRect(QRectF(inner + round(width * 0.08), line_y, width - 2 * round(width * 0.08), line), RED)
    mk_top = line_y + line + gap
    draw(painter, "by MK", QRectF(inner, mk_top, width, bottom - mk_top))
    painter.end()
    return image


def app_icon() -> QIcon:
    icon = QIcon()
    for size in ICO_SIZES:
        icon.addPixmap(QPixmap.fromImage(render(size)))
    return icon


def write_ico(path: Path) -> None:
    """Plik .ico z obrazami PNG we wszystkich rozmiarach (format obsługiwany od Windows Vista)."""
    images = []
    for size in ICO_SIZES:
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        render(size).save(buffer, "PNG")
        images.append((size, bytes(buffer.data())))

    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    entries, data = b"", b""
    for size, png in images:
        dim = size if size < 256 else 0  # 0 oznacza 256 px
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(png), offset + len(data))
        data += png
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + entries + data)


if __name__ == "__main__":
    from PySide6.QtGui import QGuiApplication

    _app = QGuiApplication(sys.argv)
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "DeathCounter.ico")
    write_ico(target)
    print(f"Zapisano {target}")
