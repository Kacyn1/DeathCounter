"""Ikona aplikacji: czerwone „DC” na ciemnym, zaokrąglonym kwadracie, rysowane w Qt.

Okno korzysta z ikony narysowanej w locie, a build.ps1 zapisuje z niej plik .ico dla PyInstallera:
    python -m deathcounter.icon build\\DeathCounter.ico
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QImage, QPainter, QPainterPath, QPen, QPixmap

ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)
BACKGROUND = QColor(24, 25, 28)
BORDER = QColor(110, 22, 22)
TEXT = QColor(220, 38, 38)


def render(size: int) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    border = max(1.0, size / 32)
    box = QRectF(0, 0, size, size).adjusted(border / 2, border / 2, -border / 2, -border / 2)
    radius = size * 0.18
    painter.setPen(QPen(BORDER, border) if size >= 24 else Qt.PenStyle.NoPen)
    painter.setBrush(BACKGROUND)
    painter.drawRoundedRect(box, radius, radius)

    font = QFont("Segoe UI")
    font.setWeight(QFont.Weight.Black)
    font.setPixelSize(100)
    path = QPainterPath()
    path.addText(QPointF(0, 0), font, "DC")
    bounds = path.boundingRect()
    # Mniejsze rozmiary dostają większe litery, żeby napis był czytelny na pasku zadań.
    fill = 0.88 if size <= 24 else 0.76
    scale = min(size * fill / bounds.width(), size * 0.62 / bounds.height())
    painter.translate(size / 2, size / 2)
    painter.scale(scale, scale)
    painter.translate(-bounds.center())
    painter.fillPath(path, TEXT)
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
