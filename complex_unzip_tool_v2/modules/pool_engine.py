"""
7-Zip engine for the work pool.
工作池使用的 7-Zip 引擎。

Implements `work_pool.Engine` on top of the existing 7-Zip helpers: archive
classification, one-level extraction and header-only probes, each trying the
empty password first and then the password book in order. Outcomes carry the
password's position in the book (password #N) so output never shows it.
"""

import os
import shutil
from typing import Optional, Protocol

from complex_unzip_tool_v2.classes.ArchiveTypes import (
    ArchiveCorruptedError,
    ArchiveError,
    ArchiveMissingVolumeError,
    ArchiveNotFoundError,
    ArchiveParsingError,
    ArchivePasswordError,
    ArchiveUnsupportedError,
    SevenZipNotFoundError,
)
from complex_unzip_tool_v2.modules import archive_utils
from complex_unzip_tool_v2.modules.const import PATH_ERROR_KEYWORDS
from complex_unzip_tool_v2.modules.work_pool import Outcome, PasswordRef


class PasswordSource(Protocol):
    def get_passwords(self) -> list[str]:
        ...

    def add_password(self, password: str) -> None:
        ...


def _reset_dir(path: str) -> None:
    shutil.rmtree(path, ignore_errors=True)
    os.makedirs(path, exist_ok=True)


class SevenZipEngine:
    """Work-pool engine backed by the bundled 7-Zip."""

    def __init__(
        self, book: PasswordSource, seven_zip_path: Optional[str] = None
    ) -> None:
        self.book = book
        self.seven_zip_path = seven_zip_path

    # ---------- helpers ----------

    def _candidates(self, password: Optional[str]) -> list[str]:
        if password is not None:
            return [password]
        return ["", *(p for p in self.book.get_passwords() if p)]

    def _ref(self, password: str) -> PasswordRef:
        if password == "":
            return 0
        passwords = self.book.get_passwords()
        if password in passwords:
            return passwords.index(password) + 1
        return "entered"

    # ---------- Engine ----------

    def classify(self, path: str) -> str:
        if archive_utils.is_valid_archive(
            path, password="", seven_zip_path=self.seven_zip_path
        ):
            return "container"
        if archive_utils._has_zip_document_extension(
            path
        ) and archive_utils._is_intact_zip_document(
            path, password="", seven_zip_path=self.seven_zip_path
        ):
            return "regular"
        if archive_utils.detect_archive_extension(path) is None:
            return "regular"
        return "broken"

    def extract(
        self, archive: str, dest: str, password: Optional[str] = None
    ) -> Outcome:
        saw_password = False
        for candidate in self._candidates(password):
            _reset_dir(dest)
            try:
                extracted = archive_utils.extractArchiveWith7z(
                    archive_path=archive,
                    output_path=dest,
                    password=candidate,
                    seven_zip_path=self.seven_zip_path,
                    overwrite=True,
                )
            except ArchivePasswordError:
                saw_password = True
                continue
            except ArchiveMissingVolumeError as error:
                return Outcome("missing_volume", detail=str(error))
            except ArchiveUnsupportedError as error:
                return Outcome("unsupported", detail=str(error))
            except (ArchiveCorruptedError, ArchiveNotFoundError) as error:
                return Outcome("failed", detail=str(error))
            except SevenZipNotFoundError:
                raise
            except ArchiveError as error:
                if any(key in str(error).lower() for key in PATH_ERROR_KEYWORDS):
                    return Outcome("failed", detail=str(error))
                continue
            if extracted:
                return Outcome("ok", candidate, self._ref(candidate))
        _reset_dir(dest)
        return Outcome("password" if saw_password else "failed")

    def probe(self, archive: str, password: Optional[str] = None) -> Outcome:
        saw_password = False
        for candidate in self._candidates(password):
            try:
                archive_type, _content, volumes = archive_utils._list_archive_with7z(
                    archive, password=candidate, seven_zip_path=self.seven_zip_path
                )
            except ArchivePasswordError:
                saw_password = True
                continue
            except ArchiveMissingVolumeError as error:
                return Outcome("missing_volume", detail=str(error))
            except ArchiveUnsupportedError as error:
                return Outcome("unsupported", detail=str(error))
            except (
                ArchiveCorruptedError,
                ArchiveNotFoundError,
                ArchiveParsingError,
            ) as error:
                return Outcome("failed", detail=str(error))
            except SevenZipNotFoundError:
                raise
            except ArchiveError:
                continue
            # A one-volume Split is a lone numbered file, not an archive set.
            if archive_type and archive_type.lower() == "split" and (volumes or 0) < 2:
                return Outcome("unsupported", detail="lone numbered file")
            if candidate == "":
                # Readable headers prove nothing about an encrypted payload:
                # leave the password to extraction, which tries the book.
                return Outcome("ok", None, None, volumes=volumes)
            return Outcome("ok", candidate, self._ref(candidate), volumes=volumes)
        return Outcome("password" if saw_password else "failed")

    def remember(self, password: str) -> None:
        self.book.add_password(password)
