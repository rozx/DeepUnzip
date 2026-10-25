import builtins
import os
import types
import importlib

import complex_unzip_tool_v2.modules.archive_utils as au
from complex_unzip_tool_v2.classes.ArchiveTypes import (
    ArchivePasswordError,
    ArchiveCorruptedError,
    ArchiveMissingVolumeError,
    ArchiveUnsupportedError,
    ArchiveFileInfo,
)

# Recorded 7-Zip 26.03 output for a split set whose second volume is missing.
SPLIT_7Z_MISSING_VOLUME_STDOUT = (
    "ERROR: split.7z.001\n"
    "split.7z\n"
    "Open ERROR: Cannot open the file as [7z] archive\n"
    "\n"
    "ERRORS:\n"
    "Unexpected end of archive\n"
    "\n"
    "Can't open as archive: 1\n"
)
SPLIT_ZIP_MISSING_VOLUME_STDOUT = (
    "split.zip\n"
    "ERRORS:\n"
    "Unexpected end of archive\n"
    "Path = split.zip\n"
    "Type = zip\n"
    "ERROR: CRC Failed : src\\blob.bin\n"
    "Sub items Errors: 1\n"
)


def test_parse_7z_list_output_basic():
    sample = (
        "----------\n"
        "Path = folder/file.txt\n"
        "Folder = -\n"
        "Size = 123\n"
        "Packed Size = 100\n"
        "Modified = 2024-01-01 12:00:00\n"
        "Attributes = A\n"
        "CRC = 1234ABCD\n"
        "Method = LZMA2\n"
    )
    files = au._parse7zListOutput(sample)
    assert len(files) == 1
    f = files[0]
    assert f["name"] == "folder/file.txt"
    assert f["size"] == 123
    assert f["packed_size"] == 100
    assert f["type"] == "File"


def test_raise_for_7z_error_password():
    try:
        au._raise_for_7z_error(2, "Wrong password", "archive.7z")
    except ArchivePasswordError:
        pass
    else:
        assert False, "Expected ArchivePasswordError"


def test_raise_for_7z_error_corrupted():
    try:
        au._raise_for_7z_error(2, "Data error in encrypted file", "archive.7z")
    except ArchiveCorruptedError:
        pass
    else:
        assert False, "Expected ArchiveCorruptedError"


def test_raise_for_7z_error_unsupported():
    try:
        au._raise_for_7z_error(2, "Unsupported method", "archive.7z")
    except ArchiveUnsupportedError:
        pass
    else:
        assert False, "Expected ArchiveUnsupportedError"


def test_raise_for_7z_error_not_archive_mapping():
    # 7-Zip message variants for non-archive files should map to unsupported, not corrupted
    messages = [
        "Can not open file as archive",
        "cannot open file as archive",
        "is not archive",
    ]
    for msg in messages:
        try:
            au._raise_for_7z_error(2, msg, "file.mp4")
        except ArchiveUnsupportedError:
            pass
        else:
            assert False, f"Expected ArchiveUnsupportedError for message: {msg}"


def test_raise_for_7z_error_missing_7z_volume():
    try:
        au._raise_for_7z_error(
            2, "", "split.7z.001", stdout=SPLIT_7Z_MISSING_VOLUME_STDOUT
        )
    except ArchiveMissingVolumeError:
        pass
    else:
        assert False, "Expected ArchiveMissingVolumeError"


def test_raise_for_7z_error_missing_volume_wins_over_crc_failure():
    # A truncated split zip also reports CRC Failed; it must not look corrupted.
    try:
        au._raise_for_7z_error(
            2, "", "split.zip.001", stdout=SPLIT_ZIP_MISSING_VOLUME_STDOUT
        )
    except ArchiveMissingVolumeError:
        pass
    else:
        assert False, "Expected ArchiveMissingVolumeError"


def test_raise_for_7z_error_missing_volume_message():
    try:
        au._raise_for_7z_error(2, "Missing volume : x.part2.rar", "x.part1.rar")
    except ArchiveMissingVolumeError:
        pass
    else:
        assert False, "Expected ArchiveMissingVolumeError"


def test_password_loop_stops_on_missing_volume(monkeypatch, tmp_path):
    monkeypatch.setattr(au, "is_valid_archive", lambda *args, **kwargs: True)
    attempts = []

    def missing_volume(*args, **kwargs):
        attempts.append(kwargs.get("password"))
        raise ArchiveMissingVolumeError("missing volume")

    monkeypatch.setattr(au, "extractArchiveWith7z", missing_volume)
    (tmp_path / "x.7z.001").write_bytes(b"dummy")

    result = au.extract_nested_archives(
        archive_path=str(tmp_path / "x.7z.001"),
        output_path=str(tmp_path / "out"),
        password_list=["a", "b", "c"],
        interactive=False,
        use_recycle_bin=False,
    )

    assert attempts == [""]
    assert result["success"] is False
    assert result["password_failed_archives"] == []


def test_is_valid_archive_false_on_garbage(monkeypatch):
    # Simulate the 7z listing raising ArchiveUnsupportedError
    def fake_read(*args, **kwargs):
        raise ArchiveUnsupportedError("not an archive")

    monkeypatch.setattr(au, "_list_archive_with7z", fake_read)
    assert au.is_valid_archive("not.zip") is False


