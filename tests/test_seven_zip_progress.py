"""7-Zip progress: parsing the -bsp2 stream and turning it into Progress events."""

import os
import sys

import pytest

from complex_unzip_tool_v2.classes.ArchiveTypes import ArchivePasswordError
from complex_unzip_tool_v2.modules import archive_utils as au
from complex_unzip_tool_v2.modules import events as ev
from complex_unzip_tool_v2.modules import pool_engine
from complex_unzip_tool_v2.modules import seven_zip_progress as szp

# Recorded from the bundled 7-Zip 26.03 on Windows: `7z x … -bsp2 big.7z.001`
# with stderr redirected (only the scanned folder is shortened).
RECORDED_OK = (
    b"  0M Scan C:\\archives\\\r"
    + b" " * 72
    + b"\r  0% 1 Open\r           \r  0%\r    \r 78% - big.bin\r              \r"
)
RECORDED_WRONG_PASSWORD = (
    b"  0M Scan C:\\archives\\\r"
    + b" " * 72
    + b"\r  0% 1 Open\r           \r  0%\r    \r 30% - big.bin\r              \r"
    b"ERROR: CRC Failed in encrypted file. Wrong password? : big.bin\r\n"
    b"100% - big.bin\r              \r"
)
# A console 7-Zip erases its progress line with backspaces instead.
BACKSPACED = b"  5%\b\b\b\b    \b\b\b\b 41% 3 - a.bin\b\b\b\b\b\b\b\b\b\b\b\b\b"


def parse(stream, chunk=None):
    parser = szp.ProgressParser()
    chunk = chunk or len(stream)
    percents = []
    for start in range(0, len(stream), chunk):
        percents += parser.feed(stream[start : start + chunk])
    percents += parser.close()
    return percents, parser.text


def test_recorded_stream_yields_percents_and_no_text():
    assert parse(RECORDED_OK) == ([0, 0, 78], b"")


def test_chunk_boundaries_do_not_matter():
    for stream in (RECORDED_OK, RECORDED_WRONG_PASSWORD, BACKSPACED):
        assert parse(stream, chunk=1) == parse(stream)


def test_backspace_separated_stream():
    assert parse(BACKSPACED) == ([5, 41], b"")


def test_error_text_is_kept_without_progress():
    percents, text = parse(RECORDED_WRONG_PASSWORD)
    assert percents == [0, 0, 30, 100]
    assert text == b"ERROR: CRC Failed in encrypted file. Wrong password? : big.bin"


def test_run_with_progress_reads_both_streams():
    script = (
        "import sys;"
        "sys.stderr.write('  0%\\r 55% - a\\r');"
        "sys.stderr.write('ERROR: boom\\r\\n');"
        "sys.stdout.write('Everything is Ok\\n' * 20000);"
        "sys.exit(2)"
    )
    seen = []
    stdout, stderr, code = szp.run_with_progress(
        [sys.executable, "-c", script], seen.append
    )
    assert seen == [0, 55]
    assert stderr == b"ERROR: boom"
    assert stdout.count(b"Everything is Ok") == 20000
    assert code == 2


# ------------------------------
# Extraction with progress
# ------------------------------


def _archive(tmp_path, name="a.7z", size=10):
    path = tmp_path / name
    path.write_bytes(b"x" * size)
    return str(path)


def test_extract_streams_progress_with_bsp2(tmp_path, monkeypatch):
    calls = []

    def fake_stream(cmd, on_progress):
        calls.append(cmd)
        for percent in (0, 50, 100):
            on_progress(percent)
        return b"Everything is Ok", b"", 0

    monkeypatch.setattr(au, "_resolve_seven_zip_path", lambda path: "7z")
    monkeypatch.setattr(szp, "run_with_progress", fake_stream)
    seen = []
    assert au.extractArchiveWith7z(
        _archive(tmp_path), str(tmp_path / "out"), on_progress=seen.append
    )
    assert seen == [0, 50, 100]
    assert "-bsp2" in calls[0]
    assert calls[0].index("-bsp2") < calls[0].index(str(tmp_path / "a.7z"))


