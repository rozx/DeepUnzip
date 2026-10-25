"""
Work pool: round-based extraction of one input root.
工作池：按轮次解压一个输入根目录。

Every file, whether scanned from the input root or extracted at any depth,
becomes a WorkItem in one pool and goes through the same cycle: uncloak →
classify → group → extract. Containers are opened one level per round;
multipart sets are assembled from the whole pool by widening scope once no
container is pending; sources are deleted only at the end, based on lineage.
See openspec/changes/redesign-work-pool-extraction/design.md.

7-Zip access, prompting, uncloaking, deletion and output go through injected
callables so the whole loop can be tested without real archives.
"""

import os
import re
import shutil
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional, Protocol, Sequence, Union

from complex_unzip_tool_v2.modules import multipart_assembly as ma
from complex_unzip_tool_v2.modules.const import OUTPUT_FOLDER
from complex_unzip_tool_v2.modules.file_utils import normalize_output_relative_path
from complex_unzip_tool_v2.modules.utils import sanitize_filename

WORK_DIR_PREFIX = "temp.deepunzip-"
ASSEMBLY_DIR_NAME = ".assemble"
DEFAULT_MAX_DEPTH = 10


class Origin(Enum):
    SOURCE = "source"
    DERIVED = "derived"


class Kind(Enum):
    CONTAINER = "container"
    VOLUME = "volume"
    REGULAR = "regular"


class State(Enum):
    PENDING = "pending"
    CONSUMED = "consumed"
    FINAL = "final"
    KEPT = "kept"
    UNRESOLVED = "unresolved"


# 0 = empty password, N = 1-based password-book index, "entered" = typed by
# the user, None = not encrypted. Raw passwords never leave the engine/pool.
PasswordRef = Union[int, str, None]


@dataclass(frozen=True)
class Outcome:
    """Result of an engine call. `status` is one of ok, password,
    missing_volume, unsupported or failed."""

    status: str
    password: Optional[str] = None
    password_ref: PasswordRef = None
    detail: str = ""
    # Volumes 7-Zip actually used, when it reports them (probe only).
    volumes: Optional[int] = None

    @property
    def ok(self) -> bool:
        return self.status == "ok"


class Engine(Protocol):
    def classify(self, path: str) -> str:
        """Return "container", "regular" or "broken"."""

    def extract(
        self, archive: str, dest: str, password: Optional[str] = None
    ) -> Outcome:
        """Extract one level. Without `password`, try the password book."""

    def probe(self, archive: str, password: Optional[str] = None) -> Outcome:
        """List headers only. Without `password`, try the password book."""

    def remember(self, password: str) -> None:
        """Add a user-entered password to the password book."""


class RelocationLog(Protocol):
    def record(self, original: str, renamed: str) -> None:
        ...

    def clear(self, renamed: str) -> None:
        ...


class MemoryRelocationLog:
    """In-memory relocation log (the real one is persisted with RenameHistory)."""

    def __init__(self) -> None:
        self.entries: dict[str, str] = {}
        self.recorded: list[tuple[str, str]] = []

    def record(self, original: str, renamed: str) -> None:
        self.entries[renamed] = original
        self.recorded.append((original, renamed))

    def clear(self, renamed: str) -> None:
        self.entries.pop(renamed, None)


class _SkipAll:
    def __repr__(self) -> str:
        return "SKIP_ALL"


# Returned by a prompt to skip every further password prompt in the run.
SKIP_ALL = _SkipAll()
PromptAnswer = Union[str, None, _SkipAll]


@dataclass(eq=False)
class WorkItem:
    id: int
    path: str
    origin: Origin
    lineage: frozenset[int]
    depth: int
    # Folder that output paths of this item are computed relative to.
    rel_base: str
    kind: Kind = Kind.REGULAR
    state: State = State.PENDING
    reason: str = ""
    volume: Optional[ma.VolumeName] = None
    original_name: Optional[str] = None
    parents: tuple[int, ...] = ()
    password_ref: PasswordRef = None
    output_path: Optional[str] = None
    # A consumed derived archive that could not be removed is kept as output.
    keep_in_output: bool = False
    tried_as_container: bool = False

    @property
    def is_source(self) -> bool:
        return self.origin is Origin.SOURCE

    @property
    def name(self) -> str:
        return os.path.basename(self.path)


