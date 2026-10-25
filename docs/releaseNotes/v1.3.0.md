# Release Notes v1.3.0 / 发布说明 v1.3.0

Version 1.3.0 adds native macOS and Linux support, updates the bundled 7-Zip to **26.03** on all platforms, and fixes password-book lookup, multipart cleanup, and redirected Windows output. It also introduces GitHub Actions builds and releases for five platform targets.

1.3.0 新增 macOS 和 Linux 原生支持，将各平台内置的 7-Zip 更新至 **26.03**，并修复密码本路径、分卷清理和 Windows 输出重定向问题。同时新增 GitHub Actions，为五个平台构建程序并自动发布。

## Platform Support / 平台支持

Choose the package for your operating system and CPU architecture. Each package contains a standalone executable with Python and the native 7-Zip engine, plus documentation and licenses. No separate Python or 7-Zip installation is needed, and no engine is downloaded at runtime.

请按操作系统和 CPU 架构选择发布包。每个包包含内置 Python 和原生 7-Zip 引擎的独立程序，以及说明文档和许可证。无需另行安装 Python 或 7-Zip，运行时也不会联网下载引擎。

| Platform / 平台 | Package / 发布包 |
| --- | --- |
| Windows x64 | `complex-unzip-tool-v2-v1.3.0-windows-x64.zip` |
| macOS Intel | `complex-unzip-tool-v2-v1.3.0-macos-x64.tar.gz` |
| macOS Apple Silicon | `complex-unzip-tool-v2-v1.3.0-macos-arm64.tar.gz` |
| Linux x64 | `complex-unzip-tool-v2-v1.3.0-linux-x64.tar.gz` |
| Linux ARM64 | `complex-unzip-tool-v2-v1.3.0-linux-arm64.tar.gz` |

- Windows includes the updated `7z.exe` and `7z.dll`; macOS uses universal `7zz`; Linux uses the matching static `7zzs`. The macOS application itself has separate Intel and Apple Silicon builds.
- Missing or unusable engines are reported before the CLI modifies input files. `--help` and `--version` remain available.
- macOS and Linux programs exit without an extra Enter prompt. Windows only pauses when both input and output are interactive terminals.

- Windows 内置更新后的 `7z.exe` 和 `7z.dll`；macOS 使用通用二进制 `7zz`；Linux 使用对应架构的静态 `7zzs`。macOS 应用本身仍分别提供 Intel 和 Apple Silicon 构建。
- 引擎缺失或不可用时，会在修改输入文件前报错；`--help` 和 `--version` 仍可使用。
- macOS 和 Linux 程序结束后直接退出；Windows 仅在输入、输出均为交互式终端时等待回车。

## Bug Fixes / 错误修复

### Password books follow the tool directory / 密码本固定使用工具目录 — [#19](https://github.com/rozx/Complex-unzip-tool-v2/issues/19)

The global `passwords.txt` is now loaded and saved beside the executable, or at the project root when running from source. Launching from another working directory or dragging an archive onto the Windows executable no longer changes that location. The target-directory password book remains an additional read-only source, unless it is the same file as the global book.

If the global book cannot be saved, the CLI reports the path and write-permission problem and continues its final cleanup. Builds no longer embed a personal `passwords.txt` inside the executable.

全局 `passwords.txt` 现在固定在可执行文件旁读写；从源码运行时使用项目根目录。从其他工作目录启动，或将压缩包拖到 Windows 程序上，都不会改变这个位置。目标目录的密码本仍作为额外的只读来源，除非它与全局密码本是同一个文件。

全局密码本无法保存时，CLI 会提示路径和写入权限问题，并继续完成收尾。构建程序也不再内嵌个人 `passwords.txt`。

### Single-file inputs include matching volumes / 单文件输入自动收集同组分卷 — [#18](https://github.com/rozx/Complex-unzip-tool-v2/issues/18)

Passing only `movie.7z.001` now discovers its matching sibling volumes before extraction, including cloaked names such as `movie.7z.002删除`. A cloaked primary is also recognized. Successful extraction cleans up the entire discovered set instead of leaving `.002` and later parts behind. Discovery is limited to the same directory, archive name, and split convention; unrelated archives and subdirectories are excluded. Extraction or password failure still preserves all source parts.

只传入 `movie.7z.001` 时，现在会先收集同组分卷再解压，包括 `movie.7z.002删除` 等伪装续卷；传入伪装主卷同样可以识别。成功后统一清理已收集的整组源文件，不再遗留 `.002` 等续卷。收集范围限定为同目录、同名且采用同一分卷格式的文件，不包含无关档案和子目录。解压或密码失败时，仍会保留全部源分卷。

