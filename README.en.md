# Complex Unzip Tool v2

![GitHub Release](https://img.shields.io/github/v/release/rozx/Complex-unzip-tool-v2)
[![Python](https://img.shields.io/badge/python-3.11+-green.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)](https://github.com/rozx/Complex-unzip-tool-v2)

🌐 [中文](README.md) | **English**

**One-click extraction for disguised ("cloaked") archives downloaded from cloud drives — built for 百度网盘 / Baidu Netdisk.**

**v1.3.2** reuses manually entered passwords for later archives in the same run, so batches with a shared password no longer prompt for each archive. See the [1.3.2 release notes](docs/releaseNotes/v1.3.2.md).

---

## 🤔 What problem does it solve?

Archives shared on 百度网盘 (Baidu Netdisk) and other cloud drives are often **cloaked**: their names are deliberately scrambled with junk characters to dodge content scanning — e.g. `movie.7z.001` becomes `movie.7z.00删1`, or a `.rar` is renamed to a random string. After downloading, these files **won't extract directly** and the multipart sets are broken apart.

This tool automatically **restores the real filenames (uncloaks)**, **regroups** split volumes, **tries your passwords**, and **recursively extracts** everything — including nested archives — in one pass.

> Inspired by: https://github.com/TR-Supowe/Complex-Unzip-Tool

---

## 🚀 Quick Start

1. **Download** the package for your OS and architecture from **[Releases](https://github.com/rozx/Complex-unzip-tool-v2/releases)**. On Windows, extract the `.zip` to get `complex-unzip-tool-v2.exe`.
2. **Drag & drop** your archive files or folders onto the `.exe` on Windows.
3. **Done** — it uncloaks, groups, and extracts everything automatically.

On macOS / Linux, extract the matching `.tar.gz` and run the program in a terminal. This example uses an Apple Silicon Mac; substitute the package name for your platform:

```bash
tar -xzf complex-unzip-tool-v2-v1.3.2-macos-arm64.tar.gz
./complex-unzip-tool-v2 "$HOME/Downloads/Archives"
```

| Platform | v1.3.2 package | Bundled 7-Zip 26.03 |
| --- | --- | --- |
| Windows x64 | `complex-unzip-tool-v2-v1.3.2-windows-x64.zip` | `7z.exe` + `7z.dll` |
| macOS Intel | `complex-unzip-tool-v2-v1.3.2-macos-x64.tar.gz` | Universal `7zz` |
| macOS Apple Silicon | `complex-unzip-tool-v2-v1.3.2-macos-arm64.tar.gz` | Universal `7zz` |
| Linux x64 | `complex-unzip-tool-v2-v1.3.2-linux-x64.tar.gz` | Static `7zzs` |
| Linux ARM64 | `complex-unzip-tool-v2-v1.3.2-linux-arm64.tar.gz` | Static `7zzs` |

Packages include Python and 7-Zip, so no separate installation or runtime engine download is required. Each package includes documentation and licenses; the release also includes `SHA256SUMS`. See [7z/README.md](7z/README.md) for upstream sources, checksums, and licenses.

The macOS application has separate Intel and Apple Silicon builds. Linux executables are built on Ubuntu 24.04 and require compatible system libraries. macOS signing/notarization and Windows publisher signing are not configured. See Development below to run from source or build locally.

---

## 📖 Usage Guide

### Basic usage

```powershell
# Extract every archive inside a folder
complex-unzip-tool-v2.exe "D:\Downloads\Archives"

# Extract specific files (the primary volume discovers matching sibling parts)
complex-unzip-tool-v2.exe "D:\file.zip" "D:\movie.7z.001"
```

Extracted contents are written to an `unzipped/` folder. On success, original archives are moved to the system **Recycle Bin / Trash** (recoverable). Linux needs an available desktop trash directory; originals are retained if recycling fails.

Passing a single volume collects matching parts from the same directory and naming convention by their uncloaked names, including cloaked continuation parts. All parts are cleaned up on success and retained on extraction or password failure. On Windows, output redirected to a file or pipe uses UTF-8 and the program exits without waiting for Enter.

### Passwords

Many netdisk archives are password-protected. Put your passwords in a `passwords.txt` file and the tool tries each one automatically (the empty password is tried first).

**Two locations are supported and merged automatically:**

1. **Target directory** — place `passwords.txt` in the folder you pass to the tool (or next to the file you pass). Best for passwords specific to that batch of files.
2. **Tool directory** — place `passwords.txt` next to the executable (`.exe` on Windows; `complex-unzip-tool-v2` on macOS / Linux). Source runs use the project root. This location is independent of the working directory and drag-and-drop launch behavior.

**File format** (one password per line; blank lines ignored; lines starting with `#` are comments; write a password that starts with `#` as `\#`; duplicates removed automatically):

```text
# common passwords
123456
www.example.com
mypassword
\#password-starting-with-hash
```

If a password itself starts with `#`, write it with a leading backslash: `\#abc` means the password `#abc`. Auto-saved passwords are escaped automatically. When upgrading, check your book for passwords that start with `#` and escape them this way.

- 📝 **Auto-learn**: manually entered passwords that successfully extract an archive are immediately reused for later single, multipart, and nested archives in the same run. New passwords are appended to the tool-directory `passwords.txt` when the run finishes; existing comments and order are kept, and passwords starting with `#` are saved as `\#`.
- The target-directory password book is read only, unless it is also the tool-directory book. If the tool directory is not writable, the program warns and completes extraction cleanup; move it to a writable directory to save new passwords. Builds do not embed personal password books.
- 🈶 **Encoding-aware**: auto-detects UTF-8 / GBK / GB2312 / Big5 / UTF-16 (with BOM), so Chinese passwords work without mojibake.

When upgrading, check whether an older version saved passwords in a launch directory such as Desktop or Downloads. Merge any entries you want to reuse into `passwords.txt` beside the new executable.

### Options

| Option | Description |
| --- | --- |
| `--version`, `-v` | Show version |
| `--permanent-delete` | Permanently delete originals instead of moving them to the Recycle Bin |
| `--help` | Show help |

> 🛡️ **Safe by default**: originals are never deleted when a password fails or a multipart set is incomplete.

---

## ✨ Features

- 🎭 **Filename uncloaking** — restores scrambled names via configurable rules (`config/cloaked_file_rules.json`); renames are reverted if extraction fails.
- 📦 **Multipart support** — `.001/.002`, `.part1/.part2`, `.rar/.r00`, `.zip/.z01`, and more; finds and regroups scattered parts.
- 🔐 **Smart passwords** — tries a password book automatically and caches successful ones.
- 🏗️ **Nested extraction** — recursively extracts archives inside archives.
- 🖱️ **Standalone** — build a single executable with Python and 7-Zip for each platform; Windows also supports dropping files onto the `.exe`.
- 🌐 **Bilingual UI** — clear progress output in English and 中文.

---

## 🛠️ Development

Requires Python 3.11+ and [Poetry](https://python-poetry.org/). Supports the platforms and architectures listed above.

```powershell
git clone https://github.com/rozx/Complex-unzip-tool-v2.git
cd Complex-unzip-tool-v2
poetry install

poetry run main "D:\path\to\archives"   # run the tool (alias: poetry run cuz)
poetry run pytest -q                     # run tests
poetry run build                         # build for the current platform -> dist/
```

On macOS / Linux:

```bash
poetry run main "$HOME/Downloads/Archives"
poetry run pytest -q
poetry run build
./dist/complex-unzip-tool-v2 --help
```

Build on the target OS and architecture. Windows produces an `.exe`; macOS / Linux produce an executable without an extension. Only the native engine is packaged. The macOS application targets the current Python architecture while its bundled 7-Zip is universal. Distribution signing and notarization are not configured.

If copying a source checkout loses Unix execute permissions, run `chmod +x` on the matching engine: `7z/macos/7zz`, `7z/linux-x64/7zzs`, or `7z/linux-arm64/7zzs`. Missing or non-executable engines are reported before the CLI modifies input files.

See [AGENTS.md](AGENTS.md) and [CLAUDE.md](CLAUDE.md) for architecture, conventions, and the extraction pipeline.

### GitHub CI and automatic releases

[CI](.github/workflows/ci.yml) runs fast checks on pushes and PRs targeting `main` or `release/**`: version and engine checksum validation, compilation, and the complete test suite on Ubuntu and Windows. New commits cancel older CI runs for the same branch or PR event. The five-platform standalone builds and real archive smoke tests run during releases; to run them on any branch, start CI manually in Actions with **full_build** checked. Their packages remain in Actions artifacts for 14 days.

Releases are prepared with the `release-ready` skill (`.claude/skills/release-ready/`; `.agents/skills/release-ready` links to it). All of a release's commits go on a `release/vX.Y.Z` branch, which merges through exactly one PR. The skill:

1. checks the version against the branch and bumps all three version declarations in a separate `chore: bump version to X.Y.Z` commit;
2. writes bilingual release notes to `docs/releaseNotes/vX.Y.Z.md` from the changes since the last tag (the 2.0.0 notes, for example, will be `docs/releaseNotes/v2.0.0.md`);
3. updates the READMEs and docs, runs the checks, pushes the branch, and opens the PR `release: vX.Y.Z` with the `release` label.

[Release](.github/workflows/release.yml) publishes only when all of these conditions hold:

1. The PR comes from a `release/*` branch in this repository, for example `release/v2.0.0`.
2. A version-like branch suffix (`release/2.0.0` or `release/v2.0.0`) equals the project version in `pyproject.toml`, package `__version__`, and `.bumpversion.cfg`.
3. The PR has the `release` label at merge time and is merged into `main`.

Check the version, branch, and notes locally before opening the PR:

```powershell
poetry run python -m scripts.release version
poetry run python -m scripts.release verify-branch release/v2.0.0
poetry run python -m scripts.release verify-notes
```

The release workflow rebuilds and smoke-tests all five platforms from the PR's exact merge commit. After every build succeeds, it creates a GitHub Release using the exact contents of `docs/releaseNotes/vX.Y.Z.md` as its body, and uploads the five platform packages listed above plus `SHA256SUMS`. Missing or empty notes fail before platform builds start.

Release runs are processed one at a time and never cancelled. Add the label before merging. Closing an unmerged PR, adding the label after merge, a branch from a fork, or pushing a tag alone does not publish. The built-in `GITHUB_TOKEN` is sufficient; only the final publishing job has `contents: write`.

Use Actions to rerun failed jobs. Interrupted uploads leave a draft that can be resumed for the same version and merge commit; its body is updated from that commit's matching release notes file. Publication waits until all remote assets pass checksum verification. Published releases are never overwritten, and a tag or draft belonging to another commit causes a clear failure.

---

## 🤝 Contributing

Issues and pull requests are welcome. Please keep changes small, tested, and follow the TDD workflow described in [CLAUDE.md](CLAUDE.md).

## 📄 License

MIT License — see [LICENSE](LICENSE).

## 👤 Author

**Rozx** — [GitHub](https://github.com/rozx)
