"""
Multipart volume naming, combination search and prefilters for the work pool.
工作池使用的分卷命名、组合搜索与预过滤。

Everything here is pure (no 7-Zip calls) so the assembly rules can be tested
directly. See D4 in
openspec/changes/archive/2026-10-25-redesign-work-pool-extraction/design.md.
"""

import hashlib
import itertools
import os
import re
import struct
import zlib
from dataclasses import dataclass
from typing import Iterator, Optional, Sequence

# Probes allowed per multipart set over a whole run (fixed, not a CLI option).
MAX_ASSEMBLY_ATTEMPTS = 64
# Combinations examined per set attempt, probed or not: prefilters reject
# without spending a probe, so they need their own bound.
MAX_COMBINATIONS_PER_ATTEMPT = 4096

_SEVEN_Z_SIGNATURE = b"7z\xbc\xaf\x27\x1c"
_SEVEN_Z_START_HEADER_SIZE = 32
# Families whose volumes may legitimately differ in size; size is only a hint.
_NAMED_VOLUME_FAMILIES = frozenset(
    {"rar-part", "rar-vol", "zip-span", "zipx-span", "arj-vol", "ace-vol"}
)
# Above this many combinations per scope, products are walked lazily in
# per-volume proximity order instead of being fully sorted.
_FULL_SORT_LIMIT = 4096


def read_7z_total_size(path: str) -> Optional[int]:
    """Return the archive size recorded in a 7z start header, or None.

    The 32-byte start header is never encrypted, so this works for
    header-encrypted archives and for the first volume of a split set,
    where it gives the size of the whole joined archive.
    """
    try:
        with open(path, "rb") as handle:
            header = handle.read(_SEVEN_Z_START_HEADER_SIZE)
    except OSError:
        return None
    if len(header) < _SEVEN_Z_START_HEADER_SIZE:
        return None
    if not header.startswith(_SEVEN_Z_SIGNATURE):
        return None
    (start_header_crc,) = struct.unpack("<I", header[8:12])
    if zlib.crc32(header[12:32]) != start_header_crc:
        return None
    next_offset, next_size = struct.unpack("<QQ", header[12:28])
    return _SEVEN_Z_START_HEADER_SIZE + int(next_offset) + int(next_size)


@dataclass(frozen=True)
class VolumeName:
    """A file name parsed as one volume of a multipart set.

    `index` is 1 for the volume 7-Zip must be invoked on and counts up through
    the continuations, so every format shares the same contiguity rule.
    `ambiguous` marks single-archive extensions (.rar, .zip, …) that are only a
    set primary when a continuation of the same key exists.
    """

    base: str
    family: str
    index: int
    is_primary: bool
    ambiguous: bool = False

    @property
    def key(self) -> tuple[str, str]:
        return os.path.normcase(self.base), self.family

    @property
    def display_key(self) -> str:
        return f"{self.base}|{self.family}"

    @property
    def is_numbered_split(self) -> bool:
        """True for `.7z.NNN` / `.<ext>.NNN` splits, whose volumes are equal-sized."""
        return self.family not in _NAMED_VOLUME_FAMILIES


# (pattern, family, continuation index offset). A continuation's index is its
# number plus the offset, so `.r00` and `.c00` become 2 and `.z01` becomes 2.
_CONTINUATION_PATTERNS = [
    (re.compile(r"^(.+)\.zx(\d{2})$", re.IGNORECASE), "zipx-span", 1),
    (re.compile(r"^(.+)\.z(\d{2})$", re.IGNORECASE), "zip-span", 1),
    (re.compile(r"^(.+)\.r(\d{2})$", re.IGNORECASE), "rar-vol", 2),
    (re.compile(r"^(.+)\.a(\d{2})$", re.IGNORECASE), "arj-vol", 1),
    (re.compile(r"^(.+)\.c(\d{2})$", re.IGNORECASE), "ace-vol", 2),
]
_AMBIGUOUS_PRIMARY_FAMILIES = {
    "rar": "rar-vol",
    "zip": "zip-span",
    "zipx": "zipx-span",
    "arj": "arj-vol",
    "ace": "ace-vol",
}
_TAR_SPLIT_RE = re.compile(r"^(.+)\.tar\.(gz|bz2|xz)\.(\d{1,3})$", re.IGNORECASE)
_SEVEN_Z_SPLIT_RE = re.compile(r"^(.+)\.7z\.(\d{1,3})$", re.IGNORECASE)
_NUMBERED_SPLIT_RE = re.compile(r"^(.+)\.([A-Za-z0-9]+)\.(\d{3,})$")
_RAR_PART_RE = re.compile(r"^(.+)\.part(\d+)\.rar$", re.IGNORECASE)


