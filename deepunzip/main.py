"""
Command line interface.
命令行界面。

`run` drives one CLI invocation: it picks the renderer (terminal view, plain
lines or --json), reports fatal errors as events, and returns the exit code:
0 when everything is resolved, 1 when something is unresolved, 2 on a fatal
or usage error. User-facing text comes from `modules/i18n.py`.
"""

import os
import platform
import sys
import time
from typing import Annotated, List, Optional, TextIO

import typer

from . import __version__
from .modules import (
    archive_utils,
    events,
    file_utils,
    password_util,
    work_pool,
)
from .classes.PasswordBook import PasswordBook
from .modules.i18n import t
from .modules.pool_engine import SevenZipEngine
from .modules.rename_history import KIND_RELOCATION, RelocationLog, RenameHistory
from .modules.render import create_renderer

EXIT_OK = 0
EXIT_UNRESOLVED = 1
EXIT_FATAL = 2
RECOVERY_LIST_LIMIT = 10

app = typer.Typer(help=t("cli.help"))


# ------------------------------
# Prompts
# ------------------------------


def _windows_console(stream: TextIO) -> bool:
    """True unless the stream is provably not a console (e.g. `< NUL`)."""
    try:
        import ctypes
        import msvcrt

        handle = msvcrt.get_osfhandle(stream.fileno())
        mode = ctypes.c_uint32()
        kernel32 = getattr(ctypes, "windll").kernel32
        return bool(kernel32.GetConsoleMode(handle, ctypes.byref(mode)))
    except (AttributeError, ImportError, OSError, ValueError):
        return True  # no real handle (test doubles): trust isatty()


def _stdin_is_terminal() -> bool:
    stream = sys.stdin
    if stream is None or not stream.isatty():
        return False
    # Windows reports the NUL device as a TTY; only a console can answer.
    return sys.platform != "win32" or _windows_console(stream)


def _ask(prompt: str, strip: bool = True) -> Optional[str]:
    """Read one answer; end of input or Ctrl+C means "take the default"."""
    try:
        answer = input(prompt)
    except (EOFError, KeyboardInterrupt):
        sys.stdout.write("\n")  # end the unanswered prompt line
        return None
    return answer.strip() if strip else answer


def _prompt_for_password(archive_path: str) -> work_pool.PromptAnswer:
    """Ask what to do with an archive whose password is unknown.

    Returns the typed password, None to skip this archive, or SKIP_ALL to skip
    every further prompt. End of input means skip.
    """
    events.notice("warning", "prompt.title", name=os.path.basename(archive_path))
    events.notice("info", "prompt.choices")
    while True:
        choice = _ask(t("prompt.choose"))
        if choice is None or choice in ("", "2"):
            return None
        if choice == "3":
            return work_pool.SKIP_ALL
        if choice == "1":
            return _ask(t("prompt.password"), strip=False)
        events.notice("warning", "prompt.invalid")


def _maybe_recover_pending_renames(
    input_root: str, interactive: bool = True
) -> list[dict]:
    """Recover what an interrupted run left in `input_root`.

    Leftover work directories are reported. Source volumes that were moved
    for multipart assembly are restored without asking; uncloak renames are
    only reverted if the user agrees (default, and non-interactive: no).

    Returns the relocation entries that could not be restored, so the caller
    can carry them into this run's history instead of losing them.
    """
    for leftover in work_pool.leftover_work_dirs(input_root):
        events.notice("warning", "recovery.work_dir", path=leftover)

    pending = RenameHistory.load_pending(input_root)
    if pending is None:
        return []

    restored = pending.restore_relocations()
    if restored:
        events.notice("info", "recovery.restored", count=restored)
    stranded = [e for e in pending.entries if e.get("kind") == KIND_RELOCATION]
    if not pending.uncloak_entries():
        pending.delete_file()
        return stranded

    events.notice("warning", "recovery.pending", count=len(pending.entries))
    if not pending.root_matches(input_root):
        events.notice("warning", "recovery.other_root", root=pending.input_root)
    for entry in pending.entries[:RECOVERY_LIST_LIMIT]:
        events.notice(
            "info",
            "recovery.entry",
            renamed=os.path.basename(entry["renamed"]),
            original=os.path.basename(entry["original"]),
        )
    if len(pending.entries) > RECOVERY_LIST_LIMIT:
        more = len(pending.entries) - RECOVERY_LIST_LIMIT
        events.notice("info", "recovery.more", count=more)

    choice = _ask(t("recovery.ask")) if interactive else None
    if (choice or "").lower() not in ("y", "yes"):
        events.notice("info", "recovery.skipped")
        return stranded

    total = 0
    for group_key in pending.bound_group_keys():
        count, _ = pending.revert_group(group_key)
        total += count
    unbound_count, _ = pending.revert_unbound()
    total += unbound_count
    pending.delete_file()
    events.notice("info", "recovery.reverted", count=total)
    return [e for e in pending.entries if e.get("kind") == KIND_RELOCATION]


