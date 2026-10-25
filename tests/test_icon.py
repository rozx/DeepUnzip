"""The pixel-art icon is written as SVG, PNG and a multi-size ICO."""

import re
import struct

from scripts import generate_icon as icon


def _png_size(data):
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", data[16:24])


def test_pixel_grid_is_16_by_16_with_known_colors():
    assert len(icon.PIXELS) == 16
    for row in icon.PIXELS:
        assert len(row) == 16
        assert set(row) <= set(icon.PALETTE) | {"."}


def test_png_scales_every_pixel_by_an_integer():
    assert _png_size(icon.png_bytes(16)) == (256, 256)
    assert _png_size(icon.png_bytes(1)) == (16, 16)


def test_ico_holds_one_png_per_size():
    data = icon.ico_bytes()
    reserved, kind, count = struct.unpack("<HHH", data[:6])
    assert (reserved, kind, count) == (0, 1, len(icon.ICO_SIZES))
    for index, size in enumerate(icon.ICO_SIZES):
        entry = data[6 + 16 * index : 22 + 16 * index]
        width, height, _, _, planes, bits, length, offset = struct.unpack(
            "<BBBBHHII", entry
        )
        assert (width or 256, height or 256, planes, bits) == (size, size, 1, 32)
        assert _png_size(data[offset : offset + length]) == (size, size)


def test_svg_draws_exactly_the_opaque_pixels():
    svg = icon.svg_text()
    assert 'viewBox="0 0 16 16"' in svg and 'shape-rendering="crispEdges"' in svg
    widths = [int(w) for w in re.findall(r'<rect x="\d+" y="\d+" width="(\d+)"', svg)]
    opaque = sum(char != "." for row in icon.PIXELS for char in row)
    assert sum(widths) == opaque