def test_is_valid_archive_false_on_not_archive_message(monkeypatch):
    # Simulate 7z returning a "not an archive" error so that listing fails appropriately
    monkeypatch.setattr(au, "_resolve_seven_zip_path", lambda *a, **k: "7z.exe")
    monkeypatch.setattr(au, "_ensure_archive_exists", lambda *a, **k: None)

    def fake_run(cmd):
        _ = cmd
        return ("", "Can not open file as archive", 2)

    monkeypatch.setattr(au, "_run_7z_cmd", fake_run)
    assert au.is_valid_archive("video.mp4") is False


def test_extract_nested_archives_treats_non_archive_as_regular_file(
    monkeypatch, tmp_path
):
    # Create placeholder archive and output paths
    archive_path = str(tmp_path / "outer.7z")
    output_path = str(tmp_path / "out")
    (tmp_path / "outer.7z").write_bytes(b"dummy")

    # is_valid_archive: True for the outer archive, False for anything inside (e.g., .mp4)
    def fake_is_valid(path, *args, **kwargs):
        _ = (args, kwargs)
        return os.path.basename(path) == "outer.7z"

    monkeypatch.setattr(au, "is_valid_archive", fake_is_valid)

    # extractArchiveWith7z: create a dummy non-archive file in the extraction folder and report success
    def fake_extract(archive_path: str, output_path: str, *args, **kwargs) -> bool:
        _ = (archive_path, args, kwargs)
        os.makedirs(output_path, exist_ok=True)
        with open(os.path.join(output_path, "video.mp4"), "wb") as f:
            f.write(b"video-bytes")
        return True

    monkeypatch.setattr(au, "extractArchiveWith7z", fake_extract)

    # Run nested extraction (non-interactive)
    result = au.extract_nested_archives(
        archive_path=archive_path,
        output_path=output_path,
        interactive=False,
        use_recycle_bin=False,
    )

    assert result.get("success") is True
    assert result.get("errors") == []
    finals = result.get("final_files")
    assert any(p.endswith("video.mp4") for p in finals)


def test_is_valid_archive_true_on_password_protected(monkeypatch):
    # Simulate the 7z listing raising ArchivePasswordError
    def fake_read(*args, **kwargs):
        raise ArchivePasswordError("needs password")

    monkeypatch.setattr(au, "_list_archive_with7z", fake_read)
    assert au.is_valid_archive("protected.7z") is True


def test_build_7z_extract_cmd():
    cmd = au._build_7z_extract_cmd(
        seven_zip_path="7z.exe",
        password="secret",
        output_path="/out",
        archive_path="archive.zip",
        overwrite=True,
        specific_files=["file1.txt", "file2.txt"],
    )

    expected = [
        "7z.exe",
        "x",
        "-psecret",
        "-o/out",
        "-y",
        "archive.zip",
        "file1.txt",
        "file2.txt",
    ]
    assert cmd == expected


def test_build_7z_extract_cmd_no_overwrite():
    cmd = au._build_7z_extract_cmd(
        seven_zip_path="7z.exe",
        password="",
        output_path="/out",
        archive_path="archive.zip",
        overwrite=False,
    )

    expected = ["7z.exe", "x", "-p", "-o/out", "-aos", "archive.zip"]
    assert cmd == expected


def test_extract_nested_archives_returns_false_when_passwords_fail(
    monkeypatch, tmp_path
):
    # Always treat the input as a valid archive so extraction is attempted
    monkeypatch.setattr(au, "is_valid_archive", lambda *args, **kwargs: True)

    # Simulate 7z extraction always failing due to wrong password
    def fail_extract(*args, **kwargs):
        raise ArchivePasswordError("wrong password")

    monkeypatch.setattr(au, "extractArchiveWith7z", fail_extract)

    archive_path = str(tmp_path / "protected.7z")
    output_path = str(tmp_path / "out")

    # Create a placeholder file to represent the archive (not actually used by the mocked functions)
    (tmp_path / "protected.7z").write_bytes(b"dummy")

    result = au.extract_nested_archives(
        archive_path=archive_path,
        output_path=output_path,
        password_list=["a", "b"],  # passwords to try
        interactive=False,  # do not prompt for input in tests
        use_recycle_bin=False,
    )

    assert isinstance(result, dict)
    assert result.get("success") is False
    assert result.get("final_files") == []
    assert result.get("extracted_archives") == []


def test_extract_nested_archives_preserves_nested_archive_when_password_fails(
    monkeypatch, tmp_path
):
    """If a nested archive fails due to password, it should be preserved in final_files and reported."""
    archive_path = str(tmp_path / "outer.7z")
    output_path = str(tmp_path / "out")
    (tmp_path / "outer.7z").write_bytes(b"dummy")

    def fake_is_valid(path, *args, **kwargs):
        _ = (args, kwargs)
        # Treat both outer and the nested protected archive as valid archives (password-protected is still valid)
        return os.path.basename(path) in {"outer.7z", "protected.7z"}

    monkeypatch.setattr(au, "is_valid_archive", fake_is_valid)

    def fake_extract(archive_path: str, output_path: str, *args, **kwargs) -> bool:
        os.makedirs(output_path, exist_ok=True)
        if os.path.basename(archive_path) == "outer.7z":
            # Outer extraction "succeeds" by producing a nested protected archive file
            with open(os.path.join(output_path, "protected.7z"), "wb") as f:
                f.write(b"protected-bytes")
            return True
        # Nested protected archive extraction fails due to wrong password
        raise ArchivePasswordError("wrong password")

    monkeypatch.setattr(au, "extractArchiveWith7z", fake_extract)

    result = au.extract_nested_archives(
        archive_path=archive_path,
        output_path=output_path,
        password_list=["a", "b"],
        interactive=False,
        use_recycle_bin=False,
    )

    assert isinstance(result, dict)
    # Outer archive extracted, but nested one failed due to password
    assert os.path.join(output_path, "protected.7z") in result.get("final_files", [])
    assert os.path.join(output_path, "protected.7z") in result.get(
        "password_failed_archives", []
    )


