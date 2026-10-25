"""SevenZipEngine maps 7-Zip helpers onto work-pool outcomes (7-Zip mocked)."""

import os

import pytest

import deepunzip.modules.archive_utils as au
from deepunzip.classes.ArchiveTypes import (
    ArchiveCorruptedError,
    ArchiveMissingVolumeError,
    ArchivePasswordError,
    ArchiveUnsupportedError,
    SevenZipNotFoundError,
)
from deepunzip.modules.pool_engine import SevenZipEngine


class Book:
    def __init__(self, passwords):
        self.passwords = list(passwords)

    def get_passwords(self):
        return list(self.passwords)

    def add_password(self, password):
        if password not in self.passwords:
            self.passwords.append(password)


def _extract_needing(correct, calls, write_name="out.txt"):
    def fake_extract(archive_path, output_path, password="", **kwargs):
        calls.append(password)
        # A failed attempt may leave partial files behind.
        with open(os.path.join(output_path, f"partial-{len(calls)}"), "w") as handle:
            handle.write("x")
        if password != correct:
            raise ArchivePasswordError("wrong password")
        with open(os.path.join(output_path, write_name), "w") as handle:
            handle.write("ok")
        return True

    return fake_extract


def test_extract_tries_empty_then_book_in_order(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(au, "extractArchiveWith7z", _extract_needing("b", calls))
    dest = tmp_path / "dest"
    dest.mkdir()
    outcome = SevenZipEngine(Book(["a", "b", "c"])).extract("x.7z", str(dest))
    assert calls == ["", "a", "b"]
    assert (outcome.status, outcome.password, outcome.password_ref) == ("ok", "b", 2)
    # Partial files of failed attempts are cleared.
    assert sorted(os.listdir(dest)) == ["out.txt", "partial-3"]


def test_extract_with_given_password_tries_only_that(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(au, "extractArchiveWith7z", _extract_needing("typed", calls))
    outcome = SevenZipEngine(Book(["a"])).extract("x.7z", str(tmp_path), "typed")
    assert calls == ["typed"]
    assert (outcome.status, outcome.password_ref) == ("ok", "entered")


def test_extract_reports_password_failure(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(au, "extractArchiveWith7z", _extract_needing("zzz", calls))
    outcome = SevenZipEngine(Book(["a"])).extract("x.7z", str(tmp_path))
    assert outcome.status == "password"
    assert os.listdir(tmp_path) == []


@pytest.mark.parametrize(
    "error, status",
    [
        (ArchiveMissingVolumeError("missing"), "missing_volume"),
        (ArchiveUnsupportedError("not an archive"), "unsupported"),
        (ArchiveCorruptedError("crc"), "failed"),
    ],
)
def test_extract_stops_on_archive_errors(monkeypatch, tmp_path, error, status):
    calls = []

    def fail(*args, **kwargs):
        calls.append(kwargs.get("password"))
        raise error

    monkeypatch.setattr(au, "extractArchiveWith7z", fail)
    outcome = SevenZipEngine(Book(["a", "b"])).extract("x.7z", str(tmp_path))
    assert outcome.status == status
    assert calls == [""]


def test_missing_engine_is_fatal(monkeypatch, tmp_path):
    def fail(*args, **kwargs):
        raise SevenZipNotFoundError("no 7z")

    monkeypatch.setattr(au, "extractArchiveWith7z", fail)
    with pytest.raises(SevenZipNotFoundError):
        SevenZipEngine(Book([])).extract("x.7z", str(tmp_path))


def test_probe_with_readable_headers_leaves_password_unknown(monkeypatch):
    monkeypatch.setattr(
        au,
        "_list_archive_with7z",
        lambda *a, **k: ("7z", [{"name": "f"}], 2),
    )
    outcome = SevenZipEngine(Book(["a"])).probe("x.7z.001")
    assert (outcome.status, outcome.password, outcome.volumes) == ("ok", None, 2)


def test_probe_with_encrypted_headers_finds_the_password(monkeypatch):
    def listing(archive_path, password="", **kwargs):
        if password != "b":
            raise ArchivePasswordError("Cannot open encrypted archive")
        return "7z", [{"name": "f"}], None

    monkeypatch.setattr(au, "_list_archive_with7z", listing)
    outcome = SevenZipEngine(Book(["a", "b"])).probe("x.7z.001")
    assert (outcome.status, outcome.password, outcome.password_ref) == ("ok", "b", 2)


def test_probe_rejects_a_bare_one_volume_split(monkeypatch):
    monkeypatch.setattr(
        au, "_list_archive_with7z", lambda *a, **k: ("Split", [{"name": "f"}], 1)
    )
    assert SevenZipEngine(Book([])).probe("report.2024.001").status == "unsupported"


def test_probe_reports_missing_volume(monkeypatch):
    def listing(*args, **kwargs):
        raise ArchiveMissingVolumeError("Unexpected end of archive")

    monkeypatch.setattr(au, "_list_archive_with7z", listing)
    assert SevenZipEngine(Book(["a"])).probe("x.7z.001").status == "missing_volume"


@pytest.mark.parametrize(
    "valid, document, signature, verdict",
    [
        (True, False, ".7z", "container"),
        (False, True, ".zip", "regular"),
        (False, False, None, "regular"),
        (False, False, ".7z", "broken"),
    ],
)
def test_classify(monkeypatch, valid, document, signature, verdict):
    monkeypatch.setattr(au, "is_valid_archive", lambda *a, **k: valid)
    monkeypatch.setattr(au, "_is_intact_zip_document", lambda *a, **k: document)
    monkeypatch.setattr(au, "detect_archive_extension", lambda *a, **k: signature)
    name = "report.docx" if document else "thing.bin"
    assert SevenZipEngine(Book([])).classify(name) == verdict


def test_remember_adds_to_the_password_book():
    book = Book(["a"])
    SevenZipEngine(book).remember("typed")
    assert book.get_passwords() == ["a", "typed"]
