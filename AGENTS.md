
# AI Agents Guide

This document defines how AI agents (and humans using them) should operate in this repository.

- Repo: `Complex-unzip-tool-v2`
- Primary language: Python (3.11)
- Package/Deps: Poetry (`pyproject.toml`, `poetry.lock`)
- Tests: `pytest` in `tests/`
- Bundling: scripts in `scripts/` and `7z/` binaries bundled for archive ops
- Supported platforms: Windows x64, macOS Intel/Apple Silicon, Linux x64/ARM64
- Dev shells: PowerShell on Windows; bash/zsh on macOS/Linux

## Project Summary
A command-line tool to unzip/extract various archive formats, including nested and password-protected archives, with cloaked file detection.
- Handles multiple archive types (zip, rar, 7z, tar, etc.)
- Supports nested archives
- Handles password-protected archives using a password book
- Detects cloaked files based on configurable rules
- Always extract single archive first to see if it contains other contained archives
- Supports extraction to a specified output directory
- Provides clear CLI feedback and logging
- Have both Chinese and English language support

## Goals
- Keep the app stable and easy to maintain.
- Prefer minimal, well-scoped changes with tests.
- Follow a clear workflow so changes are reproducible locally on each supported platform.
- **When making changes, ensure all existing behavior is preserved unless intentionally modified.**

## Ground Rules
- Do not exfiltrate secrets or make network calls unless explicitly required.
- Keep code portable across supported platforms; use PowerShell-compatible commands on Windows and native shell commands on macOS/Linux.
- Respect the existing structure under `complex_unzip_tool_v2/` and `scripts/`.
- Use `pytest` for tests; add or update tests when changing behavior.
- Keep public APIs stable unless the change is intentional and documented.
- Use concise, focused commits/PRs with a clear description and checklist status.
- Always try to reuse existing utilities and patterns in the codebase.        

## Quickstart Commands

- Run in PowerShell:

```powershell
# From repo root
poetry run main
```

- Install dependencies (Poetry):

```powershell
# From repo root
poetry install
```

- Run tests:

```powershell
poetry run pytest -q                                        # all tests
poetry run pytest tests/test_archive_utils.py -q            # one file
poetry run pytest tests/test_archive_utils.py::test_build_7z_extract_cmd -q   # one test
```

- Lint / format / type-check:

```powershell
poetry run black complex_unzip_tool_v2/ tests/   # format (line-length 88)
poetry run flake8 complex_unzip_tool_v2/ tests/  # lint
poetry run mypy complex_unzip_tool_v2/           # type check (strict)
```

- Smoke test the CLI:

```powershell
poetry run main --help
```

- Build (packaging helper):

```powershell
# Option A: via Poetry
poetry run build
```

The project bundles 7-Zip 26.03 for each supported platform. Use `modules/seven_zip_runtime.py` for engine selection; see `7z/README.md` for paths, checksums, and licenses. Build on the target OS/architecture with `poetry run build`.

## Repository Facts
- Entry points: `complex_unzip_tool_v2/__main__.py`, `complex_unzip_tool_v2/main.py`.
- Core modules:
  - `modules/archive_utils.py`, `modules/archive_extension_utils.py`
  - `modules/file_utils.py`, `modules/password_util.py`
  - `modules/cloaked_file_detector.py` (uses `config/cloaked_file_rules.json`)
- Domain classes under `classes/`: archive types, groups, password book.
- Icons for packaging: `icons/`.
- Tests in `tests/` cover archives, cloaked file detection, file utilities.

## Typical Agent Roles
- Feature/Code Agent: implement small features/bug fixes with tests.
- Test Agent: expand coverage, add regression tests, ensure edge cases.
- Docs Agent: update `README.md` and inline docs for changed behavior.
- Build/Release Agent: keep packaging scripts working; no secret leakage.

## Change Workflow
1) Branch and plan a minimal change set.
2) **TDD: write a failing test first** under `tests/` (regression test for a bug, or a spec test for new behavior); confirm it fails for the right reason.
3) Implement the minimum change in `complex_unzip_tool_v2/` to make it pass (keep diffs small and focused), then refactor with the test green.
4) Run quality gates locally:
   - Build: ensure code runs (smoke test CLI)
   - Tests: `poetry run pytest -q`
   - Lint/Typecheck: if configured in `pyproject.toml`