def parse_volume_name(filename: str) -> Optional[VolumeName]:
    """Parse a (already uncloaked) file name as a multipart volume, or None."""
    name = os.path.basename(filename)

    match = _TAR_SPLIT_RE.match(name)
    if match:
        index = int(match.group(3))
        family = f"tar.{match.group(2).lower()}"
        return VolumeName(match.group(1), family, index, index == 1)

    match = _SEVEN_Z_SPLIT_RE.match(name)
    if match:
        index = int(match.group(2))
        return VolumeName(match.group(1), "7z", index, index == 1)

    match = _NUMBERED_SPLIT_RE.match(name)
    if match:
        index = int(match.group(3))
        return VolumeName(match.group(1), match.group(2).lower(), index, index == 1)

    match = _RAR_PART_RE.match(name)
    if match:
        index = int(match.group(2))
        return VolumeName(match.group(1), "rar-part", index, index == 1)

    for pattern, family, offset in _CONTINUATION_PATTERNS:
        match = pattern.match(name)
        if match:
            return VolumeName(
                match.group(1), family, int(match.group(2)) + offset, False
            )

    stem, ext = os.path.splitext(name)
    primary_family = _AMBIGUOUS_PRIMARY_FAMILIES.get(ext[1:].lower())
    if primary_family and stem:
        return VolumeName(stem, primary_family, 1, True, ambiguous=True)
    return None


@dataclass(frozen=True)
class Candidate:
    """A pool file that can take part in a multipart combination."""

    path: str
    volume: VolumeName
    size: int

    @classmethod
    def from_path(
        cls, path: str, volume: Optional[VolumeName] = None
    ) -> Optional["Candidate"]:
        parsed = volume or parse_volume_name(path)
        if parsed is None:
            return None
        try:
            size = os.path.getsize(path)
        except OSError:
            return None
        return cls(os.path.abspath(path), parsed, size)


def _norm(path: str) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(path)))


def _is_within(path: str, folder: str) -> bool:
    path_n, folder_n = _norm(path), _norm(folder)
    prefix = folder_n if folder_n.endswith(os.sep) else folder_n + os.sep
    return path_n == folder_n or path_n.startswith(prefix)


@dataclass(frozen=True)
class Scope:
    """A folder searched for volumes, either alone or with its whole subtree."""

    folder: str
    recursive: bool

    def contains(self, path: str) -> bool:
        parent = os.path.dirname(os.path.abspath(path))
        if self.recursive:
            return _is_within(parent, self.folder)
        return _norm(parent) == _norm(self.folder)


def scopes_for(primary_path: str, root: str) -> list[Scope]:
    """Return the widening scopes for a primary, ending at the input root.

    Order: the primary's folder, that folder's subtree, then each ancestor's
    subtree up to and including `root`. Nothing above `root` is searched.
    """
    folder = os.path.dirname(os.path.abspath(primary_path))
    root_abs = os.path.abspath(root)
    if not _is_within(folder, root_abs):
        raise ValueError(f"{primary_path} is outside the input root {root}")
    scopes = [Scope(folder, False), Scope(folder, True)]
    current = folder
    while _norm(current) != _norm(root_abs):
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
        scopes.append(Scope(current, True))
    return scopes


def _folder_distance(from_dir: str, to_dir: str) -> int:
    a = _norm(from_dir).split(os.sep)
    b = _norm(to_dir).split(os.sep)
    common = 0
    for left, right in zip(a, b):
        if left != right:
            break
        common += 1
    return (len(a) - common) + (len(b) - common)


def _sizes_consistent(combo: Sequence[Candidate]) -> bool:
    if len(combo) < 2:
        return True
    head = combo[0].size
    return all(c.size == head for c in combo[:-1]) and combo[-1].size <= head


