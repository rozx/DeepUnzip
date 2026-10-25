"""
Live progress from a 7-Zip extraction.
读取 7-Zip 解压的实时进度。

With `-bsp2`, 7-Zip writes its percentage line to stderr and redraws it in
place: Windows separates updates with `\\r` when stderr is redirected, a
console build erases them with `\\b`. Error lines (`ERROR: …`) go to the same
stream, so the parser keeps every non-progress segment as error text for
`archive_utils._raise_for_7z_error`. stdout keeps 7-Zip's normal output.
"""

import os
import re
import subprocess
import threading
from typing import Callable, Optional

_SEPARATORS = re.compile(rb"[\b\r\n]")
_PERCENT = re.compile(rb"^\s*(\d{1,3})%")
# Size-only status lines shown before the total is known, e.g. "  0M Scan …".
_STATUS = re.compile(rb"^\s*\d+[KMGTP]\s")


class ProgressParser:
    """Feed raw stderr bytes; get percentages and the remaining error text."""

    def __init__(self) -> None:
        self._pending = b""
        self._text: list[bytes] = []

    def feed(self, data: bytes) -> list[int]:
        segments = _SEPARATORS.split(self._pending + data)
        self._pending = segments.pop()
        return [p for p in map(self._segment, segments) if p is not None]

    def close(self) -> list[int]:
        rest, self._pending = self._pending, b""
        percent = self._segment(rest)
        return [] if percent is None else [percent]

    @property
    def text(self) -> bytes:
        return b"\n".join(self._text)

    def _segment(self, segment: bytes) -> Optional[int]:
        match = _PERCENT.match(segment)
        if match:
            return min(int(match.group(1)), 100)
        if segment.strip() and not _STATUS.match(segment):
            self._text.append(segment.strip())
        return None


def run_with_progress(
    cmd: list[str], on_progress: Callable[[int], None]
) -> tuple[bytes, bytes, int]:
    """Run 7-Zip, reporting percentages; return stdout, error text and exit code."""
    parser = ProgressParser()
    chunks: list[bytes] = []
    with subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as process:
        stdout, stderr = process.stdout, process.stderr
        assert stdout is not None and stderr is not None
        # Drain stdout in the background so a full pipe never blocks 7-Zip.
        reader = threading.Thread(target=lambda: chunks.append(stdout.read()))
        reader.daemon = True
        reader.start()
        while True:
            data = os.read(stderr.fileno(), 4096)  # returns what is available
            if not data:
                break
            for percent in parser.feed(data):
                on_progress(percent)
        for percent in parser.close():
            on_progress(percent)
        reader.join()
        code = process.wait()
    return b"".join(chunks), parser.text, code