5) Update docs (`README.md`) if user-facing behavior changes.
6) Commit with a clear message and open a PR with a short checklist. Release work is the exception: commit it directly on `release/vX.Y.Z`; the `release-ready` skill opens the single release PR (see "CI and releases").

## Spec-driven development (OpenSpec)
This repo uses **OpenSpec**. Active specs live in `openspec/specs/`, proposed changes in `openspec/changes/`, and project conventions in `openspec/project.md`. For non-trivial features or behavior changes, create/advance an OpenSpec change (via the `openspec-*` skills) instead of ad-hoc edits, then archive it once implemented. Small bugfixes can skip this, but still follow TDD.

## CI and releases

- `.github/workflows/ci.yml` runs fast checks (version/engine verification, compile, full `pytest`) on Ubuntu and Windows for every push and PR. The five-target build (Windows x64, macOS x64/ARM64, Linux x64/ARM64) with `scripts/smoke_test.py` native source/standalone extraction runs only when the release workflow calls it, or on manual dispatch with `full_build`.
- Prepare releases with the `release-ready` skill (`.claude/skills/release-ready/SKILL.md`; `.agents/skills/release-ready` is a symlink to it). All of a release's commits go directly on `release/vX.Y.Z`, and the release merges as exactly one PR (`release: vX.Y.Z`, `release` label) into `main`. Do not open feature branches or extra PRs for release work.
- `.github/workflows/release.yml` triggers on the merged `pull_request`. It publishes only for a same-repository `release/*` branch carrying the `release` label, whose version-like suffix equals the project version (`scripts.release verify-branch`). Build and tag the exact merge commit. Release runs are serialized and never cancelled.
- Versions in `pyproject.toml`, package `__version__`, and `.bumpversion.cfg` must match and be bumped before release, in a separate `chore: bump version to X.Y.Z` commit. `scripts/release.py` validates versions and branches, and packages assets/checksums.
- Release bodies come verbatim from `docs/releaseNotes/vX.Y.Z.md` (bilingual, `release-ready` template) in the merge commit. Missing or empty notes block publication; do not fall back to generated GitHub notes or another version.
- Only the publication job has write permissions. Never move an existing version tag or overwrite a published release; `scripts/publish_release.cjs` can resume a matching draft.

## Quality Gates (Definition of Done)
- Build/Run: CLI `--help` works without errors.
- Tests: all tests pass locally; new behavior is covered by tests.
- No syntax/type errors; imports resolved.
- No unnecessary refactors or churn; only relevant lines changed.
- Docs updated when behavior or usage changes.

## Testing Guidelines
- **Always use TDD**: write the failing test before the implementation (see Change Workflow).
- Put tests in `tests/`, named `test_*.py`.
- Cover happy path and at least one edge case (e.g., missing password, invalid archive, cloaked file detection).
- Prefer small, deterministic examples; avoid large fixtures unless needed.
- Unit tests do **not** execute the real 7-Zip engine: mock the subprocess/extraction calls with `monkeypatch` and use the `tmp_path` fixture for filesystem effects. Pure helpers (regex / grouping / uncloaking / path normalization) are tested directly. See `tests/test_archive_utils.py` for the mocking pattern.

## Coding Conventions
- Keep functions small; prefer pure helpers in `modules/` when feasible.
- Error handling: raise domain exceptions under `classes/ArchiveExceptions.py` when appropriate.
- Paths: prefer using `pathlib` and utilities in `modules/file_utils.py`.
- Archive ops: centralize in `archive_utils.py` and `archive_extension_utils.py`.
- Config-driven behavior (e.g., cloaked rules) should read from `config/`.

## Passwords handling
- Password discovery sources (in this order):
  1) Target directory: `passwords.txt` located in the directory you pass to the CLI.
  2) Tool directory: `passwords.txt` beside `sys.executable` in frozen builds; repository root (next to `AGENTS.md`) in source runs. Never use CWD or `_MEIPASS` for the global book.

- File format: one password per line; blank lines and lines starting with `#` (after trimming) are ignored. A password that starts with `#` is escaped with a leading backslash (`\#abc` → `#abc`): loading removes one leading backslash before `#`, saving adds one, so learned passwords round-trip.

