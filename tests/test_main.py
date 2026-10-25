import json
import os

import pytest

import deepunzip.main as main
from deepunzip.classes.ArchiveTypes import (
    ArchiveCorruptedError,
    ArchivePasswordError,
)
from deepunzip.modules import const
from deepunzip.modules.rename_history import (
    HISTORY_FILENAME,
    RenameHistory,
)

# The fake_7z fixture stubs the exit; exit-code tests put the real one back
# (it only pauses in a frozen Windows build).
_real_exit = main._ask_for_user_input_and_exit


# ---------------------------------------------------------------------------
# Fake 7-Zip: extract_files runs the real work pool on top of these mocks.
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_7z(monkeypatch):
    """Mock every 7-Zip call; tests fill in `contents` and `failures`.

    `contents` maps an archive name to the files it extracts (name → text).
    `failures` maps an archive name to the exception extraction raises.
    """
    state = {"contents": {}, "failures": {}, "extracted": [], "removed": {}}

    def is_valid(path, *args, **kwargs):
        return os.path.basename(path) in state["contents"]

    def extract(archive_path, output_path, password="", **kwargs):
        name = os.path.basename(archive_path)
        if name in state["failures"]:
            raise state["failures"][name]
        state["extracted"].append(name)
        for child, text in state["contents"].get(name, {}).items():
            target = os.path.join(output_path, child)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w", encoding="utf-8") as handle:
                handle.write(text)
        return True

    def listing(archive_path, password="", **kwargs):
        name = os.path.basename(archive_path)
        if name in state["failures"]:
            raise state["failures"][name]
        return "7z", [{"name": "entry"}], None

    def remove(path, use_recycle_bin=True, error_callback=None):
        state["removed"][os.path.basename(path)] = use_recycle_bin
        os.remove(path)
        return True

    monkeypatch.setattr(main.archive_utils, "resolve_seven_zip_path", lambda *a: "7z")
    monkeypatch.setattr(main.archive_utils, "is_valid_archive", is_valid)
    monkeypatch.setattr(main.archive_utils, "extractArchiveWith7z", extract)
    monkeypatch.setattr(main.archive_utils, "_list_archive_with7z", listing)
    monkeypatch.setattr(main.archive_utils, "detect_archive_extension", lambda p: None)
    monkeypatch.setattr(main.file_utils, "safe_remove", remove)
    monkeypatch.setattr(main, "_ask_for_user_input_and_exit", lambda *a: None)
    return state


class FakeDetector:
    """Renames `<name>.cloaked` to `<name>` and records it like the real one."""

    def __init__(self, renames):
        self.renames = renames

    def uncloak_file(self, path, history=None):
        target = self.renames.get(os.path.basename(path))
        if target is None:
            return path
        new_path = os.path.join(os.path.dirname(path), target)
        os.rename(path, new_path)
        if history is not None:
            history.record(path, new_path)
        return new_path


def _outputs(root):
    out = root / const.OUTPUT_FOLDER
    return sorted(
        os.path.relpath(os.path.join(folder, name), out).replace(os.sep, "/")
        for folder, _dirs, names in os.walk(out)
        for name in names
    )


# ---------------------------------------------------------------------------
# Extraction flow
# ---------------------------------------------------------------------------


def test_contained_multipart_parts_preserved_to_output_when_extraction_fails(
    fake_7z, tmp_path
):
    """Regression: multipart parts inside a container must not be deleted by temp cleanup."""
    (tmp_path / "outer.7z").write_bytes(b"dummy")
    fake_7z["contents"]["outer.7z"] = {"A/MySet.7z.001": "p1", "B/MySet.7z.002": "p2"}
    fake_7z["failures"]["MySet.7z.001"] = ArchiveCorruptedError("CRC failed")

    main.extract_files([str(tmp_path)], use_recycle_bin=False)

    # A failed set's volumes are preserved together at the primary's location.
    assert _outputs(tmp_path) == ["A/MySet.7z.001", "A/MySet.7z.002"]
    assert (tmp_path / "outer.7z").exists()


