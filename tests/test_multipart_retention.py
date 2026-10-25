"""Source volumes of a multipart set are never deleted when it fails (7-Zip mocked)."""

import os

import pytest

import complex_unzip_tool_v2.main as main
from complex_unzip_tool_v2.classes.ArchiveTypes import ArchiveMissingVolumeError


@pytest.fixture
def missing_volumes(monkeypatch):
    removed = []

    def missing(*args, **kwargs):
        raise ArchiveMissingVolumeError("Unexpected end of archive")

    def remove(path, use_recycle_bin=True, error_callback=None):
        removed.append(path)
        return True

    monkeypatch.setattr(main.archive_utils, "resolve_seven_zip_path", lambda *a: "7z")
    monkeypatch.setattr(main.archive_utils, "is_valid_archive", lambda *a, **k: True)
    monkeypatch.setattr(main.archive_utils, "extractArchiveWith7z", missing)
    monkeypatch.setattr(main.archive_utils, "_list_archive_with7z", missing)
    monkeypatch.setattr(main.file_utils, "safe_remove", remove)
    monkeypatch.setattr(main, "_ask_for_user_input_and_exit", lambda *a: None)
    return removed


@pytest.mark.parametrize(
    "names",
    [["set.zip"], ["archive.part1.rar"], ["data.7z.001"], ["set.zip", "set.z01"]],
)
def test_multipart_parts_not_deleted_on_failure(missing_volumes, tmp_path, names):
    for name in names:
        (tmp_path / name).write_bytes(b"volume")

    main.extract_files([str(tmp_path)], use_recycle_bin=False)

    for name in names:
        assert (tmp_path / name).read_bytes() == b"volume"
    assert missing_volumes == []
    assert not any(n.startswith("temp.deepunzip-") for n in os.listdir(tmp_path))