def _ordered_products(
    primary: Candidate, per_index: list[list[Candidate]]
) -> Iterator[tuple[Candidate, ...]]:
    primary_dir = os.path.dirname(primary.path)

    def distance(candidate: Candidate) -> int:
        return _folder_distance(primary_dir, os.path.dirname(candidate.path))

    ordered = [
        sorted(candidates, key=lambda c: (distance(c), c.path))
        for candidates in per_index
    ]
    total = 1
    for candidates in ordered:
        total *= len(candidates)
    products = ((primary,) + rest for rest in itertools.product(*ordered))
    if total > _FULL_SORT_LIMIT:
        yield from products
        return

    def rank(combo: tuple[Candidate, ...]) -> tuple[int, int, tuple[str, ...]]:
        size_penalty = 0 if _sizes_consistent(combo) else 1
        return (
            sum(distance(c) for c in combo[1:]),
            size_penalty,
            tuple(c.path for c in combo),
        )

    yield from sorted(products, key=rank)


def iter_combinations(
    primary: Candidate, candidates: Sequence[Candidate], root: str
) -> Iterator[tuple[Scope, tuple[Candidate, ...]]]:
    """Yield volume combinations for `primary`, narrowest scope first.

    Only `candidates` (pool items) are considered. A combination already
    yielded by a narrower scope is not repeated. Within a scope, the full run
    of indices comes first; shorter prefixes follow only for a 7z split whose
    header records the total size. Otherwise a scope whose volume indices
    have a gap cannot succeed and is skipped.
    """
    seen: set[tuple[str, ...]] = set()
    prefixes_checkable = (
        primary.volume.family == "7z" and read_7z_total_size(primary.path) is not None
    )
    for scope in scopes_for(primary.path, root):
        by_index: dict[int, list[Candidate]] = {}
        for candidate in candidates:
            if candidate.volume.key != primary.volume.key:
                continue
            if candidate.volume.index == 1 or candidate.path == primary.path:
                continue
            if scope.contains(candidate.path):
                by_index.setdefault(candidate.volume.index, []).append(candidate)
        last = 1
        while last + 1 in by_index:
            last += 1
        # A gap means the full run cannot be the set, unless a later index
        # belongs to another set; only a checkable 7z prefix can tell.
        if not prefixes_checkable and any(index > last for index in by_index):
            continue
        if last == 1 and primary.volume.ambiguous:
            continue
        # Longest first. A later index may belong to another set that shares
        # the name, so a shorter prefix can still be the whole set; only a 7z
        # start header (its recorded total size) can tell, via the prefilter.
        shortest = 2 if last > 1 and prefixes_checkable else last
        for end in range(last, shortest - 1, -1):
            per_index = [by_index[index] for index in range(2, end + 1)]
            for combo in _ordered_products(primary, per_index):
                identity = tuple(c.path for c in combo)
                if identity in seen:
                    continue
                seen.add(identity)
                yield scope, combo


def prefilter(combo: Sequence[Candidate]) -> Optional[str]:
    """Return why a combination cannot be a valid set, or None to probe it."""
    first = combo[0]
    if not first.volume.is_numbered_split:
        return None
    if not _sizes_consistent(combo):
        return "inconsistent volume sizes"
    if first.volume.family == "7z":
        total = read_7z_total_size(first.path)
        if total is not None and total != sum(c.size for c in combo):
            return "volume sizes do not add up to the 7z header size"
    return None


def _content_hash(path: str, cache: dict[str, str]) -> str:
    if path not in cache:
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        cache[path] = digest.hexdigest()
    return cache[path]


def find_duplicates(
    consumed: Sequence[Candidate], leftovers: Sequence[Candidate]
) -> list[Candidate]:
    """Return leftovers that are byte-identical copies of a consumed volume."""
    cache: dict[str, str] = {}
    duplicates = []
    for leftover in leftovers:
        for used in consumed:
            if (
                leftover.path != used.path
                and leftover.volume.key == used.volume.key
                and leftover.volume.index == used.volume.index
                and leftover.size == used.size
                and _content_hash(leftover.path, cache)
                == _content_hash(used.path, cache)
            ):
                duplicates.append(leftover)
                break
    return duplicates
