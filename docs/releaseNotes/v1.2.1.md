# Release Notes v1.2.1 / 发布说明 v1.2.1

A focused patch release fixing two **data-loss** bugs in cloaked-file detection and archive grouping, and **expanding multi-part archive format detection** to all archive types. No breaking changes.

一个聚焦的补丁版本，修复了伪装文件检测和档案分组中的两个**数据丢失**问题，并**将多卷档案格式识别扩展到所有档案类型**。无破坏性更改。

## 🐛 Bug Fixes / 错误修复

### Don't rename ordinary files into bogus archive parts / 不再把普通文件改名成伪造的档案分卷
A plain non-archive file whose name ends in digits (e.g. `2382`) could be renamed into a fake 7z multipart part (`2.7z.382`). It was then swept into a same-named real archive set and **deleted at the end without ever being extracted — losing the user's data**.

Root cause: `_verify_with_signature()` always returned `True`, so the weak extensionless/digit-suffix cloaking rules renamed *any* digit-suffixed file.

The signature gate now distinguishes deliberate cloaking from a guess:
- If the name carries an explicit archive token (`.7z` / `.rar` / `.zip`, via `ARCHIVE_TOKEN_RE`), the rename is trusted — continuation parts legitimately have no signature (e.g. `something.7z.002删除`).
- If the type was only **guessed** from a trailing number, a real magic-byte signature is now **required** before renaming.
- On verification error the tool is now conservative and **skips** the rename instead of assuming the file is valid.

Genuine cloaked first parts and `.7z.00N删` style parts still uncloak correctly.

名字以数字结尾的普通（非档案）文件（例如 `2382`）原先可能被改名成伪造的 7z 分卷（`2.7z.382`），随后被并入同名的真实档案集合，**在结尾被删除却从未解压 —— 导致用户数据丢失**。

根因：`_verify_with_signature()` 永远返回 `True`，导致弱规则（无扩展名 / 尾部数字）会改名**任何**带数字后缀的文件。

签名校验现在区分"有意伪装"与"猜测"：
- 名字中带有显式档案标记（`.7z` / `.rar` / `.zip`，由 `ARCHIVE_TOKEN_RE` 识别）时，信任改名 —— 续卷本来就没有签名（例如 `something.7z.002删除`）。
- 若类型只是从尾部数字**猜测**得到，改名前现在**必须**有真实的魔数签名。
- 校验出错时改为保守处理，**跳过**改名，而不是假定文件有效。

真正的伪装首卷以及 `.7z.00N删` 之类的分卷仍能正确还原。

### Don't merge different archive types that share a base name / 不再合并同名但类型不同的档案
The similarity check in `_should_group_files` ignored the archive extension, so a standalone `.7z` could be swept into a spanned `.zip` / `.z01` group when they shared a base name and directory. The merged multipart group then **deleted the `.7z` along with the zip parts (data loss)** and mishandled the set during extraction.

Fix: the similarity path now requires `ext1 == ext2`, so only same-family archives group that way. `.zip` / `.z01` still group via the exact `(base, ext)` check, and `foo.7z` stays its own single group alongside the `foo.zip` / `foo.z01` set.

`_should_group_files` 的相似度判断忽略了档案扩展名，导致独立的 `.7z` 在与跨卷 `.zip` / `.z01` 同名且同目录时被并入同一组。合并后的多卷组随后**把 `.7z` 连同 zip 分卷一起删除（数据丢失）**，解压时也处理错误。

修复：相似度路径现在要求 `ext1 == ext2`，只有同家族档案才走该路径分组。`.zip` / `.z01` 仍通过精确的 `(base, ext)` 判断分组，而 `foo.7z` 与 `foo.zip` / `foo.z01` 集合并存时保持为独立的单档案组。

## ✨ Improvements / 功能增强

### Expanded multi-part archive format detection / 扩展多卷档案格式识别
Multi-part sets across **all** archive types are now recognized into a single group with the correct primary as the extraction entry point (previously only `.7z.001`, `.tar.*.001`, `.zip`/`.z01`, `.rar`/`.r00`/`.partN.rar` were handled correctly):

