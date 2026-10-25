
# AI Agents Guide

This document defines how AI agents (and humans using them) should operate in this repository.

- Repo: `rozx/DeepUnzip`
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
- Output in English, Simplified Chinese, Traditional Chinese, Japanese and Korean

## Goals
- Keep the app stable and easy to maintain.
- Prefer minimal, well-scoped changes with tests.
- Follow a clear workflow so changes are reproducible locally on each supported platform.
- **When making changes, ensure all existing behavior is preserved unless intentionally modified.**

## Ground Rules
- Do not exfiltrate secrets or make network calls unless explicitly required.
- Keep code portable across supported platforms; use PowerShell-compatible commands on Windows and native shell commands on macOS/Linux.
- Respect the existing structure under `deepunzip/` and `scripts/`.
- Use `pytest` for tests; add or update tests when changing behavior.
- Keep public APIs stable unless the change is intentional and documented.
- Use concise, focused commits/PRs with a clear description and checklist status.
- Always try to reuse existing utilities and patterns in the codebase.        

## Quickstart Commands

- Run in PowerShell:

```powershell
# From repo root
poetry run deepunzip
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
poetry run black deepunzip/ tests/   # format (line-length 88)
poetry run flake8 deepunzip/ tests/  # lint
poetry run mypy deepunzip/           # type check (strict)
```

- Smoke test the CLI:

```powershell
poetry run deepunzip --help
```

- Build (packaging helper):

```powershell
# Option A: via Poetry
poetry run build
```

The project bundles 7-Zip 26.03 for each supported platform. Use `modules/seven_zip_runtime.py` for engine selection; see `7z/README.md` for paths, checksums, and licenses. Build on the target OS/architecture with `poetry run build`.

## Repository Facts
- Entry points: `deepunzip/__main__.py`, `deepunzip/main.py`.
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
3) Implement the minimum change in `deepunzip/` to make it pass (keep diffs small and focused), then refactor with the test green.
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
- Discovery previews the configured uncloaking rules without renaming files. The work pool's intake still owns all renames and recovery history. If sibling scanning raises `OSError`, retain explicitly selected inputs.
- The work pool deletes all discovered parts after the set extracts successfully, and retains them all on extraction or password failure.
- Regression coverage: `tests/test_multipart_file_input.py`; real source/frozen coverage: `scripts/smoke_test.py`.

## User-facing text and output
- Every user-facing string lives in `deepunzip/modules/i18n.py` `CATALOG` with an entry in each of the five output languages (`en`, `zh`, `zh-TW`, `ja`, `ko`, matching the five READMEs) that use the same placeholders; code calls `t(key, **params)`. Add new keys in all five languages. Never write inline user-facing strings, and never inline bilingual ones (`"Wrong password 密码错误"`). Each run uses one language: `DEEPUNZIP_LANG` (`en`, `zh`, `zh-TW`, `ja`, `ko`), else the system UI language, else English.
- Library code does not print. It emits events (`modules/events.py`); warnings use `events.notice("warning", key, **params)`. Exactly one renderer (`modules/render.py`) writes the output: terminal view, plain lines when redirected, or JSON lines with `--json`.
- `--json` writes only JSON lines to stdout and never prompts or pauses. Exit codes: `0` all resolved, `1` something unresolved, `2` fatal or usage error.
- Passwords never appear in any output; refer to them as `password #N`.

## Redirected Windows output
- Configure redirected stdout/stderr as UTF-8 before the first Rich output (`render.configure_redirected_output`). Preserve interactive terminal streams and wrappers without `reconfigure`.
- Keep the PyInstaller `X utf8` option. The frozen CLI pauses only when both stdin and stdout are interactive Windows terminals.
- Smoke tests deliberately use legacy GBK Python stream settings on Windows and validate UTF-8 output bytes.

## Renaming/Uncloaking rules
The tool normalizes “cloaked” filenames before classifying and grouping them. The work pool's intake uncloaks every new item, both scanned sources and files extracted at any depth. Only renames of sources are recorded in rename history.

- Engine: `CloakedFileDetector` using rules from `deepunzip/config/cloaked_file_rules.json`.
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
- Edit `deepunzip/config/cloaked_file_rules.json`.
- Use `priority` to order more specific rules above generic ones.
- Set `enabled: false` to disable a rule without removing it.

Testing:
- See `tests/test_cloaked_file_detector.py` for unit tests covering rule matching and safety guards.
- Run tests with `poetry run pytest -q`.

## Rename history (revert-on-failure)
Uncloaking renames source files *in place*. If a file is kept, the user must still be able to recognize it. `RenameHistory` (`deepunzip/modules/rename_history.py`) makes those renames reversible.

- There is one history file per input root: `<input_root>/.unzip-rename-history.tmp.json`. It is persisted eagerly via atomic temp+replace, so a crash mid-run still leaves a recoverable record.
- It records renames of **source** files only, in two kinds:
  - `uncloak`: a cloaked-name normalization;
  - `relocation`: a source volume moved into an assembly folder for a multipart attempt (through `RelocationLog`). This entry is cleared as soon as the volume is moved back.

  Renames of tool-extracted files are not recorded; their source is the recovery point. Files written by 1.3.x have no `kind` and load as `uncloak`.
- After each root, `_reconcile_history()` in `main.py`:
  - clears the entries of deleted sources (`clear_for`);
  - reverts every remaining entry, so kept originals get their cloaked names back;
  - deletes the file on a clean run (`finalize`).