def test_nested_continuation_parts_are_relocated(monkeypatch, tmp_path):
    """Continuation parts found inside nested extraction should be relocated via callback and not counted as finals."""
    archive_path = str(tmp_path / "outer.7z")
    output_path = str(tmp_path / "out")
    (tmp_path / "outer.7z").write_bytes(b"dummy")

    # Only the outer archive is considered valid
    monkeypatch.setattr(
        au, "is_valid_archive", lambda p, *a, **k: os.path.basename(p) == "outer.7z"
    )

    # Extraction creates a continuation part inside the output directory
    def fake_extract(archive_path: str, output_path: str, *args, **kwargs) -> bool:
        _ = (archive_path, args, kwargs)
        os.makedirs(output_path, exist_ok=True)
        # Create a nested continuation part that should be relocated and skipped
        with open(os.path.join(output_path, "MySet.7z.002"), "wb") as f:
            f.write(b"part-bytes")
        return True

    monkeypatch.setattr(au, "extractArchiveWith7z", fake_extract)

    called_with: list[str] = []

    def relocator(path: str) -> bool:
        called_with.append(path)
        return True  # indicate relocation happened

    result = au.extract_nested_archives(
        archive_path=archive_path,
        output_path=output_path,
        interactive=False,
        use_recycle_bin=False,
        group_relocator=relocator,
    )

    assert result.get("success") is True
    # The continuation part should not appear in final files
    finals = result.get("final_files")
    assert finals is not None
    assert not any(p.endswith("MySet.7z.002") for p in finals)
    # Relocator should have been invoked with the nested file path
    assert len(called_with) == 1
    assert os.path.basename(called_with[0]) == "MySet.7z.002"


def test_nested_continuation_parts_skipped_when_not_relocated(monkeypatch, tmp_path):
    """If relocation says False, continuation parts are still skipped (not treated as finals)."""
    archive_path = str(tmp_path / "outer.7z")
    output_path = str(tmp_path / "out")
    (tmp_path / "outer.7z").write_bytes(b"dummy")

    monkeypatch.setattr(
        au, "is_valid_archive", lambda p, *a, **k: os.path.basename(p) == "outer.7z"
    )

    def fake_extract(archive_path: str, output_path: str, *args, **kwargs) -> bool:
        _ = (archive_path, args, kwargs)
        os.makedirs(output_path, exist_ok=True)
        with open(os.path.join(output_path, "AnotherSet.7z.003"), "wb") as f:
            f.write(b"part-bytes")
        return True

    monkeypatch.setattr(au, "extractArchiveWith7z", fake_extract)

    called_with: list[str] = []

    def relocator_false(path: str) -> bool:
        called_with.append(path)
        return False  # indicate relocation did not occur

    result = au.extract_nested_archives(
        archive_path=archive_path,
        output_path=output_path,
        interactive=False,
        use_recycle_bin=False,
        group_relocator=relocator_false,
    )

    assert result.get("success") is True
    finals = result.get("final_files")
    # Continuation should still be skipped from finals even if not relocated
    assert not any(p.endswith("AnotherSet.7z.003") for p in finals)
    assert len(called_with) == 1
    assert os.path.basename(called_with[0]) == "AnotherSet.7z.003"


def test_nested_continuation_parts_relocated_across_all_formats(monkeypatch, tmp_path):
    """Continuation parts of every supported format found inside nested
    extraction must be relocated via callback and never counted as finals:
    generic numbered splits (.zip.002/.rar.002/.iso.002) plus ZIPX/ARJ/ACE
    continuations (.zx01/.a01/.c00)."""
    continuation_names = [
        "Set.zip.002",
        "Set.rar.002",
        "Set.iso.002",
        "Set.zx01",
        "Set.a01",
        "Set.c00",
    ]

    for cont_name in continuation_names:
        sub = tmp_path / cont_name.replace(".", "_")
        sub.mkdir()
        archive_path = str(sub / "outer.7z")
        output_path = str(sub / "out")
        (sub / "outer.7z").write_bytes(b"dummy")

        monkeypatch.setattr(
            au,
            "is_valid_archive",
            lambda p, *a, **k: os.path.basename(p) == "outer.7z",
        )

        def fake_extract(archive_path, output_path, *args, _name=cont_name, **kwargs):
            _ = (archive_path, args, kwargs)
            os.makedirs(output_path, exist_ok=True)
            with open(os.path.join(output_path, _name), "wb") as f:
                f.write(b"part-bytes")
            return True

        monkeypatch.setattr(au, "extractArchiveWith7z", fake_extract)

        called_with: list[str] = []

        def relocator(path, _sink=called_with):
            _sink.append(path)
            return True

        result = au.extract_nested_archives(
            archive_path=archive_path,
            output_path=output_path,
            interactive=False,
            use_recycle_bin=False,
            group_relocator=relocator,
        )

        finals = result.get("final_files") or []
        assert not any(
            os.path.basename(p) == cont_name for p in finals
        ), f"{cont_name} should not be a final file"
        assert [os.path.basename(p) for p in called_with] == [
            cont_name
        ], f"{cont_name} should be relocated as a continuation"


