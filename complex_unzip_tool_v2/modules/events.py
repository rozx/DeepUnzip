"""
Typed events of an extraction run.
解压运行过程中的类型化事件。

The work pool, the 7-Zip engine and the CLI emit these; exactly one renderer
(terminal tree, plain lines or JSON lines) turns them into output. Library
code that has something to tell the user, but no direct emit callback, uses
`notice()`, which goes to the sink installed by the CLI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Optional, Union

if TYPE_CHECKING:
    from complex_unzip_tool_v2.modules.work_pool import PoolResult, WorkItem


@dataclass(frozen=True)
class RunStarted:
    version: str
    roots: tuple[str, ...]


@dataclass(frozen=True)
class RootStarted:
    index: int
    root: str


@dataclass(frozen=True)
class RoundStarted:
    number: int
    # Archives (containers and sets) finished so far, and still pending.
    done: int = 0
    pending: int = 0


@dataclass(frozen=True)
class ItemStarted:
    """A container is about to be opened, or a set to be assembled."""

    item: "WorkItem"


@dataclass(frozen=True)
class ItemOpened:
    item: "WorkItem"
    files: int


@dataclass(frozen=True)
class SetAssembled:
    primary: "WorkItem"
    volumes: tuple["WorkItem", ...]
    files: int


@dataclass(frozen=True)
class ItemUnresolved:
    """Live notice; an item may still be promoted later (renderers report the
    final unresolved items from RootFinished)."""

    item: "WorkItem"


@dataclass(frozen=True)
class Progress:
    path: str
    percent: int
    bytes_done: Optional[int] = None
    bytes_total: Optional[int] = None


@dataclass(frozen=True)
class PromptNeeded:
    """An interactive prompt is about to read stdin."""

    path: str


@dataclass(frozen=True)
class Notice:
    """A message from library code: `level` is info or warning; `key` is a
    message-catalog key formatted with `params`."""

    level: str
    key: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RootFinished:
    result: "PoolResult"


@dataclass(frozen=True)
class RunFailed:
    """A fatal error; `code` is machine-readable, `detail` is shown to users."""

    code: str
    detail: str


@dataclass(frozen=True)
class RunFinished:
    results: tuple["PoolResult", ...]
    exit_code: int
    elapsed: float


Event = Union[
    RunStarted,
    RootStarted,
    RoundStarted,
    ItemStarted,
    ItemOpened,
    SetAssembled,
    ItemUnresolved,
    Progress,
    PromptNeeded,
    Notice,
    RootFinished,
    RunFailed,
    RunFinished,
]

_sink: Optional[Callable[[Event], None]] = None


def set_sink(sink: Optional[Callable[[Event], None]]) -> None:
    """Install (or remove, with None) the receiver of `emit` / `notice`."""
    global _sink
    _sink = sink


def emit(event: Event) -> None:
    if _sink is not None:
        _sink(event)


def notice(level: str, key: str, **params: Any) -> None:
    emit(Notice(level, key, params))