def test_extract_without_progress_keeps_the_plain_runner(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(au, "_resolve_seven_zip_path", lambda path: "7z")
    monkeypatch.setattr(au, "_run_7z_cmd", lambda cmd: calls.append(cmd) or ("", "", 0))
    assert au.extractArchiveWith7z(_archive(tmp_path), str(tmp_path / "out"))
    assert "-bsp2" not in calls[0]


def test_streamed_errors_are_still_mapped(tmp_path, monkeypatch):
    def fake_stream(cmd, on_progress):
        _, text = parse(RECORDED_WRONG_PASSWORD)
        return b"Sub items Errors: 1", text, 2

    monkeypatch.setattr(au, "_resolve_seven_zip_path", lambda path: "7z")
    monkeypatch.setattr(szp, "run_with_progress", fake_stream)
    with pytest.raises(ArchivePasswordError):
        au.extractArchiveWith7z(
            _archive(tmp_path), str(tmp_path / "out"), on_progress=lambda p: None
        )


# ------------------------------
# Engine events
# ------------------------------


class _Book:
    def __init__(self, passwords=()):
        self.passwords = list(passwords)

    def get_passwords(self):
        return self.passwords

    def add_password(self, password):
        self.passwords.append(password)


def _fake_extract(percents):
    def extract(archive_path, output_path, password, on_progress=None, **kwargs):
        for percent in percents:
            on_progress(percent)
        return True

    return extract


def test_engine_emits_progress_on_percent_changes(tmp_path, monkeypatch):
    archive = _archive(tmp_path, size=1000)
    emitted = []
    engine = pool_engine.SevenZipEngine(_Book(), emit=emitted.append)
    monkeypatch.setattr(au, "extractArchiveWith7z", _fake_extract([0, 0, 40, 40, 100]))
    assert engine.extract(archive, str(tmp_path / "out")).ok
    assert emitted == [
        ev.Progress(archive, 0, 0, 1000),
        ev.Progress(archive, 40, 400, 1000),
        ev.Progress(archive, 100, 1000, 1000),
    ]


def test_engine_counts_the_bytes_of_every_volume_of_a_set(tmp_path, monkeypatch):
    primary = _archive(tmp_path, "X.7z.001", 600)
    _archive(tmp_path, "X.7z.002", 400)
    _archive(tmp_path, "other.7z.001", 5000)
    emitted = []
    engine = pool_engine.SevenZipEngine(_Book(), emit=emitted.append)
    monkeypatch.setattr(au, "extractArchiveWith7z", _fake_extract([50]))
    engine.extract(primary, str(tmp_path / "out"))
    assert emitted == [ev.Progress(primary, 50, 500, 1000)]


def test_engine_without_a_sink_extracts_without_progress(tmp_path, monkeypatch):
    seen = {}

    def extract(archive_path, output_path, password, on_progress=None, **kwargs):
        seen["on_progress"] = on_progress
        return True

    monkeypatch.setattr(au, "extractArchiveWith7z", extract)
    pool_engine.SevenZipEngine(_Book()).extract(
        _archive(tmp_path), str(tmp_path / "out")
    )
    assert seen["on_progress"] is None


def test_engine_restarts_progress_for_each_password(tmp_path, monkeypatch):
    archive = _archive(tmp_path, size=100)
    emitted = []
    attempts = iter([ArchivePasswordError("wrong"), None])

    def extract(archive_path, output_path, password, on_progress=None, **kwargs):
        on_progress(30)
        error = next(attempts)
        if error:
            raise error
        return True

    monkeypatch.setattr(au, "extractArchiveWith7z", extract)
    engine = pool_engine.SevenZipEngine(_Book(["pw"]), emit=emitted.append)
    assert engine.extract(archive, str(tmp_path / "out")).password_ref == 1
    assert [event.percent for event in emitted] == [30, 30]
    assert os.path.basename(emitted[0].path) == "a.7z"
