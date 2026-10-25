import importlib
import codecs
import sys
from pathlib import Path

import pytest

from deepunzip.classes.PasswordBook import PasswordBook
from deepunzip.modules.password_util import load_all_passwords
from typer.testing import CliRunner

import deepunzip.main as main


@pytest.mark.parametrize("frozen", [False, True])
def test_password_book_uses_tool_directory_across_working_directories(
    monkeypatch, tmp_path, frozen
):
    tool = tmp_path / "tool"
    target = tmp_path / "archives"
    working = tmp_path / "working"
    bundle = tmp_path / "bundle"
    for directory in (tool, target, working, bundle):
        directory.mkdir()
    (bundle / "passwords.txt").write_text("embedded-decoy\n", encoding="utf-8")
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    global_book = tool / "passwords.txt"
    global_book.write_text("全局密码\n", encoding="utf-8")
    target_book = target / "passwords.txt"
    target_book.write_text("目标密码\n", encoding="utf-8")
    cwd_book = working / "passwords.txt"
    cwd_book.write_text("unrelated\n", encoding="utf-8")
    monkeypatch.setattr(sys, "frozen", frozen, raising=False)
    monkeypatch.setattr(sys, "executable", str(tool / "cuz.exe"))
    module = importlib.import_module("deepunzip.classes.PasswordBook")
    monkeypatch.setattr(
        module, "__file__", str(tool / "deepunzip/classes/PasswordBook.py")
    )
    monkeypatch.chdir(working)

    book = load_all_passwords([str(target)])
    assert set(book.get_passwords()) == {"全局密码", "目标密码"}
    book.add_password("新密码")
    monkeypatch.chdir(target)
    book.save_passwords()

    assert set(global_book.read_text(encoding="utf-8").splitlines()) == {"全局密码", "新密码"}
    assert target_book.read_text(encoding="utf-8") == "目标密码\n"
    assert cwd_book.read_text(encoding="utf-8") == "unrelated\n"
    assert not book.has_unsaved_changes()


def test_cli_finishes_when_password_book_is_not_writable(monkeypatch, tmp_path):
    book = PasswordBook()
    book.password_file = tmp_path / "read-only" / "passwords.txt"
    book.add_password("synthetic-secret")
    original_open = open

    def deny_password_write(file, mode="r", *args, **kwargs):
        if Path(file) == book.password_file and "w" in mode:
            raise PermissionError("Permission denied")
        return original_open(file, mode, *args, **kwargs)

    monkeypatch.setattr("builtins.open", deny_password_write)
    monkeypatch.setattr(main.password_util, "load_all_passwords", lambda paths: book)
    monkeypatch.setattr(main.archive_utils, "resolve_seven_zip_path", lambda: "7z")
    result = CliRunner().invoke(main.app, [str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "Could not save passwords" in result.output
    assert "synthetic-secret" not in result.output
    assert book.has_unsaved_changes()
    assert not (tmp_path / ".unzip-rename-history.tmp.json").exists()


@pytest.mark.parametrize(
    "encoding,bom",
    [
        ("utf-8-sig", b""),
        ("gbk", b""),
        ("gb2312", b""),
        ("utf-16-le", codecs.BOM_UTF16_LE),
        ("utf-16-be", codecs.BOM_UTF16_BE),
    ],
)
def test_password_book_reads_encoded_books_and_strips_bom(
    monkeypatch, tmp_path, encoding, bom
):
    module = importlib.import_module("deepunzip.classes.PasswordBook")
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setattr(
        module,
        "__file__",
        str(tmp_path / "deepunzip/classes/PasswordBook.py"),
    )
    data = bom + "密码\n\n123456\n密码\n".encode(encoding)
    path = tmp_path / "passwords.txt"
    path.write_bytes(data)
    book = PasswordBook()
    assert set(book.get_passwords()) == {"密码", "123456"}
    assert not book.has_unsaved_changes()
    book.save_passwords()
    assert path.read_bytes() == data


def _book_in(monkeypatch, tmp_path):
    module = importlib.import_module("deepunzip.classes.PasswordBook")
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setattr(
        module,
        "__file__",
        str(tmp_path / "deepunzip/classes/PasswordBook.py"),
    )
    return PasswordBook()


def test_password_book_skips_comment_lines(monkeypatch, tmp_path):
    """Issue #22: lines starting with # are comments, not passwords."""
    (tmp_path / "passwords.txt").write_text(
        "# 常用弱口令\n123456\n  # indented comment\n# 这个包专用\nmypassword\n",
        encoding="utf-8",
    )
    target = tmp_path / "archives"
    target.mkdir()
    (target / "passwords.txt").write_text("# only a note\nlocal\n", encoding="utf-8")

    book = _book_in(monkeypatch, tmp_path)
    book.load_passwords(str(target / "passwords.txt"))

    assert set(book.get_passwords()) == {"123456", "mypassword", "local"}


def test_password_book_keeps_file_order_without_duplicates(monkeypatch, tmp_path):
    """Password indexes shown to the user (password #N) must be stable."""
    (tmp_path / "passwords.txt").write_text("zz\naa\nzz\nmm\n", encoding="utf-8")
    target = tmp_path / "archives"
    target.mkdir()
    (target / "passwords.txt").write_text("bb\naa\n", encoding="utf-8")

    book = _book_in(monkeypatch, tmp_path)
    book.load_passwords(str(target / "passwords.txt"))
    book.add_password("cc")

    assert book.get_passwords() == ["zz", "aa", "mm", "cc", "bb"]


def test_password_book_save_keeps_comments_and_order(monkeypatch, tmp_path):
    """Issue #22: saving learned passwords must not erase the user's comments."""
    path = tmp_path / "passwords.txt"
    original = "# 常用弱口令\n123456\n\n# 这个包专用\nmypassword\n"
    path.write_text(original, encoding="utf-8")

    book = _book_in(monkeypatch, tmp_path)
    book.add_passwords(["新密码", "123456"])
    book.save_passwords()

    assert path.read_text(encoding="utf-8") == original + "新密码\n"
    assert not book.has_unsaved_changes()


def test_password_book_save_drops_removed_password_but_keeps_comments(
    monkeypatch, tmp_path
):
    path = tmp_path / "passwords.txt"
    path.write_text("# note\nold\nkeep\n", encoding="utf-8")

    book = _book_in(monkeypatch, tmp_path)
    book.remove_password("old")
    book.save_passwords()

    assert path.read_text(encoding="utf-8") == "# note\nkeep\n"


def test_password_book_escaped_hash_is_a_password(monkeypatch, tmp_path):
    """A literal leading # is written as \\# so it is not read as a comment."""
    (tmp_path / "passwords.txt").write_text(
        "# comment\n\\#abc\n\\\\#def\n", encoding="utf-8"
    )

    book = _book_in(monkeypatch, tmp_path)

    assert set(book.get_passwords()) == {"#abc", "\\#def"}


def test_password_book_learned_hash_passwords_round_trip(monkeypatch, tmp_path):
    """Auto-learned passwords starting with # must survive save + reload."""
    path = tmp_path / "passwords.txt"
    path.write_text("# my book\nplain\n", encoding="utf-8")

    book = _book_in(monkeypatch, tmp_path)
    book.add_passwords(["#abc", "\\#def"])
    book.save_passwords()

    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[:2] == ["# my book", "plain"]
    assert sorted(lines[2:]) == ["\\#abc", "\\\\#def"]
    reloaded = _book_in(monkeypatch, tmp_path)
    assert set(reloaded.get_passwords()) == {"plain", "#abc", "\\#def"}
