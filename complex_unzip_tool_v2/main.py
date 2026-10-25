"""Main CLI interface for Complex Unzip Tool v2."""

import os
import sys
import platform
import typer
from typing import List, Optional, Annotated
from . import __version__

from .modules import (
    file_utils,
    archive_utils,
    password_util,
    work_pool,
)
from .modules.pool_engine import SevenZipEngine
from .modules.rename_history import RelocationLog, RenameHistory
from .modules.rich_utils import (
    init_statistics,
    update_stats,
    print_header,
    print_step,
    print_info,
    print_success,
    print_warning,
    print_error,
    print_final_completion,
    print_version,
    print_general,
    print_file_path,
    print_major_section_break,
    print_minor_section_break,
    print_password_failed_options,
    print_invalid_choice,
)

app = typer.Typer(
    help="Complex Unzip Tool v2 - Advanced Archive Extraction Utility 复杂解压工具v2 - 高级档案提取实用程序"
)


def _maybe_recover_pending_renames(input_root: str) -> None:
    """Recover what an interrupted run left in `input_root`.

    Leftover work directories are reported. Source volumes that were moved
    for multipart assembly are restored without asking; uncloak renames are
    only reverted if the user agrees (default: no).
    """
    for leftover in work_pool.leftover_work_dirs(input_root):
        print_warning("Work directory left by an interrupted run 发现中断运行遗留的工作目录:")
        print_file_path(leftover, 1)

    pending = RenameHistory.load_pending(input_root)
    if pending is None:
        return

    restored = pending.restore_relocations()
    if restored:
        print_success(
            f"Restored {restored} source volume(s) moved by an interrupted run "
            f"已还原中断运行移动的 {restored} 个原始分卷"
        )
    if not pending.uncloak_entries():
        pending.delete_file()
        return

    print_warning(
        f"Detected pending rename history from a previous run "
        f"检测到上次运行遗留的改名记录: {len(pending.entries)} entries"
    )
    if not pending.root_matches(input_root):
        print_warning(
            f"⚠ History was recorded for a different input root "
            f"历史文件来自另一个输入目录: {pending.input_root}",
            1,
        )

    for entry in pending.entries[:10]:
        ren_basename = os.path.basename(entry["renamed"])
        orig_basename = os.path.basename(entry["original"])
        group_label = entry.get("group") or "unbound"
        print_file_path(f"{ren_basename} → {orig_basename}  ({group_label})", 1)
    if len(pending.entries) > 10:
        print_info(f"... and {len(pending.entries) - 10} more", 1)

    try:
        choice = (
            input(
                "Revert these renames before starting? "
                "在开始前回滚这些改名? (y/N) [default: N]: "
            )
            .strip()
            .lower()
        )
    except (KeyboardInterrupt, EOFError):
        choice = "n"

    if choice not in ("y", "yes"):
        print_info(
            "Skipping recovery. This run will overwrite the history file. "
            "跳过恢复，本次运行将覆盖历史记录。"
        )
        return

    total = 0
    for group_key in pending.bound_group_keys():
        count, _ = pending.revert_group(group_key)
        total += count
    unbound_count, _ = pending.revert_unbound()
    total += unbound_count
    pending.delete_file()
    print_success(
        f"✓ Reverted {total} rename(s) and removed history file "
        f"已回滚 {total} 个改名并删除历史文件"
    )


def _ask_for_user_input_and_exit(exit_code: int = 0) -> None:
    """Ask for random user input before exiting the application."""
    # Only ask for input in standalone builds (PyInstaller frozen executables)
    if (
        getattr(sys, "frozen", False)
        and platform.system() == "Windows"
        and sys.stdin is not None
        and sys.stdin.isatty()
        and sys.stdout is not None
        and sys.stdout.isatty()
    ):
        try:
            input("Press Enter to exit... 按回车键退出...")
        except (EOFError, KeyboardInterrupt):
            pass
    sys.exit(exit_code)