def test_nested_multipart_missing_parts_are_preserved_in_final_files(
    monkeypatch, tmp_path
):
    """If a nested multipart primary can't be extracted (even after matching), its parts must be preserved."""
    archive_path = str(tmp_path / "outer.7z")
    output_path = str(tmp_path / "out")
    (tmp_path / "outer.7z").write_bytes(b"dummy")

    # Treat the outer and the nested primary as valid archives.
    def fake_is_valid(path, *args, **kwargs):
        _ = (args, kwargs)
        return os.path.basename(path) in {"outer.7z", "MySet.7z.001"}

    monkeypatch.setattr(au, "is_valid_archive", fake_is_valid)

    def fake_extract(archive_path: str, output_path: str, *args, **kwargs) -> bool:
        _ = (args, kwargs)
        os.makedirs(output_path, exist_ok=True)
        base = os.path.basename(archive_path)
        if base == "outer.7z":
            # Place primary and continuation in different subfolders to require matching/moving.
            d1 = os.path.join(output_path, "A")
            d2 = os.path.join(output_path, "B")
            os.makedirs(d1, exist_ok=True)
            os.makedirs(d2, exist_ok=True)
            with open(os.path.join(d1, "MySet.7z.001"), "wb") as f:
                f.write(b"part1")
            with open(os.path.join(d2, "MySet.7z.002"), "wb") as f:
                f.write(b"part2")
            return True
        if base == "MySet.7z.001":
            # Always fail to force the preservation path.
            raise au.ArchiveError("Missing volume")
        return True

    monkeypatch.setattr(au, "extractArchiveWith7z", fake_extract)

    result = au.extract_nested_archives(
        archive_path=archive_path,
        output_path=output_path,
        interactive=False,
        use_recycle_bin=False,
    )

    finals = result.get("final_files")
    assert isinstance(finals, list)
    assert any(p.endswith("MySet.7z.001") for p in finals)
    assert any(p.endswith("MySet.7z.002") for p in finals)


# ---------------------------------------------------------------------------
# Issue #21: classify archives by 7-Zip's archive-level header Type
# ---------------------------------------------------------------------------

_SLT_PLAIN_PE = (
    "7-Zip 26.03 (x64)\n"
    "Listing archive: UnityPlayer.dll\n"
    "\n"
    "--\n"
    "Path = UnityPlayer.dll\n"
    "Type = PE\n"
    "Physical Size = 667648\n"
    "CPU = x64\n"
    "\n"
    "----------\n"
    "Path = .text\n"
    "Size = 4096\n"
    "Packed Size = 4096\n"
    "\n"
    "Path = .rsrc\\B7\\UPDATER.PACKED.7Z\n"
    "Size = 100\n"
    "Offset = 2048\n"
    "\n"
    "--\n"
    "Path = updater.7z\n"
    "Type = 7z\n"
    "Physical Size = 100\n"
)

_SLT_SFX = (
    "Listing archive: foobar.exe\n"
    "\n"
    "--\n"
    "Path = foobar.exe\n"
    "Type = 7z\n"
    "Offset = 215040\n"
    "Physical Size = 45933698\n"
    "\n"
    "----------\n"
    "Path = foobar.rar\n"
    "Size = 45953433\n"
)

_SLT_SPLIT = (
    "Listing archive: set.7z.001\n"
    "\n"
    "--\n"
    "Path = set.7z.001\n"
    "Type = Split\n"
    "Volumes = 4\n"
    "----\n"
    "Path = set.7z\n"
    "Size = 3200\n"
    "--\n"
    "Path = set.7z\n"
    "Type = 7z\n"
    "Physical Size = 3200\n"
    "\n"
    "----------\n"
    "Path = big.bin\n"
    "Size = 3000\n"
)

_SLT_COMPOUND = (
    "--\n"
    "Path = setup.msi\n"
    "Type = Compound\n"
    "\n"
    "----------\n"
    "Path = [5]SummaryInformation\n"
    "Size = 400\n"
)


def test_parse_7z_archive_type_uses_header_not_entry_level_type():
    assert au._parse7zArchiveType(_SLT_PLAIN_PE) == "PE"


def test_parse_7z_archive_type_sfx_is_container():
    assert au._parse7zArchiveType(_SLT_SFX) == "7z"


def test_parse_7z_archive_type_split_uses_innermost_header_type():
    assert au._parse7zArchiveType(_SLT_SPLIT) == "7z"


def test_parse_7z_archive_type_none_without_header():
    sample = "----------\nPath = a.txt\nSize = 1\n"
    assert au._parse7zArchiveType(sample) is None


def _fake_7z_listing(monkeypatch, stdout, stderr="", code=0):
    monkeypatch.setattr(au, "_resolve_seven_zip_path", lambda *a, **k: "7z.exe")
    monkeypatch.setattr(au, "_ensure_archive_exists", lambda *a, **k: None)
    monkeypatch.setattr(au, "_run_7z_cmd", lambda cmd: (stdout, stderr, code))