def _ask_for_user_input_and_exit(exit_code: int = 0, json_mode: bool = False) -> None:
    """Exit; a frozen Windows program in a terminal waits for Enter first."""
    if (
        not json_mode
        and getattr(sys, "frozen", False)
        and platform.system() == "Windows"
        and _stdin_is_terminal()
        and sys.stdout is not None
        and sys.stdout.isatty()
    ):
        try:
            input(t("cli.pause"))
        except (EOFError, KeyboardInterrupt):
            pass
    sys.exit(exit_code)


# ------------------------------
# Commands
# ------------------------------


def _version_text() -> str:
    return t("version", product=t("product"), version=__version__)


def _sanitize_cli_paths(paths: List[str]) -> List[str]:
    """Drop dash-prefixed tokens that are not existing paths.

    Such tokens are mistyped/misplaced options, never real input paths.
    """
    kept: List[str] = []
    for token in paths:
        if token.startswith("-") and not os.path.exists(token):
            typer.echo(t("cli.unknown_option", token=token), err=True)
            continue
        kept.append(token)
    return kept


# Options must be accepted after paths too (drag-and-drop puts paths first).
@app.callback(
    invoke_without_command=True,
    context_settings={"allow_interspersed_args": True},
)
def main_callback(
    ctx: typer.Context,
    paths: Annotated[
        Optional[List[str]],
        typer.Argument(help=t("cli.paths"), show_default=False),
    ] = None,
    version: bool = typer.Option(False, "--version", "-v", help=t("cli.version")),
    permanent_delete: bool = typer.Option(
        False, "--permanent-delete", "-pd", help=t("cli.permanent_delete")
    ),
    json_mode: bool = typer.Option(False, "--json", help=t("cli.json")),
) -> None:
    if version:
        typer.echo(_version_text())
        _ask_for_user_input_and_exit(EXIT_OK, json_mode)
        return

    if ctx.invoked_subcommand is not None:
        return
    # The variadic `paths` argument swallows subcommand names, so dispatch
    # `version` here unless it names a real file/folder.
    if paths == ["version"] and not os.path.exists("version"):
        version_command()
        return
    paths = _sanitize_cli_paths(paths or [])
    if not paths and not json_mode:
        typer.echo(ctx.get_help())
        _ask_for_user_input_and_exit(EXIT_OK)
        return
    code = run(paths, use_recycle_bin=not permanent_delete, json_mode=json_mode)
    _ask_for_user_input_and_exit(code, json_mode)


@app.command("version", help=t("cli.version_command"))
def version_command() -> None:
    typer.echo(_version_text())
    _ask_for_user_input_and_exit()


# ------------------------------
# Run
# ------------------------------


