"""Generate the README terminal screenshots from a recorded demo run.

`record` runs the real work pool and 7-Zip on a copy of the demo set (see
scripts/make_demo_archives.py) and stores its events in
tests/fixtures/demo_events.json. `render` (the default) replays those events
through the human renderer and writes docs/images/terminal-zh.svg and
terminal-en.svg. Rendering needs neither 7-Zip nor archives, so it is
deterministic; it shows the screen a terminal run leaves behind (the live
progress lines are transient).

Usage:
    poetry run python -m scripts.generate_screenshots record <demo-folder>
    poetry run python -m scripts.generate_screenshots
"""

import argparse
import dataclasses
import html
import io
import json
import os
import re
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Optional

from rich.cells import cell_len
from rich.console import Console

from deepunzip import __version__
from deepunzip.modules import events as ev
from deepunzip.modules import file_utils, i18n
from deepunzip.modules import multipart_assembly as ma
from deepunzip.modules import work_pool as wp
from deepunzip.modules.pool_engine import SevenZipEngine
from deepunzip.modules.render import PlainRenderer

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "demo_events.json"
IMAGES = ROOT / "docs" / "images"
# Shown instead of the temporary folder the demo was recorded in.
DISPLAY_ROOT = "D:\\Downloads\\demo"
WIDTH = 100
_SKIPPED = (ev.Progress, ev.PromptNeeded)
_SVG_TEXT = re.compile(r'textLength="([\d.]+)"([^>]*)>([^<]*)</text>')

# ------------------------------
# Serialization
# ------------------------------


def _relative(path: Optional[str], root: str) -> Optional[str]:
    if path is None:
        return None
    return os.path.relpath(path, root).replace(os.sep, "/")


def _item_data(item: wp.WorkItem, root: str) -> dict[str, Any]:
    return {
        "id": item.id,
        "path": _relative(item.path, root),
        "origin": item.origin.value,
        "lineage": sorted(item.lineage),
        "depth": item.depth,
        "rel_base": _relative(item.rel_base, root),
        "kind": item.kind.value,
        "state": item.state.value,
        "reason": item.reason,
        "volume": dataclasses.asdict(item.volume) if item.volume else None,
        "original_name": item.original_name,
        "parents": list(item.parents),
        "password_ref": item.password_ref,
        "output_path": _relative(item.output_path, root),
    }


def _result_data(result: wp.PoolResult) -> dict[str, Any]:
    return {
        "items": [_item_data(item, result.root) for item in result.items],
        "work_dir_kept": result.work_dir_kept,
        "deleted_sources": [_relative(p, result.root) for p in result.deleted_sources],
        "kept_sources": [_relative(p, result.root) for p in result.kept_sources],
    }


def event_data(event: ev.Event, root: str) -> dict[str, Any]:
    """One event as JSON data, with paths relative to the demo root."""
    data: dict[str, Any] = {"type": type(event).__name__}
    for field in dataclasses.fields(event):  # type: ignore[arg-type]
        value = getattr(event, field.name)
        if isinstance(value, wp.WorkItem):
            value = _item_data(value, root)
        elif isinstance(value, wp.PoolResult):
            value = _result_data(value)
        elif field.name == "volumes":
            value = [_item_data(item, root) for item in value]
        elif field.name == "results":
            value = [_result_data(result) for result in value]
        elif field.name in ("root", "roots"):
            value = None  # replaced by DISPLAY_ROOT when replayed
        data[field.name] = value
    return data


def _display(path: Optional[str]) -> Optional[str]:
    if path is None:
        return None
    return os.path.join(DISPLAY_ROOT, *path.split("/"))


def _item(data: dict[str, Any]) -> wp.WorkItem:
    volume = data["volume"]
    return wp.WorkItem(
        id=data["id"],
        path=_display(data["path"]) or "",
        origin=wp.Origin(data["origin"]),
        lineage=frozenset(data["lineage"]),
        depth=data["depth"],
        rel_base=_display(data["rel_base"]) or "",
        kind=wp.Kind(data["kind"]),
        state=wp.State(data["state"]),
        reason=data["reason"],
        volume=ma.VolumeName(**volume) if volume else None,
        original_name=data["original_name"],
        parents=tuple(data["parents"]),
        password_ref=data["password_ref"],
        output_path=_display(data["output_path"]),
    )


def _result(data: dict[str, Any]) -> wp.PoolResult:
    return wp.PoolResult(
        root=DISPLAY_ROOT,
        items=[_item(item) for item in data["items"]],
        output_dir=DISPLAY_ROOT + "\\unzipped",
        work_dir=DISPLAY_ROOT + "\\temp.deepunzip-demo",
        work_dir_kept=data["work_dir_kept"],
        deleted_sources=[_display(p) or "" for p in data["deleted_sources"]],
        kept_sources=[_display(p) or "" for p in data["kept_sources"]],
    )


