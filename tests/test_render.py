"""Renderers turn run events into terminal lines, a lineage tree or JSON lines."""

import io
import json
import os

import pytest
from rich.console import Console

from complex_unzip_tool_v2.modules import events as ev
from complex_unzip_tool_v2.modules import i18n, render
from complex_unzip_tool_v2.modules import work_pool as wp

from fake_archives import FakeEngine, archive, run_pool, uncloak_suffix, volume, write


def drive(handle, root, **pool_kwargs):
    """Emit a whole run for one root into `handle`, like the CLI does."""
    handle(ev.RunStarted("9.9.9", (str(root),)))
    handle(ev.RootStarted(1, str(root)))
    result, _ = run_pool(root, emit=handle, **pool_kwargs)
    handle(ev.RunFinished((result,), 1 if result.unresolved else 0, 2.5))
    return result


def reproduction(root):
    write(root / "A.7z", archive({"X.7z.002": volume("S1", 2, 2)}, "pw1"))
    write(
        root / "B.rar",
        archive({"X.7z.001删掉": volume("S1", 1, 2, files={"movie.mp4": "m"})}, "pw1"),
    )
    return {"engine": FakeEngine(passwords=["pw1"]), "uncloak": uncloak_suffix([])}


def plain(**kwargs):
    stream = io.StringIO()
    return stream, render.create_renderer(json_mode=False, stream=stream, **kwargs)


def json_lines(stream):
    return [json.loads(line) for line in stream.getvalue().splitlines()]


# ------------------------------
# Human output
# ------------------------------


def test_plain_output_lists_items_then_tree_and_summary(tmp_path):
    stream, renderer = plain(recycle_bin=True)
    drive(renderer, tmp_path, **reproduction(tmp_path))
    out = stream.getvalue()
    assert out.count("A.7z  opened → 1 files · password #1") == 1
    assert out.count("B.rar  opened → 1 files · password #1") == 1
    assert "X.7z.001  2 volumes assembled → 1 files" in out
    assert "X.7z  1 files" in out
    assert ".7z.001 ← B.rar  uncloaked from X.7z.001删掉" in out
    assert ".7z.002 ← A.7z" in out
    assert "output: 1 files →" in out
    assert "sources: 2 moved to the recycle bin" in out
    assert "exit code 0" in out
    assert "\x1b[" not in out


def test_plain_output_reports_kept_and_unresolved_items(tmp_path):
    write(tmp_path / "readme.txt", "hello")
    write(tmp_path / "A.7z", archive({"inner.rar": archive({"x": "x"}, "zz")}))
    stream, renderer = plain(recycle_bin=False)
    drive(renderer, tmp_path)
    out = stream.getvalue()
    assert "readme.txt  kept (not an archive)" in out
    assert "inner.rar  unresolved: wrong or missing password" in out
    assert "inner.rar: wrong or missing password → unzipped/inner.rar" in out
    assert "sources kept: 1" in out
    assert "exit code 1" in out


def _item(tmp_path, name, number):
    return wp.WorkItem(
        number, str(tmp_path / name), wp.Origin.SOURCE, frozenset({number}), 0, ""
    )


def test_item_lines_are_capped_per_root(tmp_path):
    stream, renderer = plain()
    renderer(ev.RootStarted(1, str(tmp_path)))
    for number in range(250):
        renderer(ev.ItemOpened(_item(tmp_path, f"a{number}.7z", number), 1))
    renderer(
        ev.RootFinished(wp.PoolResult(str(tmp_path), [], str(tmp_path), "", False))
    )
    out = stream.getvalue()
    assert out.count("opened →") == 200
    assert "… and 50 more" in out


def test_chinese_output(tmp_path):
    i18n.set_language("zh")
    stream, renderer = plain()
    drive(renderer, tmp_path, **reproduction(tmp_path))
    out = stream.getvalue()
    assert "已打开" in out and "已拼合 2 卷" in out and "退出码 0" in out
    assert "opened" not in out


def test_file_names_are_never_read_as_markup(tmp_path):
    write(tmp_path / "[group] title.7z", archive({"a.txt": "a"}))
    stream, renderer = plain()
    drive(renderer, tmp_path)
    assert "[group] title.7z  opened" in stream.getvalue()


def test_terminal_view_shows_live_progress_then_the_tree(tmp_path):
    buffer = io.StringIO()
    console = Console(file=buffer, force_terminal=True, width=100, color_system=None)
    renderer = render.TreeRenderer(console, recycle_bin=True)
    item = _item(tmp_path, "big.7z", 1)
    renderer(ev.RunStarted("9.9.9", (str(tmp_path),)))
    renderer(ev.RootStarted(1, str(tmp_path)))
    renderer(ev.RoundStarted(1, 0, 2))
    renderer(ev.ItemStarted(item))
    renderer(ev.Progress(item.path, 41, 1_200_000_000, 2_900_000_000))
    frame = buffer.getvalue()
    assert "Overall" in frame and "0/2 archives" in frame
    assert "41%" in frame and "big.7z" in frame and "1.2/2.9 GB" in frame
    renderer(ev.PromptNeeded(item.path))
    assert not renderer.live_active
    renderer(
        ev.RootFinished(wp.PoolResult(str(tmp_path), [], str(tmp_path), "", False))
    )
    renderer.close()
    assert "0 sources → 0 files" in buffer.getvalue()


