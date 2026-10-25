# Release Notes v1.1.7 / 发布说明 v1.1.7

## 🎉 What's New / 新功能

### Nested Multipart Archive Handling / 嵌套多部分档案处理
When extracting archives that contain multipart archives (e.g., a .7z file containing another multipart set), the tool now intelligently filters continuation parts to prevent them from cluttering your output directory.

当提取包含多部分档案的档案时（例如，一个包含另一个多部分集的 .7z 文件），工具现在会智能地过滤续档部分，以防止它们污染输出目录。

**Example / 示例:**
- Input: `outer.7z` contains `archive.7z.001`, `archive.7z.002`, `archive.7z.003`
- Previous behavior: All parts moved to output folder
- New behavior: Only extracts `archive.7z.001`, continuation parts are cleaned up automatically

- 输入：`outer.7z` 包含 `archive.7z.001`、`archive.7z.002`、`archive.7z.003`
- 之前的行为：所有部分移动到输出文件夹
- 新行为：仅提取 `archive.7z.001`，续档部分自动清理

## 🐛 Bug Fixes / 错误修复

### 1. Fixed Incorrect Renaming of Proper Archive Names / 修复了正确档案名称的错误重命名
**Issue / 问题:** Files with already-correct multipart extensions (like `.7z.001`, `.r00`, `.z01`) were being renamed incorrectly.

已经具有正确多部分扩展名的文件（如 `.7z.001`、`.r00`、`.z01`）被错误地重命名。

**Fix / 修复:** Added safety guards to the uncloaking system to skip files that already have proper archive extensions.

在揭示系统中添加了安全防护，跳过已经具有正确档案扩展名的文件。

**Protected formats / 受保护的格式:**
- Multipart: `.7z.001`, `.7z.002`, `.r00`, `.r01`, `.z01`, `.z02`, `.part1.rar`, `.part2.rar`, `.tar.gz.001`, etc.
- Single: `.7z`, `.rar`, `.zip`, `.tar`, `.tgz`, `.tbz2`, `.gz`, `.bz2`, `.xz`, `.iso`, etc.

### 2. Fixed Password Loading from Target Directory / 修复了从目标目录加载密码的问题
**Issue / 问题:** Passwords in `passwords.txt` were not being loaded correctly, especially when containing Chinese characters.

`passwords.txt` 中的密码未正确加载，尤其是包含中文字符时。

**Fix / 修复:** Enhanced password file reading with multi-encoding support and proper BOM handling.

增强了密码文件读取功能，支持多种编码和正确的 BOM 处理。

**Supported encodings / 支持的编码:**
- UTF-8 (with/without BOM)
- GBK, GB2312, Big5
- UTF-16 (LE/BE)

**Password sources / 密码来源:**
1. Target directory: `passwords.txt` in the extraction directory
2. Tool root: `passwords.txt` at the repository root

1. 目标目录：提取目录中的 `passwords.txt`
2. 工具根目录：存储库根目录中的 `passwords.txt`

### 3. Fixed False "Corrupted Archive" Errors for Regular Files / 修复了常规文件的虚假"损坏档案"错误
**Issue / 问题:** Non-archive files (e.g., `.mp4`, `.txt`) encountered during nested extraction were incorrectly reported as corrupted archives.

在嵌套提取过程中遇到的非档案文件（例如 `.mp4`、`.txt`）被错误地报告为损坏的档案。

**Fix / 修复:** Improved 7-Zip error message mapping to correctly distinguish between corrupted archives and non-archive files.

改进了 7-Zip 错误消息映射，以正确区分损坏的档案和非档案文件。

**Behavior / 行为:**
- Files are still probed with 7-Zip (no pre-filtering)
- "Can not open file as archive" → Treated as non-archive (skipped silently)
- "Data error" / "CRC failed" → Treated as corrupted archive (error reported)

- 文件仍然使用 7-Zip 探测（无预过滤）
- "Can not open file as archive" → 视为非档案（静默跳过）
- "Data error" / "CRC failed" → 视为损坏的档案（报告错误）

## 🔧 Improvements / 改进

### Enhanced Multipart Detection / 增强的多部分检测
The tool now recognizes and properly handles these multipart formats during nested extraction:

工具现在可以在嵌套提取期间识别并正确处理这些多部分格式：

