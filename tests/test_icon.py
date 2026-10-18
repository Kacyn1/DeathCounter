import os
import struct

import pytest


@pytest.fixture(scope="module")
def qt_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QGuiApplication

    return QGuiApplication.instance() or QGuiApplication([])


def test_logo_renders_in_all_icon_sizes_with_transparent_corners(qt_app):
    from deathcounter.icon import ICO_SIZES, LOGO_PATH, render

    assert LOGO_PATH.exists()
    for size in ICO_SIZES:
        image = render(size)
        assert (image.width(), image.height()) == (size, size)
    big = render(256)
    assert big.pixelColor(0, 0).alpha() == 0             # róg poza ramką jest przezroczysty
    assert big.pixelColor(128, 128).alpha() == 255       # środek logo jest pełny


def test_ico_file_contains_every_size(qt_app, tmp_path):
    from deathcounter.icon import ICO_SIZES, write_ico

    path = tmp_path / "DeathCounter.ico"
    write_ico(path)
    data = path.read_bytes()
    reserved, kind, count = struct.unpack("<HHH", data[:6])
    assert (reserved, kind, count) == (0, 1, len(ICO_SIZES))
