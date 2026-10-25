"""
User-facing text in English and Chinese.
面向用户的中英文文案。

Every user-facing string lives in CATALOG with an "en" and a "zh" entry; code
calls `t(key, **params)`. The language is chosen once per run: DEEPUNZIP_LANG
(zh/en) if set, otherwise the system UI language (zh* means Chinese),
otherwise English. tests/test_i18n.py fails if a key lacks a language.
"""

import os
import sys
from typing import Callable, Mapping, Optional

LANGUAGES = ("en", "zh")
_LANG_CHINESE = 0x04  # primary language id of every Chinese LANGID

CATALOG: dict[str, dict[str, str]] = {
    # ---------- product and CLI ----------
    "product": {"en": "DeepUnzip", "zh": "深度解压"},
    "version": {"en": "{product} {version}", "zh": "{product} {version}"},
    "cli.help": {
        "en": "Extract nested, password-protected, multipart and disguised archives.",
        "zh": "解开嵌套、加密、分卷和伪装的压缩包。",
    },
    "cli.paths": {"en": "Archives or folders to extract", "zh": "要解压的压缩包或文件夹"},
    "cli.version": {"en": "Show the version and exit", "zh": "显示版本后退出"},
    "cli.permanent_delete": {
        "en": "Delete extracted sources permanently instead of moving them "
        "to the recycle bin",
        "zh": "永久删除已解压的原文件，而不是移到回收站",
    },
    "cli.json": {
        "en": "Write JSON lines for programs instead of the terminal view; "
        "never prompts",
        "zh": "输出供程序读取的 JSON 行而不是终端界面；不会询问",
    },
    "cli.version_command": {"en": "Show the version", "zh": "显示版本"},
    "cli.unknown_option": {
        "en": "Ignoring unknown option: {token}",
        "zh": "忽略未知选项：{token}",
    },
    "cli.pause": {"en": "Press Enter to exit...", "zh": "按回车键退出..."},
    "cli.deprecated_alias": {
        "en": "`{alias}` is deprecated and will be removed in 3.0.0; "
        "use `deepunzip` (or `dz`).",
        "zh": "`{alias}` 已弃用，将在 3.0.0 移除；请使用 `deepunzip`（或 `dz`）。",
    },
    # ---------- errors ----------
    "error.no_input": {
        "en": "None of the given paths exists: {paths}",
        "zh": "给出的路径都不存在：{paths}",
    },
    "error.engine": {"en": "{detail}", "zh": "{detail}"},
    "error.unexpected": {"en": "Unexpected error: {detail}", "zh": "意外错误：{detail}"},
    "error.cancelled": {"en": "Cancelled.", "zh": "已取消。"},
    # ---------- item lines ----------
    "line.opened": {
        "en": "{name}  opened → {files} files{password}",
        "zh": "{name}  已打开 → {files} 个文件{password}",
    },
    "line.assembled": {
        "en": "{name}  {volumes} volumes assembled → {files} files{password}",
        "zh": "{name}  已拼合 {volumes} 卷 → {files} 个文件{password}",
    },
    "line.kept": {
        "en": "{name}  kept (not an archive)",
        "zh": "{name}  已保留（不是压缩包）",
    },
    "line.unresolved": {
        "en": "{name}  unresolved: {reason}",
        "zh": "{name}  未解决：{reason}",
    },
    "line.more": {"en": "… and {count} more", "zh": "…… 另有 {count} 项"},
    "password.index": {"en": " · password #{index}", "zh": " · 密码 #{index}"},
    "password.entered": {"en": " · entered password", "zh": " · 手动输入的密码"},
    # ---------- live progress ----------
    "live.overall": {"en": "Overall", "zh": "总体"},
    "live.archives": {"en": "{done}/{total} archives", "zh": "{done}/{total} 个压缩包"},
    "live.round": {"en": "round {number}", "zh": "第 {number} 轮"},
    "live.current": {"en": "Current", "zh": "当前"},
    # ---------- final tree and summary ----------
    "tree.root": {
        "en": "{root}  {sources} sources → {files} files  {elapsed}",
        "zh": "{root}  {sources} 个原文件 → {files} 个文件  {elapsed}",
    },
    "tree.set": {"en": "{name}  {files} files", "zh": "{name}  {files} 个文件"},
    "tree.volume": {"en": "{volume} ← {source}", "zh": "{volume} ← {source}"},
    "tree.input": {"en": "input folder", "zh": "输入目录"},
    "tree.uncloaked": {"en": "uncloaked from {original}", "zh": "原名 {original}"},
    "tree.unresolved": {
        "en": "{name}: {reason} → {location}",
        "zh": "{name}：{reason} → {location}",
    },
    "tree.in_place": {"en": "kept in place", "zh": "保留在原处"},
    "summary.output": {
        "en": "output: {files} files → {folder}",
        "zh": "输出：{files} 个文件 → {folder}",
    },
    "summary.recycled": {
        "en": "sources: {count} moved to the recycle bin",
        "zh": "原文件：{count} 个已移到回收站",
    },
    "summary.deleted": {
        "en": "sources: {count} deleted",
        "zh": "原文件：{count} 个已删除",
    },
    "summary.kept": {"en": "sources kept: {count}", "zh": "保留的原文件：{count} 个"},
    "summary.work_dir_kept": {
        "en": "work directory kept: {path}",
        "zh": "工作目录已保留：{path}",
    },
    "summary.done": {
        "en": "Done in {elapsed} · exit code {code}",
        "zh": "完成，用时 {elapsed} · 退出码 {code}",
    },
    "summary.passwords_saved": {
        "en": "New passwords saved to {path}",
        "zh": "新密码已保存到 {path}",
    },
    "summary.passwords_failed": {
        "en": "Could not save passwords to {path} ({error}). Check write permissions.",
        "zh": "无法保存密码本 {path}（{error}），请检查写入权限。",
    },
    # ---------- unresolved reasons ----------
    "reason.password": {"en": "wrong or missing password", "zh": "密码错误或缺失"},
    "reason.missing volume": {"en": "missing volume", "zh": "缺少分卷"},
    "reason.unmatched volume": {
        "en": "volume without its set",
        "zh": "找不到所属的分卷组",
    },
    "reason.assembly failed": {
        "en": "volumes do not form a set",
        "zh": "分卷无法组成完整的压缩包",
    },
    "reason.too many combinations": {
        "en": "too many volume combinations",
        "zh": "分卷组合过多",
    },
    "reason.unsupported": {"en": "not a supported archive", "zh": "不支持的压缩格式"},
    "reason.not a valid archive": {"en": "not a valid archive", "zh": "不是有效的压缩包"},
    "reason.empty": {"en": "empty archive", "zh": "空压缩包"},
    "reason.max depth": {"en": "nested too deep", "zh": "嵌套层数过多"},
    "reason.move failed": {"en": "could not move to output", "zh": "无法移到输出目录"},
    "reason.error": {"en": "extraction error", "zh": "解压出错"},
    # ---------- password prompt ----------
    "prompt.title": {
        "en": "No known password opens {name}.",
        "zh": "已知密码都无法打开 {name}。",
    },
    "prompt.choices": {
        "en": "1) enter a password   2) skip this archive   "
        "3) skip all password prompts",
        "zh": "1) 输入密码   2) 跳过此压缩包   3) 跳过所有密码提示",
    },
    "prompt.choose": {"en": "Choose 1/2/3 [2]: ", "zh": "请选择 1/2/3 [2]："},
    "prompt.password": {"en": "Password: ", "zh": "密码："},
    "prompt.invalid": {"en": "Enter 1, 2 or 3.", "zh": "请输入 1、2 或 3。"},
    # ---------- recovery at startup ----------
    "recovery.work_dir": {
        "en": "Work directory left by an interrupted run: {path}",
        "zh": "发现中断运行遗留的工作目录：{path}",
    },
    "recovery.restored": {
        "en": "Restored {count} source volume(s) moved by an interrupted run",
        "zh": "已还原中断运行移动的 {count} 个原始分卷",
    },
    "recovery.pending": {
        "en": "A previous run left {count} rename(s):",
        "zh": "上次运行遗留了 {count} 条改名记录：",
    },
    "recovery.other_root": {
        "en": "These were recorded for another input folder: {root}",
        "zh": "这些记录来自另一个输入目录：{root}",
    },
    "recovery.entry": {"en": "{renamed} → {original}", "zh": "{renamed} → {original}"},
    "recovery.more": {"en": "… and {count} more", "zh": "…… 另有 {count} 条"},
    "recovery.ask": {
        "en": "Revert these renames before starting? (y/N): ",
        "zh": "开始前回滚这些改名吗？(y/N)：",
    },
    "recovery.skipped": {
        "en": "Renames kept; this run overwrites the history file.",
        "zh": "保留改名；本次运行会覆盖历史记录。",
    },
    "recovery.reverted": {
        "en": "Reverted {count} rename(s).",
        "zh": "已回滚 {count} 个改名。",
    },
    "history.reverted": {
        "en": "Reverted {count} rename(s) of kept files",
        "zh": "已回滚 {count} 个保留文件的改名",
    },
    # ---------- notices from library code ----------
    "notice.rename_duplicate": {
        "en": "{name} duplicates {existing}; renamed to {target}",
        "zh": "{name} 与 {existing} 重复，已改名为 {target}",
    },
    "notice.rename_failed": {
        "en": "Could not rename {name}: {error}",
        "zh": "无法重命名 {name}：{error}",
    },
    "notice.path_fallback": {
        "en": "Path problem while extracting {name}; retrying with safe file names",
        "zh": "解压 {name} 时遇到路径问题，改用安全的文件名重试",
    },
    "notice.remove_failed": {"en": "{detail}", "zh": "{detail}"},
    "notice.missing_path": {
        "en": "Path not found, skipped: {path}",
        "zh": "路径不存在，已跳过：{path}",
    },
    "notice.rules_failed": {
        "en": "Could not load the uncloaking rules from {path}: {error}",
        "zh": "无法加载伪装文件规则 {path}：{error}",
    },
    "notice.signature_failed": {
        "en": "Could not check the file signature of {name}: {error}",
        "zh": "无法检查 {name} 的文件签名：{error}",
    },
    "notice.move_failed": {
        "en": "Could not move {name}: {error}",
        "zh": "无法移动 {name}：{error}",
    },
    # ---------- file helper messages (passed to callbacks) ----------
    "file.rename_error": {
        "en": "Error renaming file {old} to {new}: {error}",
        "zh": "重命名文件出错 {old} → {new}：{error}",
    },
    "file.remove_error": {
        "en": "Error removing file {path}: {error}",
        "zh": "删除文件出错 {path}：{error}",
    },
    "file.group_rename_missing": {
        "en": "Could not rename {old} to {new}: the file does not exist. "
        "The group is not updated.",
        "zh": "无法将 {old} 改名为 {new}：文件不存在，分组未更新。",
    },
    "file.moved": {"en": "Moved: {path}", "zh": "已移动：{path}"},
    "file.move_error": {
        "en": "Error moving {path}: {error}",
        "zh": "移动出错 {path}：{error}",
    },
}

