"""
Renderers: run events → terminal view, plain lines or JSON lines.
渲染器：把运行事件变成终端界面、纯文本行或 JSON 行。

Exactly one renderer is active per run (see openspec/changes/
redesign-terminal-output/design.md):

- TreeRenderer: stdout is a terminal. Item lines scroll above two live
  progress lines; when a root finishes, the live lines go and a lineage tree
  plus a summary are printed.
- PlainRenderer: stdout is redirected. Same lines, tree and summary, without
  live rendering.
- JsonRenderer: --json. One JSON object per line, no human text.

File names are always printed as rich.text.Text, never as markup, so names
like "[group] title.rar" survive. Passwords are never part of any event.
"""

import json
import os
import platform
import sys
import time
from typing import IO, Any, Callable, Optional, Union

from rich.cells import cell_len
from rich.console import Console
from rich.live import Live
from rich.progress_bar import ProgressBar
from rich.table import Table
from rich.text import Text

from deepunzip.modules import events as ev
from deepunzip.modules.const import OUTPUT_FOLDER
from deepunzip.modules.i18n import CATALOG, t
from deepunzip.modules.work_pool import (
    PasswordRef,
    PoolResult,
    State,
    WorkItem,
)

SCHEMA_VERSION = 1
ITEM_LINE_LIMIT = 200
TREE_CHILD_LIMIT = 50
PROGRESS_INTERVAL = 0.2
NAME_WIDTH = 48
_SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
_FAMILY_EXTENSION = {
    "rar-part": "rar",
    "rar-vol": "rar",
    "zip-span": "zip",
    "zipx-span": "zipx",
    "arj-vol": "arj",
    "ace-vol": "ace",
}


def configure_redirected_output() -> None:
    """Keep Windows pipes/logs Unicode-safe before the first output."""
    if platform.system() == "Windows":
        for stream in (sys.stdout, sys.stderr):
            reconfigure = getattr(stream, "reconfigure", None)
            if callable(reconfigure) and not stream.isatty():
                reconfigure(encoding="utf-8", errors="backslashreplace")


configure_redirected_output()


# ------------------------------
# Formatting helpers
# ------------------------------