- **7-Zip volumes / 7-Zip 卷:** `.7z.001` (primary), `.7z.002+` (continuations)
- **RAR volumes / RAR 卷:** `.rar` or `.part1.rar` (primary), `.r00`, `.r01+`, `.part2+.rar` (continuations)
- **ZIP spanned / ZIP 分卷:** `.zip` (primary), `.z01`, `.z02+` (continuations)
- **TAR multipart / TAR 多部分:** `.tar.gz.001`, `.tar.bz2.001`, `.tar.xz.001` (primary), `.002+` (continuations)

### Robust Password Handling / 健壮的密码处理
- Automatic encoding detection for international characters
- BOM (Byte Order Mark) stripping
- Empty line and whitespace handling
- UTF-8 output for saved passwords

- 国际字符的自动编码检测
- BOM（字节顺序标记）剥离
- 空行和空白处理
- 保存密码的 UTF-8 输出

## 📝 Documentation Updates / 文档更新

### AGENTS.md Additions / AGENTS.md 新增内容
- Passwords handling section with encoding details
- Renaming/Uncloaking rules with safety guards
- Nested multipart handling behavior
- Non-archive handling during nested scan

- 密码处理部分，包含编码详细信息
- 重命名/揭示规则，包含安全防护
- 嵌套多部分处理行为
- 嵌套扫描期间的非档案处理

### Test Coverage / 测试覆盖
Added comprehensive unit tests for:
- Multipart continuation filtering
- Password encoding robustness
- Non-archive error mapping
- Proper archive name protection

为以下内容添加了全面的单元测试：
- 多部分续档过滤
- 密码编码鲁棒性
- 非档案错误映射
- 正确的档案名称保护

## ⚙️ Technical Details / 技术细节

### Modified Files / 修改的文件
- `complex_unzip_tool_v2/modules/archive_utils.py`
  - Enhanced `_raise_for_7z_error()` for non-archive detection
  - Added continuation part filtering in `extract_nested_archives()`
  - Improved `_parse7zListOutput()` robustness

- `complex_unzip_tool_v2/modules/cloaked_file_detector.py`
  - Added safety guards in `detect_cloaked_file()`
  - Skip renaming for proper multipart and single archive extensions

- `complex_unzip_tool_v2/classes/PasswordBook.py`
  - Multi-encoding support in `load_passwords()`
  - UTF-8 encoding in `save_passwords()`

- `complex_unzip_tool_v2/modules/password_util.py`
  - Variable naming cleanup (avoid shadowing)

- `tests/test_archive_utils.py`
  - New tests for non-archive handling
  - New tests for error message mapping

- `tests/test_cloaked_file_detector.py`
  - Tests for safety guard behavior

### Validation / 验证
- ✅ All 100 unit tests passing
- ✅ CLI smoke tests successful
- ✅ Real-world directory testing (E:\testDir, E:\testDir2 - Copy)
- ✅ Chinese password handling verified

- ✅ 所有 100 个单元测试通过
- ✅ CLI 冒烟测试成功
- ✅ 真实世界目录测试（E:\testDir、E:\testDir2 - Copy）
- ✅ 中文密码处理已验证

## 🚀 Migration Notes / 迁移说明

### For Users / 用户须知
No action required. All changes are backward compatible and improve existing functionality.

无需操作。所有更改都向后兼容并改进了现有功能。

### For Developers / 开发者须知
If you have custom code that:
- Relies on specific error types from archive operations, review the new `ArchiveUnsupportedError` usage for non-archives
- Manipulates archive filenames, check the new safety guards in uncloaking rules

如果您有自定义代码：
- 依赖于档案操作的特定错误类型，请查看非档案的新 `ArchiveUnsupportedError` 使用情况
- 操作档案文件名，请检查揭示规则中的新安全防护

## 🙏 Acknowledgments / 致谢

Special thanks to all users who reported issues and helped test these fixes!

特别感谢所有报告问题并帮助测试这些修复的用户！

---

**Full Changelog:** [v1.1.6...v1.1.7](https://github.com/rozx/Complex-unzip-tool-v2/compare/v1.1.6...v1.1.7)

**完整变更日志：** [v1.1.6...v1.1.7](https://github.com/rozx/Complex-unzip-tool-v2/compare/v1.1.6...v1.1.7)
