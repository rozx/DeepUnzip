# Release Notes v1.1.8 / 发布说明 v1.1.8

## 🎉 What's New / 新功能

### Continuation Parts Relocation from Nested Containers / 从嵌套容器中重定位分卷续档
When an outer archive contains parts of a multipart set (e.g., a .zip holding `MySet.7z.002`), the tool now relocates those continuation parts next to their multipart set before attempting the multipart extraction. This guarantees the set is complete when extraction begins.

当外层档案包含多部分档案的续档（例如 .zip 内含 `MySet.7z.002`）时，工具会在尝试多部分提取前，将这些续档移动到对应的多部分集旁边，确保在开始提取时分卷齐全。

**Highlights / 亮点：**
- Continuation parts found during nested extraction are no longer lost with temp cleanup—they are moved to the correct group (if possible).
- Primary parts are still the only ones considered for recursive nested extraction.
- A safety-net reconciliation pass scans the output folder to relocate any remaining parts before multipart extraction.

- 在嵌套提取过程中发现的续档不再随临时清理丢失——若可能，将移动到正确的分组目录。
- 递归嵌套提取仍仅针对主分卷执行。
- 在多部分提取前，会对输出目录执行一次兜底扫描，将尚未移动到位的续档重定位。

## 🐛 Bug Fixes / 错误修复

### Fix: Multipart extraction failing when a part was inside another container / 修复：当分卷在其他容器中时多部分提取失败
**Issue / 问题：** If one of the multipart volumes existed inside another archive, the tool didn’t place it next to the set before attempting extraction, causing missing-volume errors.

如果某个分卷存在于另一个档案内，工具在开始提取前没有将它放到多部分集旁边，导致缺失分卷错误。

**Fix / 修复：** Added a relocation callback to nested extraction that moves continuation parts into the correct multipart group directory immediately. Also added a reconciliation pass after single-archive extraction to relocate any parts that landed in the output folder.

在嵌套提取中新增重定位回调，立即将续档移动到对应的多部分组目录；并在单一档案提取结束后新增一次对输出目录的兜底扫描，重定位落在输出目录中的续档。

## 🔧 Improvements / 改进

- Optional `group_relocator` callback in nested extraction to handle continuation parts discovered inside containers.
- Output-folder reconciliation step ensures multipart sets are complete before extraction begins.
- Clearer CLI messages (English/Chinese) showing when continuation parts are relocated.

- 在嵌套提取中新增可选 `group_relocator` 回调，用于处理在容器中发现的续档。
- 新增输出目录的兜底扫描步骤，确保开始多部分提取前分卷齐全。
- 更清晰的 CLI 提示（中英文），在续档被移动时给出明确反馈。

## 📝 Documentation Updates / 文档更新

- Updated `AGENTS.md` with the new nested multipart relocation behavior and the reconciliation pass.
- Documented how continuation parts are identified and handled across formats (7z, RAR, ZIP, TAR.*).

- 更新了 `AGENTS.md`，说明新增的嵌套续档重定位行为与兜底扫描步骤。
- 文档化了不同格式（7z、RAR、ZIP、TAR.*）的续档识别与处理方式。

## ✅ Test Coverage / 测试覆盖

- Added unit tests ensuring continuation parts found during nested extraction are relocated via the callback (or skipped) and do not leak into `final_files`.
- Full test suite passes locally.

- 新增单元测试，确保嵌套提取中发现的续档会通过回调被重定位（或被跳过），且不会泄漏到 `final_files`。
- 本地完整测试套件全部通过。

## ⚙️ Technical Details / 技术细节

### Modified Files / 修改的文件
- `complex_unzip_tool_v2/modules/archive_utils.py`
  - Added optional `group_relocator` to `extract_nested_archives()` and used it when encountering continuation parts during nested scanning.
- `complex_unzip_tool_v2/main.py`
  - Wired `group_relocator` to reuse `file_utils.add_file_to_groups` and added a reconciliation step after single-archive extraction.
- `complex_unzip_tool_v2/modules/file_utils.py`
  - Added `relocate_multipart_parts_from_directory(source_root, groups)` to scan output folder and relocate parts into their group directories.
  - Kept strict base-name matching semantics to avoid cross-group misclassification.
- `tests/test_archive_utils.py`
  - Added tests: continuation parts are relocated via callback and not included in `final_files`; skipped when not relocated.
- `AGENTS.md`
  - Documented the new relocation and reconciliation behavior.

### Validation / 验证
- ✅ CLI verified on a sample real-world directory (e.g., `E:\testDir - Copy`).
- ✅ 102 unit tests passing locally.

- ✅ 在真实目录（例如 `E:\\testDir - Copy`）中验证。
- ✅ 本地 102 个单元测试全部通过。

## 🚀 Migration Notes / 迁移说明

### For Users / 用户须知
No breaking changes. The tool will more reliably extract multipart archives when some parts are inside containers.

无破坏性变化。当部分分卷位于容器内时，工具将更可靠地完成多部分提取。

### For Developers / 开发者须知
- `extract_nested_archives()` now accepts an optional `group_relocator` parameter. Existing calls continue to work (parameter is optional).
- If you maintain custom extraction flows, consider wiring a relocator to ensure continuation parts found in nested contexts are handled immediately.

- `extract_nested_archives()` 现已支持可选参数 `group_relocator`。现有调用无需修改（该参数是可选的）。
- 若维护自定义提取流程，建议接入重定位逻辑，以便及时处理嵌套环境中发现的续档。

---

**Full Changelog:** [v1.1.7...v1.1.8](https://github.com/rozx/Complex-unzip-tool-v2/compare/v1.1.7...v1.1.8)

**完整变更日志：** [v1.1.7...v1.1.8](https://github.com/rozx/Complex-unzip-tool-v2/compare/v1.1.7...v1.1.8)
