# Release Notes v1.2.0 / 发布说明 v1.2.0

## 🎉 What's New / 新功能

### Rename History with Revert-on-Failure / 重命名历史与失败回滚
The cloaked-file detector renames source files in-place (e.g. `1525.zip(1).001` → `1525.7z.001`) before extraction begins. Previously, when extraction later failed (wrong password, corruption, missing volume, crash), users were left with files whose names no longer matched what they originally downloaded — making manual recovery difficult.

This release introduces a `RenameHistory` system that:
- Tracks every successful uncloak rename to a JSON file in the input directory.
- Binds each rename to its owning archive group after grouping.
- **Reverts** the renames for any group whose extraction is preserved (failed / password-skipped / exception).
- **Clears** the history for any group whose originals are deleted (success path).
- **Survives crashes**: if the program is killed mid-run, the JSON file is left on disk; the next run detects it and offers `[y/N]` recovery.

伪装文件检测器在解压开始之前会就地重命名源文件（例如 `1525.zip(1).001` → `1525.7z.001`）。之前如果之后解压失败（密码错、损坏、分卷缺失、崩溃），用户面对的就是被改过名的文件，无法识别原始文件——手动恢复非常困难。

本版本引入 `RenameHistory` 系统：
- 每次成功 uncloak 改名都记录到输入目录下的 JSON 文件。
- 分组后将每条改名绑定到对应档案组。
- 对任何**保留原档**的组（失败 / 密码跳过 / 异常）—— **回滚**改名。
- 对任何**删除原档**的组（成功路径）—— **清除**历史条目。
- **崩溃可恢复**：程序中途被杀，JSON 文件留在磁盘上；下次运行检测到并提示 `[y/N]` 恢复。

**Log examples / 日志示例：**
```
⚠ Reverted 3 rename(s) for testDir-1525 已回滚 3 个改名:
    1525.7z.001 → 1525.zip(1).001
    ...
⚠ Detected pending rename history from a previous run
   检测到上次运行遗留的改名记录: 5 entries
```

## 🐛 Bug Fixes / 错误修复

### Spanned ZIP / Volume RAR Multipart Grouping / 跨卷 ZIP 与多卷 RAR 分组
Spanned ZIP sets (`.zip + .z01 + .z02`) and volume RAR sets (`.rar + .r00 + .r01`) were being grouped inconsistently and the main archive was set to the continuation part (`.z01` / `.r00`), causing 7-Zip to fail because extraction must be invoked on the `.zip` / `.rar` entry point.

Three root causes fixed:
- **`get_archive_base_name`** now maps continuation suffixes (`.zNN`, `.rNN`, `.partN.rar`) to their family extension (`zip` / `rar`), so all parts of a set share the same `(base, ext)` tuple and are properly grouped.
- **`MULTI_PART_PATTERNS`** in `const.py` now includes `.partN.rar`, `.rNN`, `.zNN` patterns.
- **`ArchiveGroup.add_file`** now selects the main archive by entry-point priority (`.7z.001` / `.partN.rar` = 100, `.zip` / `.rar` = 90, continuations = 0) regardless of insertion order. This guarantees the spanned `.zip` (not `.z01`) and volume `.rar` (not `.r00`) are always the main archive, so 7-Zip is invoked on the correct entry point.

跨卷 ZIP 集合（`.zip + .z01 + .z02`）和多卷 RAR 集合（`.rar + .r00 + .r01`）原先分组不一致，主档案会被设成续卷（`.z01` / `.r00`），导致 7-Zip 失败 —— 因为提取必须从 `.zip` / `.rar` 入口开始。

修复了三个根因：
- **`get_archive_base_name`** 把续卷后缀（`.zNN`、`.rNN`、`.partN.rar`）映射到家族扩展名（`zip` / `rar`），让同一集合所有分卷共享相同的 `(base, ext)`，正确归组。
- **`MULTI_PART_PATTERNS`** 增加 `.partN.rar`、`.rNN`、`.zNN` 模式。
- **`ArchiveGroup.add_file`** 按"入口点优先级"选主档案（`.7z.001` / `.partN.rar` = 100，`.zip` / `.rar` = 90，续卷 = 0），无论加入顺序，跨卷 `.zip`（不是 `.z01`）和多卷 `.rar`（不是 `.r00`）总是作为主档案，确保 7-Zip 调用正确入口。

## ✅ Test Coverage / 测试覆盖

### New/Updated Tests / 新增/更新测试
- **24 unit tests** for `RenameHistory`: record/bind/revert/clear/finalize/load_pending, atomic write, collision-safe revert.
- **4 integration tests** in `test_main.py`: revert-on-failure, clear-on-success, recovery prompt accept (`y`), recovery prompt decline (`n`).
- **13 regression tests** for spanned ZIP / volume RAR grouping covering family extension mapping, ordered main-archive selection, and end-to-end `create_groups_by_name` scenarios.

Total: **163 tests pass** (was 122 in v1.1.11, +41 new).

- `RenameHistory` 的 24 个单元测试：record/bind/revert/clear/finalize/load_pending、原子写入、冲突安全回滚。
- `test_main.py` 的 4 个集成测试：失败回滚、成功清除、恢复提示接受 `y`、恢复提示拒绝 `n`。
- 跨卷 ZIP / 多卷 RAR 分组的 13 个回归测试，覆盖家族扩展名映射、有序主档案选择、`create_groups_by_name` 端到端场景。

总计：**163 个测试通过**（v1.1.11 是 122 个，新增 41 个）。

## 🚀 Migration Notes / 迁移说明

### For Users / 用户须知
- **No breaking changes.**
- A new file `.unzip-rename-history.tmp.json` may appear in your input directory **only while a run is in progress**. It is automatically deleted when the run completes cleanly. If you see it after a crash or Ctrl+C, the next run will offer to revert pending renames; you can also delete it manually.
- Spanned ZIP / volume RAR sets that previously failed due to wrong main-archive selection should now extract correctly without manual intervention.
- If a group fails to extract, you'll see a `Reverted N rename(s)` message and the source files will be back to their original cloaked names — making manual recovery straightforward.

- **无破坏性更改。**
- 输入目录中**只在运行过程中**可能出现新文件 `.unzip-rename-history.tmp.json`，正常完成时自动删除。如果在崩溃或 Ctrl+C 后看到它，下次运行会提示是否回滚待恢复的改名；你也可以手动删除。
- 之前因主档案选错而失败的跨卷 ZIP / 多卷 RAR 集合，现在应当无需手动介入即可正确解压。
- 若某组提取失败，会看到 `Reverted N rename(s)` 信息，源文件被恢复为原始的伪装名 —— 手动处理更直观。