def test_spanned_zip_inside_a_container_is_extracted_in_the_same_run(fake_7z, tmp_path):
    (tmp_path / "outer.zip").write_bytes(b"dummy")
    fake_7z["contents"]["outer.zip"] = {"Set.zip": "zip", "Set.z01": "z01"}
    fake_7z["contents"]["Set.zip"] = {"inner.txt": "inner"}

    (result,) = main.extract_files([str(tmp_path)], use_recycle_bin=False)

    assert "Set.zip" in fake_7z["extracted"]
    assert _outputs(tmp_path) == ["Set/inner.txt"]
    assert not (tmp_path / "outer.zip").exists()
    assert result.unresolved == []


@pytest.mark.parametrize("use_recycle_bin", [True, False])
def test_nested_cleanup_follows_user_recycle_bin_choice(
    fake_7z, tmp_path, use_recycle_bin
):
    """Issue #21: nested-archive cleanup must honor --permanent-delete."""
    (tmp_path / "outer.zip").write_bytes(b"dummy")
    fake_7z["contents"]["outer.zip"] = {"inner.zip": "nested"}
    fake_7z["contents"]["inner.zip"] = {"file.txt": "x"}

    main.extract_files([str(tmp_path)], use_recycle_bin=use_recycle_bin)

    assert fake_7z["removed"] == {
        "inner.zip": use_recycle_bin,
        "outer.zip": use_recycle_bin,
    }
    assert _outputs(tmp_path) == ["inner/file.txt"]


def test_top_level_non_archive_is_kept_and_not_counted_as_failure(fake_7z, tmp_path):
    """A readme next to the archives must be skipped quietly: kept on disk,
    no error lines, not counted as a failed extraction."""
    readme = tmp_path / "请先看我.txt"
    readme.write_text("解压密码见下方", encoding="utf-8")

    (result,) = main.extract_files([str(tmp_path)], use_recycle_bin=True)

    assert readme.exists()
    assert fake_7z["removed"] == {}
    assert result.unresolved == []
    assert result.kept_sources == []


def test_unknown_password_with_closed_stdin_keeps_the_source(
    fake_7z, monkeypatch, tmp_path
):
    (tmp_path / "locked.7z").write_bytes(b"dummy")
    fake_7z["contents"]["locked.7z"] = {"a.txt": "a"}
    fake_7z["failures"]["locked.7z"] = ArchivePasswordError("Wrong password")

    def closed_stdin(*args, **kwargs):
        raise EOFError

    monkeypatch.setattr("builtins.input", closed_stdin)

    (result,) = main.extract_files([str(tmp_path)], use_recycle_bin=True)

    assert (tmp_path / "locked.7z").exists()
    assert fake_7z["removed"] == {}
    assert [item.reason for item in result.unresolved] == ["password"]


def test_each_input_root_gets_its_own_output_folder(fake_7z, tmp_path):
    for name in ("a", "b"):
        (tmp_path / name).mkdir()
        (tmp_path / name / f"{name}.7z").write_bytes(b"dummy")
        fake_7z["contents"][f"{name}.7z"] = {f"{name}.txt": name}

    main.extract_files([str(tmp_path / "a"), str(tmp_path / "b")])

    assert _outputs(tmp_path / "a") == ["a.txt"]
    assert _outputs(tmp_path / "b") == ["b.txt"]


def test_leftover_work_directory_is_not_scanned(fake_7z, tmp_path):
    leftover = tmp_path / "temp.deepunzip-old" / "outer"
    leftover.mkdir(parents=True)
    (leftover / "stale.7z").write_bytes(b"dummy")
    fake_7z["contents"]["stale.7z"] = {"stale.txt": "x"}

    main.extract_files([str(tmp_path)])

    assert fake_7z["extracted"] == []
    assert (leftover / "stale.7z").exists()


# ---------------------------------------------------------------------------
# Rename history integration
# ---------------------------------------------------------------------------


def test_rename_history_reverts_on_extraction_failure(fake_7z, monkeypatch, tmp_path):
    """When extraction fails, uncloak renames must be reverted so the user
    sees the original filenames."""
    cloaked = tmp_path / "1525.zip(1).001"
    cloaked.write_bytes(b"PK\x03\x04dummy-7z-data")
    detector = FakeDetector({"1525.zip(1).001": "1525.7z.001"})
    monkeypatch.setattr(main.file_utils, "create_cloaked_detector", lambda: detector)
    fake_7z["failures"]["1525.7z.001"] = ArchiveCorruptedError("CRC failed")

    main.extract_files([str(tmp_path)], use_recycle_bin=False)

    assert cloaked.exists(), "rename was not reverted on failure"
    assert not (tmp_path / "1525.7z.001").exists()
    assert not (tmp_path / HISTORY_FILENAME).exists()


