"""DeepUnzip names: package metadata, commands, aliases and continuity."""

import json
import os
import sys
import tomllib
from pathlib import Path

import pytest
from typer.testing import CliRunner

import deepunzip
from deepunzip import main
from deepunzip.modules import i18n
from deepunzip.modules.rename_history import HISTORY_FILENAME

ROOT = Path(__file__).resolve().parents[1]
DESCRIPTION = (
    "DeepUnzip extracts nested, password-protected, multipart and disguised "
    "archives in one pass."
)


def _pyproject():
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_package_metadata():
    poetry = _pyproject()["tool"]["poetry"]
    assert poetry["name"] == "deepunzip"
    assert poetry["description"] == DESCRIPTION
    assert poetry["packages"] == [{"include": "deepunzip"}]


def test_commands_and_aliases():
    scripts = _pyproject()["tool"]["poetry"]["scripts"]
    assert scripts["deepunzip"] == scripts["dz"] == "deepunzip.main:app"
    assert scripts["main"] == "deepunzip.main:main_alias"
    assert scripts["cuz"] == "deepunzip.main:cuz_alias"


@pytest.mark.parametrize("language, product", [("en", "DeepUnzip"), ("zh", "深度解压")])
def test_version_names_the_product(language, product):
    i18n.set_language(language)
    result = CliRunner().invoke(main.app, ["--version"])
    assert result.exit_code == 0
    assert result.output.strip() == f"{product} {deepunzip.__version__}"


@pytest.mark.parametrize("alias", ["main_alias", "cuz_alias"])
def test_deprecated_alias_names_deepunzip_on_stderr(monkeypatch, capsys, alias):
    monkeypatch.setattr(sys, "argv", [alias.split("_")[0], "--version"])
    with pytest.raises(SystemExit) as exc:
        getattr(main, alias)()
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "deepunzip" in captured.err and len(captured.err.splitlines()) == 1
    assert "DeepUnzip" in captured.out


def test_deprecated_alias_is_silent_with_json(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["cuz", "--json", "--version"])
    with pytest.raises(SystemExit):
        main.cuz_alias()
    assert capsys.readouterr().err == ""


def test_history_left_by_1_3_2_is_still_recovered(monkeypatch, tmp_path):
    """1.3.2 wrote entries without a kind, bound to group keys."""
    original = tmp_path / "movie.7z.001删"
    renamed = tmp_path / "movie.7z.001"
    renamed.write_bytes(b"volume")
    payload = {
        "version": 1,
        "input_root": str(tmp_path),
        "started_at": "2026-09-30T10:00:00",
        "entries": [
            {
                "original": str(original),
                "renamed": str(renamed),
                "group": "movie|7z",
            }
        ],
    }
    (tmp_path / HISTORY_FILENAME).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    monkeypatch.setattr("builtins.input", lambda *a, **k: "y")

    main._maybe_recover_pending_renames(str(tmp_path), interactive=True)

    assert original.read_bytes() == b"volume"
    assert not renamed.exists()
    assert not os.path.exists(tmp_path / HISTORY_FILENAME)
