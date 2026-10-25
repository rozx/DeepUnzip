import platform
import subprocess
import sys
from pathlib import Path

import pytest

from deepunzip.classes.ArchiveTypes import SevenZipNotFoundError
from deepunzip.modules import archive_utils as au


@pytest.mark.parametrize(
    "system,machine,relative",
    [
        ("Windows", "AMD64", "7z/windows-x64/7z.exe"),
        ("Windows", "x86_64", "7z/windows-x64/7z.exe"),
        ("Darwin", "arm64", "7z/macos/7zz"),
        ("Darwin", "x86_64", "7z/macos/7zz"),
        ("Linux", "x86_64", "7z/linux-x64/7zzs"),
        ("Linux", "aarch64", "7z/linux-arm64/7zzs"),
        ("Linux", "arm64", "7z/linux-arm64/7zzs"),
    ],
)
def test_archive_operations_use_native_bundle(
    monkeypatch, tmp_path, system, machine, relative
):
    monkeypatch.setattr(platform, "system", lambda: system)
    monkeypatch.setattr(platform, "machine", lambda: machine)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "bundle"), raising=False)
    engine = tmp_path / "bundle" / relative
    engine.parent.mkdir(parents=True)
    engine.touch(mode=0o755)
    if system == "Windows":
        engine.with_suffix(".dll").touch()
    archive = tmp_path / "中文 archive.zip"
    archive.touch()
    monkeypatch.chdir(tmp_path)
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(
            cmd, 0, b"----------\nPath = file.txt\nSize = 5\nFolder = -\n", b""
        )

    monkeypatch.setattr(subprocess, "run", run)
    assert au.readArchiveContentWith7z(str(archive))[0]["name"] == "file.txt"
    assert au.extractArchiveWith7z(str(archive), str(tmp_path / "output"))
    assert [cmd[0] for cmd in calls] == [str(engine), str(engine)]
    assert all(str(archive) in cmd for cmd in calls)


def test_explicit_engine_override_on_unsupported_platform(monkeypatch, tmp_path):
    monkeypatch.setattr(platform, "system", lambda: "FreeBSD")
    engine = tmp_path / "custom 7zz"
    engine.touch(mode=0o755)
    archive = tmp_path / "archive.zip"
    archive.touch()

    def run(cmd, **kwargs):
        assert cmd[0] == str(engine)
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    monkeypatch.setattr(subprocess, "run", run)
    assert au.extractArchiveWith7z(
        str(archive), str(tmp_path / "output"), seven_zip_path=str(engine)
    )


@pytest.mark.parametrize("problem", ["missing", "permission", "directory"])
def test_unusable_explicit_engine_fails_before_output_creation(tmp_path, problem):
    engine = tmp_path / "7zz"
    if problem == "permission":
        if sys.platform == "win32":
            pytest.skip("POSIX executable permission")
        engine.touch(mode=0o644)
    elif problem == "directory":
        engine.mkdir()
    archive = tmp_path / "archive.zip"
    archive.touch()
    output = tmp_path / "output"
    with pytest.raises(SevenZipNotFoundError):
        au.extractArchiveWith7z(str(archive), str(output), seven_zip_path=str(engine))
    assert not output.exists()


def test_source_checkout_engine_does_not_depend_on_cwd(monkeypatch, tmp_path):
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.chdir(tmp_path)
    archive = tmp_path / "archive.zip"
    archive.touch()
    expected = Path(__file__).resolve().parents[1] / "7z" / "macos" / "7zz"

    def run(cmd, **kwargs):
        assert cmd[0] == str(expected)
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    monkeypatch.setattr(subprocess, "run", run)
    assert au.extractArchiveWith7z(str(archive), str(tmp_path / "output"))
