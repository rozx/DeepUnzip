"""
Archive-related exception classes and types for DeepUnzip.

This module defines custom exception classes and structured types used
throughout the archive processing functionality.
"""
from typing import TypedDict


class ArchiveFileInfo(TypedDict, total=False):
    """Structured type for archive file information returned by 7z parsing."""

    name: str
    size: int
    packed_size: int
    type: str
    modified: str
    attributes: str
    crc: str
    method: str


class ArchiveError(Exception):
    """Base exception for archive-related errors."""

    pass


class ArchiveNotFoundError(ArchiveError):
    """Raised when the archive file is not found."""

    pass


class SevenZipNotFoundError(ArchiveError):
    """Raised when 7z executable is not found."""

    pass


class ArchivePasswordError(ArchiveError):
    """Raised when password is incorrect or required."""

    pass


class ArchiveCorruptedError(ArchiveError):
    """Raised when archive is corrupted or unreadable."""

    pass


class ArchiveMissingVolumeError(ArchiveError):
    """Raised when a multi-volume archive is missing one of its volumes."""

    pass


class ArchiveUnsupportedError(ArchiveError):
    """Raised when archive format is not supported."""

    pass


class ArchiveParsingError(ArchiveError):
    """Raised when unable to parse 7z output."""

    pass