def test_is_valid_archive_false_for_plain_pe(monkeypatch):
    _fake_7z_listing(monkeypatch, _SLT_PLAIN_PE)
    assert au.is_valid_archive("UnityPlayer.dll") is False


def test_is_valid_archive_true_for_sfx_container(monkeypatch):
    _fake_7z_listing(monkeypatch, _SLT_SFX)
    assert au.is_valid_archive("foobar.exe") is True


def test_is_valid_archive_true_for_split_volume(monkeypatch):
    _fake_7z_listing(monkeypatch, _SLT_SPLIT)
    assert au.is_valid_archive("set.7z.001") is True


def test_is_valid_archive_false_for_non_container_formats(monkeypatch):
    for fmt in ("PE", "ELF", "MachO", "Compound", "FLV", "Hash", "Nsis"):
        _fake_7z_listing(monkeypatch, _SLT_COMPOUND.replace("Compound", fmt))
        assert au.is_valid_archive("file.bin") is False, fmt


def test_is_valid_archive_false_for_pe_with_unknown_overlay(monkeypatch):
    _fake_7z_listing(
        monkeypatch,
        "ERROR: tool.exe : Cannot open the file as archive\n",
        code=2,
    )
    assert au.is_valid_archive("tool.exe") is False


def test_is_valid_archive_legacy_listing_without_header_still_valid(monkeypatch):
    _fake_7z_listing(monkeypatch, "----------\nPath = a.txt\nSize = 1\n")
    assert au.is_valid_archive("legacy.7z") is True


def test_nested_pe_is_kept_as_regular_file(monkeypatch, tmp_path):
    """Issue #21: a DLL inside an archive must be kept, not exploded/deleted."""
    archive_path = str(tmp_path / "outer.7z")
    (tmp_path / "outer.7z").write_bytes(b"dummy")
    output_path = str(tmp_path / "out")

    listings = {"outer.7z": _SLT_SFX, "UnityPlayer.dll": _SLT_PLAIN_PE}
    monkeypatch.setattr(au, "_resolve_seven_zip_path", lambda *a, **k: "7z.exe")
    monkeypatch.setattr(
        au,
        "_run_7z_cmd",
        lambda cmd: (listings[os.path.basename(cmd[-1])], "", 0),
    )

    extracted: list[str] = []

    def fake_extract(archive_path: str, output_path: str, *args, **kwargs) -> bool:
        _ = (args, kwargs)
        extracted.append(os.path.basename(archive_path))
        os.makedirs(output_path, exist_ok=True)
        with open(os.path.join(output_path, "UnityPlayer.dll"), "wb") as f:
            f.write(b"MZ-pe-bytes")
        return True

    monkeypatch.setattr(au, "extractArchiveWith7z", fake_extract)

    result = au.extract_nested_archives(
        archive_path=archive_path,
        output_path=output_path,
        interactive=False,
        use_recycle_bin=False,
    )

    assert extracted == ["outer.7z"]
    finals = result.get("final_files")
    assert isinstance(finals, list)
    dll = [p for p in finals if p.endswith("UnityPlayer.dll")]
    assert len(dll) == 1
    assert os.path.exists(dll[0])


# ---------------------------------------------------------------------------
# Zip-based documents/packages (Type = zip) are kept as regular files
# ---------------------------------------------------------------------------


_REAL_DOC_ENTRIES = {
    "opc": ["[Content_Types].xml", "_rels/.rels", "word/document.xml"],
    "odf": ["mimetype", "content.xml", "META-INF/manifest.xml"],
    "java": ["META-INF/MANIFEST.MF", "com/example/Main.class"],
    "android": ["AndroidManifest.xml", "classes.dex", "res/layout/main.xml"],
    "ipa": ["Payload/App.app/Info.plist"],
    "webext": ["manifest.json", "background.js"],
    "iwork": ["Index/Document.iwa", "Metadata/Properties.plist"],
}
_DOC_FAMILY = {
    ".odt": "odf",
    ".ods": "odf",
    ".odp": "odf",
    ".odb": "odf",
    ".odm": "odf",
    ".epub": "odf",
    ".jar": "java",
    ".apk": "android",
    ".ipa": "ipa",
    ".xpi": "webext",
    ".pages": "iwork",
    ".numbers": "iwork",
    ".key": "iwork",
}
# A plain zip of user files, as found in a cloaked archive.
_PLAIN_ZIP_ENTRIES = ["photos/001.jpg", "photos/002.jpg", "readme.txt"]


def _real_doc_entries(name: str) -> list:
    ext = os.path.splitext(name)[1].lower()
    return _REAL_DOC_ENTRIES[_DOC_FAMILY.get(ext, "opc")]


def _slt_header(name: str, archive_type: str, entries=None) -> str:
    if entries is None:
        entries = _real_doc_entries(name)
    listing = "".join(f"Path = {e}\nSize = 100\n\n" for e in entries)
    return (
        f"Listing archive: {name}\n"
        "\n"
        "--\n"
        f"Path = {name}\n"
        f"Type = {archive_type}\n"
        "Physical Size = 2048\n"
        "\n"
        "----------\n" + listing
    )


_ZIP_DOCUMENT_NAMES = (
    "report.docx",
    "budget.xlsx",
    "slides.pptx",
    "letter.odt",
    "sheet.ods",
    "talk.odp",
    "novel.epub",
    "lib.jar",
    "LIB.JAR",
    "app.apk",
    "app.ipa",
    "addon.xpi",
    "pkg.appx",
    "pkg.msix",
    "ext.vsix",
)