def test_rename_history_cleared_on_extraction_success(fake_7z, monkeypatch, tmp_path):
    """When extraction succeeds, originals are deleted and history is cleared
    (the renamed files do not get reverted)."""
    cloaked = tmp_path / "1525.7z隐藏"
    cloaked.write_bytes(b"PK\x03\x04dummy")
    detector = FakeDetector({"1525.7z隐藏": "1525.7z"})
    monkeypatch.setattr(main.file_utils, "create_cloaked_detector", lambda: detector)
    fake_7z["contents"]["1525.7z"] = {"data.txt": "x"}

    main.extract_files([str(tmp_path)], use_recycle_bin=False)

    assert not (tmp_path / "1525.7z").exists()
    assert not cloaked.exists()
    assert not (tmp_path / HISTORY_FILENAME).exists()
    assert _outputs(tmp_path) == ["data.txt"]


def test_rename_history_recovery_prompt_yes_reverts(fake_7z, monkeypatch, tmp_path):
    """A leftover history file from a previous run can be reverted on prompt 'y'."""
    renamed = tmp_path / "leftover.7z.001"
    original = tmp_path / "leftover.bin"
    renamed.write_bytes(b"data")

    h = RenameHistory(str(tmp_path))
    h.record(str(original), str(renamed))
    h.bind(str(renamed), "previous-run-group")
    assert (tmp_path / HISTORY_FILENAME).exists()

    monkeypatch.setattr("builtins.input", lambda *a, **k: "y")

    main.extract_files([str(tmp_path)], use_recycle_bin=False)

    assert original.exists()
    assert not renamed.exists()
    assert not (tmp_path / HISTORY_FILENAME).exists()


def test_rename_history_recovery_prompt_no_keeps_file(fake_7z, monkeypatch, tmp_path):
    """Answering 'n' to recovery leaves the renamed file in place."""
    renamed = tmp_path / "leftover.7z.001"
    original = tmp_path / "leftover.bin"
    renamed.write_bytes(b"data")
    fake_7z["failures"]["leftover.7z.001"] = ArchiveCorruptedError("not a set")

    h = RenameHistory(str(tmp_path))
    h.record(str(original), str(renamed))
    h.bind(str(renamed), "previous-run-group")

    monkeypatch.setattr("builtins.input", lambda *a, **k: "n")

    main.extract_files([str(tmp_path)], use_recycle_bin=False)

    assert renamed.exists()
    assert not original.exists()
    assert not (tmp_path / HISTORY_FILENAME).exists()


def test_leftover_relocation_is_restored_without_asking(fake_7z, monkeypatch, tmp_path):
    home = tmp_path / "src" / "X.7z.002"
    stranded = tmp_path / "temp.deepunzip-old" / ".assemble" / "1" / "X.7z.002"
    stranded.parent.mkdir(parents=True)
    stranded.write_bytes(b"volume")
    (tmp_path / "src").mkdir()
    h = RenameHistory(str(tmp_path))
    h.record(str(home), str(stranded), kind="relocation")

    asked = []
    monkeypatch.setattr("builtins.input", lambda *a, **k: asked.append(a) or "n")

    main.extract_files([str(tmp_path)], use_recycle_bin=False)

    assert asked == []
    assert home.read_bytes() == b"volume"
    assert not stranded.exists()


def _capture_cli_extract(monkeypatch) -> list:
    """Stub out the real extraction so CLI parsing can be observed in isolation."""
    calls: list = []

    def run(paths, use_recycle_bin=True, json_mode=False):
        calls.append((paths, use_recycle_bin))
        return 0

    monkeypatch.setattr(main, "run", run)
    monkeypatch.setattr(main, "_ask_for_user_input_and_exit", lambda *a, **k: None)
    return calls


@pytest.mark.parametrize(
    "args",
    [
        ["IN", "--permanent-delete"],
        ["IN", "-pd"],
        ["--permanent-delete", "IN"],
        ["-pd", "IN"],
    ],
)
def test_cli_options_are_parsed_in_any_position(monkeypatch, tmp_path, args):
    """Regression: a flag after the path (drag-and-drop order) must not be
    swallowed as an input path."""
    from typer.testing import CliRunner

    calls = _capture_cli_extract(monkeypatch)
    argv = [str(tmp_path) if a == "IN" else a for a in args]

    result = CliRunner().invoke(main.app, argv)

    assert result.exit_code == 0, result.output
    assert calls == [([str(tmp_path)], False)]