def _sanitize_cli_paths(paths: List[str]) -> List[str]:
    """Drop dash-prefixed tokens that are not existing paths.

    Such tokens are mistyped/misplaced options, never real input paths.
    """
    kept: List[str] = []
    for token in paths:
        if token.startswith("-") and not os.path.exists(token):
            print_warning(f"Ignoring unknown option 忽略未知选项: {token}")
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
        typer.Argument(help="Archive paths to extract 要提取的档案路径"),
    ] = None,
    version: bool = typer.Option(
        False, "--version", "-v", help="Show version information 显示版本信息"
    ),
    permanent_delete: bool = typer.Option(
        False,
        "--permanent-delete",
        "-pd",
        help="Permanently delete original files instead of moving to recycle bin 永久删除原始文件而不是移动到回收站",
    ),
) -> None:
    """Complex Unzip Tool v2 - Advanced Archive Extraction Utility 复杂解压工具v2 - 高级档案提取实用程序"""
    if version:
        print_version(__version__)
        _ask_for_user_input_and_exit()

    # If no command is provided, run the default extract command
    if ctx.invoked_subcommand is None:
        # The variadic `paths` argument swallows subcommand names, so dispatch
        # `version` here unless it names a real file/folder.
        if paths == ["version"] and not os.path.exists("version"):
            version_command()
            return
        paths = _sanitize_cli_paths(paths or [])
        if paths:
            try:
                archive_utils.resolve_seven_zip_path()
            except archive_utils.SevenZipNotFoundError as exc:
                print_error(str(exc))
                _ask_for_user_input_and_exit(1)
            # Call extract_files directly instead of extract command
            extract_files(paths, use_recycle_bin=not permanent_delete)
        else:
            # Show help when no paths are provided
            print_general(ctx.get_help())
            _ask_for_user_input_and_exit()


@app.command("version")
def version_command() -> None:
    """Show version information 显示版本信息"""

    print_version(__version__)
    _ask_for_user_input_and_exit()


def extract(
    paths: Annotated[
        List[str],
        typer.Argument(help="Paths to the archives to extract 要提取的档案路径"),
    ],
    permanent_delete: bool = typer.Option(
        False,
        "--permanent-delete",
        "-pd",
        help="Permanently delete original files instead of moving to recycle bin 永久删除原始文件而不是移动到回收站",
    ),
) -> None:
    """Extract files from an archive 从档案中提取文件"""
    extract_files(paths, use_recycle_bin=not permanent_delete)


# ------------------------------
# Work-pool wiring
# ------------------------------


def _prompt_for_password(archive_path: str) -> work_pool.PromptAnswer:
    """Ask what to do with an archive whose password is unknown.

    Returns the typed password, None to skip this archive, or SKIP_ALL to skip
    every further prompt. End of input (redirected stdin) means skip.
    """
    print_password_failed_options(os.path.basename(archive_path))
    while True:
        try:
            choice = input("Choose an option 选择一个选项 (1/2/3) [default: 2]: ").strip()
        except (EOFError, KeyboardInterrupt):
            return None
        if choice in ("", "2"):
            return None
        if choice == "3":
            return work_pool.SKIP_ALL
        if choice == "1":
            try:
                return input("Enter password 输入密码: ")
            except (EOFError, KeyboardInterrupt):
                return None
        print_invalid_choice()


def _describe_password(ref: work_pool.PasswordRef) -> str:
    if ref == "entered":
        return " · entered password 手动输入的密码"
    if isinstance(ref, int) and ref > 0:
        return f" · password #{ref} 密码 #{ref}"
    return ""


def _print_pool_event(event: work_pool.Event) -> None:
    """Temporary rendering of pool events with the existing console helpers."""
    if isinstance(event, work_pool.RoundStarted):
        print_info(f"🔄 Round {event.number} 第 {event.number} 轮")
    elif isinstance(event, work_pool.ItemOpened):
        item = event.item
        print_success(
            f"Opened 已打开: {item.name} → {event.files} files 个文件"
            f"{_describe_password(item.password_ref)}",
            1,
        )
    elif isinstance(event, work_pool.SetAssembled):
        print_success(
            f"Assembled 已拼合: {event.primary.name} "
            f"({len(event.volumes)} volumes 卷) → {event.files} files 个文件"
            f"{_describe_password(event.primary.password_ref)}",
            1,
        )
    elif isinstance(event, work_pool.ItemUnresolved):
        print_warning(
            f"Unresolved 未解决: {event.item.name} ({event.item.reason})",
            1,
        )


def _reconcile_history(history: RenameHistory, result: work_pool.PoolResult) -> None:
    """Forget renames of deleted sources; put kept sources' names back."""
    for path in result.deleted_sources:
        history.clear_for(path)
    count, sample = history.revert_unbound()
    if count:
        print_warning(
            f"Reverted {count} rename(s) of kept files 已回滚 {count} 个保留文件的改名:",
            1,
        )
        for renamed_basename, original_basename in sample:
            print_file_path(f"{renamed_basename} → {original_basename}", 2)
    history.finalize()