- **7-Zip generic numbered split for any base extension** — `name.<ext>.001` / `.002` … (zero-padded, 3+ digits), with `.001` as the entry point. This covers the common `name.zip.001` (produced by 7-Zip's "Split file") as well as `name.rar.001`, `name.iso.001`, and any other `<ext>`. Previously these were split into wrong groups or treated as single archives, leaving continuation parts behind.
- **WinZip ZIPX split** — `name.zipx` + `name.zx01` / `.zx02` … (primary `.zipx`).
- **ARJ multi-volume** — `name.arj` + `name.a01` / `.a02` … (primary `.arj`).
- **ACE multi-volume** — `name.ace` + `name.c00` / `.c01` … (primary `.ace`). **Note:** ACE sets are now grouped/classified correctly, but the bundled 7-Zip **cannot decode ACE**, so extraction still fails and the source parts are retained (never deleted).

Safety is unchanged: source files are deleted only after a **successful** extraction, so an ordinary numbered file that is not actually an archive (e.g. `report.2024.001`) is retained when extraction fails.

现在**所有**档案类型的多卷集合都会被识别为单个分组，并以正确的主卷作为解压入口（此前仅 `.7z.001`、`.tar.*.001`、`.zip`/`.z01`、`.rar`/`.r00`/`.partN.rar` 能被正确处理）：

- **任意扩展名的 7-Zip 通用编号分卷** —— `name.<ext>.001` / `.002` …（补零、3 位及以上），以 `.001` 为入口。覆盖常见的 `name.zip.001`（7-Zip"拆分文件"生成）以及 `name.rar.001`、`name.iso.001` 等任意 `<ext>`。此前这些会被分到错误的组或当成单个档案，导致续卷被遗留。
- **WinZip ZIPX 分卷** —— `name.zipx` + `name.zx01` / `.zx02` …（主卷 `.zipx`）。
- **ARJ 多卷** —— `name.arj` + `name.a01` / `.a02` …（主卷 `.arj`）。
- **ACE 多卷** —— `name.ace` + `name.c00` / `.c01` …（主卷 `.ace`）。**注意：** ACE 集合现在能被正确分组/识别，但捆绑的 7-Zip **无法解码 ACE**，因此解压仍会失败，且源分卷会被保留（绝不删除）。

安全策略不变：仅在解压**成功**后才删除源文件，所以并非真正档案的编号文件（例如 `report.2024.001`）在解压失败时会被保留。

## ✅ Test Coverage / 测试覆盖

### New/Updated Tests / 新增/更新测试
- **Cloaked false-positives** (`TestCloakedFalsePositives`): a plain `2382` file is not detected/renamed, `uncloak_file` leaves a non-archive digit-suffixed file untouched, and a genuine cloaked 7z first part (real magic bytes) still uncloaks to `secret.7z.001`. Two existing `_verify_with_signature` tests were updated to pin the stricter behavior.
- **Grouping guard**: unit (`_should_group_files`) regression that `foo.7z` vs `foo.zip` are not grouped, plus an integration (`create_groups_by_name`) regression asserting `foo.7z` stays a standalone group while `foo.zip` / `.z01` / `.z02` form one spanned set.
- **Multi-part format detection**: a new `test_regex.py` for the pattern catalog, plus `get_archive_base_name`, `_entry_point_priority`, `create_groups_by_name`, nested-continuation, and `ensure_contained_multipart_groups` cases for the generic numbered split and ZIPX/ARJ/ACE formats.

Total: **199 tests pass** (was 163 in v1.2.0, +36 new).

- **伪装误报**（`TestCloakedFalsePositives`）：普通的 `2382` 文件不会被检测/改名；`uncloak_file` 对非档案的数字后缀文件保持原样；而真正的伪装 7z 首卷（带真实魔数）仍会还原为 `secret.7z.001`。两个原有的 `_verify_with_signature` 测试更新为锁定更严格的行为。
- **分组守卫**：单元测试（`_should_group_files`）回归确认 `foo.7z` 与 `foo.zip` 不被分到一组；集成测试（`create_groups_by_name`）回归确认 `foo.7z` 保持独立组，而 `foo.zip` / `.z01` / `.z02` 组成一个跨卷集合。
- **多卷格式识别**：新增 `test_regex.py` 覆盖模式表，以及 `get_archive_base_name`、`_entry_point_priority`、`create_groups_by_name`、嵌套续卷、`ensure_contained_multipart_groups` 针对通用编号分卷与 ZIPX/ARJ/ACE 格式的用例。

总计：**199 个测试通过**（v1.2.0 是 163 个，新增 36 个）。

## 🚀 Migration Notes / 迁移说明

### For Users / 用户须知
- **No breaking changes.**
- Ordinary files whose names happen to end in digits (e.g. `2382`) are no longer mistaken for archive parts, renamed, or deleted — they are left exactly as they are.
- A standalone `.7z` that shares a base name with a spanned `.zip` set is now extracted on its own instead of being deleted with the zip parts.

- **无破坏性更改。**
- 名字恰好以数字结尾的普通文件（例如 `2382`）不再被误认为档案分卷、被改名或被删除 —— 它们保持原样。
- 与跨卷 `.zip` 集合同名的独立 `.7z` 现在会被单独解压，而不会随 zip 分卷一起被删除。
