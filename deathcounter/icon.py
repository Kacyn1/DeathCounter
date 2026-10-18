"""Ikona aplikacji: logo „DC by MK” (assets/logo.png, przezroczyste rogi poza czerwoną ramką).

Okno korzysta z logo bezpośrednio, a build.ps1 zapisuje z niego plik .ico dla PyInstallera:
    python -m deathcounter.icon build\\DeathCounter.ico
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QIcon, QImage, QPixmap

LOGO_PATH = Path(__file__).resolve().parent / "assets" / "logo.png"
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def render(size: int) -> QImage:
    """Logo w danym rozmiarze. Zmniejszanie po połowie daje wyraźniejsze małe ikony niż jeden duży krok."""
    image = QImage(str(LOGO_PATH))
    if image.isNull():
        raise FileNotFoundError(f"Brak pliku logo: {LOGO_PATH}")
    while image.width() >= size * 2:
        image = image.scaled(
            image.width() // 2, image.height() // 2,
            Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation,
        )
    return image.scaled(size, size, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)


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