# ------------------------------
# Events (rendered by the terminal output; see redesign-terminal-output)
# ------------------------------


@dataclass(frozen=True)
class RoundStarted:
    number: int


@dataclass(frozen=True)
class ItemOpened:
    item: WorkItem
    files: int


@dataclass(frozen=True)
class SetAssembled:
    primary: WorkItem
    volumes: tuple[WorkItem, ...]
    files: int


@dataclass(frozen=True)
class ItemUnresolved:
    item: WorkItem


@dataclass
class PoolResult:
    root: str
    items: list[WorkItem]
    output_dir: str
    work_dir: str
    work_dir_kept: bool
    deleted_sources: list[str] = field(default_factory=list)
    kept_sources: list[str] = field(default_factory=list)

    @property
    def unresolved(self) -> list[WorkItem]:
        return [i for i in self.items if i.state is State.UNRESOLVED]

    @property
    def output_files(self) -> list[str]:
        return [i.output_path for i in self.items if i.output_path]

    def item(self, item_id: int) -> WorkItem:
        return next(i for i in self.items if i.id == item_id)


@dataclass(frozen=True)
class RootFinished:
    result: PoolResult


Event = Union[RoundStarted, ItemOpened, SetAssembled, ItemUnresolved, RootFinished]


@dataclass
class _SetState:
    version: int = -1
    probes: int = 0
    password_failures: int = 0
    other_failures: int = 0
    last_status: str = ""
    prompted: bool = False


# ------------------------------
# Helpers
# ------------------------------

_ARCHIVE_SUFFIXES = (
    ".zip",
    ".zipx",
    ".7z",
    ".rar",
    ".tar",
    ".gz",
    ".bz2",
    ".xz",
    ".iso",
    ".img",
    ".bin",
    ".cab",
    ".ace",
    ".arj",
    ".lzh",
    ".lha",
)


def derive_folder_name(filename: str) -> str:
    """Folder name for an archive's contents: the name without archive suffixes."""
    name = filename
    while True:
        stem, ext = os.path.splitext(name)
        ext_low = ext.lower()
        if not ext_low:
            break
        if len(ext_low) == 4 and ext_low[1:].isdigit():
            name = stem
        elif re.fullmatch(r"\.(?:zx|[zrac])[0-9]{2}", ext_low):
            name = stem
        elif ext_low.startswith(".part") and ext_low[5:].isdigit():
            name = stem
        elif ext_low in _ARCHIVE_SUFFIXES:
            name = stem
        else:
            break
    return sanitize_filename(name) or "archive"


def _unique_dir(base: str) -> str:
    candidate, counter = base, 2
    while os.path.exists(candidate):
        candidate = f"{base}_{counter}"
        counter += 1
    os.makedirs(candidate)
    return candidate


def _list_files(folder: str) -> list[str]:
    found = []
    for current, _dirs, names in os.walk(folder):
        for name in names:
            found.append(os.path.join(current, name))
    return sorted(found)


def _norm(path: str) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(path)))


def group_input_roots(paths: Sequence[str]) -> list[tuple[str, list[str]]]:
    """Map CLI paths to input roots (a folder, or a file's folder).

    A root nested inside another root is merged into the outer one. Roots
    keep the order in which they first appear.
    """
    roots = []
    for path in paths:
        absolute = os.path.abspath(path)
        root = absolute if os.path.isdir(absolute) else os.path.dirname(absolute)
        roots.append((path, root))

    def outermost(root: str) -> str:
        best = root
        for _path, other in roots:
            other_n, best_n = _norm(other), _norm(best)
            if other_n != best_n and best_n.startswith(other_n.rstrip(os.sep) + os.sep):
                best = other
        return best

    grouped: dict[str, tuple[str, list[str]]] = {}
    for path, root in roots:
        outer = outermost(root)
        grouped.setdefault(_norm(outer), (outer, []))[1].append(path)
    return list(grouped.values())