def test_is_valid_archive_false_for_zip_based_documents(monkeypatch):
    for name in _ZIP_DOCUMENT_NAMES:
        _fake_7z_listing(monkeypatch, _slt_header(name, "zip"))
        assert au.is_valid_archive(name) is False, name


def test_is_valid_archive_true_for_zip_disguised_as_other_file(monkeypatch):
    for name in ("photo.jpg", "clip.MP4", "notes.txt", "noext", "issue1.cbz"):
        _fake_7z_listing(monkeypatch, _slt_header(name, "zip"))
        assert au.is_valid_archive(name) is True, name


def test_is_valid_archive_true_for_non_zip_container_named_like_document(
    monkeypatch,
):
    for archive_type in ("7z", "Rar5"):
        _fake_7z_listing(monkeypatch, _slt_header("pack.docx", archive_type))
        assert au.is_valid_archive("pack.docx") is True, archive_type


def test_is_valid_archive_true_for_password_error_on_document_name(monkeypatch):
    _fake_7z_listing(
        monkeypatch,
        "",
        stderr="ERROR: Wrong password : pack.docx\n",
        code=2,
    )
    assert au.is_valid_archive("pack.docx") is True


def _fake_7z_listings_by_name(monkeypatch, listings):
    not_archive = ("", "ERROR: x : Cannot open the file as archive\n", 2)
    monkeypatch.setattr(au, "_resolve_seven_zip_path", lambda *a, **k: "7z.exe")
    monkeypatch.setattr(
        au,
        "_run_7z_cmd",
        lambda cmd: (
            (listings[os.path.basename(cmd[-1])], "", 0)
            if os.path.basename(cmd[-1]) in listings
            else not_archive
        ),
    )


def test_nested_zip_document_is_kept_while_nested_zip_is_extracted(
    monkeypatch, tmp_path
):
    archive_path = str(tmp_path / "outer.7z")
    (tmp_path / "outer.7z").write_bytes(b"dummy")
    output_path = str(tmp_path / "out")

    _fake_7z_listings_by_name(
        monkeypatch,
        {
            "outer.7z": _slt_header("outer.7z", "7z"),
            "report.docx": _slt_header("report.docx", "zip"),
            "inner.zip": _slt_header("inner.zip", "zip"),
        },
    )
    messages: list[str] = []
    monkeypatch.setattr(au, "print_info", lambda msg, *a, **k: messages.append(msg))

    extracted: list[str] = []

    def fake_extract(archive_path: str, output_path: str, *args, **kwargs) -> bool:
        _ = (args, kwargs)
        name = os.path.basename(archive_path)
        extracted.append(name)
        os.makedirs(output_path, exist_ok=True)
        children = (
            {"report.docx": b"PK-docx", "inner.zip": b"PK-zip"}
            if name == "outer.7z"
            else {"readme.txt": b"hello"}
        )
        for child, data in children.items():
            with open(os.path.join(output_path, child), "wb") as f:
                f.write(data)
        return True

    monkeypatch.setattr(au, "extractArchiveWith7z", fake_extract)

    result = au.extract_nested_archives(
        archive_path=archive_path,
        output_path=output_path,
        interactive=False,
        use_recycle_bin=False,
    )

    assert extracted == ["outer.7z", "inner.zip"]
    finals = result.get("final_files")
    assert isinstance(finals, list)
    docx = [p for p in finals if p.endswith("report.docx")]
    assert len(docx) == 1
    assert os.path.exists(docx[0])
    assert any(p.endswith("readme.txt") for p in finals)
    assert any("report.docx" in m and "保留" in m for m in messages)


def test_top_level_zip_document_is_not_extracted_or_deleted(monkeypatch, tmp_path):
    doc = tmp_path / "report.docx"
    doc.write_bytes(b"PK-docx")

    _fake_7z_listings_by_name(
        monkeypatch, {"report.docx": _slt_header("report.docx", "zip")}
    )
    warnings: list[str] = []
    monkeypatch.setattr(au, "print_warning", lambda msg, *a, **k: warnings.append(msg))

    def fail_extract(*args, **kwargs) -> bool:
        raise AssertionError("zip-based document must not be extracted")

    monkeypatch.setattr(au, "extractArchiveWith7z", fail_extract)

    result = au.extract_nested_archives(
        archive_path=str(doc),
        output_path=str(tmp_path / "temp.report"),
        interactive=False,
        use_recycle_bin=False,
    )

    assert doc.exists()
    assert result["success"] is False
    assert any("report.docx" in m and "文档" in m for m in warnings)


# ---------------------------------------------------------------------------
# Top-level non-archives (readme .txt, .url, images) are skipped, not errors
# ---------------------------------------------------------------------------


def _run_top_level(monkeypatch, tmp_path, name, data, stdout, code):
    path = tmp_path / name
    path.write_bytes(data)
    _fake_7z_listing(monkeypatch, stdout, code=code)

    def fail_extract(*args, **kwargs) -> bool:
        raise AssertionError("non-archive must not be extracted")

    monkeypatch.setattr(au, "extractArchiveWith7z", fail_extract)
    result = au.extract_nested_archives(
        archive_path=str(path),
        output_path=str(tmp_path / f"temp.{name}"),
        interactive=False,
        use_recycle_bin=False,
    )
    assert path.exists()
    assert result["success"] is False
    return result


