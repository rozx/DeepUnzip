import builtins
import os
import platform
import subprocess
import sys
from pathlib import Path

import pytest
from rich.text import Text
from typer.testing import CliRunner

import deepunzip.main as main


def test_cli_rejects_unsupported_platform_before_extraction(monkeypatch, tmp_path):
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(platform, "machine", lambda: "riscv64")
    archive = tmp_path / "archive.zip删除"
    archive.write_bytes(b"unchanged")
    monkeypatch.setattr(
        main, "extract_files", lambda *a, **k: pytest.fail("Extraction started")
    )
    result = CliRunner().invoke(main.app, [str(archive)])
    assert result.exit_code == 2
    assert "Unsupported 7-Zip platform" in Text.from_ansi(result.output).plain
    assert list(tmp_path.iterdir()) == [archive]
    assert archive.read_bytes() == b"unchanged"


@pytest.mark.parametrize("option", ["--help", "--version"])
def test_cli_information_does_not_require_engine(monkeypatch, option):
    monkeypatch.setattr(platform, "system", lambda: "FreeBSD")
    assert CliRunner().invoke(main.app, [option]).exit_code == 0


def test_cli_missing_engine_preserves_input(monkeypatch, tmp_path):
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "missing"), raising=False)
    archive = tmp_path / "archive.zip删除"
    archive.write_bytes(b"unchanged")
    result = CliRunner().invoke(main.app, [str(archive)])
    assert result.exit_code == 2
    assert "7-Zip executable not found" in Text.from_ansi(result.output).plain
    assert list(tmp_path.iterdir()) == [archive]
    assert archive.read_bytes() == b"unchanged"


@pytest.mark.parametrize(
    "terminal,interruption",
    [(True, None), (False, None), (True, EOFError), (True, KeyboardInterrupt)],
)
def test_missing_engine_keeps_error_visible_without_losing_exit_code(
    monkeypatch, tmp_path, terminal, interruption
):
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setattr(platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "missing"), raising=False)
    prompts = []

    def answer(prompt):
        prompts.append(prompt)
        if interruption:
            raise interruption()
        return ""

    monkeypatch.setattr(builtins, "input", answer)
    runner = CliRunner()
    with runner.isolation():
        monkeypatch.setattr(sys.stdin, "isatty", lambda: terminal)
        monkeypatch.setattr(sys.stdout, "isatty", lambda: terminal)
        with pytest.raises(SystemExit) as exc:
            main.app(args=[str(tmp_path)])
    assert exc.value.code == 2
    assert len(prompts) == int(terminal)
    assert not (tmp_path / "unzipped").exists()


@pytest.mark.parametrize(
    "system,terminal,output_terminal,expected_prompts",
    [
        ("Darwin", True, True, 0),
        ("Linux", True, True, 0),
        ("Windows", False, True, 0),
        ("Windows", True, False, 0),
        ("Windows", True, True, 1),
    ],
)
def test_standalone_exit_only_pauses_in_windows_terminal(
    monkeypatch, system, terminal, output_terminal, expected_prompts
):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(platform, "system", lambda: system)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: terminal)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: output_terminal)
    prompts = []
    monkeypatch.setattr(builtins, "input", lambda prompt: prompts.append(prompt))
    with pytest.raises(SystemExit) as exc:
        main._ask_for_user_input_and_exit()
    assert exc.value.code == 0
    assert len(prompts) == expected_prompts


@pytest.mark.parametrize("destination", ["pipe", "file"])
def test_windows_cli_redirects_legacy_encoded_output_as_utf8(tmp_path, destination):
    # Run the real CLI with GBK streams on any host, selecting Windows behavior.
    script = (
        "import platform, sys; platform.system = lambda: 'Windows'; "
        "platform.machine = lambda: 'AMD64'; "
        "from deepunzip.main import app; "
        "print('错误 🚀', file=sys.stderr); app()"
    )
    env = {
        **os.environ,
        "PYTHONUTF8": "0",
        "PYTHONIOENCODING": "gbk",
        "DEEPUNZIP_LANG": "zh",
    }
    command = [sys.executable, "-c", script, str(tmp_path)]
    kwargs = dict(
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        stdin=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    if destination == "file":
        log = tmp_path.parent / f"{tmp_path.name}.log"
        with log.open("wb") as stream:
            result = subprocess.run(command, stdout=stream, **kwargs)
        output = log.read_bytes()
    else:
        result = subprocess.run(command, stdout=subprocess.PIPE, **kwargs)
        output = result.stdout
    assert result.returncode == 0, result.stderr
    assert "复杂解压工具" in output.decode("utf-8")
    assert "错误 🚀" in result.stderr.decode("utf-8")