def _default_remove(path: str) -> bool:
    try:
        os.remove(path)
        return True
    except OSError:
        return False


# ------------------------------
# The pool
# ------------------------------


class WorkPool:
    """Extract every source of one input root (see module docstring)."""

    def __init__(
        self,
        root: str,
        sources: Sequence[str],
        engine: Engine,
        *,
        output_dir: Optional[str] = None,
        max_depth: int = DEFAULT_MAX_DEPTH,
        max_attempts: int = ma.MAX_ASSEMBLY_ATTEMPTS,
        prompt: Optional[Callable[[str], PromptAnswer]] = None,
        uncloak: Optional[Callable[[str, bool], str]] = None,
        remove: Optional[Callable[[str], bool]] = None,
        relocations: Optional[RelocationLog] = None,
        mover: Optional[Callable[[str, str], object]] = None,
        emit: Optional[Callable[[Event], None]] = None,
        run_id: Optional[str] = None,
    ) -> None:
        self.root = os.path.abspath(root)
        self.sources = [os.path.abspath(s) for s in sources]
        self.engine = engine
        self.output_dir = output_dir or os.path.join(self.root, OUTPUT_FOLDER)
        self.work_dir = os.path.join(
            self.root, WORK_DIR_PREFIX + (run_id or uuid.uuid4().hex[:8])
        )
        self.max_depth = max_depth
        self.max_attempts = max_attempts
        self.prompt = prompt
        self.uncloak = uncloak or (lambda path, _is_source: path)
        self.remove = remove or _default_remove
        self.relocations: RelocationLog = relocations or MemoryRelocationLog()
        self.mover = mover or shutil.move
        self.emit = emit or (lambda _event: None)

        self.items: list[WorkItem] = []
        self._next_id = 1
        self._key_versions: dict[tuple[str, str], int] = {}
        self._sets: dict[int, _SetState] = {}
        self._skip_all = False
        self._assembly_count = 0

    # ---------- driver ----------

    def run(self) -> PoolResult:
        os.makedirs(self.work_dir, exist_ok=True)
        for path in sorted(self.sources):
            if os.path.isfile(path):
                self._add(path, Origin.SOURCE, (), 0, self.work_dir)

        round_number = 0
        while True:
            round_number += 1
            self.emit(RoundStarted(round_number))
            containers = self._pending(Kind.CONTAINER)
            if containers:
                for item in sorted(containers, key=lambda i: i.path):
                    if item.kind is Kind.CONTAINER and item.state is State.PENDING:
                        self._open_container(item)
                continue
            if self._assemble_ready_sets():
                continue
            if self._prompt_deferred_sets():
                continue
            if self._fall_back_to_containers():
                continue
            break

        self._fail_remaining()
        work_dir_kept = self._finalize()
        result = PoolResult(
            self.root, self.items, self.output_dir, self.work_dir, work_dir_kept
        )
        self._cleanup_sources(result)
        self.emit(RootFinished(result))
        return result

    def _pending(self, kind: Kind) -> list[WorkItem]:
        return [i for i in self.items if i.kind is kind and i.state is State.PENDING]

    # ---------- intake ----------

    def _add(
        self,
        path: str,
        origin: Origin,
        parents: tuple[int, ...],
        depth: int,
        rel_base: str,
    ) -> WorkItem:
        original_name = os.path.basename(path)
        new_path = self.uncloak(path, origin is Origin.SOURCE)
        item_id = self._next_id
        self._next_id += 1
        if origin is Origin.SOURCE:
            lineage = frozenset({item_id})
        else:
            lineage = frozenset().union(*(self._get(p).lineage for p in parents))
        item = WorkItem(
            id=item_id,
            path=new_path,
            origin=origin,
            lineage=lineage,
            depth=depth,
            rel_base=rel_base,
            parents=parents,
            original_name=(
                original_name if os.path.basename(new_path) != original_name else None
            ),
        )
        self.items.append(item)
        self._classify(item)
        return item

    def _classify(self, item: WorkItem) -> None:
        parsed = ma.parse_volume_name(item.path)
        item.volume = parsed
        if parsed is not None and (
            not parsed.ambiguous or self._has_pending_continuation(parsed.key)
        ):
            item.kind = Kind.VOLUME
            self._bump(parsed.key)
            if not parsed.is_primary:
                self._promote_ambiguous(parsed.key)
            return
        verdict = self.engine.classify(item.path)
        if verdict == "container":
            item.kind = Kind.CONTAINER
        elif verdict == "broken" and item.is_source:
            item.kind = Kind.REGULAR
            self._unresolve(item, "not a valid archive")
        else:
            item.kind = Kind.REGULAR
            item.state = State.KEPT if item.is_source else State.FINAL

    def _has_pending_continuation(self, key: tuple[str, str]) -> bool:
        return any(
            i.kind is Kind.VOLUME
            and i.state is State.PENDING
            and i.volume is not None
            and i.volume.key == key
            and not i.volume.is_primary
            for i in self.items
        )

    def _promote_ambiguous(self, key: tuple[str, str]) -> None:
        """A continuation arrived: matching ambiguous primaries become set primaries."""
        for item in self.items:
            if (
                item.volume is not None
                and item.volume.ambiguous
                and item.volume.key == key
                and item.kind is Kind.CONTAINER
                and item.state in (State.PENDING, State.UNRESOLVED)
            ):
                item.kind = Kind.VOLUME
                item.state = State.PENDING
                item.reason = ""

    def _bump(self, key: tuple[str, str]) -> None:
        self._key_versions[key] = self._key_versions.get(key, 0) + 1

    def _get(self, item_id: int) -> WorkItem:
        return next(i for i in self.items if i.id == item_id)

    def _unresolve(self, item: WorkItem, reason: str) -> None:
        item.state = State.UNRESOLVED
        item.reason = reason
        self.emit(ItemUnresolved(item))

    # ---------- containers ----------

    def _container_dest(self, item: WorkItem) -> str:
        parent = self.work_dir if item.is_source else os.path.dirname(item.path)
        return _unique_dir(os.path.join(parent, derive_folder_name(item.name)))

    def _open_container(self, item: WorkItem) -> None:
        item.tried_as_container = True
        if item.depth > self.max_depth:
            self._unresolve(item, "max depth")
            return
        dest = self._container_dest(item)

        def attempt(password: Optional[str]) -> Outcome:
            shutil.rmtree(dest, ignore_errors=True)
            os.makedirs(dest, exist_ok=True)
            return self.engine.extract(item.path, dest, password)

        outcome = self._with_prompt(item.path, attempt(None), attempt)
        if outcome.ok:
            files = _list_files(dest)
            if not files:
                shutil.rmtree(dest, ignore_errors=True)
                self._unresolve(item, "empty")
                return
            item.state = State.CONSUMED
            item.password_ref = outcome.password_ref
            rel_base = dest if item.is_source else item.rel_base
            for path in files:
                self._add(path, Origin.DERIVED, (item.id,), item.depth + 1, rel_base)
            self.emit(ItemOpened(item, len(files)))
            if not item.is_source:
                self._discard_derived(item)
            return

        shutil.rmtree(dest, ignore_errors=True)
        if outcome.status == "missing_volume" and item.volume is not None:
            item.kind = Kind.VOLUME
            self._bump(item.volume.key)
            return
        reasons = {
            "password": "password",
            "missing_volume": "missing volume",
            "unsupported": "unsupported",
        }
        self._unresolve(item, reasons.get(outcome.status, "error"))

    def _with_prompt(
        self,
        name: str,
        outcome: Outcome,
        retry: Callable[[Optional[str]], Outcome],
    ) -> Outcome:
        """Prompt for a password while the outcome is a password failure."""
        while (
            outcome.status == "password"
            and self.prompt is not None
            and not self._skip_all
        ):
            answer = self.prompt(name)
            if isinstance(answer, _SkipAll):
                self._skip_all = True
                break
            if answer is None:
                break
            outcome = retry(answer)
            if outcome.ok:
                self.engine.remember(answer)
                return Outcome("ok", answer, "entered", outcome.detail, outcome.volumes)
        return outcome

    def _discard_derived(self, item: WorkItem) -> None:
        """Clean up a consumed derived file now; keep it as output if that fails."""
        if os.path.exists(item.path) and not self.remove(item.path):
            item.keep_in_output = True

    # ---------- multipart sets ----------

    def _primaries(self) -> list[WorkItem]:
        return sorted(
            (
                i
                for i in self._pending(Kind.VOLUME)
                if i.volume is not None and i.volume.is_primary
            ),
            key=lambda i: i.path,
        )

    def _assemble_ready_sets(self) -> bool:
        attempted = False
        for primary in self._primaries():
            if primary.state is not State.PENDING or primary.volume is None:
                continue
            state = self._sets.setdefault(primary.id, _SetState())
            version = self._key_versions.get(primary.volume.key, 0)
            if state.version == version:
                continue
            state.version = version
            attempted = True
            if primary.depth > self.max_depth:
                self._unresolve(primary, "max depth")
                continue
            self._attempt_set(primary, state, None)
        return attempted

    def _attempt_set(
        self, primary: WorkItem, state: _SetState, password: Optional[str]
    ) -> bool:
        assert primary.volume is not None
        key = primary.volume.key
        members = {
            os.path.abspath(i.path): i
            for i in self._pending(Kind.VOLUME)
            if i.volume is not None and i.volume.key == key
        }
        candidates = [
            c
            for c in (ma.Candidate.from_path(p, i.volume) for p, i in members.items())
            if c is not None
        ]
        primary_candidate = ma.Candidate.from_path(primary.path, primary.volume)
        if primary_candidate is None:
            return False
        for _scope, combo in ma.iter_combinations(
            primary_candidate, candidates, self.root
        ):
            if ma.prefilter(combo) is not None:
                continue
            volumes = [members[c.path] for c in combo]
            if self._try_volumes(primary, volumes, state, password):
                return True
            if primary.state is State.UNRESOLVED:
                return False
        return False

    def _probe_budget_left(self, primary: WorkItem, state: _SetState) -> bool:
        if state.probes >= self.max_attempts:
            self._unresolve(primary, "too many combinations")
            return False
        state.probes += 1
        return True

    def _try_volumes(
        self,
        primary: WorkItem,
        volumes: list[WorkItem],
        state: _SetState,
        password: Optional[str],
    ) -> bool:
        if not self._probe_budget_left(primary, state):
            return False
        # Create the destination before any volume moves away, so it can never
        # take a path that a temporarily relocated volume must return to.
        dest = self._set_dest(primary, primary.path)
        moved = self._assemble(volumes)
        success = False
        # 7-Zip used fewer volumes than chosen: retry with only those, once this
        # attempt is fully undone (never consume a volume 7-Zip did not use).
        retry_with: Optional[list[WorkItem]] = None
        files: list[str] = []
        try:
            probe = self.engine.probe(primary.path, password)
            state.last_status = probe.status
            if not probe.ok:
                if probe.status == "password":
                    state.password_failures += 1
                elif probe.status != "missing_volume":
                    state.other_failures += 1
            elif probe.volumes is not None and probe.volumes < len(volumes):
                used = volumes[: probe.volumes]
                if len(used) == 1 and primary.volume and primary.volume.ambiguous:
                    state.other_failures += 1
                else:
                    retry_with = used
            else:
                extracted = self.engine.extract(primary.path, dest, probe.password)
                files = _list_files(dest) if extracted.ok else []
                if files:
                    success = True
                else:
                    state.other_failures += 1
                    state.last_status = (
                        extracted.status if not extracted.ok else "empty"
                    )
        finally:
            self._restore(moved, success)
            if not success:
                shutil.rmtree(dest, ignore_errors=True)
        if retry_with is not None:
            return self._try_volumes(primary, retry_with, state, password)
        if not success:
            return False

        ref = "entered" if password is not None else probe.password_ref
        for volume in volumes:
            volume.state = State.CONSUMED
            volume.password_ref = ref
        # Compare leftovers against the used volumes before those are removed.
        self._mark_duplicates(volumes)
        for volume in volumes:
            if not volume.is_source:
                self._discard_derived(volume)
        rel_base = dest if primary.is_source else primary.rel_base
        depth = max(v.depth for v in volumes) + 1
        parents = tuple(v.id for v in volumes)
        for path in files:
            self._add(path, Origin.DERIVED, parents, depth, rel_base)
        assert primary.volume is not None
        self._bump(primary.volume.key)
        self.emit(SetAssembled(primary, tuple(volumes), len(files)))
        return True

    def _set_dest(self, primary: WorkItem, home: str) -> str:
        parent = self.work_dir if primary.is_source else os.path.dirname(home)
        return _unique_dir(os.path.join(parent, derive_folder_name(primary.name)))

    def _assemble(self, volumes: list[WorkItem]) -> list[tuple[WorkItem, str]]:
        """Bring the chosen volumes together so 7-Zip sees exactly them.

        Returns the moves made, so `_restore` can undo them. When the volumes
        already share a folder with no other same-set file in it, nothing moves.
        """
        if self._in_place(volumes):
            return []
        self._assembly_count += 1
        folder = os.path.join(
            self.work_dir, ASSEMBLY_DIR_NAME, str(self._assembly_count)
        )
        os.makedirs(folder, exist_ok=True)
        moves = []
        for volume in volumes:
            original = volume.path
            target = os.path.join(folder, os.path.basename(original))
            if volume.is_source:
                self.relocations.record(original, target)
            shutil.move(original, target)
            volume.path = target
            moves.append((volume, original))
        return moves

    def _restore(self, moves: list[tuple[WorkItem, str]], success: bool) -> None:
        """Move every relocated volume back where it came from."""
        folders = set()
        for volume, original in moves:
            folders.add(os.path.dirname(volume.path))
            shutil.move(volume.path, original)
            if volume.is_source:
                self.relocations.clear(volume.path)
            volume.path = original
        for folder in folders:
            try:
                os.rmdir(folder)
            except OSError:
                pass

    def _in_place(self, volumes: list[WorkItem]) -> bool:
        folders = {_norm(os.path.dirname(v.path)) for v in volumes}
        if len(folders) != 1:
            return False
        folder = os.path.dirname(volumes[0].path)
        chosen = {_norm(v.path) for v in volumes}
        key = volumes[0].volume.key if volumes[0].volume else None
        for name in os.listdir(folder):
            parsed = ma.parse_volume_name(name)
            if (
                parsed is not None
                and parsed.key == key
                and _norm(os.path.join(folder, name)) not in chosen
            ):
                return False
        return True

    def _mark_duplicates(self, consumed: list[WorkItem]) -> None:
        key = consumed[0].volume.key if consumed[0].volume else None
        leftovers = {
            os.path.abspath(i.path): i
            for i in self._pending(Kind.VOLUME)
            if i.volume is not None and i.volume.key == key and not i.volume.is_primary
        }
        used = [
            c
            for c in (ma.Candidate.from_path(v.path, v.volume) for v in consumed)
            if c is not None
        ]
        rest = [
            c
            for c in (ma.Candidate.from_path(p, i.volume) for p, i in leftovers.items())
            if c is not None
        ]
        for duplicate in ma.find_duplicates(used, rest):
            item = leftovers[duplicate.path]
            item.state = State.CONSUMED
            item.reason = "duplicate"
            if not item.is_source:
                self._discard_derived(item)

    # ---------- quiescence ----------

    def _prompt_deferred_sets(self) -> bool:
        if self.prompt is None or self._skip_all:
            return False
        for primary in self._primaries():
            state = self._sets.get(primary.id)
            if state is None or state.prompted:
                continue
            if state.password_failures == 0 or state.other_failures:
                continue
            state.prompted = True
            answer = self.prompt(primary.path)
            if isinstance(answer, _SkipAll):
                self._skip_all = True
                return False
            if answer is None:
                continue
            if self._attempt_set(primary, state, answer):
                self.engine.remember(answer)
                return True
        return False

    def _fall_back_to_containers(self) -> bool:
        """Open ambiguous primaries whose set failed as single containers."""
        fell_back = False
        for primary in self._primaries():
            if (
                primary.volume is not None
                and primary.volume.ambiguous
                and not primary.tried_as_container
            ):
                primary.kind = Kind.CONTAINER
                fell_back = True
        return fell_back

    def _fail_remaining(self) -> None:
        for item in self.items:
            if item.state is not State.PENDING:
                continue
            if item.kind is not Kind.VOLUME or item.volume is None:
                self._unresolve(item, "error")
                continue
            if not item.volume.is_primary:
                self._unresolve(item, "unmatched volume")
                continue
            state = self._sets.get(item.id)
            if state is None or state.probes == 0:
                self._unresolve(item, "missing volume")
            elif state.password_failures and not state.other_failures:
                self._unresolve(item, "password")
            elif state.last_status == "missing_volume":
                self._unresolve(item, "missing volume")
            else:
                self._unresolve(item, "assembly failed")

    # ---------- finalization ----------

    def _output_relpath(self, item: WorkItem) -> str:
        if item.kind is Kind.VOLUME and item.state is State.UNRESOLVED and item.volume:
            primary = next(
                (
                    p
                    for p in self.items
                    if p.volume is not None
                    and p.volume.key == item.volume.key
                    and p.volume.is_primary
                    and p.state is State.UNRESOLVED
                ),
                None,
            )
            if primary is not None:
                folder = (
                    ""
                    if primary.is_source
                    else os.path.relpath(
                        os.path.dirname(primary.path), primary.rel_base
                    )
                )
                return normalize_output_relative_path(os.path.join(folder, item.name))
        return normalize_output_relative_path(os.path.relpath(item.path, item.rel_base))

    def _move_to_output(self, item: WorkItem) -> bool:
        destination = os.path.join(self.output_dir, self._output_relpath(item))
        stem, ext = os.path.splitext(destination)
        counter = 1
        while os.path.exists(destination):
            destination = f"{stem}_{counter}{ext}"
            counter += 1
        try:
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            self.mover(item.path, destination)
        except OSError:
            return False
        item.output_path = destination
        return True

    def _finalize(self) -> bool:
        """Move outputs and unresolved derived items out; True if work dir kept."""
        failed = False
        for item in self.items:
            if item.is_source or not os.path.exists(item.path):
                continue
            wanted = (
                item.state in (State.FINAL, State.UNRESOLVED) or item.keep_in_output
            )
            if wanted and not self._move_to_output(item):
                failed = True
                self._unresolve(item, "move failed")
        if failed:
            return True
        shutil.rmtree(self.work_dir, ignore_errors=True)
        return False

    def _cleanup_sources(self, result: PoolResult) -> None:
        for source in (i for i in self.items if i.is_source):
            if source.state is State.KEPT:
                continue
            descendants = [
                i for i in self.items if source.id in i.lineage and i is not source
            ]
            deletable = (
                source.state is State.CONSUMED
                and bool(descendants)
                and all(d.state is not State.UNRESOLVED for d in descendants)
            )
            if deletable and self.remove(source.path):
                result.deleted_sources.append(source.path)
                self._remove_empty_parents(os.path.dirname(source.path))
            else:
                result.kept_sources.append(source.path)

    def _remove_empty_parents(self, folder: str) -> None:
        protected = {_norm(self.root), _norm(self.output_dir), _norm(self.work_dir)}
        current = folder
        while _norm(current) not in protected and _norm(current).startswith(
            _norm(self.root)
        ):
            try:
                os.rmdir(current)
            except OSError:
                return
            current = os.path.dirname(current)