def test_top_level_plain_file_is_skipped_without_error(monkeypatch, tmp_path):
    result = _run_top_level(
        monkeypatch,
        tmp_path,
        "请先看我.txt",
        "解压密码见下方".encode("utf-8"),
        "ERROR: 请先看我.txt : Cannot open the file as archive\n",
        2,
    )
    assert result["errors"] == []
    assert result.get("skipped_non_archive") is True


def test_top_level_broken_archive_is_still_reported(monkeypatch, tmp_path):
    result = _run_top_level(
        monkeypatch,
        tmp_path,
        "data.7z",
        b"\x00garbage",
        "ERROR: data.7z : Cannot open the file as archive\n",
        2,
    )
    assert len(result["errors"]) == 1
    assert not result.get("skipped_non_archive")


def test_top_level_zip_document_is_skipped_without_error(monkeypatch, tmp_path):
    result = _run_top_level(
        monkeypatch,
        tmp_path,
        "report.docx",
        b"PK\x03\x04docx",
        _slt_header("report.docx", "zip"),
        0,
    )
    assert result["errors"] == []
    assert result.get("skipped_non_archive") is True


def test_is_valid_archive_false_for_remaining_ooxml_and_odf_extensions(monkeypatch):
    """PR review: add-ins, slides and Visio stencils/templates are OOXML too."""
    for name in (
        "addin.xlam",
        "addin.ppam",
        "one.sldx",
        "one.sldm",
        "shapes.vssx",
        "shapes.vssm",
        "diagram.vstx",
        "diagram.vstm",
        "base.odb",
        "master.odm",
    ):
        _fake_7z_listing(monkeypatch, _slt_header(name, "zip"))
        assert au.is_valid_archive(name) is False, name


def test_nested_archive_kept_when_recycle_bin_fails(monkeypatch, tmp_path):
    """PR review: if recycling a processed nested archive fails, keep it in
    final_files; otherwise the temp-folder rmtree deletes it permanently."""
    archive_path = str(tmp_path / "outer.7z")
    (tmp_path / "outer.7z").write_bytes(b"dummy")
    output_path = str(tmp_path / "out")

    listings = {
        "outer.7z": _slt_header("outer.7z", "7z"),
        "inner.7z": _slt_header("inner.7z", "7z"),
    }
    monkeypatch.setattr(au, "_resolve_seven_zip_path", lambda *a, **k: "7z.exe")
    monkeypatch.setattr(
        au, "_run_7z_cmd", lambda cmd: (listings[os.path.basename(cmd[-1])], "", 0)
    )
    monkeypatch.setattr(au, "safe_remove", lambda *a, **k: False)

    def fake_extract(archive_path: str, output_path: str, *args, **kwargs) -> bool:
        _ = (args, kwargs)
        os.makedirs(output_path, exist_ok=True)
        name = "inner.7z" if os.path.basename(archive_path) == "outer.7z" else "a.txt"
        with open(os.path.join(output_path, name), "wb") as f:
            f.write(b"data")
        return True

    monkeypatch.setattr(au, "extractArchiveWith7z", fake_extract)

    result = au.extract_nested_archives(
        archive_path=archive_path,
        output_path=output_path,
        interactive=False,
        use_recycle_bin=True,
    )

    finals = result["final_files"]
    assert any(p.endswith("inner.7z") for p in finals)
    assert any(p.endswith("a.txt") for p in finals)


def test_top_level_damaged_archive_with_unknown_extension_is_reported(
    monkeypatch, tmp_path
):
    """PR review: a partial 7z saved as .dat still has its magic bytes, so it
    is reported as a failure rather than silently skipped."""
    result = _run_top_level(
        monkeypatch,
        tmp_path,
        "partial.dat",
        b"7z\xbc\xaf\x27\x1c" + b"\x00" * 26,
        "ERROR: partial.dat : Cannot open the file as archive\n",
        2,
    )
    assert len(result["errors"]) == 1
    assert not result.get("skipped_non_archive")


def test_is_valid_archive_false_for_apple_iwork_documents(monkeypatch):
    """PR review: modern Pages/Numbers/Keynote files are zip packages."""
    for name in ("essay.pages", "sheet.numbers", "talk.key", "TALK.KEY"):
        _fake_7z_listing(monkeypatch, _slt_header(name, "zip"))
        assert au.is_valid_archive(name) is False, name


# ---------------------------------------------------------------------------
# A plain zip renamed to a document extension is a cloaked archive: extract it
# ---------------------------------------------------------------------------

_CLOAKED_DOC_NAMES = (
    "资源.zip.docx",
    "movie.docx",
    "pack.xlsx",
    "album.epub",
    "tool.jar",
    "game.apk",
    "app.ipa",
    "essay.pages",
    "talk.key",
)


def test_is_valid_archive_true_for_plain_zip_named_like_document(monkeypatch):
    for name in _CLOAKED_DOC_NAMES:
        _fake_7z_listing(
            monkeypatch, _slt_header(name, "zip", entries=_PLAIN_ZIP_ENTRIES)
        )
        assert au.is_valid_archive(name) is True, name


