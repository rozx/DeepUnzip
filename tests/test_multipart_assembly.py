import os
import struct
import zlib

import pytest

from complex_unzip_tool_v2.modules import multipart_assembly as ma

SEVEN_Z_SIGNATURE = b"7z\xbc\xaf\x27\x1c\x00\x04"


def _seven_z_start_header(next_offset: int, next_size: int, crc_ok=True) -> bytes:
    tail = struct.pack("<QQI", next_offset, next_size, 0)
    crc = zlib.crc32(tail) if crc_ok else zlib.crc32(tail) ^ 1
    return SEVEN_Z_SIGNATURE + struct.pack("<I", crc) + tail


# ------------------------------
# 7z start header
# ------------------------------


def test_7z_total_size_from_start_header(tmp_path):
    path = tmp_path / "x.7z.001"
    path.write_bytes(_seven_z_start_header(312275728, 52) + b"\x00" * 100)
    assert ma.read_7z_total_size(str(path)) == 32 + 312275728 + 52


def test_7z_total_size_none_for_other_files(tmp_path):
    path = tmp_path / "x.zip.001"
    path.write_bytes(b"PK\x03\x04" + b"\x00" * 60)
    assert ma.read_7z_total_size(str(path)) is None


def test_7z_total_size_none_for_short_file(tmp_path):
    path = tmp_path / "x.7z.001"
    path.write_bytes(SEVEN_Z_SIGNATURE)
    assert ma.read_7z_total_size(str(path)) is None


def test_7z_total_size_none_when_start_header_crc_mismatches(tmp_path):
    path = tmp_path / "x.7z.001"
    path.write_bytes(_seven_z_start_header(1000, 52, crc_ok=False))
    assert ma.read_7z_total_size(str(path)) is None


def test_7z_total_size_none_for_missing_file(tmp_path):
    assert ma.read_7z_total_size(str(tmp_path / "absent.7z.001")) is None


# ------------------------------
# Volume names
# ------------------------------


@pytest.mark.parametrize(
    "name, base, family, index, primary",
    [
        ("a.7z.001", "a", "7z", 1, True),
        ("a.7z.002", "a", "7z", 2, False),
        ("a.7Z.1", "a", "7z", 1, True),
        ("a.tar.gz.001", "a", "tar.gz", 1, True),
        ("a.tar.xz.003", "a", "tar.xz", 3, False),
        ("a.zip.001", "a", "zip", 1, True),
        ("a.iso.0002", "a", "iso", 2, False),
        ("a.part1.rar", "a", "rar-part", 1, True),
        ("a.part01.rar", "a", "rar-part", 1, True),
        ("a.part12.RAR", "a", "rar-part", 12, False),
        ("a.rar", "a", "rar-vol", 1, True),
        ("a.r00", "a", "rar-vol", 2, False),
        ("a.R07", "a", "rar-vol", 9, False),
        ("a.zip", "a", "zip-span", 1, True),
        ("a.z01", "a", "zip-span", 2, False),
        ("a.zipx", "a", "zipx-span", 1, True),
        ("a.zx02", "a", "zipx-span", 3, False),
        ("a.arj", "a", "arj-vol", 1, True),
        ("a.a01", "a", "arj-vol", 2, False),
        ("a.ace", "a", "ace-vol", 1, True),
        ("a.c00", "a", "ace-vol", 2, False),
        ("东风起 风月孤星等你.7z.001", "东风起 风月孤星等你", "7z", 1, True),
        ("my.photos.2024.7z.002", "my.photos.2024", "7z", 2, False),
    ],
)
def test_parse_volume_name(name, base, family, index, primary):
    parsed = ma.parse_volume_name(name)
    assert parsed is not None
    assert (parsed.base, parsed.family, parsed.index, parsed.is_primary) == (
        base,
        family,
        index,
        primary,
    )


@pytest.mark.parametrize("name", ["a.rar", "a.zip", "a.zipx", "a.arj", "a.ace"])
def test_single_archive_extensions_are_ambiguous_primaries(name):
    parsed = ma.parse_volume_name(name)
    assert parsed is not None and parsed.ambiguous and parsed.is_primary


@pytest.mark.parametrize(
    "name", ["a.7z.001", "a.part1.rar", "a.zip.001", "a.r00", "a.z01"]
)
def test_explicit_volume_names_are_not_ambiguous(name):
    parsed = ma.parse_volume_name(name)
    assert parsed is not None and not parsed.ambiguous


@pytest.mark.parametrize(
    "name", ["a.7z", "photo.001", "readme.txt", "a.tar.gz", "movie.mp4"]
)
def test_non_volume_names(name):
    assert ma.parse_volume_name(name) is None