def replay(data: dict[str, Any]) -> ev.Event:
    """Rebuild an event recorded by `event_data`."""
    fields = {k: v for k, v in data.items() if k not in ("type", "t")}
    kind = getattr(ev, data["type"])
    for name, value in fields.items():
        if name in ("item", "primary"):
            fields[name] = _item(value)
        elif name == "volumes":
            fields[name] = tuple(_item(v) for v in value)
        elif name == "result":
            fields[name] = _result(value)
        elif name == "results":
            fields[name] = tuple(_result(v) for v in value)
        elif name == "root":
            fields[name] = DISPLAY_ROOT
        elif name == "roots":
            fields[name] = (DISPLAY_ROOT,)
        elif name == "version":
            fields[name] = __version__
    event: ev.Event = kind(**fields)
    return event


# ------------------------------
# Record
# ------------------------------


class _DemoBook:
    """The demo passwords only: the user's password book is never read."""

    def __init__(self, passwords: list[str]) -> None:
        self.passwords = passwords

    def get_passwords(self) -> list[str]:
        return self.passwords

    def add_password(self, password: str) -> None:
        self.passwords.append(password)


def record(demo: Path, fixture: Path = FIXTURE) -> int:
    """Run the pool on a copy of `demo`; store its events; return the count."""
    with tempfile.TemporaryDirectory(prefix="deepunzip-record-") as temporary:
        root = os.path.join(temporary, "demo")
        shutil.copytree(demo, root)
        passwords = [
            line.strip()
            for line in Path(root, "passwords.txt").read_text("utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        ]
        started = time.monotonic()
        recorded: list[dict[str, Any]] = []

        def sink(event: ev.Event) -> None:
            if not isinstance(event, _SKIPPED):
                data = event_data(event, root)
                data["t"] = round(time.monotonic() - started, 1)
                recorded.append(data)

        engine = SevenZipEngine(_DemoBook(passwords), emit=sink)
        detector = file_utils.create_cloaked_detector()
        sources = sorted(
            os.path.join(root, name)
            for name in os.listdir(root)
            if name != "passwords.txt"
        )
        sink(ev.RunStarted(__version__, (root,)))
        sink(ev.RootStarted(1, root))
        result = wp.WorkPool(
            root,
            sources,
            engine,
            uncloak=lambda path, _is_source: detector.uncloak_file(path),
            remove=_remove,
            emit=sink,
            run_id="demo",
        ).run()
        exit_code = 1 if result.unresolved else 0
        sink(ev.RunFinished((result,), exit_code, time.monotonic() - started))
    recorded[-1]["elapsed"] = recorded[-1]["t"]
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text(
        json.dumps(recorded, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    return len(recorded)


def _remove(path: str) -> bool:
    os.remove(path)
    return True


# ------------------------------
# Render
# ------------------------------


def _widen_wide_characters(svg: str) -> str:
    """Give each text span the width of its terminal cells.

    Rich sizes a span by its character count, which squeezes Chinese text
    (two cells per character) into half its width.
    """

    def widen(match: re.Match[str]) -> str:
        text = html.unescape(match.group(3))
        width = float(match.group(1)) / len(text) * cell_len(text)
        return (
            f'textLength="{round(width, 2):g}"{match.group(2)}>{match.group(3)}</text>'
        )

    return _SVG_TEXT.sub(widen, svg)


class _ReplayClock:
    """Returns the recorded time of the event being replayed."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def render_svg(language: str, fixture: Path = FIXTURE) -> str:
    """The final terminal screen of the demo run, as SVG, in `language`."""
    previous = i18n.get_language()
    i18n.set_language(language)
    try:
        console = Console(
            file=io.StringIO(),
            record=True,
            width=WIDTH,
            force_terminal=True,
            color_system="truecolor",
            legacy_windows=False,
            highlight=False,
            emoji=False,
        )
        clock = _ReplayClock()
        renderer = PlainRenderer(console, recycle_bin=True, clock=clock)
        for data in json.loads(fixture.read_text(encoding="utf-8")):
            clock.now = data["t"]
            renderer(replay(data))
        renderer.close()
        return _widen_wide_characters(console.export_svg(title="DeepUnzip"))
    finally:
        i18n.set_language(previous)


def render(images: Path = IMAGES, fixture: Path = FIXTURE) -> list[Path]:
    images.mkdir(parents=True, exist_ok=True)
    written = []
    for language in ("zh", "en"):
        path = images / f"terminal-{language}.svg"
        path.write_text(render_svg(language, fixture), encoding="utf-8")
        written.append(path)
    return written


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command")
    recorder = commands.add_parser("record", help="record the demo run's events")
    recorder.add_argument("demo", type=Path, help="folder made by make_demo_archives")
    commands.add_parser("render", help="write the SVG screenshots (default)")
    arguments = parser.parse_args(argv)
    if arguments.command == "record":
        count = record(arguments.demo)
        print(f"{count} events → {FIXTURE.relative_to(ROOT)}")
        return
    for path in render():
        print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
