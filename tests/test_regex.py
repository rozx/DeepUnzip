"""Unit tests for multipart detection regex patterns."""

import re

from deepunzip.modules.regex import multipart_regex, first_part_regex


def _is_multipart(name: str) -> bool:
    return bool(re.search(multipart_regex, name, re.IGNORECASE))


def _is_first_part(name: str) -> bool:
    return bool(re.search(first_part_regex, name, re.IGNORECASE))


class TestMultipartRegex:
    """multipart_regex must match every supported continuation/volume form."""

    def test_existing_formats_still_match(self):
        for name in [
            "a.7z.001",
            "a.7z.002",
            "a.tar.gz.001",
            "a.tar.bz2.002",
            "a.z01",
            "a.r00",
            "a.part1.rar",
            "a.part2.rar",
        ]:
            assert _is_multipart(name), name

    def test_generic_numbered_split_any_extension(self):
        for name in [
            "a.zip.001",
            "a.zip.002",
            "a.rar.001",
            "a.iso.001",
            "a.bin.002",
            "a.tar.001",
        ]:
            assert _is_multipart(name), name

    def test_zipx_arj_ace_continuations_match(self):
        for name in ["a.zx01", "a.zx02", "a.a01", "a.a02", "a.c00", "a.c01"]:
            assert _is_multipart(name), name

    def test_non_multipart_names_do_not_match(self):
        # Standalone primaries and ordinary files are not continuations.
        for name in [
            "a.zip",
            "a.7z",
            "a.rar",
            "a.zipx",
            "a.arj",
            "a.ace",
            "movie.mp4",
            "a.001",  # bare numeric, no archive token before the number
        ]:
            assert not _is_multipart(name), name

    def test_one_and_two_digit_numeric_suffix_not_multipart(self):
        # Only zero-padded 3+ digit volume suffixes count (what 7-Zip emits).
        for name in ["a.zip.1", "a.zip.01", "a.iso.1"]:
            assert not _is_multipart(name), name


class TestFirstPartRegex:
    """first_part_regex marks only the unambiguous numbered entry point."""

    def test_existing_first_parts_match(self):
        for name in ["a.7z.001", "a.tar.gz.001", "a.part1.rar"]:
            assert _is_first_part(name), name

    def test_generic_numbered_first_part_matches(self):
        for name in ["a.zip.001", "a.rar.001", "a.iso.001"]:
            assert _is_first_part(name), name

    def test_continuations_are_not_first_parts(self):
        for name in ["a.zip.002", "a.7z.002", "a.z01", "a.r00", "a.part2.rar"]:
            assert not _is_first_part(name), name
