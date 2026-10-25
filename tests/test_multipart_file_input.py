import pytest
import os
from pathlib import Path
from typer.testing import CliRunner

import deepunzip.main as main

from deepunzip.modules.file_utils import read_dir


def test_single_primary_input_collects_only_its_numbered_volumes(tmp_path):
    selected = tmp_path / "sample.7z.001"
    continuation = tmp_path / "sample.7z.002"
    unrelated = ["sample.7z", "sample.zip.002", "sample-other.7z.002", "notes.txt"]
    for name in [selected.name, continuation.name, *unrelated]:
        (tmp_path / name).write_bytes(b"fixture")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / continuation.name).write_bytes(b"other set")

    assert set(read_dir([str(selected)])) == {str(selected), str(continuation)}


@pytest.mark.parametrize("primary", ["sample.7z.001", "sample.7z.00删1"])
def test_file_input_discovers_cloaked_siblings_without_renaming(tmp_path, primary):
    names = [primary, "sample.7z.002删除", "sample.7z.0删03"]
    unrelated = ["sample.zip.002删除", "other.7z.002删除", "invoice002", "notes.txt"]
    for name in names + unrelated:
        (tmp_path / name).write_bytes(b"fixture")
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert set(read_dir([str(tmp_path / primary)])) == {
        str(tmp_path / name) for name in names
    }
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


@pytest.mark.parametrize("error", [PermissionError, FileNotFoundError])
def test_unavailable_sibling_directory_preserves_explicit_input(
    monkeypatch, tmp_path, error
):
    primary = tmp_path / "sample.7z.001"
    primary.write_bytes(b"source")

    def unavailable(path):
        raise error("Directory unavailable")

    monkeypatch.setattr(os, "scandir", unavailable)
    assert read_dir([str(primary)]) == [str(primary)]
    assert primary.read_bytes() == b"source"


@pytest.mark.parametrize(
    "parts,other",
    [
        (["a.rar", "a.r00", "a.r01"], "a.part2.rar"),
        (["a.part1.rar", "a.part2.rar"], "a.rar"),
        (["a.zip", "a.z01", "a.z02"], "a.zip.001"),
        (["a.zipx", "a.zx01"], "a.zip"),
        (["a.arj", "a.a01"], "a.ace"),
        (["a.ace", "a.c00"], "a.arj"),
        (["a.iso.001", "a.iso.002"], "a.iso"),
        (["a.zip.001", "a.zip.002"], "a.z01"),
        (["a.tar.gz.001", "a.tar.gz.002"], "a.tar.bz2.002"),
        (["a.7z.1", "a.7z.2"], "a.7z"),
    ],
)
def test_file_input_discovers_its_volume_family(monkeypatch, tmp_path, parts, other):
    monkeypatch.chdir(tmp_path)
    for name in [*parts, other]:
        (tmp_path / name).write_bytes(b"fixture")
    for selected in parts:
        assert set(read_dir([selected])) == set(parts)
    assert sorted(read_dir(parts)) == sorted(parts)


@pytest.mark.parametrize("outcome", ["success", "failure", "password-skip"])
@pytest.mark.parametrize("recycle", [False, True])
@pytest.mark.parametrize("cloaked", [False, True])
def test_cli_handles_all_selected_set_parts_safely(
    monkeypatch, tmp_path, outcome, recycle, cloaked
):
    normalized = [tmp_path / f"sample.7z.{n:03d}" for n in (1, 2, 3)]
    parts = [Path(str(part) + "删除") for part in normalized] if cloaked else normalized
    for part in parts:
        part.write_bytes(b"source volume")
    unrelated = tmp_path / "unrelated.7z.001"
    unrelated.write_bytes(b"unrelated source")

    def listing(archive_path, password="", **kwargs):
        # The complete set sits in one folder, so it is extracted in place.
        assert Path(archive_path) == normalized[0]
        return "7z", [{"name": "result.txt"}], 3

    def extract(archive_path, output_path, password="", **kwargs):
        if Path(archive_path).name == "nested.7z":
            raise main.archive_utils.ArchivePasswordError("Wrong password")
        assert Path(archive_path) == normalized[0]
        if outcome == "failure":
            raise main.archive_utils.ArchiveCorruptedError("CRC failed")
        (Path(output_path) / "result.txt").write_text("extracted", encoding="utf-8")
        if outcome == "password-skip":
            (Path(output_path) / "nested.7z").write_bytes(b"locked nested archive")
        return True

    monkeypatch.setattr(main.archive_utils, "_list_archive_with7z", listing)
    monkeypatch.setattr(main.archive_utils, "extractArchiveWith7z", extract)
    monkeypatch.setattr(
        main.archive_utils,
        "is_valid_archive",
        lambda path, **kwargs: Path(path).name == "nested.7z",
    )
    monkeypatch.setattr(main.archive_utils, "resolve_seven_zip_path", lambda: "7z")
    recycled = []

    def recycle_file(path):
        recycled.append(Path(path).name)
        Path(path).unlink()

    monkeypatch.setattr(main.file_utils, "send2trash", recycle_file)
    arguments = [str(parts[0])] if recycle else ["--permanent-delete", str(parts[0])]
    result = CliRunner().invoke(main.app, arguments)
    # A failed set, or a nested archive whose password prompt is skipped
    # (stdin is not a terminal), leaves an unresolved item: exit code 1.
    assert result.exit_code == (0 if outcome == "success" else 1), result.output
    if outcome == "success":
        assert all(not part.exists() for part in parts)
        assert all(not part.exists() for part in normalized)
        assert (tmp_path / "unzipped/result.txt").read_text() == "extracted"
        assert sorted(recycled) == (
            [part.name for part in normalized] if recycle else []
        )
    else:
        assert all(part.read_bytes() == b"source volume" for part in parts)
        assert not recycled
    assert unrelated.read_bytes() == b"unrelated source"
    assert not (tmp_path / ".unzip-rename-history.tmp.json").exists()
