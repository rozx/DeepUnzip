# Release Notes v1.1.10 / 发布说明 v1.1.10

## 🎉 What's New / 新功能

### Enhanced Retry Extraction with User Passwords / 增强的重试提取与用户密码支持
The tool now supports a comprehensive retry extraction mechanism that can handle user-provided passwords and intelligently manage extraction results.

工具现在支持全面的重试提取机制，可以处理用户提供的密码并智能管理提取结果。

**Highlights / 亮点：**
- User-provided passwords are now supported during retry extraction attempts.
- Extracted files from retry operations are automatically moved to the output folder with progress tracking.
- Original archives are preserved when extraction fails due to password issues.
- Temporary folders are cleaned up after extraction attempts.

- 重试提取期间现在支持用户提供的密码。
- 重试操作的提取文件会自动移动到输出文件夹，并带有进度跟踪。
- 当由于密码问题导致提取失败时，原始档案会被保留。
- 提取尝试后临时文件夹会被清理。

### Improved Nested Archive Preservation / 改进的嵌套档案保留
When nested archive extraction fails due to password issues, the tool now intelligently preserves the original nested archives instead of deleting them, allowing users to retry with correct passwords later.

当嵌套档案提取由于密码问题失败时，工具现在会智能地保留原始嵌套档案而不是删除它们，允许用户稍后使用正确的密码重试。

## 🐛 Bug Fixes / 错误修复

### 1. Fixed Incomplete Error Reporting / 修复不完整的错误报告
**Issue / 问题:** Error summaries were limited to showing only the first few errors, making it difficult to diagnose issues when multiple archives failed.

错误摘要仅显示前几个错误，使得在多个档案失败时难以诊断问题。

**Fix / 修复:** Updated error reporting functions to display all encountered errors without limiting the output, providing complete diagnostic information.

更新了错误报告函数，显示所有遇到的错误而不限制输出，提供完整的诊断信息。

**Affected functions / 受影响的函数:**
- `print_final_completion()` - Now shows all completion errors
- `print_error_summary()` - Now displays all error details

### 2. Enhanced Archive Deletion Logic / 增强的档案删除逻辑
**Issue / 问题:** Original archives were sometimes deleted even when extraction failed due to password issues, making it impossible to retry.

即使由于密码问题导致提取失败，原始档案有时也会被删除，使得无法重试。

**Fix / 修复:** Added intelligent logic to determine whether original archives should be deleted based on extraction results. Archives are now preserved when extraction fails due to password authentication issues.

添加了智能逻辑，根据提取结果确定是否应删除原始档案。当由于密码身份验证问题导致提取失败时，档案现在会被保留。

## 🔧 Improvements / 改进

### Comprehensive Password Handling / 全面的密码处理
- Passwords from both destination folder and tool root directory are now combined automatically.
- User-provided passwords during retry extraction are properly tracked and used.
- Better error messages when password authentication fails.

- 目标文件夹和工具根目录的密码现在会自动合并。
- 重试提取期间的用户提供的密码会被正确跟踪和使用。
- 密码身份验证失败时提供更好的错误消息。

### Enhanced Error Diagnostics / 增强的错误诊断
- Archive extraction functions now consider both stdout and stderr for comprehensive error detection.
- More detailed error information helps users understand why extraction failed.

- 档案提取函数现在考虑 stdout 和 stderr 以进行全面的错误检测。
- 更详细的错误信息帮助用户理解提取失败的原因。

### Improved Cleanup Process / 改进的清理过程
- Temporary folders created during extraction are now cleaned up more reliably.
- Files from retry operations are properly moved to the output folder with progress feedback.

- 提取期间创建的临时文件夹现在更可靠地被清理。
- 重试操作的文件会正确移动到输出文件夹，并带有进度反馈。

## 📝 Documentation Updates / 文档更新

### README.md Enhancements / README.md 增强内容
- Expanded password file handling section with multiple search locations.
- Clarified how passwords from different locations are combined.
- Updated examples to reflect the new password handling capabilities.

- 扩展了密码文件处理部分，包含多个搜索位置。
- 阐明了不同位置的密码如何合并。
- 更新了示例以反映新的密码处理功能。

**Key additions / 主要新增内容:**
- Passwords can now be placed in both destination folder and tool root directory.
- All found password files are combined automatically.
- Clear examples showing password file placement.

- 密码现在可以放在目标文件夹和工具根目录中。
- 所有找到的密码文件会自动合并。
- 清晰的示例显示密码文件的放置位置。

## ✅ Test Coverage / 测试覆盖

### New Tests / 新增测试
- Added tests for retry extraction with user-provided passwords.
- Tests for archive preservation logic when extraction fails.
- Enhanced error reporting tests to verify all errors are displayed.
- Tests for temporary folder cleanup after extraction attempts.

- 添加了使用用户提供的密码进行重试提取的测试。
- 提取失败时档案保留逻辑的测试。
- 增强的错误报告测试，验证显示所有错误。
- 提取尝试后临时文件夹清理的测试。