_language: Optional[str] = None


def language_from_langid(langid: int) -> str:
    """Map a Windows LANGID to a catalog language."""
    return "zh" if langid & 0x3FF == _LANG_CHINESE else "en"


def posix_language(env: Mapping[str, str]) -> Optional[str]:
    """Language from the first set of LC_ALL, LC_MESSAGES and LANG, or None."""
    for name in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = env.get(name)
        if value:
            return "zh" if value.lower().startswith("zh") else "en"
    return None


def system_language() -> Optional[str]:
    """The operating system's UI language, or None when it cannot be read."""
    if sys.platform == "win32":
        try:
            import ctypes

            windll = getattr(ctypes, "windll")
            return language_from_langid(int(windll.kernel32.GetUserDefaultUILanguage()))
        except (AttributeError, OSError):
            return None
    return posix_language(os.environ)


def resolve_language(
    env: Optional[Mapping[str, str]] = None,
    system_language: Callable[[], Optional[str]] = system_language,
) -> str:
    """DEEPUNZIP_LANG (zh/en) first, then the system UI language, then English."""
    env = os.environ if env is None else env
    override = env.get("DEEPUNZIP_LANG", "").strip().lower()
    if override in LANGUAGES:
        return override
    return system_language() or "en"


def set_language(language: str) -> None:
    global _language
    _language = language if language in LANGUAGES else "en"


def get_language() -> str:
    if _language is None:
        set_language(resolve_language())
    assert _language is not None
    return _language


def t(key: str, **params: object) -> str:
    """The text of `key` in the run's language (English when missing)."""
    entry = CATALOG.get(key)
    if entry is None:
        return key
    text = entry.get(get_language()) or entry["en"]
    return text.format(**params) if params else text