# ------------------------------
# JSON lines
# ------------------------------


def test_json_stream_describes_the_run(tmp_path):
    stream = io.StringIO()
    drive(
        render.create_renderer(json_mode=True, stream=stream),
        tmp_path,
        **reproduction(tmp_path),
    )
    lines = json_lines(stream)
    assert all(line["schema_version"] == 1 for line in lines)
    assert lines[0]["event"] == "start" and lines[-1]["event"] == "summary"
    items = [line for line in lines if line["event"] == "item"]
    assert sorted((i["path"], i["action"], i["password_index"]) for i in items) == [
        ("A.7z", "opened", 1),
        ("B.rar", "opened", 1),
    ]
    (set_event,) = [line for line in lines if line["event"] == "set"]
    assert [
        (v["index"], v["source"], v["uncloaked_from"]) for v in set_event["volumes"]
    ] == [(1, "B.rar", "X.7z.001删掉"), (2, "A.7z", None)]
    assert set_event["status"] == "extracted" and set_event["files"] == 1
    summary = lines[-1]
    assert summary["status"] == "ok" and summary["exit"] == 0
    assert summary["files"] == 1 and summary["sources"] == {"deleted": 2, "kept": 0}


def test_json_stream_is_identical_in_both_languages(tmp_path):
    streams = []
    for language in ("en", "zh"):
        i18n.set_language(language)
        root = tmp_path / language
        root.mkdir()
        stream = io.StringIO()
        drive(
            render.create_renderer(json_mode=True, stream=stream),
            root,
            **reproduction(root),
        )
        streams.append(
            [
                {k: v for k, v in line.items() if k != "roots"}
                for line in json_lines(stream)
            ]
        )
    for line in streams[0] + streams[1]:
        line.pop("output_dirs", None)  # absolute paths differ between the roots
        if line["event"] == "root":
            line.pop("path")
    assert streams[0] == streams[1]


def test_json_reports_unresolved_items_with_their_location(tmp_path):
    write(tmp_path / "A.7z", archive({"inner.rar": archive({"x": "x"}, "zz")}))
    stream = io.StringIO()
    drive(render.create_renderer(json_mode=True, stream=stream), tmp_path)
    lines = json_lines(stream)
    (unresolved,) = [line for line in lines if line["event"] == "unresolved"]
    assert unresolved["reason"] == "password"
    assert unresolved["preserved_to"] == "unzipped/inner.rar"
    assert lines[-1]["status"] == "partial" and lines[-1]["exit"] == 1


def test_json_progress_is_throttled():
    clock = iter([0.0, 0.05, 0.1, 0.15, 0.16, 0.5])
    stream = io.StringIO()
    renderer = render.JsonRenderer(stream, clock=lambda: next(clock))
    renderer(ev.RootStarted(1, "root"))
    for percent in (0, 0, 1, 1, 5, 5):
        renderer(ev.Progress(os.path.join("root", "a.7z"), percent))
    assert [line["percent"] for line in json_lines(stream)[1:]] == [0, 1, 5, 5]


def test_json_fatal_error_still_ends_with_a_summary():
    stream = io.StringIO()
    renderer = render.create_renderer(json_mode=True, stream=stream)
    renderer(ev.RunStarted("9.9.9", ("root",)))
    renderer(ev.RunFailed("engine_missing", "7-Zip executable not found"))
    renderer(ev.RunFinished((), 2, 0.0))
    lines = json_lines(stream)
    assert [line["event"] for line in lines] == ["start", "error", "summary"]
    assert lines[1]["code"] == "engine_missing"
    assert lines[-1]["status"] == "error" and lines[-1]["exit"] == 2


# ------------------------------
# Selection and safety
# ------------------------------


class _Terminal(io.StringIO):
    def isatty(self):
        return True


def test_renderer_selection(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert isinstance(
        render.create_renderer(json_mode=True, stream=io.StringIO()),
        render.JsonRenderer,
    )
    assert isinstance(
        render.create_renderer(json_mode=False, stream=io.StringIO()),
        render.PlainRenderer,
    )
    assert isinstance(
        render.create_renderer(json_mode=False, stream=_Terminal()), render.TreeRenderer
    )
    monkeypatch.setenv("NO_COLOR", "1")
    renderer = render.create_renderer(json_mode=False, stream=_Terminal())
    assert renderer.console.no_color


@pytest.mark.parametrize("mode", ["plain", "tree", "json"])
def test_passwords_never_appear_in_any_output(tmp_path, mode):
    write(tmp_path / "A.7z", archive({"a.txt": "a"}, "s3cr3t-book-password"))
    write(tmp_path / "B.7z", archive({"b.txt": "b"}, "typed-secret"))
    stream = _Terminal() if mode == "tree" else io.StringIO()
    renderer = render.create_renderer(json_mode=mode == "json", stream=stream)
    drive(
        renderer,
        tmp_path,
        engine=FakeEngine(passwords=["s3cr3t-book-password"]),
        prompt=lambda path: "typed-secret",
    )
    renderer.close()
    out = stream.getvalue()
    assert "s3cr3t-book-password" not in out and "typed-secret" not in out
    if mode == "json":
        assert '"password_index": 1' in out and '"password_index": "entered"' in out
    else:
        assert "password #1" in out and "entered password" in out
