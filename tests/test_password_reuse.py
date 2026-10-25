import importlib
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

import complex_unzip_tool_v2.main as main


@pytest.fixture
def password_directories(monkeypatch, tmp_path):
    tool = tmp_path / "tool"
    source = tmp_path / "archives"
    tool.mkdir()
    source.mkdir()
    book_path = tool / "passwords.txt"
    book_module = importlib.import_module("complex_unzip_tool_v2.classes.PasswordBook")
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setattr(
        book_module,
        "__file__",
        str(tool / "complex_unzip_tool_v2/classes/PasswordBook.py"),
    )
    monkeypatch.setattr(main.archive_utils, "resolve_seven_zip_path", lambda: "7z")
    monkeypatch.setattr(main.file_utils, "send2trash", lambda path: Path(path).unlink())
    # Multipart sets are probed by listing; headers are readable without a password.
    monkeypatch.setattr(
        main.archive_utils,
        "_list_archive_with7z",
        lambda *a, **k: ("7z", [{"name": "entry"}], None),
    )
    return source, book_path


@pytest.mark.parametrize("multipart", [(False, False), (True, True), (False, True)])
@pytest.mark.parametrize("existing_password", [False, True])
def test_cli_reuses_entered_password_for_later_archives(
    monkeypatch, password_directories, multipart, existing_password
):
    """Issue #24: one password entry unlocks later groups and nested archives."""
    source, book_path = password_directories
    if existing_password:
        book_path.write_text("# keep this comment\nwrong\n", encoding="utf-8")

    monkeypatch.setattr(
        main.archive_utils,
        "is_valid_archive",
        lambda path, **kwargs: Path(path).name.endswith((".7z", ".7z.001")),
    )
    for index, is_multipart in enumerate(multipart):
        names = (
            [f"archive{index}.7z.001", f"archive{index}.7z.002"]
            if is_multipart
            else [f"archive{index}.7z"]
        )
        for name in names:
            (source / name).write_bytes(b"encrypted fixture")

    entered = []

    def prompt(text):
        if text.startswith("Enter password"):
            entered.append("learned-password")
            return "learned-password"
        return "1"

    monkeypatch.setattr("builtins.input", prompt)
    extracted = []

    def extract(archive_path, output_path, password="", **kwargs):
        if password != "learned-password":
            raise main.archive_utils.ArchivePasswordError("Incorrect password")
        name = Path(archive_path).name
        extracted.append(name)
        output = Path(output_path)
        output.mkdir(parents=True, exist_ok=True)
        stem = name.split(".")[0]
        if name.startswith("archive"):
            (output / f"nested-{stem}.7z").write_bytes(b"encrypted nested fixture")
        else:
            (output / f"{stem}.txt").write_text("extracted", encoding="utf-8")
        return True

    monkeypatch.setattr(main.archive_utils, "extractArchiveWith7z", extract)

    result = CliRunner().invoke(main.app, [str(source)])

    assert result.exit_code == 0, result.output
    assert entered == ["learned-password"]
    assert len(extracted) == 4
    assert len(list((source / "unzipped").rglob("*.txt"))) == 2
    saved = book_path.read_text(encoding="utf-8")
    assert saved.splitlines().count("learned-password") == 1
    if existing_password:
        assert saved.startswith("# keep this comment\nwrong\n")
    assert not (source / "passwords.txt").exists()


def test_cli_learned_password_unlocks_later_archives_but_keeps_failed_sources(
    monkeypatch, password_directories
):
    """A typed password is reused; a nested archive it cannot open keeps its source."""
    source, book_path = password_directories
    for name in ("archive0.7z", "archive1.7z"):
        (source / name).write_bytes(b"encrypted fixture")
    monkeypatch.setattr(
        main.archive_utils,
        "is_valid_archive",
        lambda path, **kwargs: Path(path).name.endswith(".7z"),
    )

    answers = iter(["1", "learned-password", "2"])
    monkeypatch.setattr("builtins.input", lambda *a, **k: next(answers))

    def extract(archive_path, output_path, password="", **kwargs):
        name = Path(archive_path).name
        if name == "locked.7z" or password != "learned-password":
            raise main.archive_utils.ArchivePasswordError("Incorrect password")
        output = Path(output_path)
        (output / f"{name.split('.')[0]}.txt").write_text("extracted", encoding="utf-8")
        if name == "archive0.7z":
            (output / "locked.7z").write_bytes(b"other password")
        return True

    monkeypatch.setattr(main.archive_utils, "extractArchiveWith7z", extract)

    result = CliRunner().invoke(main.app, [str(source)])

    assert result.exit_code == 0, result.output
    assert list(answers) == []  # one password entry, one skip for locked.7z
    assert (source / "archive0.7z").exists()
    assert not (source / "archive1.7z").exists()
    assert (source / "unzipped" / "locked.7z").exists()
    assert book_path.read_text(encoding="utf-8").splitlines() == ["learned-password"]