def run(paths: List[str], use_recycle_bin: bool = True, json_mode: bool = False) -> int:
    """Extract `paths` with the renderer for this terminal; return the exit code."""
    interactive = not json_mode and _stdin_is_terminal()
    renderer = create_renderer(json_mode, recycle_bin=use_recycle_bin)
    events.set_sink(renderer)
    started = time.monotonic()
    results: list[work_pool.PoolResult] = []
    code = EXIT_FATAL
    try:
        existing = [path for path in paths if os.path.exists(path)]
        roots = work_pool.group_input_roots(existing)
        events.emit(events.RunStarted(__version__, tuple(r for r, _ in roots)))
        for path in paths:
            if existing and path not in existing:
                events.notice("warning", "notice.missing_path", path=path)
        try:
            if not existing:
                events.emit(
                    events.RunFailed(
                        "no_input", t("error.no_input", paths=", ".join(paths))
                    )
                )
            else:
                # The engine is checked before anything touches the inputs.
                archive_utils.resolve_seven_zip_path()
                results = extract_files(existing, use_recycle_bin, interactive)
                unresolved = any(result.unresolved for result in results)
                code = EXIT_UNRESOLVED if unresolved else EXIT_OK
        except archive_utils.SevenZipNotFoundError as exc:
            events.emit(
                events.RunFailed("engine_missing", t("error.engine", detail=exc))
            )
        except KeyboardInterrupt:
            events.emit(events.RunFailed("cancelled", t("error.cancelled")))
        except Exception as exc:  # reported as an event, then exit code 2
            events.emit(
                events.RunFailed("unexpected", t("error.unexpected", detail=exc))
            )
        events.emit(
            events.RunFinished(tuple(results), code, time.monotonic() - started)
        )
    finally:
        renderer.close()
        events.set_sink(None)
    return code


def _reconcile_history(history: RenameHistory, result: work_pool.PoolResult) -> None:
    """Forget renames of deleted sources; put kept sources' names back."""
    for path in result.deleted_sources:
        history.clear_for(path)
    count, _sample = history.revert_unbound()
    if count:
        events.notice("info", "history.reverted", count=count)
    history.finalize()


def _save_passwords(book: PasswordBook) -> None:
    if not book.has_unsaved_changes():
        return
    try:
        book.save_passwords()
    except OSError as exc:
        events.notice(
            "warning", "summary.passwords_failed", path=book.password_file, error=exc
        )
    else:
        events.notice("info", "summary.passwords_saved", path=book.password_file)


def extract_files(
    paths: List[str], use_recycle_bin: bool = True, interactive: bool = True
) -> list[work_pool.PoolResult]:
    """Run one work pool per input root; return the results in root order."""
    password_book = password_util.load_all_passwords(paths)
    engine = SevenZipEngine(password_book, emit=events.emit)
    detector = file_utils.create_cloaked_detector()
    results: list[work_pool.PoolResult] = []

    for index, (root, root_paths) in enumerate(
        work_pool.group_input_roots(paths), start=1
    ):
        events.emit(events.RootStarted(index, root))
        stranded = _maybe_recover_pending_renames(root, interactive)

        history = RenameHistory(root)
        for entry in stranded:
            # Retried by _reconcile_history once this run finishes.
            history.record(entry["original"], entry["renamed"], kind=KIND_RELOCATION)
        sources = file_utils.read_dir(root_paths)

        def uncloak(
            path: str, is_source: bool, history: RenameHistory = history
        ) -> str:
            return detector.uncloak_file(path, history=history if is_source else None)

        def remove(path: str) -> bool:
            return file_utils.safe_remove(
                path,
                use_recycle_bin=use_recycle_bin,
                error_callback=lambda detail: events.notice(
                    "warning", "notice.remove_failed", detail=detail
                ),
            )

        pool = work_pool.WorkPool(
            root,
            sources,
            engine,
            prompt=_prompt_for_password if interactive else None,
            uncloak=uncloak,
            remove=remove,
            relocations=RelocationLog(history),
            emit=events.emit,
        )
        result = pool.run()
        _reconcile_history(history, result)
        results.append(result)

    _save_passwords(password_book)
    return results


def cli() -> None:
    """Command line entry point."""
    app()


def _deprecated_alias(alias: str) -> None:
    if "--json" not in sys.argv[1:]:
        typer.echo(t("cli.deprecated_alias", alias=alias), err=True)
    app()


def main_alias() -> None:
    """`main`: deprecated alias of `deepunzip` (removed in 3.0.0)."""
    _deprecated_alias("main")


def cuz_alias() -> None:
    """`cuz`: deprecated alias of `deepunzip` (removed in 3.0.0)."""
    _deprecated_alias("cuz")


def main() -> None:
    """Application entry point."""
    try:
        cli()
    except KeyboardInterrupt:
        typer.echo(t("error.cancelled"), err=True)
        _ask_for_user_input_and_exit(EXIT_FATAL)


if __name__ == "__main__":
    main()