### Redirected Windows output uses UTF-8 / Windows 重定向输出使用 UTF-8 — [#17](https://github.com/rozx/Complex-unzip-tool-v2/issues/17)

Windows stdout and stderr redirected to a file or pipe are configured as UTF-8 before the first banner. Chinese text and emoji no longer trigger the reported GBK `UnicodeEncodeError`. Standalone builds also enable Python's UTF-8 mode, without depending on environment variables. Redirected output no longer waits for Enter at exit.

Windows 的 stdout 和 stderr 被重定向到文件或管道时，会在首次输出前设置为 UTF-8。中文和 emoji 不再触发此前的 GBK `UnicodeEncodeError`。独立构建同时启用 Python UTF-8 模式，无需依赖环境变量；输出重定向时，结束后也不会等待回车。

## Build and Release Automation / 构建与自动发布

- GitHub CI runs tests, engine checksum checks, real archive smoke tests, and standalone builds for all five platform targets.
- Automatic publication requires a PR from `release/*`, carrying the `release` label at merge time, to be merged into `main`. The workflow builds the exact merge commit and publishes only after all platform builds and asset checks succeed.
- Release descriptions come verbatim from `ReleaseNotes/RELEASE_NOTES_vX.Y.Z.md`. Missing or empty notes stop the release before platform builds begin.
- Releases include the five packages and `SHA256SUMS`. Interrupted uploads can resume a matching draft; published releases are not overwritten.

- GitHub CI 为五个平台执行测试、引擎校验、真实压缩包冒烟测试和独立程序构建。
- 自动发布要求来源分支为 `release/*`，PR 在合并时带有 `release` 标签，并合并到 `main`。工作流使用确切的合并提交构建，所有平台构建及产物校验成功后才发布。
- 发布说明直接采用 `ReleaseNotes/RELEASE_NOTES_vX.Y.Z.md` 的原文。文件缺失或为空时，会在平台构建开始前中止发布。
- Release 包含五个平台的发布包和 `SHA256SUMS`。上传中断后可以继续匹配的草稿，已公开的版本不会被覆盖。

## Upgrade Notes / 升级须知

- **Windows packaging:** extract the `.zip` first, then run or drag files onto `complex-unzip-tool-v2.exe`. Keep your global `passwords.txt` beside the new executable.
- **Password migration:** if an older version wrote passwords into a launch directory such as Desktop or Downloads, move or merge those entries into the tool-directory book. A book beside the input archive is still read for that input, but learned passwords are saved to the tool directory.
- **macOS / Linux:** extract the matching `.tar.gz` and run `./complex-unzip-tool-v2 "archive directory"` in a terminal. Preserve executable permissions.
- **Compatibility:** Linux standalone packages are built on Ubuntu 24.04 and require compatible system libraries; the static 7-Zip engine does not make the entire application static. Windows publisher signing and macOS signing/notarization are not configured. Linux recycling requires a usable desktop trash directory; originals remain if recycling fails.

- **Windows 发布包：** 先解开 `.zip`，再运行 `complex-unzip-tool-v2.exe` 或将文件拖到程序上。全局 `passwords.txt` 请保留在新程序旁。
- **密码本迁移：** 如果旧版本曾把密码写到桌面、下载目录等启动目录，请将这些条目移入或合并到工具目录的密码本。输入档案旁的密码本仍可用于该任务，但新学到的密码会写到工具目录。
- **macOS / Linux：** 解开对应的 `.tar.gz` 后，在终端运行 `./complex-unzip-tool-v2 "待解压目录"`，并保留执行权限。
- **兼容性：** Linux 独立包在 Ubuntu 24.04 上构建，需要兼容的系统库；内置静态 7-Zip 不代表整个应用静态链接。Windows 发行者签名、macOS 签名及公证尚未配置。Linux 回收文件需要可用的桌面废纸篓目录；回收失败时保留原文件。

## Validation / 验证

The **300-test** suite passes locally on macOS ARM64. Source and standalone smoke tests passed with nested ZIPs, encrypted 7z archives, Unicode filenames/passwords, and both directory and single-file multipart inputs. Regression coverage includes GBK-encoded redirected streams, password-save failures, and source retention on extraction/password failure. Native builds for all five platforms are enforced by the release CI.

**300 项测试**已在本地 macOS ARM64 上通过。源码与独立程序均通过了嵌套 ZIP、加密 7z、中文文件名及密码、目录输入和单文件分卷输入的冒烟验证。回归测试覆盖 GBK 重定向输出、密码本保存失败，以及解压或密码失败时的源文件保留。五个平台的原生构建由发布 CI 检查。