def test_cli_defaults_to_recycle_bin_without_flag(monkeypatch, tmp_path):
    from typer.testing import CliRunner

    calls = _capture_cli_extract(monkeypatch)

    result = CliRunner().invoke(main.app, [str(tmp_path), str(tmp_path / "b.7z")])

    assert result.exit_code == 0, result.output
    assert calls == [([str(tmp_path), str(tmp_path / "b.7z")], True)]


def test_cli_unknown_option_after_path_is_rejected_not_used_as_path(
    monkeypatch, tmp_path
):
    from typer.testing import CliRunner

    calls = _capture_cli_extract(monkeypatch)

    result = CliRunner().invoke(main.app, [str(tmp_path), "--bogus"])

    assert result.exit_code != 0
    assert calls == []


def test_cli_dash_token_that_is_not_a_path_is_never_an_input_path(
    monkeypatch, tmp_path
):
    """Even after `--`, a dash-prefixed token that does not exist is dropped."""
    from typer.testing import CliRunner

    calls = _capture_cli_extract(monkeypatch)

    result = CliRunner().invoke(main.app, [str(tmp_path), "--", "--permanent-delete"])

    assert result.exit_code == 0, result.output
    assert calls == [([str(tmp_path)], True)]


def test_cli_existing_dash_prefixed_path_is_kept(monkeypatch, tmp_path):
    from typer.testing import CliRunner

    calls = _capture_cli_extract(monkeypatch)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "-odd.zip").write_bytes(b"x")

    result = CliRunner().invoke(main.app, ["--", "-odd.zip"])

    assert result.exit_code == 0, result.output
    assert calls == [(["-odd.zip"], True)]


def test_cli_version_subcommand_still_works(monkeypatch, tmp_path):
    from typer.testing import CliRunner

    calls = _capture_cli_extract(monkeypatch)
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(main.app, ["version"])

    assert result.exit_code == 0, result.output
    assert main.__version__ in result.output
    assert calls == []


# ---------------------------------------------------------------------------
# Output modes, prompts and exit codes
# ---------------------------------------------------------------------------


def _json_run(monkeypatch, args):
    from typer.testing import CliRunner

    monkeypatch.setattr(main, "_ask_for_user_input_and_exit", _real_exit)
    result = CliRunner().invoke(main.app, ["--json", *args])
    lines = [json.loads(line) for line in result.stdout.splitlines()]
    return result, lines


def _no_prompts(monkeypatch):
    monkeypatch.setattr(
        "builtins.input", lambda *a, **k: pytest.fail("prompted in --json mode")
    )