def test_part_without_number_is_a_plain_rar_name():
    parsed = ma.parse_volume_name("a.part.rar")
    assert parsed is not None
    assert (parsed.base, parsed.family, parsed.ambiguous) == ("a.part", "rar-vol", True)


def test_volume_keys_separate_split_conventions():
    numbered = ma.parse_volume_name("a.zip.001")
    spanned = ma.parse_volume_name("a.z01")
    assert numbered is not None and spanned is not None
    assert numbered.key != spanned.key


def _make(path, size=100, content=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content if content is not None else b"\x00" * size)
    candidate = ma.Candidate.from_path(str(path))
    assert candidate is not None
    return candidate


def _names(combo):
    return [os.path.relpath(c.path) for c in combo]


# ------------------------------
# Scopes
# ------------------------------


def test_scopes_for_primary_in_root(tmp_path):
    root = str(tmp_path)
    scopes = ma.scopes_for(str(tmp_path / "X.7z.001"), root)
    assert [(s.folder, s.recursive) for s in scopes] == [(root, False), (root, True)]


def test_scopes_widen_up_to_the_root_and_never_beyond(tmp_path):
    root = str(tmp_path / "in")
    primary = tmp_path / "in" / "work" / "A" / "X.7z.001"
    scopes = ma.scopes_for(str(primary), root)
    assert [(s.folder, s.recursive) for s in scopes] == [
        (str(tmp_path / "in" / "work" / "A"), False),
        (str(tmp_path / "in" / "work" / "A"), True),
        (str(tmp_path / "in" / "work"), True),
        (root, True),
    ]


def test_scope_containment(tmp_path):
    folder = str(tmp_path / "A")
    flat = ma.Scope(folder, recursive=False)
    deep = ma.Scope(folder, recursive=True)
    inside = str(tmp_path / "A" / "x")
    nested = str(tmp_path / "A" / "B" / "x")
    sibling = str(tmp_path / "AB" / "x")
    assert flat.contains(inside) and not flat.contains(nested)
    assert deep.contains(inside) and deep.contains(nested)
    assert not deep.contains(sibling)


# ------------------------------
# Combinations
# ------------------------------