def _print_root_summary(result: work_pool.PoolResult, use_recycle_bin: bool) -> None:
    outputs = len(result.output_files)
    print_success(f"Output 输出: {outputs} files 个文件 →", 1)
    print_file_path(result.output_dir, 2)
    if result.deleted_sources:
        where = "recycle bin 回收站" if use_recycle_bin else "deleted 已删除"
        print_success(
            f"Sources 原文件: {len(result.deleted_sources)} → {where}",
            1,
        )
    unresolved = result.unresolved
    if unresolved:
        print_warning(
            f"Unresolved 未解决: {len(unresolved)} (kept 已保留)",
            1,
        )
        for item in unresolved:
            print_file_path(f"{item.name}: {item.reason}", 2)
    if result.work_dir_kept:
        print_warning("Work directory kept 工作目录已保留:", 1)
        print_file_path(result.work_dir, 2)

    def is_archive(item: work_pool.WorkItem) -> bool:
        """A container, or a whole multipart set (counted by its primary)."""
        if item.kind is work_pool.Kind.CONTAINER:
            return True
        if item.kind is work_pool.Kind.VOLUME:
            return item.volume is not None and item.volume.is_primary
        return item.reason == "not a valid archive"

    archives = sum(
        1
        for i in result.items
        if is_archive(i)
        and i.state in (work_pool.State.CONSUMED, work_pool.State.UNRESOLVED)
    )
    failed = sum(1 for i in unresolved if is_archive(i))
    update_stats(
        archives=archives,
        successful=archives - failed,
        failed=failed,
        files=outputs,
    )


def extract_files(paths: List[str], use_recycle_bin: bool = True) -> None:
    """Shared extraction logic 共享提取逻辑"""

    init_statistics()
    print_header(f"🚀 Starting Complex Unzip Tool v2 启动复杂解压工具v2 v{__version__} By Rozx")

    print_step(1, "🔑 Loading passwords 加载密码")
    passwordBook = password_util.load_all_passwords(paths)
    print_success(
        f"Loaded {len(passwordBook.get_passwords())} unique passwords 已加载 {len(passwordBook.get_passwords())} 个唯一密码"
    )
    print_minor_section_break()

    engine = SevenZipEngine(passwordBook)
    detector = file_utils.create_cloaked_detector()
    roots = work_pool.group_input_roots(paths)
    results: list[work_pool.PoolResult] = []

    for number, (root, root_paths) in enumerate(roots, start=2):
        print_step(number, "📂 Extracting input root 处理输入目录")
        print_file_path(root)
        _maybe_recover_pending_renames(root)

        history = RenameHistory(root)
        sources = file_utils.read_dir(root_paths)
        print_info(f"Found {len(sources)} files 发现 {len(sources)} 个文件")

        def uncloak(
            path: str, is_source: bool, history: RenameHistory = history
        ) -> str:
            return detector.uncloak_file(path, history=history if is_source else None)

        def remove(path: str) -> bool:
            return file_utils.safe_remove(
                path, use_recycle_bin=use_recycle_bin, error_callback=print_error
            )

        pool = work_pool.WorkPool(
            root,
            sources,
            engine,
            prompt=_prompt_for_password,
            uncloak=uncloak,
            remove=remove,
            relocations=RelocationLog(history),
            emit=_print_pool_event,
        )
        result = pool.run()
        _reconcile_history(history, result)
        _print_root_summary(result, use_recycle_bin)
        results.append(result)
        print_minor_section_break()

    print_step(len(roots) + 2, "📊 Final summary 最终摘要")
    if passwordBook.has_unsaved_changes():
        print_info("💾 Saving passwords 正在保存密码...")
        try:
            passwordBook.save_passwords()
        except OSError as exc:
            print_warning(
                f"Could not save passwords 无法保存密码本: "
                f"{passwordBook.password_file} ({exc}). "
                "Check write permissions 请检查目录写入权限。"
            )
    else:
        print_info("📝 No new passwords to save 没有新密码需要保存")

    print_major_section_break()
    print_final_completion("\n    ".join(r.output_dir for r in results))

    # Ask for random user input before exit
    _ask_for_user_input_and_exit()


def cli() -> None:
    """Command line interface entry point 命令行界面入口点"""
    app()


def main() -> None:
    """Entry point for the application 应用程序入口点"""
    try:
        cli()
    except KeyboardInterrupt:
        print_error("\nOperation cancelled by user 操作被用户取消")
        _ask_for_user_input_and_exit()
    except Exception as e:
        print_error(f"Unexpected error 意外错误: {e}")
        _ask_for_user_input_and_exit()


if __name__ == "__main__":
    main()
