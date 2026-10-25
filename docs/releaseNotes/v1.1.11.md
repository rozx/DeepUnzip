# Release Notes v1.1.11 / 发布说明 v1.1.11

## 🎉 What's New / 新功能

### Output Path Normalization / 输出路径规范化
Extracted output now flattens *meaningless leading folders* (typically numeric/symbol-only wrapper directories) while preserving meaningful structure.

提取输出现在会扁平化“无意义的前置文件夹”（通常为纯数字/符号的包裹目录），同时保留有意义的目录结构。

**Examples / 示例：**
- `1/aaa.jpg` → `aaa.jpg`
- `1/5555+/222.jpg` → `222.jpg`

### Auto-group Contained Multipart Sets / 自动分组容器内分卷集合
When a container archive extracts a multipart set into the output folder (e.g., `.7z.001`, `.part1.rar`, spanned `.zip`/`.z01`), the tool now auto-creates a multipart group so it can be extracted in the same run.

当容器档案在输出目录中解出分卷集合（例如 `.7z.001`、`.part1.rar`、跨卷 `.zip`/`.z01`）时，工具现在会自动创建分卷组，以便同一次运行中继续提取。

## 🐛 Bug Fixes / 错误修复

### Prevent Source Multipart Deletion on Failure / 提取失败时不再删除源分卷
Multipart extraction failures (missing volumes, wrong password, etc.) no longer risk deleting the original multipart parts. The tool cleans up only tool-created temporary folders and keeps the source volumes for safe retry.

分卷提取失败（缺少分卷、密码错误等）时，不再有误删源分卷的风险。工具仅清理其创建的临时目录，并保留源分卷，便于安全重试。

**Log / 日志：**
- `Retained source multipart parts due to extraction failure 提取失败，保留源分卷`

### Cloaked Rename Collision Handling / 伪装文件重命名冲突处理
If cloaked normalization would rename two different files to the same target name, the tool now resolves the collision by renaming the duplicate to a unique `__duplicate_<token>` name (multipart-aware), preventing extraction failures and preserving sets.

如果“伪装文件规范化”会将两个不同文件重命名为同一个目标名，工具现在会将重复项改名为唯一的 `__duplicate_<token>`（兼容分卷后缀），从而避免提取失败并保留完整集合。

## 🔧 Improvements / 改进

### Better Nested Multipart Robustness / 更稳健的嵌套分卷处理
- During nested extraction, multipart continuation parts are tracked as candidates.
- If a nested multipart primary fails (non-password failure), the tool attempts to locate/move matching continuation parts next to the primary and retries once.
- If it still fails, the tool preserves the primary and gathered parts as outputs for later manual retry.

- 嵌套提取过程中，会将续卷分卷记录为候选。
- 若嵌套分卷主卷提取失败（非密码失败），工具会尝试查找/移动对应续卷到主卷旁边并重试一次。
- 若仍失败，会保留主卷及已收集分卷到输出中，便于后续手动重试。

## ✅ Test Coverage / 测试覆盖

### New/Updated Tests / 新增/更新测试
- Output path normalization rules (flatten only meaningless *leading* folders)
- Multipart retention guardrails on failure
- Contained multipart discovery and grouping behavior
- Cloaked rename collision scenarios

- 输出路径规范化规则（仅扁平化“前置无意义”目录）
- 分卷失败保留的保护逻辑
- 容器内分卷发现与分组行为
- 伪装重命名冲突场景

## 🚀 Migration Notes / 迁移说明

### For Users / 用户须知
- **No breaking changes.**
- Output folder layout may be flatter if the archive contains meaningless wrapper directories.
- Multipart failures are now safer: source parts are retained for retry.

- **无破坏性更改。**
- 若档案包含无意义包裹目录，输出目录结构可能更扁平。
- 分卷失败更安全：源分卷会被保留以便重试。