def test_complete_set_in_the_primary_folder_is_tried_first(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    primary = _make(tmp_path / "X.7z.001")
    local = _make(tmp_path / "X.7z.002")
    far = _make(tmp_path / "work" / "B" / "X.7z.002")
    combos = list(ma.iter_combinations(primary, [primary, local, far], str(tmp_path)))
    assert _names(combos[0][1]) == ["X.7z.001", "X.7z.002"]
    assert combos[0][0].recursive is False
    # The far volume only appears once the subtree scope is reached.
    assert [_names(c) for _, c in combos[1:]] == [
        ["X.7z.001", os.path.join("work", "B", "X.7z.002")]
    ]


def test_source_primary_finds_continuation_in_the_work_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    primary = _make(tmp_path / "X.7z.001")
    inner = _make(tmp_path / "temp.deepunzip-1" / "A" / "X.7z.002")
    combos = list(ma.iter_combinations(primary, [primary, inner], str(tmp_path)))
    assert [_names(c) for _, c in combos] == [
        ["X.7z.001"],
        ["X.7z.001", os.path.join("temp.deepunzip-1", "A", "X.7z.002")],
    ]


def test_volumes_split_across_sibling_containers(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    primary = _make(tmp_path / "work" / "A" / "X.7z.001")
    other = _make(tmp_path / "work" / "B" / "X.7z.002")
    combos = list(ma.iter_combinations(primary, [primary, other], str(tmp_path)))
    scope, combo = combos[-1]
    assert scope.folder == str(tmp_path / "work")
    assert _names(combo) == [
        os.path.join("work", "A", "X.7z.001"),
        os.path.join("work", "B", "X.7z.002"),
    ]


def test_scope_with_a_gap_is_skipped(tmp_path):
    primary = _make(tmp_path / "X.7z.001")
    third = _make(tmp_path / "X.7z.003")
    combos = list(ma.iter_combinations(primary, [primary, third], str(tmp_path)))
    assert combos == []


def test_combinations_are_ordered_by_proximity(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    primary = _make(tmp_path / "work" / "A" / "X.7z.001")
    near = _make(tmp_path / "work" / "B" / "X.7z.002")
    far = _make(tmp_path / "work" / "C" / "D" / "X.7z.002")
    combos = list(ma.iter_combinations(primary, [primary, far, near], str(tmp_path)))
    assert [_names(c)[1] for _, c in combos if len(c) > 1] == [
        os.path.join("work", "B", "X.7z.002"),
        os.path.join("work", "C", "D", "X.7z.002"),
    ]


def test_other_keys_are_ignored(tmp_path):
    primary = _make(tmp_path / "X.7z.001")
    other = _make(tmp_path / "Y.7z.002")
    spanned = _make(tmp_path / "X.z01")
    combos = list(
        ma.iter_combinations(primary, [primary, other, spanned], str(tmp_path))
    )
    assert [len(c) for _, c in combos] == [1]


def test_spanned_zip_combination_uses_its_continuations(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    primary = _make(tmp_path / "X.zip")
    first = _make(tmp_path / "X.z01")
    second = _make(tmp_path / "X.z02")
    combos = list(
        ma.iter_combinations(primary, [second, primary, first], str(tmp_path))
    )
    assert _names(combos[0][1]) == ["X.zip", "X.z01", "X.z02"]


# ------------------------------
# Prefilters
# ------------------------------


def test_numbered_split_with_inconsistent_sizes_is_rejected(tmp_path):
    combo = (
        _make(tmp_path / "X.7z.001", size=100),
        _make(tmp_path / "X.7z.002", size=90),
        _make(tmp_path / "X.7z.003", size=40),
    )
    assert ma.prefilter(combo) is not None


def test_numbered_split_with_larger_last_volume_is_rejected(tmp_path):
    combo = (
        _make(tmp_path / "X.zip.001", size=100),
        _make(tmp_path / "X.zip.002", size=120),
    )
    assert ma.prefilter(combo) is not None


def test_7z_split_total_must_match_start_header(tmp_path):
    header = _seven_z_start_header(150 - 32 - 10, 10)  # whole archive is 150 bytes
    good = (
        _make(tmp_path / "a" / "X.7z.001", content=header + b"\x00" * 68),
        _make(tmp_path / "a" / "X.7z.002", size=50),
    )
    bad = (good[0], _make(tmp_path / "b" / "X.7z.002", size=100))
    assert ma.prefilter(good) is None
    assert ma.prefilter(bad) is not None


def test_rar_volumes_of_different_sizes_are_not_rejected(tmp_path):
    combo = (
        _make(tmp_path / "X.part1.rar", size=100),
        _make(tmp_path / "X.part2.rar", size=80),
        _make(tmp_path / "X.part3.rar", size=30),
    )
    assert ma.prefilter(combo) is None


def test_size_hint_orders_consistent_rar_combination_first(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    primary = _make(tmp_path / "work" / "A" / "X.part1.rar", size=100)
    odd = _make(tmp_path / "work" / "B" / "X.part2.rar", size=70)
    even = _make(tmp_path / "work" / "C" / "X.part2.rar", size=100)
    third = _make(tmp_path / "work" / "D" / "X.part3.rar", size=20)
    combos = [
        combo
        for _, combo in ma.iter_combinations(
            primary, [primary, odd, even, third], str(tmp_path)
        )
        if len(combo) > 1
    ]
    assert _names(combos[0])[1] == os.path.join("work", "C", "X.part2.rar")


def test_ambiguous_primary_is_never_tried_alone(tmp_path):
    primary = _make(tmp_path / "X.rar")
    elsewhere = _make(tmp_path / "work" / "B" / "X.r00")
    combos = list(ma.iter_combinations(primary, [primary, elsewhere], str(tmp_path)))
    assert [len(c) for _, c in combos] == [2]


def test_other_primaries_are_not_continuations(tmp_path):
    primary = _make(tmp_path / "A" / "X.7z.001")
    rival = _make(tmp_path / "B" / "X.7z.001")
    combos = list(ma.iter_combinations(primary, [primary, rival], str(tmp_path)))
    assert all(len(c) == 1 for _, c in combos)


# ------------------------------
# Duplicates
# ------------------------------


def test_identical_leftover_volume_is_a_duplicate(tmp_path):
    used = _make(tmp_path / "A" / "X.7z.002", content=b"same bytes")
    copy = _make(tmp_path / "B" / "X.7z.002", content=b"same bytes")
    differs = _make(tmp_path / "C" / "X.7z.002", content=b"other byte")
    other_index = _make(tmp_path / "D" / "X.7z.003", content=b"same bytes")
    assert ma.find_duplicates([used], [copy, differs, other_index]) == [copy]


def test_volumes_of_one_set_share_a_key():
    upper = ma.parse_volume_name("Movie.7z.001")
    lower = ma.parse_volume_name("Movie.7z.002")
    assert upper is not None and lower is not None
    assert upper.key == lower.key
    assert upper.display_key == "Movie|7z"