- Encoding support when reading `passwords.txt`:
  - Tries multiple encodings automatically: `utf-8-sig`, `utf-8`, `gbk`, `gb2312`, `big5`, `utf-16`, `utf-16-le`, `utf-16-be`.
  - Falls back to UTF-8 with errors ignored if necessary.
  - Byte Order Marks (BOM) are handled/stripped.

- Saving behavior:
  - When new passwords are learned during a run, they are saved to the local `passwords.txt` in UTF-8. Existing lines (comments, blanks, order) are kept; removed passwords are dropped and new ones appended.
  - Save only occurs when there are actual changes.
  - Save to the same tool-directory path used for loading; target-directory books are read-only sources unless they are the same file. If saving raises `OSError`, warn without interrupting rename-history finalization or CLI completion. Builds must not embed `passwords.txt`.

## Single-file multipart inputs
- `file_utils.read_dir` includes matching sibling volumes when a file is selected, using the same directory, exact archive name, and split convention. It must not pull in unrelated archives, subdirectories, or another split convention with the same base name.
- Discovery previews the configured uncloaking rules without renaming files. Step 4 still owns all renames and recovery history. If sibling scanning raises `OSError`, retain explicitly selected inputs.
- Reuse the existing group extraction and cleanup paths: clean all discovered parts on success; retain them all on extraction/password failure.
- Regression coverage: `tests/test_multipart_file_input.py`; real source/frozen coverage: `scripts/smoke_test.py`.

## Redirected Windows output
- Configure redirected stdout/stderr as UTF-8 before the first Rich output. Preserve interactive terminal streams and wrappers without `reconfigure`.
- Keep the PyInstaller `X utf8` option. The frozen CLI pauses only when both stdin and stdout are interactive Windows terminals.
- Smoke tests deliberately use legacy GBK Python stream settings on Windows and validate UTF-8 output bytes.

## Renaming/Uncloaking rules
The tool normalizes “cloaked” filenames before grouping/extracting. This is Step 4 in the CLI (“Uncloaking file extensions”).

- Engine: `CloakedFileDetector` using rules from `complex_unzip_tool_v2/config/cloaked_file_rules.json`.
- Goal: Convert disguised names (with trailing junk/suffixes) into proper archive names, including multipart suffixes.

Safety guards (never rename these):
- Files that already have a proper multipart format are left as-is, e.g.:
  - `.7z.001`, `.7z.002`, ...
  - `.<ext>.001`, `.<ext>.002`, ... (7-Zip generic numbered split of any extension, e.g. `.zip.001`, `.rar.001`, `.iso.001`; 3+ zero-padded digits)
  - `.r00`, `.r01`, ... (RAR continuation)
  - `.z01`, `.z02`, ... (ZIP continuation)
  - `.zx01`, `.zx02`, ... (ZIPX continuation)
  - `.a01`, `.a02`, ... (ARJ continuation)
  - `.c00`, `.c01`, ... (ACE continuation)
  - `.tar.gz.001`, `.tar.bz2.001`, `.tar.xz.001`
  - `.part1.rar`, `.part2.rar`
- Files that already end with a proper single archive extension are left as-is, e.g.:
  - `.7z`, `.rar`, `.zip`, `.tar`, `.tgz`, `.tbz2`, `.txz`, `.gz`, `.bz2`, `.xz`, `.arj`, `.cab`, `.lzh`, `.lha`, `.ace`, `.iso`, `.img`, `.bin`.

Rule schema (JSON):
- `name`: identifier for the rule.
- `matching_type`: one of `both`, `filename`, `ext`.
  - `both`: `filename_pattern` matches the name, and `ext_pattern` matches the extension part (can be empty string to mean “no extension”).
  - `filename`: only `filename_pattern` is used; can capture archive type and part number.
  - `ext`: only `ext_pattern` is used (works on the last extension token).
- `filename_pattern` / `ext_pattern`: regexes; capture groups feed the new name.
- `priority`: larger values run first.
- `type`: archive type hint (`7z`, `rar`, `zip`, `auto`, etc.).
- `enabled`: toggle rule on/off.

Resolution flow:
1) Skip if filename is already proper (see “Safety guards”).
2) Iterate rules by `priority` (desc). If a rule matches, build the new filename:
   - Multipart part numbers are normalized to 3 digits (e.g., `1` -> `001`).
   - If `type` is `auto`, we try to detect via `archive_extension_utils.detect_archive_extension`.
