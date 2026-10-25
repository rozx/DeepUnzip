"""
Generate the DeepUnzip icon: a cat peeking out of a cardboard box.
生成 DeepUnzip 图标：从纸箱里探出头的猫。

The icon is the 16x16 pixel art in PIXELS. It is written as:

- icons/app_icon.svg: one rect per run of same-colored pixels (READMEs);
- icons/app_icon.png: 256x256;
- icons/app_icon.ico: 16 to 256 px, the Windows executable's icon.

Every size is an integer multiple of 16, so the pixels stay sharp. Only the
standard library is needed.

Usage: poetry run python -m scripts.generate_icon
"""

import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ICONS = ROOT / "icons"
ICO_SIZES = (16, 32, 48, 64, 128, 256)

PALETTE = {
    "o": "4A3B5C",  # outline
    "e": "3A2C4A",  # eyes and mouth
    "c": "FFF1D6",  # cat
    "p": "FF9EB5",  # blush
    "t": "F2C38B",  # cardboard
    "T": "D9985B",  # cardboard shade and tape
}
PIXELS = (
    "................",
    "...o........o...",
    "..oco......oco..",
    "..occoooooocco..",
    "..occcccccccco..",
    "..occeccccecco..",
    "..opceccccecpo..",
    "..occcceecccco..",
    ".oooccooooccooo.",
    ".otttttTTttttto.",
    ".otttttTTttttto.",
    ".otttttTTttttto.",
    ".otttttTTttttto.",
    ".oTTTTTTTTTTTTo.",
    "..oooooooooooo..",
    "................",
)


def _rgba(char: str) -> bytes:
    if char == ".":
        return b"\x00\x00\x00\x00"
    return bytes.fromhex(PALETTE[char]) + b"\xff"


def png_bytes(scale: int) -> bytes:
    """The icon as an RGBA PNG, each pixel drawn as scale x scale."""
    rows = []
    for line in PIXELS:
        row = b"".join(_rgba(char) * scale for char in line)
        rows.extend([b"\x00" + row] * scale)  # filter type 0 per row

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    size = 16 * scale
    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(b"".join(rows), 9))
        + chunk(b"IEND", b"")
    )


def ico_bytes() -> bytes:
    """A Windows ICO with one PNG-compressed image per size in ICO_SIZES."""
    images = [png_bytes(size // 16) for size in ICO_SIZES]
    offset = 6 + 16 * len(images)
    entries = []
    for size, image in zip(ICO_SIZES, images):
        side = size % 256  # 0 means 256
        entries.append(
            struct.pack("<BBBBHHII", side, side, 0, 0, 1, 32, len(image), offset)
        )
        offset += len(image)
    return struct.pack("<HHH", 0, 1, len(images)) + b"".join(entries) + b"".join(images)


def svg_text() -> str:
    """The icon as SVG: one rect per horizontal run of one color."""
    rects = []
    for y, line in enumerate(PIXELS):
        x = 0
        while x < len(line):
            char = line[x]
            run = 1
            while x + run < len(line) and line[x + run] == char:
                run += 1
            if char != ".":
                rects.append(
                    f'<rect x="{x}" y="{y}" width="{run}" height="1" '
                    f'fill="#{PALETTE[char]}"/>'
                )
            x += run
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" '
        'viewBox="0 0 16 16" shape-rendering="crispEdges">\n'
        "<title>DeepUnzip</title>\n" + "\n".join(rects) + "\n</svg>\n"
    )


def write_icons(directory: Path = ICONS) -> list[Path]:
    directory.mkdir(exist_ok=True)
    outputs = {
        "app_icon.svg": svg_text().encode("utf-8"),
        "app_icon.png": png_bytes(16),
        "app_icon.ico": ico_bytes(),
    }
    for name, data in outputs.items():
        (directory / name).write_bytes(data)
    return [directory / name for name in outputs]


def main() -> None:
    for path in write_icons():
        print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
