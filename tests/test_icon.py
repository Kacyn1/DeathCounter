import os
import struct

import pytest


@pytest.fixture(scope="module")
def qt_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QGuiApplication

    return QGuiApplication.instance() or QGuiApplication([])


def test_icon_renders_in_all_sizes_with_transparent_corners(qt_app):
    from deathcounter.icon import ICO_SIZES, render

    for size in ICO_SIZES:
        image = render(size)
        assert (image.width(), image.height()) == (size, size)
        assert image.pixelColor(0, 0).alpha() == 0               # róg poza ramką jest przezroczysty
        assert image.pixelColor(size // 2, 0).red() > 200        # górna krawędź ramki jest czerwona


def test_pixel_art_rows_have_equal_width_and_fit_inside_frame():
    from deathcounter.icon import PIXEL_ART

    for size, glyphs in PIXEL_ART.items():
        for x0, y0, rows in glyphs:
            assert len({len(row) for row in rows}) == 1, (size, x0, y0)
            assert x0 >= 1 and y0 >= 1
            assert x0 + len(rows[0]) <= size - 1 and y0 + len(rows) <= size - 1, (size, x0, y0)


def test_taskbar_sizes_show_by_mk(qt_app):
    """Przy 24 i 32 px (pasek zadań) pod linią jest napis „by MK” – czerwone piksele w dolnej części."""
    from deathcounter.icon import render

    for size in (24, 32):
        image = render(size)
        lower = [image.pixelColor(x, y).red() > 200 for y in range(size * 3 // 5, size - 3) for x in range(2, size - 2)]
        assert sum(lower) > size  # są litery, a nie samo tło


def test_ico_file_contains_every_size(qt_app, tmp_path):
    from deathcounter.icon import ICO_SIZES, write_ico

    path = tmp_path / "DeathCounter.ico"
    write_ico(path)
    data = path.read_bytes()
    reserved, kind, count = struct.unpack("<HHH", data[:6])
    assert (reserved, kind, count) == (0, 1, len(ICO_SIZES))