### Validation / 验证
- ✅ All existing tests continue to pass
- ✅ New retry extraction functionality tested with various password scenarios
- ✅ Error reporting verified to show all encountered errors
- ✅ Archive preservation logic tested with password failures

- ✅ 所有现有测试继续通过
- ✅ 新的重试提取功能在各种密码场景下进行了测试
- ✅ 错误报告经验证显示所有遇到的错误
- ✅ 档案保留逻辑在密码失败情况下进行了测试

## ⚙️ Technical Details / 技术细节

### Modified Files / 修改的文件

#### `complex_unzip_tool_v2/main.py`
- Added retry extraction logic with user password support (189 lines added)
- Implemented file movement from retry results to output folder
- Added intelligent archive deletion logic based on extraction results
- Enhanced error handling for nested archive extraction
- Added temporary folder cleanup after extraction attempts

- 添加了带有用户密码支持的重试提取逻辑（新增 189 行）
- 实现了从重试结果到输出文件夹的文件移动
- 添加了基于提取结果的智能档案删除逻辑
- 增强了嵌套档案提取的错误处理
- 添加了提取尝试后的临时文件夹清理

#### `complex_unzip_tool_v2/modules/archive_utils.py`
- Enhanced error handling to consider both stdout and stderr
- Improved diagnostic information for archive extraction failures
- Better support for password-related error detection

- 增强了错误处理，考虑 stdout 和 stderr
- 改进了档案提取失败的诊断信息
- 更好地支持密码相关错误检测

#### `complex_unzip_tool_v2/modules/rich_utils.py`
- Updated `print_final_completion()` to show all errors
- Updated `print_error_summary()` to display complete error information
- Removed conditional messages that limited error display

- 更新了 `print_final_completion()` 以显示所有错误
- 更新了 `print_error_summary()` 以显示完整的错误信息
- 删除了限制错误显示的条件消息

#### `README.md`
- Expanded password management section with multiple location support
- Added clear examples for password file placement
- Updated usage examples to reflect new capabilities

- 扩展了密码管理部分，支持多个位置
- 添加了密码文件放置的清晰示例
- 更新了使用示例以反映新功能

#### Test Files / 测试文件
- `tests/test_archive_utils.py` - Added 43 lines of new tests
- `tests/test_main.py` - Added 15 lines of new tests

### Code Statistics / 代码统计
- **Total changes / 总更改:** 403 insertions(+), 93 deletions(-)
- **Files modified / 修改的文件:** 9 files
- **Test additions / 测试新增:** 58 lines of new tests

## 🚀 Migration Notes / 迁移说明

### For Users / 用户须知
**No breaking changes.** All existing functionality is preserved and enhanced.

**无破坏性更改。** 所有现有功能都被保留和增强。

**New benefits / 新优势:**
- More reliable extraction when password issues occur
- Complete error information for better troubleshooting
- Automatic cleanup of temporary files
- Better handling of nested archives with password protection

- 当出现密码问题时提取更可靠
- 完整的错误信息以便更好地排除故障
- 自动清理临时文件
- 更好地处理受密码保护的嵌套档案

### For Developers / 开发者须知
**API Changes / API 更改:**
- Error reporting functions now display all errors by default (no longer limited)
- Archive extraction error handling now considers both stdout and stderr
- New helper function added for determining archive deletion logic

- 错误报告函数现在默认显示所有错误（不再受限）
- 档案提取错误处理现在考虑 stdout 和 stderr
- 添加了用于确定档案删除逻辑的新辅助函数

**If you maintain custom code / 如果您维护自定义代码:**
- Review error handling logic if you relied on limited error display
- Update any custom extraction flows to handle the new retry mechanism
- Consider the new archive preservation behavior in your workflows

- 如果您依赖受限的错误显示，请审查错误处理逻辑
- 更新任何自定义提取流程以处理新的重试机制
- 在您的工作流程中考虑新的档案保留行为

## 🎯 Performance Impact / 性能影响

- **Retry extraction / 重试提取:** Minimal overhead, only triggered when needed
- **Error reporting / 错误报告:** Slightly increased output for comprehensive diagnostics
- **Cleanup operations / 清理操作:** Improved efficiency with better temporary folder management

- **重试提取：** 最小开销，仅在需要时触发
- **错误报告：** 输出略微增加，以提供全面的诊断
- **清理操作：** 通过更好的临时文件夹管理提高了效率

## 🙏 Acknowledgments / 致谢

Special thanks to all users who provided feedback on password handling and error reporting!

特别感谢所有就密码处理和错误报告提供反馈的用户！

---

**Full Changelog:** [v1.1.8...v1.1.10](https://github.com/rozx/Complex-unzip-tool-v2/compare/v1.1.8...v1.1.10)

**完整变更日志：** [v1.1.8...v1.1.10](https://github.com/rozx/Complex-unzip-tool-v2/compare/v1.1.8...v1.1.10)