- On startup (`_maybe_recover_pending_renames`), leftover `relocation` entries are restored automatically, without a prompt, because they would otherwise strand a source volume in a work directory. Leftover `uncloak` entries are offered for revert (default "no"). Leftover `temp.deepunzip-*` work directories are reported.
- Tests: `tests/test_rename_history.py`, `tests/test_main.py`.

## Cleanup safety guards (do not break these)
- **Sources are deleted by lineage, only at the end of a root's run.** `WorkPool._cleanup_sources` deletes a source only if:
  - it was consumed;
  - it has at least one descendant;
  - no descendant is unresolved (password failure, missing volume, error, empty archive, failed move).

  Regular files in the input root are `kept` and never touched. Deletion defaults to the Recycle Bin (`send2trash`); `--permanent-delete` overrides.
- **Nothing is lost.** Before the work directory is removed, every unresolved derived item is moved to `<root>/unzipped/`, and a failed set's volumes are kept together. A failed move keeps the work directory and its sources.
- **Multipart retention on failure.** A failed set never deletes or moves away source volumes. Volumes moved for an attempt always return home.

## Multipart sets across containers
Multipart volumes may come from the input root or from any container, at any depth. The work pool (`deepunzip/modules/work_pool.py`, with pure helpers in `multipart_assembly.py`) treats them uniformly.

- Primary vs continuation identification (`multipart_assembly.parse_volume_name`):
  - 7z volumes: primary is `.7z.001`; continuations are `.7z.002+`.
  - TAR multipart: primary is `.tar.gz/.tar.bz2/.tar.xz.001`; continuations are `.002+`.
  - Generic 7-Zip split (any extension): primary is `name.<ext>.001`; continuations are `name.<ext>.002+` (3+ zero-padded digits; covers `.zip.001`, `.rar.001`, `.iso.001`, ...).
  - RAR volumes: primary is `.rar` or `.part1.rar`; continuations are `.r00`, `.r01`, ... and `.part2+.rar`.
  - ZIP spanned: primary is `.zip`; continuations are `.z01`, `.z02`, ...
  - ZIPX spanned: primary is `.zipx`; continuations are `.zx01`, `.zx02`, ...
  - ARJ volumes: primary is `.arj`; continuations are `.a01`, `.a02`, ...
  - ACE volumes: primary is `.ace`; continuations are `.c00`, `.c01`, ... (classification only: the bundled 7-Zip cannot extract ACE, so such sets fail and their parts are retained).

- Behavior:
  - Continuations are never opened as containers. They wait in the pool until a set uses them, or they are preserved to the output.
  - `.rar`/`.zip`/`.zipx`/`.arj`/`.ace` are set primaries only while a matching continuation exists. One that already failed as a single container becomes a primary when a continuation appears later. One whose set fails, and that was never opened as a container, falls back to being opened as a container.
  - Assembly runs only when no container is pending. It uses pool items only, and widens scope: the primary's folder, then its subtree, then each ancestor's subtree, never above the input root.
  - Each combination goes through, in order:
    - prefilters: equal sizes for 7z / numbered splits, and the 7z start-header total;
    - a header-only probe;
    - extraction in an isolated `<work>/.assemble/<n>/` folder.
  - When 7-Zip reports using fewer volumes than chosen, the unused ones are not consumed.
  - A failed set retries when new volumes with its key arrive, or after a password is learned. At quiescence it prompts at most once, then fails.
  - The search is capped at `MAX_ASSEMBLY_ATTEMPTS` (64) probes per set.
  - Byte-identical duplicate volumes count as used.

- Validation:
  - Unit tests: `tests/test_multipart_assembly.py`, `tests/test_work_pool.py` (fake engine), `tests/test_pool_engine.py`.
  - CLI-level tests with mocked 7-Zip: `tests/test_main.py`, `tests/test_multipart_file_input.py`, `tests/test_multipart_retention.py`.
  - Real engine: `poetry run python -m scripts.smoke_test`. The end-to-end reproduction is recorded in `openspec/changes/archive/2026-10-25-redesign-work-pool-extraction/validation.md`.

## Non-archive handling during nested scan
The tool treats every file as a potential archive by default. During nested extraction, we probe files with 7‑Zip but avoid flagging regular files (e.g., .mp4) as corrupted by mapping 7‑Zip output appropriately and parsing list output robustly.

- Behavior:
  - All files are candidates for probing via 7‑Zip.
  - If 7‑Zip prints messages like “Can not open file as archive”, “cannot open file as archive”, or “is not archive”, we treat this as unsupported/non‑archive (not corruption) and skip it.
  - Regular files encountered during nested scanning therefore do not produce spurious corruption errors.

- Implementation:
  - `deepunzip/modules/archive_utils.py` → `_raise_for_7z_error()` maps the above messages to `ArchiveUnsupportedError` (non‑archive/unsupported), not `ArchiveCorruptedError`.
  - `_parse7zListOutput()` begins parsing after the dashed separator to remain compatible with varying 7‑Zip outputs.
  - `is_valid_archive()` uses 7‑Zip listing plus the mapping above to determine if a file is an archive.

- Validation:
  - Unit tests: `poetry run pytest -q` should pass.
  - Smoke: running against directories containing non‑archive files (e.g., .mp4) should not produce “corrupted archive” messages for those files.

## Common Local Paths
- 7-Zip: `./7z/windows-x64/7z.exe` + `7z.dll` (Windows), `./7z/macos/7zz`, `./7z/linux-x64/7zzs`, or `./7z/linux-arm64/7zzs`; each platform directory also contains its `License.txt`.
- Config: `deepunzip/config/cloaked_file_rules.json`
- CLI Entrypoint: `deepunzip/__main__.py`

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