def test_is_valid_archive_false_for_real_document_with_windows_paths(monkeypatch):
    """7-Zip on Windows lists entries with backslashes."""
    cases = {
        "lib.jar": ["META-INF\\MANIFEST.MF", "a\\B.class"],
        "app.ipa": ["Payload\\App.app\\Info.plist"],
        "essay.pages": ["Index\\Document.iwa"],
    }
    for name, entries in cases.items():
        _fake_7z_listing(monkeypatch, _slt_header(name, "zip", entries=entries))
        assert au.is_valid_archive(name) is False, name


def test_is_valid_archive_false_for_suffix_marker_formats(monkeypatch):
    cases = {
        "pkg-1.0-py3-none-any.whl": ["pkg/__init__.py", "pkg-1.0.dist-info/METADATA"],
        "places.kmz": ["doc.kml", "files/icon.png"],
        "old.pages": ["index.xml", "QuickLook/Thumbnail.jpg"],
    }
    for name, entries in cases.items():
        _fake_7z_listing(monkeypatch, _slt_header(name, "zip", entries=entries))
        assert au.is_valid_archive(name) is False, name


def test_nested_cloaked_zip_named_like_document_is_extracted(monkeypatch, tmp_path):
    archive_path = str(tmp_path / "outer.7z")
    (tmp_path / "outer.7z").write_bytes(b"dummy")
    listings = {
        "outer.7z": _slt_header("outer.7z", "7z", entries=["资源.zip.docx"]),
        "资源.zip.docx": _slt_header("资源.zip.docx", "zip", entries=_PLAIN_ZIP_ENTRIES),
    }
    monkeypatch.setattr(au, "_resolve_seven_zip_path", lambda *a, **k: "7z.exe")
    monkeypatch.setattr(
        au, "_run_7z_cmd", lambda cmd: (listings[os.path.basename(cmd[-1])], "", 0)
    )
    extracted: list = []

    def fake_extract(archive_path: str, output_path: str, *args, **kwargs) -> bool:
        _ = (args, kwargs)
        name = os.path.basename(archive_path)
        extracted.append(name)
        os.makedirs(output_path, exist_ok=True)
        child = "资源.zip.docx" if name == "outer.7z" else "readme.txt"
        with open(os.path.join(output_path, child), "wb") as f:
            f.write(b"PK\x03\x04data")
        return True

    monkeypatch.setattr(au, "extractArchiveWith7z", fake_extract)

    result = au.extract_nested_archives(
        archive_path=archive_path,
        output_path=str(tmp_path / "out"),
        interactive=False,
        use_recycle_bin=False,
    )

    assert extracted == ["outer.7z", "资源.zip.docx"]
    assert any(p.endswith("readme.txt") for p in result["final_files"])


def test_libreoffice_extension_kept_unless_plain_zip(monkeypatch):
    """PR review: .oxt packages (META-INF/manifest.xml) are kept."""
    _fake_7z_listing(
        monkeypatch,
        _slt_header("tool.oxt", "zip", entries=["META-INF/manifest.xml", "x.xcu"]),
    )
    assert au.is_valid_archive("tool.oxt") is False
    _fake_7z_listing(
        monkeypatch, _slt_header("tool.oxt", "zip", entries=_PLAIN_ZIP_ENTRIES)
    )
    assert au.is_valid_archive("tool.oxt") is True


def _slt_split(name: str, volumes: int, inner_type=None) -> str:
    inner = name.rsplit(".", 1)[0]
    listing = (
        f"--\nPath = {name}\nType = Split\nVolumes = {volumes}\n----\n"
        f"Path = {inner}\nSize = 3000\n"
    )
    if inner_type:
        listing += f"--\nPath = {inner}\nType = {inner_type}\n"
    return listing + f"\n----------\nPath = {inner}\nSize = 3000\n"


def test_bare_split_needs_at_least_two_volumes(monkeypatch):
    """PR review: a lone ordinary report.001 is not an archive to extract,
    but a real multi-volume split of a raw file (movie.mkv.001) is joined."""
    _fake_7z_listing(monkeypatch, _slt_split("report.001", 1))
    assert au.is_valid_archive("report.001") is False
    _fake_7z_listing(monkeypatch, _slt_split("movie.mkv.001", 2))
    assert au.is_valid_archive("movie.mkv.001") is True
    _fake_7z_listing(monkeypatch, _slt_split("set.7z.001", 1, inner_type="7z"))
    assert au.is_valid_archive("set.7z.001") is True


def test_manifestless_jar_is_kept(monkeypatch):
    """PR review: `jar --no-manifest` JARs have no META-INF, only classes."""
    for entries in (
        ["com/example/Foo.class", "com/example/Bar.class"],
        ["com\\\\example\\\\Foo.class"],
        ["Foo.class"],
    ):
        _fake_7z_listing(monkeypatch, _slt_header("lib.jar", "zip", entries=entries))
        assert au.is_valid_archive("lib.jar") is False, entries


def test_top_level_damaged_zip_named_like_document_is_reported(monkeypatch, tmp_path):
    """PR review: a truncated zip named payload.docx must not be hidden as a
    kept document; only an intact zip with the format marker is skipped."""
    result = _run_top_level(
        monkeypatch,
        tmp_path,
        "payload.docx",
        b"PK\x03\x04" + b"\x00" * 28,
        "ERROR: payload.docx : Cannot open the file as archive\n",
        2,
    )
    assert len(result["errors"]) == 1
    assert not result.get("skipped_non_archive")
