# Release Notes v1.3.1 / 发布说明 v1.3.1

Version 1.3.1 stops executables, documents and app packages inside archives from being unpacked and deleted, and makes nested-archive cleanup recoverable. It also adds `#` comments to `passwords.txt`, stops readme files and other non-archives from being reported as errors, and accepts command-line options after the input paths.

1.3.1 修复了档案内的可执行文件、文档和程序包被误解压并删除的问题，并让嵌套档案的清理可以恢复。同时支持在 `passwords.txt` 中使用 `#` 注释，说明文件等非档案不再报错，命令行选项也可以写在输入路径之后。

## New Features / 新功能

### Comments in `passwords.txt` / `passwords.txt` 支持注释 — [#22](https://github.com/rozx/Complex-unzip-tool-v2/issues/22)

Lines starting with `#` are now comments and are not tried as passwords. When newly learned passwords are saved, they are appended to the existing file, so comments, blank lines and the original order are kept.

A password that really starts with `#` is written with a leading backslash: `\#abc` means the password `#abc`. Passwords learned during a run are escaped this way automatically. **When upgrading**, check `passwords.txt` for passwords that start with `#`: they are now read as comments until you add the backslash.

以 `#` 开头的行现在视为注释，不会被当作密码尝试。保存新学到的密码时会追加到原文件末尾，注释、空行和原有顺序均保持不变。

密码本身以 `#` 开头时，请在前面加反斜杠：`\#abc` 表示密码 `#abc`。运行中新学到的密码会自动按此方式转义。**升级时**请检查 `passwords.txt` 中是否有以 `#` 开头的密码：在加上反斜杠之前，它们会被当作注释。

## Bug Fixes / 错误修复

### Executables inside archives are no longer unpacked / 档案内的可执行文件不再被误解压 — [#21](https://github.com/rozx/Complex-unzip-tool-v2/issues/21)

A file found inside an extracted archive is now extracted only when 7-Zip identifies it as a real container (7z, RAR, ZIP, TAR, gzip, CAB, ISO, …). Plain `.exe`/`.dll` files, which 7-Zip can open to list their PE sections, are now kept unchanged instead of becoming `NAME.dll_2\` folders. The same applies to other formats 7-Zip merely opens, such as ELF/Mach-O binaries, `.msi`/`.doc` (Compound) files, NSIS installers and FLV videos. Self-extracting archives, where 7-Zip reports the embedded container, are still extracted.

Processed nested archives now follow the deletion mode: they go to the Recycle Bin by default and are deleted permanently only with `--permanent-delete`. If the Recycle Bin is unavailable, the nested archive is kept in the output folder instead of being deleted.

解压出的文件现在只有在 7-Zip 识别为真正的档案容器（7z、RAR、ZIP、TAR、gzip、CAB、ISO 等）时才会继续解压。普通 `.exe`/`.dll` 虽然能被 7-Zip 打开并列出 PE 节区，但现在会原样保留，不再变成 `NAME.dll_2\` 目录。ELF/Mach-O 程序、`.msi`/`.doc`（Compound）文件、NSIS 安装包和 FLV 视频等 7-Zip 仅能“打开”的格式同样保留。7-Zip 能识别出内嵌容器的自解压包仍会正常解压。

已处理的嵌套档案现在遵循删除模式：默认移入回收站，只有使用 `--permanent-delete` 时才永久删除。回收站不可用时，嵌套档案会保留在输出目录中，而不会被删除。

### Documents and app packages inside archives are kept intact / 档案内的文档和程序包保持完整

Office documents (`.docx`, `.xlsx`, `.pptx`), OpenDocument files (`.odt`, `.ods`, `.odp`), Apple iWork files (`.pages`, `.numbers`, `.key`), e-books (`.epub`) and app or extension packages (`.jar`, `.apk`, `.ipa`, `.appx`/`.msix`, `.vsix`, `.xpi`, `.whl`, …) are ZIP files underneath. They are now kept as regular files instead of being unpacked into their internal XML or class files. The same files found directly in an input folder are left in place with a "Kept document/package" notice and counted as skipped, not as errors. The name alone is not trusted: the file must be a ZIP that also contains the entry its format requires, such as `[Content_Types].xml` in a `.docx` or `AndroidManifest.xml` in an `.apk`. A plain ZIP renamed to a document name (for example `资源.zip.docx`), a ZIP disguised as `.jpg` or `.mp4`, a 7z/RAR named `.docx`, and `.cbz` comic archives are still extracted. To unpack a real document on purpose, rename it to `.zip`.

Office 文档（`.docx`、`.xlsx`、`.pptx`）、OpenDocument 文件（`.odt`、`.ods`、`.odp`）、Apple iWork 文件（`.pages`、`.numbers`、`.key`）、电子书（`.epub`）以及应用或扩展程序包（`.jar`、`.apk`、`.ipa`、`.appx`/`.msix`、`.vsix`、`.xpi`、`.whl` 等）本质上是 ZIP 文件。现在它们会作为普通文件保留，不再被拆成内部的 XML 或 class 文件。直接位于输入目录中的此类文件也会原样保留，提示“保留文档/程序包”，并计入“跳过”而非错误。不会仅凭文件名判断：文件必须是 ZIP，且包含该格式必需的条目，例如 `.docx` 中的 `[Content_Types].xml`、`.apk` 中的 `AndroidManifest.xml`。改成文档名的普通 ZIP（如 `资源.zip.docx`）、伪装成 `.jpg`、`.mp4` 的 ZIP、以 `.docx` 命名的 7z/RAR，以及 `.cbz` 漫画档案仍会正常解压。如确需解开真正的文档，请将其改名为 `.zip`。

### Readme and other non-archive files no longer reported as errors / 说明文件等非档案不再报错

Files next to the archives that are clearly not archives, such as a `请先看我.txt` readme, `.url` shortcuts or cover images, are now skipped with an info line and kept in place. They no longer add "Failed to extract" / "File is not a valid archive" entries to the final summary, which now lists them as "skipped". A lone numbered file such as `report.001`, with no other volumes to join, is also kept as it is. A file that looks like an archive by name or signature but cannot be opened (for example a damaged `.7z`) is still reported as an error.

与档案放在一起、明显不是档案的文件（如 `请先看我.txt` 说明、`.url` 快捷方式、封面图片）现在会提示跳过并原样保留，不再在最终摘要中产生“提取失败”/“文件不是有效档案”错误，摘要中改为计入“跳过”。没有其他分卷可合并的单个编号文件（如 `report.001`）同样原样保留。按名称或文件签名看起来是档案但无法打开的文件（例如损坏的 `.7z`）仍会报告为错误。

### Options work after input paths / 选项可写在输入路径之后

Options such as `--permanent-delete` are now recognized anywhere on the command line, including after the paths (for example `complex-unzip-tool-v2 "D:\Downloads" --permanent-delete`). Previously an option after a path was silently ignored and treated as another input path, which added bogus "archive not found" errors. An unknown option (for example a typo such as `--permanant-delete`) now stops with a "No such option" error instead of being treated as an input path. The `version` subcommand works again; `--version` is unchanged.

`--permanent-delete` 等选项现在可以写在命令行任意位置，包括输入路径之后（例如 `complex-unzip-tool-v2 "D:\Downloads" --permanent-delete`）。此前写在路径之后的选项会被静默忽略并被当作另一个输入路径，产生多余的“档案未找到”错误。未知选项（例如拼错的 `--permanant-delete`）现在会报“No such option”错误并停止，而不会被当作输入路径。`version` 子命令恢复可用，`--version` 不变。
