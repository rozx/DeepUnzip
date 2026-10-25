# Release Notes v1.2.2 / 发布说明 v1.2.2

A focused patch release fixing two **cloaked-file detection** bugs — one false positive that could corrupt a valid archive into a bogus multipart set, and one false negative that left deeply-cloaked multipart sets unextractable — plus documentation restructuring with a new English README. No breaking changes.

一个聚焦的补丁版本，修复了两个**伪装文件检测**问题 —— 一个是把有效档案误切成伪造多卷集合的误报，另一个是导致深度伪装的多卷集合无法解压的漏报 —— 并重构了文档、新增英文 README。无破坏性更改。

## 🐛 Bug Fixes / 错误修复

### Don't split a valid archive into a bogus multipart part / 不再把有效档案切成伪造的多卷分卷
A lone file that already carries a real archive signature — e.g. an SFX (`MZ` / PE) archive named `jk_20260629_192705` — could be sliced into a fake multipart part `jk_20260629_192.7z.705`. The trailing `705` of an `HHMMSS` timestamp was mistaken for a 7z part number, so a perfectly valid whole archive was renamed into a broken "part" that would never extract.

Root cause: `_verify_with_signature()` never used its `part_number` argument, so any guessed part number was accepted as long as *some* signature was present.

Fix: `_verify_with_signature()` now uses `part_number`. A signature-bearing lone file can only be a whole archive or the **first** volume (`.001`), so any other guessed part number (`.705`, `.382`, …) is refused. Genuine cloaked first parts still uncloak correctly.

一个本身带有真实档案签名的独立文件 —— 例如名为 `jk_20260629_192705` 的自解压（`MZ` / PE）档案 —— 原先可能被切成伪造的多卷分卷 `jk_20260629_192.7z.705`。`HHMMSS` 时间戳末尾的 `705` 被误当成 7z 分卷编号，于是一个完好的整档被改名成了永远无法解压的残缺"分卷"。

根因：`_verify_with_signature()` 从未使用它的 `part_number` 参数，只要存在**任意**签名，任何猜测出来的分卷编号都会被接受。

修复：`_verify_with_signature()` 现在会使用 `part_number`。带签名的独立文件只可能是整档或**首卷**（`.001`），因此任何其他猜测出的分卷编号（`.705`、`.382` 等）都会被拒绝。真正的伪装首卷仍能正确还原。

### Recover multipart parts with cloaking embedded inside the extension / 还原扩展名内部被插入伪装字符的多卷分卷
Cloaking characters embedded *inside* the extension or the part digits — such as `12.7z.0删02` or `1.part2.r删ar` — could not be matched by the flat rename rules, which only strip trailing garbage. Those parts stayed cloaked, so the multipart set was incomplete and **could not be extracted**.

Fix: added `uncloak_archive_filename`, which reuses the flexible archive-name reconstructor as a fallback. It fires **only** when the rebuilt name is an unambiguous multipart/volume form (e.g. `12.7z.002`, `1.part2.rar`), so ordinary files are never renamed into bogus parts.

被插入到扩展名或分卷数字**内部**的伪装字符 —— 例如 `12.7z.0删02` 或 `1.part2.r删ar` —— 无法被只能去除尾部垃圾的扁平改名规则匹配。这些分卷保持伪装状态，导致多卷集合不完整、**无法解压**。

修复：新增 `uncloak_archive_filename`，复用灵活的档案名重建器作为回退方案。它**仅**在重建出的名字是明确的多卷/分卷形式（例如 `12.7z.002`、`1.part2.rar`）时才生效，因此普通文件绝不会被改名成伪造的分卷。

### Safety boundary preserved / 安全边界不变
The stricter checks do not weaken existing behavior: a genuine cloaked first part (`secret001` with real magic bytes) still uncloaks to `secret.7z.001`, while non-archive files are left exactly as they are — `2382` is not renamed into `2.7z.382`, and `chapter.part2.data` (a `.data` file that merely contains `part2`) is not renamed into a `.rar` part.

更严格的检查不会削弱已有行为：真正的伪装首卷（带真实魔数的 `secret001`）仍会还原为 `secret.7z.001`；而非档案文件保持原样 —— `2382` 不会被改名成 `2.7z.382`，`chapter.part2.data`（仅名字里含 `part2` 的 `.data` 文件）也不会被改名成 `.rar` 分卷。

## 📖 Documentation / 文档

### English README + restructured docs / 新增英文 README 并重构文档
Added a standalone English `README.en.md` and restructured the main `README.md` so both language versions stay in sync and are easier to navigate.

新增独立的英文 `README.en.md`，并重构主 `README.md`，使中英文两个版本保持同步、更易浏览。

## ✅ Test Coverage / 测试覆盖

### New/Updated Tests / 新增/更新测试
- **Signature false positive** (`test_signature_bearing_file_with_timestamp_suffix_not_split`): a signature-bearing lone file whose name ends in a timestamp is not sliced into a fake `.7z.705` part.
- **Embedded-garbage recovery** (`TestCloakedEmbeddedGarbage`): `12.7z.0删02` uncloaks to `12.7z.002`, while a non-archive `chapter.part2.data` that merely contains the word `part2` is left untouched.

Total: **207 tests pass** (was 199 in v1.2.1, +8 new).

- **签名误报**（`test_signature_bearing_file_with_timestamp_suffix_not_split`）：名字以时间戳结尾且带签名的独立文件不会被切成伪造的 `.7z.705` 分卷。
- **内部伪装还原**（`TestCloakedEmbeddedGarbage`）：`12.7z.0删02` 还原为 `12.7z.002`，而仅名字里含 `part2` 的非档案 `chapter.part2.data` 保持原样。

总计：**207 个测试通过**（v1.2.1 是 199 个，新增 8 个）。

## 🚀 Migration Notes / 迁移说明

### For Users / 用户须知
- **No breaking changes.**
- Whole archives whose names end in a timestamp or trailing digits (e.g. an SFX file `jk_20260629_192705`) are no longer mis-split into broken parts, so they extract correctly.
- Multipart sets whose parts had cloaking characters buried inside the extension (e.g. `12.7z.0删02`) are now recovered and extracted instead of being left behind.

- **无破坏性更改。**
- 名字以时间戳或尾部数字结尾的整档（例如自解压文件 `jk_20260629_192705`）不再被误切成残缺分卷，能够正确解压。
- 分卷的扩展名内部藏有伪装字符的多卷集合（例如 `12.7z.0删02`）现在会被还原并解压，而不再被遗留。