def format_elapsed(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, rest = divmod(int(seconds), 60)
    return f"{minutes}m {rest}s"


def _unit(total: float) -> tuple[str, float]:
    for name, size in (("GB", 1e9), ("MB", 1e6), ("KB", 1e3)):
        if total >= size:
            return name, size
    return "B", 1.0


def format_bytes(value: float) -> str:
    name, size = _unit(value)
    return f"{value / size:.1f} {name}"


def format_byte_pair(done: float, total: float) -> str:
    """ "1.2/2.9 GB": both numbers in the unit of the total."""
    name, size = _unit(total)
    return f"{done / size:.1f}/{total / size:.1f} {name}"


def shorten(name: str, width: int = NAME_WIDTH) -> str:
    """Truncate in the middle by display width, keeping the extension."""
    if cell_len(name) <= width:
        return name
    tail = name[-12:]
    budget = width - 1 - cell_len(tail)
    head = ""
    for char in name:
        if cell_len(head + char) > budget:
            break
        head += char
    return f"{head}…{tail}"


def password_text(ref: PasswordRef) -> str:
    if ref == "entered":
        return t("password.entered")
    if isinstance(ref, int) and ref > 0:
        return t("password.index", index=ref)
    return ""


def reason_text(reason: str) -> str:
    key = f"reason.{reason}"
    return t(key) if key in CATALOG else reason


def set_name(primary: WorkItem) -> str:
    volume = primary.volume
    if volume is None:
        return primary.name
    return f"{volume.base}.{_FAMILY_EXTENSION.get(volume.family, volume.family)}"


def volume_label(item: WorkItem) -> str:
    base = item.volume.base if item.volume else ""
    return item.name[len(base) :] if base and item.name.startswith(base) else item.name


def _find(result: PoolResult, item_id: int) -> Optional[WorkItem]:
    return next((i for i in result.items if i.id == item_id), None)


# ------------------------------
# Event dispatch
# ------------------------------


def _silence_stdout(stream: Any) -> None:
    """Point a closed stdout at the null device so the exit flush cannot fail."""
    try:
        if stream is sys.stdout:
            os.dup2(os.open(os.devnull, os.O_WRONLY), stream.fileno())
    except (AttributeError, OSError, ValueError):
        pass


class _Dispatcher:
    """Calls `_on_<EventName>` for each event.

    Output must never stop the run: when a write fails because the reader is
    gone (`deepunzip … | head`: BrokenPipeError, or EINVAL on a Windows pipe),
    the renderer goes quiet and the extraction finishes normally.
    """

    _output_closed = False

    def __call__(self, event: ev.Event) -> None:
        if self._output_closed:
            return
        handler: Optional[Callable[[Any], None]] = getattr(
            self, f"_on_{type(event).__name__}", None
        )
        if handler is None:
            return
        try:
            handler(event)
        except OSError:
            self._close_output()

    def close(self) -> None:
        pass

    def _close_output(self) -> None:
        self._output_closed = True


class _Console(Console):
    """Rich exits the program on a broken pipe; report it to the renderer instead."""

    def on_broken_pipe(self) -> None:
        self.quiet = True
        raise BrokenPipeError


# ------------------------------
# Human renderers
# ------------------------------


class HumanRenderer(_Dispatcher):
    """Item lines, the final lineage tree and the summary."""

    def __init__(self, console: Console, recycle_bin: bool = True) -> None:
        self.console = console
        self.recycle_bin = recycle_bin
        self._root_started = time.monotonic()
        self._lines = 0
        self._overflow = 0
        self._sets: list[ev.SetAssembled] = []

    def _close_output(self) -> None:
        super()._close_output()
        self.console.quiet = True
        _silence_stdout(self.console.file)

    # ---------- output ----------

    def _print(self, text: Text) -> None:
        self.console.print(text, soft_wrap=True)

    def _line(self, symbol: str, style: str, text: str, count: bool = True) -> None:
        if count:
            if self._lines >= ITEM_LINE_LIMIT:
                self._overflow += 1
                return
            self._lines += 1
        self._print(Text.assemble((f"  {symbol} ", style), text))

    # ---------- events ----------

    def _on_RunStarted(self, event: ev.RunStarted) -> None:
        title = t("version", product=t("product"), version=event.version)
        self._print(Text(title, style="bold"))

    def _on_RootStarted(self, event: ev.RootStarted) -> None:
        self._root_started = time.monotonic()
        self._lines = self._overflow = 0
        self._sets = []
        self._print(Text(event.root, style="cyan"))

    def _on_ItemOpened(self, event: ev.ItemOpened) -> None:
        item = event.item
        self._line(
            "✓",
            "green",
            t(
                "line.opened",
                name=shorten(item.name),
                files=event.files,
                password=password_text(item.password_ref),
            ),
        )

    def _on_SetAssembled(self, event: ev.SetAssembled) -> None:
        self._sets.append(event)
        self._line(
            "✓",
            "green",
            t(
                "line.assembled",
                name=shorten(event.primary.name),
                volumes=len(event.volumes),
                files=event.files,
                password=password_text(event.primary.password_ref),
            ),
        )

    def _on_Notice(self, event: ev.Notice) -> None:
        symbol, style = ("⚠", "yellow") if event.level == "warning" else ("•", "blue")
        self._line(symbol, style, t(event.key, **event.params), count=False)

    def _on_RunFailed(self, event: ev.RunFailed) -> None:
        self._print(Text.assemble(("✗ ", "red"), (event.detail, "red")))

    def _on_RunFinished(self, event: ev.RunFinished) -> None:
        style = {0: "green", 1: "yellow"}.get(event.exit_code, "red")
        text = t(
            "summary.done", elapsed=format_elapsed(event.elapsed), code=event.exit_code
        )
        self._print(Text(text, style=style))

    def _on_RootFinished(self, event: ev.RootFinished) -> None:
        result = event.result
        for item in result.items:
            if item.is_source and item.state is State.KEPT:
                self._line("•", "dim", t("line.kept", name=shorten(item.name)))
        for item in result.unresolved:
            self._line(
                "⚠",
                "yellow",
                t(
                    "line.unresolved",
                    name=shorten(item.name),
                    reason=reason_text(item.reason),
                ),
            )
        if self._overflow:
            self._line("…", "dim", t("line.more", count=self._overflow), count=False)
        self._print_tree(result)

    # ---------- lineage tree ----------

    def _print_tree(self, result: PoolResult) -> None:
        sources = [i for i in result.items if i.is_source and i.state is not State.KEPT]
        ok = not result.unresolved
        header = t(
            "tree.root",
            root=result.root,
            sources=len(sources),
            files=len(result.output_files),
            elapsed=format_elapsed(time.monotonic() - self._root_started),
        )
        self._print(Text("", end=""))
        self._print(
            Text.assemble(
                ("✓ " if ok else "⚠ ", "green" if ok else "yellow"), (header, "bold")
            )
        )
        for assembled in self._sets[:TREE_CHILD_LIMIT]:
            self._print_set(result, assembled)
        if len(self._sets) > TREE_CHILD_LIMIT:
            more = len(self._sets) - TREE_CHILD_LIMIT
            self._print(Text(f"  {t('line.more', count=more)}", style="dim"))
        for item in result.unresolved[:TREE_CHILD_LIMIT]:
            if item.output_path:
                relative = os.path.relpath(item.output_path, result.output_dir)
                location = os.path.join(OUTPUT_FOLDER, relative).replace(os.sep, "/")
            else:
                location = t("tree.in_place")
            text = t(
                "tree.unresolved",
                name=shorten(item.name),
                reason=reason_text(item.reason),
                location=location,
            )
            self._print(Text.assemble(("  ⚠ ", "yellow"), text))
        if len(result.unresolved) > TREE_CHILD_LIMIT:
            more = len(result.unresolved) - TREE_CHILD_LIMIT
            self._print(Text(f"  {t('line.more', count=more)}", style="dim"))
        self._print_summary(result)

    def _print_set(self, result: PoolResult, assembled: ev.SetAssembled) -> None:
        name = t("tree.set", name=set_name(assembled.primary), files=assembled.files)
        self._print(Text.assemble(("  ", ""), (name, "bold")))
        for position, volume in enumerate(assembled.volumes):
            branch = "└─" if position == len(assembled.volumes) - 1 else "├─"
            parent = _find(result, volume.parents[0]) if volume.parents else None
            source = (
                parent.name
                if parent is not None and not volume.is_source
                else t("tree.input")
            )
            text = t("tree.volume", volume=volume_label(volume), source=source)
            parts: list[Union[str, tuple[str, str]]] = [(f"    {branch} ", "dim"), text]
            if volume.original_name:
                parts.append(
                    (
                        f"  {t('tree.uncloaked', original=volume.original_name)}",
                        "yellow",
                    )
                )
            self._print(Text.assemble(*parts))

    def _print_summary(self, result: PoolResult) -> None:
        lines = [
            t(
                "summary.output",
                files=len(result.output_files),
                folder=result.output_dir,
            )
        ]
        if result.deleted_sources:
            key = "summary.recycled" if self.recycle_bin else "summary.deleted"
            lines.append(t(key, count=len(result.deleted_sources)))
        if result.kept_sources:
            lines.append(t("summary.kept", count=len(result.kept_sources)))
        if result.work_dir_kept:
            lines.append(t("summary.work_dir_kept", path=result.work_dir))
        for line in lines:
            self._print(Text(f"  {line}", style="dim"))


class PlainRenderer(HumanRenderer):
    """Redirected output: no live rendering, every finished item once."""


class TreeRenderer(HumanRenderer):
    """Interactive terminal: two live progress lines below the item lines."""

    def __init__(self, console: Console, recycle_bin: bool = True) -> None:
        super().__init__(console, recycle_bin)
        self._live: Optional[Live] = None
        self._round = 0
        self._done = 0
        self._pending = 0
        self._current: Optional[str] = None
        self._percent = 0
        self._bytes: tuple[Optional[int], Optional[int]] = (None, None)
        self._item_started = time.monotonic()
        self._frame = 0

    @property
    def live_active(self) -> bool:
        return self._live is not None

    def close(self) -> None:
        try:
            self._stop_live()
        except OSError:
            self._close_output()

    def _close_output(self) -> None:
        self._live = None  # nothing can be redrawn on a closed output
        super()._close_output()

    def _stop_live(self) -> None:
        live, self._live = self._live, None
        if live is not None:
            live.stop()

    def _refresh(self) -> None:
        self._frame += 1
        if self._live is None:
            self._live = Live(
                self._view(),
                console=self.console,
                transient=True,
                auto_refresh=False,
                redirect_stdout=False,
                redirect_stderr=False,
            )
            self._live.start()
        self._live.update(self._view(), refresh=True)

    def _view(self) -> Table:
        grid = Table.grid(padding=(0, 1))
        total = self._done + self._pending
        overall = " · ".join(
            [
                t("live.archives", done=self._done, total=total),
                t("live.round", number=self._round),
                format_elapsed(time.monotonic() - self._root_started),
            ]
        )
        grid.add_row(
            Text(t("live.overall")),
            ProgressBar(total=max(total, 1), completed=self._done, width=24),
            Text(overall, style="dim"),
        )
        if self._current is not None:
            details = [f"{self._percent}%", shorten(self._current)]
            done, size = self._bytes
            if done is not None and size:
                details.append(format_byte_pair(done, size))
                seconds = time.monotonic() - self._item_started
                if seconds > 0.5:
                    details.append(f"{format_bytes(done / seconds)}/s")
            spinner = _SPINNER[self._frame % len(_SPINNER)]
            grid.add_row(
                Text(f"{spinner} {t('live.current')}", style="cyan"),
                ProgressBar(total=100, completed=self._percent, width=24),
                Text("  ".join(details)),
            )
        return grid

    def _on_RootStarted(self, event: ev.RootStarted) -> None:
        super()._on_RootStarted(event)
        self._round = self._done = self._pending = 0
        self._current = None

    def _on_RoundStarted(self, event: ev.RoundStarted) -> None:
        self._round, self._done, self._pending = event.number, event.done, event.pending
        self._refresh()

    def _on_ItemStarted(self, event: ev.ItemStarted) -> None:
        self._current = event.item.name
        self._percent = 0
        self._bytes = (None, None)
        self._item_started = time.monotonic()
        self._refresh()

    def _on_Progress(self, event: ev.Progress) -> None:
        self._percent = event.percent
        self._bytes = (event.bytes_done, event.bytes_total)
        self._refresh()

    def _finished_one(self) -> None:
        self._done += 1
        self._pending = max(self._pending - 1, 0)
        self._current = None
        self._refresh()

    def _on_ItemOpened(self, event: ev.ItemOpened) -> None:
        super()._on_ItemOpened(event)
        self._finished_one()

    def _on_SetAssembled(self, event: ev.SetAssembled) -> None:
        super()._on_SetAssembled(event)
        self._finished_one()

    def _on_PromptNeeded(self, event: ev.PromptNeeded) -> None:
        self._stop_live()

    def _on_RootFinished(self, event: ev.RootFinished) -> None:
        self._stop_live()
        super()._on_RootFinished(event)


# ------------------------------
# JSON lines
# ------------------------------


class JsonRenderer(_Dispatcher):
    """--json: newline-delimited JSON events; the last line is the summary."""

    def __init__(
        self, stream: IO[str], clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.stream = stream
        self.clock = clock
        self._root_index = 0
        self._root = ""
        self._paths: dict[int, str] = {}
        self._last_progress: dict[str, tuple[int, float]] = {}

    def _close_output(self) -> None:
        super()._close_output()
        _silence_stdout(self.stream)

    def _write(self, name: str, **fields: Any) -> None:
        line = {"event": name, "schema_version": SCHEMA_VERSION, **fields}
        self.stream.write(json.dumps(line, ensure_ascii=False) + "\n")
        self.stream.flush()

    def _rel(self, path: str, root: Optional[str] = None) -> str:
        try:
            relative = os.path.relpath(path, root or self._root)
        except ValueError:
            relative = path
        return relative.replace(os.sep, "/")

    def _on_RunStarted(self, event: ev.RunStarted) -> None:
        self._write("start", version=event.version, roots=list(event.roots))

    def _on_RootStarted(self, event: ev.RootStarted) -> None:
        self._root_index, self._root = event.index, event.root
        self._paths = {}
        self._write("root", index=event.index, path=event.root)

    def _on_RoundStarted(self, event: ev.RoundStarted) -> None:
        self._write("round", root=self._root_index, number=event.number)

    def _on_ItemOpened(self, event: ev.ItemOpened) -> None:
        item = event.item
        self._paths[item.id] = item.path
        self._write(
            "item",
            root=self._root_index,
            path=self._rel(item.path),
            action="opened",
            files=event.files,
            password_index=item.password_ref,
        )

    def _on_SetAssembled(self, event: ev.SetAssembled) -> None:
        volumes = []
        for volume in event.volumes:
            parent = self._paths.get(volume.parents[0]) if volume.parents else None
            volumes.append(
                {
                    "index": volume.volume.index if volume.volume else None,
                    "path": self._rel(volume.path),
                    "source": (
                        None
                        if volume.is_source or parent is None
                        else self._rel(parent)
                    ),
                    "uncloaked_from": volume.original_name,
                }
            )
        primary = event.primary
        self._write(
            "set",
            root=self._root_index,
            key=primary.volume.display_key if primary.volume else primary.name,
            volumes=volumes,
            status="extracted",
            files=event.files,
            password_index=primary.password_ref,
        )

    def _on_Progress(self, event: ev.Progress) -> None:
        now = self.clock()
        last = self._last_progress.get(event.path)
        if last is not None:
            percent, when = last
            if abs(event.percent - percent) < 1 and now - when < PROGRESS_INTERVAL:
                return
        self._last_progress[event.path] = (event.percent, now)
        self._write(
            "progress",
            root=self._root_index,
            path=self._rel(event.path),
            percent=event.percent,
            bytes_done=event.bytes_done,
            bytes_total=event.bytes_total,
        )

    def _on_RootFinished(self, event: ev.RootFinished) -> None:
        result = event.result
        for item in result.items:
            if item.is_source and item.state is State.KEPT:
                self._write(
                    "item",
                    root=self._root_index,
                    path=self._rel(item.path),
                    action="kept",
                    files=0,
                    password_index=None,
                )
        for item in result.unresolved:
            self._write(
                "unresolved",
                root=self._root_index,
                path=self._rel(item.path),
                reason=item.reason,
                preserved_to=(
                    self._rel(item.output_path, result.root)
                    if item.output_path
                    else None
                ),
            )

    def _on_RunFailed(self, event: ev.RunFailed) -> None:
        self._write("error", code=event.code, detail=event.detail)

    def _on_RunFinished(self, event: ev.RunFinished) -> None:
        unresolved = [
            {
                "root": index,
                "path": self._rel(item.path, result.root),
                "reason": item.reason,
            }
            for index, result in enumerate(event.results, start=1)
            for item in result.unresolved
        ]
        status = {0: "ok", 1: "partial"}.get(event.exit_code, "error")
        self._write(
            "summary",
            status=status,
            files=sum(len(r.output_files) for r in event.results),
            output_dirs=[r.output_dir for r in event.results],
            sources={
                "deleted": sum(len(r.deleted_sources) for r in event.results),
                "kept": sum(len(r.kept_sources) for r in event.results),
            },
            unresolved=unresolved,
            exit=event.exit_code,
        )


Renderer = Union[PlainRenderer, TreeRenderer, JsonRenderer]


def create_renderer(
    json_mode: bool, recycle_bin: bool = True, stream: Optional[IO[str]] = None
) -> Renderer:
    """JSON for --json, the live tree view for a terminal, plain lines otherwise."""
    target = stream if stream is not None else sys.stdout
    if json_mode:
        return JsonRenderer(target)
    console = _Console(file=target, highlight=False, emoji=False, no_color=None)
    if console.is_terminal:
        return TreeRenderer(console, recycle_bin)
    return PlainRenderer(console, recycle_bin)
