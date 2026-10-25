"""Exercise source or frozen CLI with nested, encrypted and split archives."""

import argparse
import io
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from deepunzip import __version__
from deepunzip.modules.archive_utils import (
    ArchivePasswordError,
    readArchiveContentWith7z,
    resolve_seven_zip_path,
)


def smoke(executable: Path | None = None) -> None:
    """Verify native extraction and output bytes without touching user archives."""
    command = (
        [str(executable.resolve())]
        if executable
        else [sys.executable, "-m", "deepunzip"]
    )
    engine = resolve_seven_zip_path()
    with tempfile.TemporaryDirectory(prefix="deepunzip-smoke-") as temporary:
        root = Path(temporary)
        if executable:
            portable = root / "portable tool"
            portable.mkdir()
            copied = portable / executable.name
            shutil.copy2(executable, copied)
            command = [str(copied)]
            # The frozen CLI must find this from a different working directory.
            (portable / "passwords.txt").write_text("测试 password\n", encoding="utf-8")

        def run(arguments: list[str], cwd: Path = root) -> bytes:
            result = subprocess.run(
                arguments,
                cwd=cwd,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                timeout=120,
                env={
                    **os.environ,
                    "PYTHONUTF8": "0" if sys.platform == "win32" else "1",
                    "PYTHONIOENCODING": "gbk" if sys.platform == "win32" else "utf-8",
                },
            )
            if result.returncode:
                raise RuntimeError(
                    f"Smoke command failed (exit {result.returncode}):\n"
                    + result.stdout.decode("utf-8", errors="replace")
                    + result.stderr.decode("utf-8", errors="replace")
                )
            return result.stdout

        run(command + ["--help"])
        run(command + ["--version"])
        source = root / "source"
        source.mkdir()
        payload = source / "中文 file.txt"
        payload.write_bytes(bytes(range(256)) * 1024)
        for case_name in (
            "nested",
            "encrypted",
            "multipart",
            "multipart-file",
            "multipart-cloaked-file",
        ):
            case = root / f"{case_name} archives"
            case.mkdir()
            if case_name == "nested":
                inner = io.BytesIO()
                with zipfile.ZipFile(inner, "w") as archive:
                    archive.writestr(payload.name, payload.read_bytes())
                with zipfile.ZipFile(case / "outer.zip", "w") as archive:
                    archive.writestr("inner.zip", inner.getvalue())
            elif case_name == "encrypted":
                protected = case / "protected.7z"
                run(
                    [
                        engine,
                        "a",
                        str(protected),
                        payload.name,
                        "-p测试 password",
                        "-mhe=on",
                    ],
                    source,
                )
                try:
                    readArchiveContentWith7z(str(protected), password="wrong")
                except ArchivePasswordError:
                    pass
                else:
                    raise AssertionError("Wrong password was accepted")
                if not executable:
                    (case / "passwords.txt").write_text(
                        "测试 password\n", encoding="utf-8"
                    )
            else:
                run(
                    [
                        engine,
                        "a",
                        str(case / "split.7z"),
                        payload.name,
                        "-mx=0",
                        "-v16k",
                    ],
                    source,
                )
                assert (case / "split.7z.002").is_file()
                if case_name == "multipart-cloaked-file":
                    for part in case.glob("split.7z.*"):
                        part.rename(part.with_name(part.name + "删除"))
            originals = [p for p in case.iterdir() if p.name != "passwords.txt"]
            target = case
            single_input = case_name in {"multipart-file", "multipart-cloaked-file"}
            if single_input:
                suffix = "删除" if case_name == "multipart-cloaked-file" else ""
                target = case / f"split.7z.001{suffix}"
                unrelated = case / "split.zip"
                with zipfile.ZipFile(unrelated, "w") as archive:
                    archive.writestr("unrelated.txt", b"keep me")
                unrelated_bytes = unrelated.read_bytes()
            output = run(command + ["--permanent-delete", str(target)])
            assert __version__ in output.decode("utf-8"), case_name
            outputs = [p for p in (case / "unzipped").rglob("*") if p.is_file()]
            assert any(
                p.read_bytes() == payload.read_bytes() for p in outputs
            ), case_name
            assert all(not p.exists() for p in originals), case_name
            if single_input:
                assert unrelated.read_bytes() == unrelated_bytes
                assert not list(case.glob("split.7z.*"))
                assert not (case / ".unzip-rename-history.tmp.json").exists()
        print(
            "Passed: help, version, nested ZIP, encrypted 7z, wrong password, "
            "split 7z (directory, single-file and cloaked input), "
            "redirected UTF-8 output"
        )


def main() -> None:
    """Run against the source CLI or the supplied standalone executable."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path)
    smoke(parser.parse_args().executable)


if __name__ == "__main__":
    main()