def test_json_run_writes_only_json_lines_and_exits_0(fake_7z, monkeypatch, tmp_path):
    (tmp_path / "a.7z").write_bytes(b"dummy")
    fake_7z["contents"]["a.7z"] = {"a.txt": "a"}

    result, lines = _json_run(monkeypatch, [str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert lines[0]["event"] == "start" and lines[-1]["event"] == "summary"
    assert lines[-1]["status"] == "ok" and lines[-1]["exit"] == 0
    assert [line["path"] for line in lines if line["event"] == "item"] == ["a.7z"]


def test_json_unknown_password_is_unresolved_without_a_prompt(
    fake_7z, monkeypatch, tmp_path
):
    _no_prompts(monkeypatch)
    monkeypatch.setattr(main, "_stdin_is_terminal", lambda: True)
    (tmp_path / "locked.7z").write_bytes(b"dummy")
    fake_7z["contents"]["locked.7z"] = {"a.txt": "a"}
    fake_7z["failures"]["locked.7z"] = ArchivePasswordError("Wrong password")

    result, lines = _json_run(monkeypatch, [str(tmp_path)])

    assert result.exit_code == 1
    (unresolved,) = [line for line in lines if line["event"] == "unresolved"]
    assert unresolved["path"] == "locked.7z" and unresolved["reason"] == "password"
    assert lines[-1]["status"] == "partial" and lines[-1]["exit"] == 1
    assert (tmp_path / "locked.7z").exists()


def test_redirected_stdin_never_prompts(fake_7z, monkeypatch, tmp_path):
    from typer.testing import CliRunner

    _no_prompts(monkeypatch)
    (tmp_path / "locked.7z").write_bytes(b"dummy")
    fake_7z["contents"]["locked.7z"] = {"a.txt": "a"}
    fake_7z["failures"]["locked.7z"] = ArchivePasswordError("Wrong password")

    monkeypatch.setattr(main, "_ask_for_user_input_and_exit", _real_exit)
    result = CliRunner().invoke(main.app, [str(tmp_path)], input="")

    assert result.exit_code == 1
    assert "locked.7z  unresolved: wrong or missing password" in result.output


def test_no_existing_path_exits_2(monkeypatch, tmp_path):
    monkeypatch.setattr(
        main, "extract_files", lambda *a, **k: pytest.fail("Extraction started")
    )
    missing = str(tmp_path / "missing")

    result, lines = _json_run(monkeypatch, [missing])

    assert result.exit_code == 2
    assert [line["event"] for line in lines] == ["start", "error", "summary"]
    assert lines[1]["code"] == "no_input"
    assert lines[-1]["status"] == "error" and lines[-1]["exit"] == 2


def test_json_without_paths_is_a_usage_error(monkeypatch):
    result, lines = _json_run(monkeypatch, [])
    assert result.exit_code == 2
    assert lines[1]["code"] == "no_input"


def test_missing_engine_exits_2_with_a_json_error(monkeypatch, tmp_path):
    def missing(*args):
        raise main.archive_utils.SevenZipNotFoundError("7-Zip executable not found")

    monkeypatch.setattr(main.archive_utils, "resolve_seven_zip_path", missing)
    (tmp_path / "a.7z").write_bytes(b"unchanged")

    result, lines = _json_run(monkeypatch, [str(tmp_path)])

    assert result.exit_code == 2
    assert lines[1]["event"] == "error" and lines[1]["code"] == "engine_missing"
    assert list(tmp_path.iterdir()) == [tmp_path / "a.7z"]


def test_unexpected_exception_exits_2(fake_7z, monkeypatch, tmp_path):
    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(main, "extract_files", boom)

    result, lines = _json_run(monkeypatch, [str(tmp_path)])

    assert result.exit_code == 2
    assert lines[1]["code"] == "unexpected" and "boom" in lines[1]["detail"]
    assert lines[-1]["exit"] == 2


def test_some_missing_paths_are_skipped_with_a_warning(fake_7z, tmp_path):
    from typer.testing import CliRunner

    missing = str(tmp_path / "missing.7z")

    result = CliRunner().invoke(main.app, [str(tmp_path), missing])

    assert result.exit_code == 0, result.output
    assert f"Path not found, skipped: {missing}" in result.output


def test_json_mode_never_pauses(monkeypatch):
    import platform
    import sys

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    _no_prompts(monkeypatch)
    with pytest.raises(SystemExit) as exc:
        main._ask_for_user_input_and_exit(1, json_mode=True)
    assert exc.value.code == 1


def test_non_interactive_recovery_keeps_renames(fake_7z, monkeypatch, tmp_path):
    _no_prompts(monkeypatch)
    renamed = tmp_path / "leftover.7z.001"
    renamed.write_bytes(b"volume")
    history = RenameHistory(str(tmp_path))
    history.record(str(tmp_path / "leftover.7z.001删"), str(renamed))

    main._maybe_recover_pending_renames(str(tmp_path), interactive=False)

    assert renamed.exists()


@pytest.mark.parametrize(
    "language, text",
    [
        ("en", "Extract nested"),
        ("zh", "解开嵌套"),
        ("zh-TW", "解開巢狀"),
        ("ja", "入れ子"),
        ("ko", "중첩"),
    ],
)
def test_help_follows_the_language(language, text):
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "deepunzip", "--help"],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        env={**os.environ, "DEEPUNZIP_LANG": language, "PYTHONIOENCODING": "utf-8"},
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert text in result.stdout.decode("utf-8")


def test_stdin_from_the_null_device_is_not_a_terminal():
    """Windows reports NUL as a TTY; `< NUL` must still be non-interactive."""
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from deepunzip.main import _stdin_is_terminal;"
            "print(_stdin_is_terminal())",
        ],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == b"False"