3) Signature gate (`_verify_with_signature`): if the filename carries an explicit archive token — `.7z` / `.rar` / `.zip` (matched by `ARCHIVE_TOKEN_RE`) — the rename is trusted, because continuation parts (e.g. `name.7z.002删除`) legitimately carry no magic-byte signature. If there is NO such token, the type was only *guessed* from a trailing number, so a real archive signature (`archive_extension_utils.detect_archive_extension`) is required before renaming — this stops ordinary files from being turned into fake parts.
4) Apply rename only if the new filename differs and passes the signature gate.

Examples (intended outcomes):
- `11111.7z删除` -> `11111.7z`
- `11111.7z.00删1` -> `11111.7z.001`
- `archive.zip.z0隐藏1` -> `archive.zip.z01`
- `file.rar.r00删除` -> `file.rar.r00`

Where to change rules:
- Edit `complex_unzip_tool_v2/config/cloaked_file_rules.json`.
- Use `priority` to order more specific rules above generic ones.
- Set `enabled: false` to disable a rule without removing it.

Testing:
- See `tests/test_cloaked_file_detector.py` for unit tests covering rule matching and safety guards.
- Run tests with `poetry run pytest -q`.

## Rename history (revert-on-failure)
Because uncloaking renames source files *in place* before extraction, a failed extraction would otherwise leave the user with renamed files they can no longer recognize. `RenameHistory` (`complex_unzip_tool_v2/modules/rename_history.py`) makes uncloaking reversible.

- Every successful uncloak rename is recorded (Step 4) and persisted eagerly via atomic temp+replace to `<input_root>/.unzip-rename-history.tmp.json`, so a crash mid-run still leaves a recoverable record.
- Entries are bound to their owning `ArchiveGroup` after grouping (Step 5).
- Per group, after extraction: on **success** the entries are cleared; on **failure** they are reverted (files renamed back to their original cloaked names). This is wired through `_reconcile_rename_history()` in `main.py`, which mirrors `_should_delete_original_archives()` — if originals are being kept, names are put back; if they are being deleted, history is cleared.
- On startup, a leftover history file from a previous crashed run is detected and the user is prompted to revert it (`_maybe_recover_pending_renames`).
- Unbound entries (renamed file vanished before grouping) are reverted defensively at the end; the on-disk file is deleted on a clean run (`finalize`).
- Tests: `tests/test_rename_history.py`.

## Cleanup safety guards (do not break these)
- **Never delete originals on password failure.** All source deletion is gated by `_should_delete_original_archives()`, which returns `False` whenever `password_failed_archives` is non-empty. Deletion defaults to the Recycle Bin (`send2trash`); `--permanent-delete` overrides.
- **Multipart retention on failure.** When a multipart set fails to extract, the source parts are retained; only tool-created temp folders are cleaned (logs say "Retained source multipart parts due to extraction failure").

## Nested multipart handling (inside containers)
When extracting an archive that itself contains multipart archives (e.g., a .7z containing another multi-part set), the tool now relocates continuation parts into their corresponding multipart group directory so that top‑level multipart extraction has all required volumes. Primary parts are still the only ones considered for recursive nested extraction.

- Primary vs continuation identification:
  - 7z volumes: primary is `.7z.001`; continuations are `.7z.002+`.
  - TAR multipart: primary is `.tar.gz/.tar.bz2/.tar.xz.001`; continuations are `.002+`.
  - Generic 7-Zip split (any extension): primary is `name.<ext>.001`; continuations are `name.<ext>.002+` (3+ zero-padded digits; covers `.zip.001`, `.rar.001`, `.iso.001`, …).
  - RAR volumes: primary is `.rar` or `.part1.rar`; continuations are `.r00`, `.r01`, … and `.part2+.rar`.
  - ZIP spanned: primary is `.zip`; continuations are `.z01`, `.z02`, …
  - ZIPX spanned: primary is `.zipx`; continuations are `.zx01`, `.zx02`, …
  - ARJ volumes: primary is `.arj`; continuations are `.a01`, `.a02`, …
  - ACE volumes: primary is `.ace`; continuations are `.c00`, `.c01`, … (classification only — the bundled 7-Zip cannot extract ACE, so such sets fail extraction and their parts are retained).

- Behavior:
  - Continuation parts detected during nested extraction are NOT treated as nested archives and are NOT added to `final_files`.
  - Instead, the extractor attempts to relocate those continuation files next to the multipart set’s main archive, updating the in‑memory group via `ArchiveGroup.add_file`.
  - If relocation isn’t possible, the continuation is simply skipped (not an error) and will be cleaned up with the temporary folder; a later reconciliation pass may still catch it (see below).
  - Only the primary part is extracted recursively.

- Reconciliation pass (safety net):
  - After single archives finish, we scan the output folder and relocate any multipart parts that were extracted there into their matching multipart group directory.

- Implementation:
  - `complex_unzip_tool_v2/modules/archive_utils.py` → `extract_nested_archives()` accepts an optional `group_relocator` callback and invokes it when a continuation file is encountered.
  - `complex_unzip_tool_v2/main.py` wires `group_relocator` to reuse `file_utils.add_file_to_groups` during the single and multipart phases, and also runs a reconciliation step after single‑archive extraction.
  - `complex_unzip_tool_v2/modules/file_utils.py` provides `relocate_multipart_parts_from_directory(source_root, groups)` to scan the output folder and move parts into their group directories.

- Validation:
  - CLI smoke: `poetry run main --help`.
  - End-to-end: run against a directory where an outer archive contains a multipart set; continuation parts should be moved beside the multipart set before the multipart extraction begins and the set should extract successfully.
  - Tests: `tests/test_archive_utils.py` includes unit tests that assert continuation parts found during nested extraction are either relocated via the callback or skipped without leaking into `final_files`.

## Non-archive handling during nested scan
The tool treats every file as a potential archive by default. During nested extraction, we probe files with 7‑Zip but avoid flagging regular files (e.g., .mp4) as corrupted by mapping 7‑Zip output appropriately and parsing list output robustly.

- Behavior:
  - All files are candidates for probing via 7‑Zip.
  - If 7‑Zip prints messages like “Can not open file as archive”, “cannot open file as archive”, or “is not archive”, we treat this as unsupported/non‑archive (not corruption) and skip it.
  - Regular files encountered during nested scanning therefore do not produce spurious corruption errors.

- Implementation:
  - `complex_unzip_tool_v2/modules/archive_utils.py` → `_raise_for_7z_error()` maps the above messages to `ArchiveUnsupportedError` (non‑archive/unsupported), not `ArchiveCorruptedError`.
  - `_parse7zListOutput()` begins parsing after the dashed separator to remain compatible with varying 7‑Zip outputs.
  - `is_valid_archive()` uses 7‑Zip listing plus the mapping above to determine if a file is an archive.

- Validation:
  - Unit tests: `poetry run pytest -q` should pass.
  - Smoke: running against directories containing non‑archive files (e.g., .mp4) should not produce “corrupted archive” messages for those files.

## Common Local Paths
- 7-Zip: `./7z/windows-x64/7z.exe` + `7z.dll` (Windows), `./7z/macos/7zz`, `./7z/linux-x64/7zzs`, or `./7z/linux-arm64/7zzs`; each platform directory also contains its `License.txt`.
- Config: `complex_unzip_tool_v2/config/cloaked_file_rules.json`
- CLI Entrypoint: `complex_unzip_tool_v2/__main__.py`

## PR Template (suggested)
- Summary: what changed and why
- Tests: added/updated tests and results (`pytest -q` passes)
- Impact: user-facing behavior changes? update `README.md`
- Risks: edge cases considered; rollback plan if needed

## Troubleshooting
- Poetry not found: install Poetry or run via system Python if necessary.
- Windows path issues: use raw strings or `pathlib` to avoid backslash escapes.
- 7-Zip missing: restore the bundled engine for the host platform (and the DLL on Windows). Unix engines require executable permissions. The CLI validates the engine before extraction changes input files.

## Scope for Agents
- Keep PRs atomic and under ~300 lines of changes when possible.
- Avoid introducing new dependencies unless clearly justified and added to `pyproject.toml`.
- Do not modify bundled binaries under `7z/` except for an explicitly requested upstream upgrade. Preserve official bytes and licenses, and update `7z/manifest.json`.

---

If anything here conflicts with `README.md`, prefer the README and update this file accordingly in the same change.
