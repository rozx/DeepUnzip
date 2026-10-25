# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Always use TDD

This repository follows **Test-Driven Development**. For every feature or bugfix:

1. Write a failing test first (regression test that reproduces the bug, or a test that specifies the new behavior).
2. Confirm it fails for the right reason (`poetry run pytest tests/<file>::<test> -q`).
3. Write the minimum code to make it pass.
4. Refactor with the test green.

Unit tests do **not** execute the real 7-Zip engine — the extraction engine's subprocess calls are mocked with `monkeypatch` and filesystem effects use the `tmp_path` fixture. Pure helpers (regex/grouping/uncloaking/path-normalization) are tested directly. Prefer this style: small, deterministic, no real archives.

## Commands

```powershell
poetry install                                  # install deps (Poetry, Python 3.11+)

poetry run pytest -q                            # run all tests
poetry run pytest tests/test_archive_utils.py -q          # one file
poetry run pytest tests/test_archive_utils.py::test_build_7z_extract_cmd -q   # one test
poetry run pytest -v                            # verbose

poetry run black complex_unzip_tool_v2/ tests/  # format (line-length 88)
poetry run flake8 complex_unzip_tool_v2/ tests/ # lint
poetry run mypy complex_unzip_tool_v2/          # type check (strict: disallow_untyped_defs)

poetry run main "C:\path\to\archives"           # run the tool (alias: poetry run cuz)
poetry run main --help                          # CLI smoke test
poetry run build                                # build native standalone -> dist/
poetry run bump-patch | bump-minor | bump-major # version bump (bump2version)
```

**Quality gates before committing:** `pytest -q` green, `flake8` clean, `mypy` clean, `black` applied, `--help` works.

Supported platforms: **Windows x64, macOS Intel/Apple Silicon, Linux x64/ARM64**. Native 7-Zip 26.03 engines are bundled; `modules/seven_zip_runtime.py` selects the correct one for source and frozen execution. See `7z/README.md` for paths, checksums, and licenses. Build on the target OS/architecture; Windows uses PowerShell and macOS/Linux use a native shell.

## Architecture

A CLI that extracts complex archives: password-protected, multipart, nested, and **cloaked** (disguised filenames). Built on Typer + Rich, driving the bundled 7-Zip binary via subprocess.

### Extraction pipeline (the big picture)

[main.py](complex_unzip_tool_v2/main.py) `extract_files()` is a fixed 9-step pipeline. Understanding the *ordering* is essential because later steps depend on earlier ones:

1. Set up `unzipped/` output folder (name from `const.OUTPUT_FOLDER`).
2. Load passwords ([password_util.py](complex_unzip_tool_v2/modules/password_util.py) → [PasswordBook](complex_unzip_tool_v2/classes/PasswordBook.py)).
3. Scan input paths into a flat file list ([file_utils.py](complex_unzip_tool_v2/modules/file_utils.py) `read_dir`).
4. **Uncloak** disguised filenames in place ([cloaked_file_detector.py](complex_unzip_tool_v2/modules/cloaked_file_detector.py)) — every rename is recorded in a [RenameHistory](complex_unzip_tool_v2/modules/rename_history.py).
5. Group files into `ArchiveGroup`s by name+directory ([file_utils.py](complex_unzip_tool_v2/modules/file_utils.py) `create_groups_by_name`); bind rename-history entries to their group.
6. Print group summary.
7. **Single archives first** — extracting them may surface *contained* multipart sets, which get registered as new groups (`ensure_contained_multipart_groups`) for step 8.
8. **Multipart archives** — extracted after singles so all volumes (including ones found inside containers and relocated in step 7's reconciliation pass) are present.
9. Final summary; save newly learned passwords; revert/finalize rename history.

The recursive engine is [archive_utils.py](complex_unzip_tool_v2/modules/archive_utils.py) `extract_nested_archives()`. It validates each file with 7-Zip, tries every password (empty password first), recurses into nested archives into per-archive subfolders, and returns a result dict (`success`, `final_files`, `password_failed_archives`, `candidate_multipart_parts`, …). `main.py` then moves `final_files` into the output folder preserving structure.

### Multipart: primary vs. continuation (cross-cutting invariant)

7-Zip must be invoked on the **primary** volume, never a continuation part. This distinction is duplicated across several files and must stay consistent:

- [regex.py](complex_unzip_tool_v2/modules/regex.py) — `multipart_regex` (is this any part of a set?) and `first_part_regex` (is this an unambiguous entry point?).
- [ArchiveGroup.py](complex_unzip_tool_v2/classes/ArchiveGroup.py) — `_entry_point_priority()` ranks files so `mainArchiveFile` is always the right entry point (e.g. spanned ZIP keeps `.zip`, not `.z01`; volume RAR keeps `.rar`, not `.r00`), regardless of insertion order. `try_set_alternative_main_archive()` is the fallback when the chosen main fails.
- `archive_utils.py` / `file_utils.py` — relocate continuation parts (`.7z.002+`, `.<ext>.002+`, `.r00+`, `.z01+`, `.zx01+`, `.a01+`, `.c00+`, `.part2+.rar`) next to their primary instead of treating them as nested archives or final files.

Primary/continuation rules per format: `.7z.001` primary / `.7z.002+` cont; `.tar.{gz,bz2,xz}.001` primary / `.002+` cont; **generic 7-Zip split `name.<ext>.001` primary / `name.<ext>.002+` cont** (any `<ext>` — covers `.zip.001`, `.rar.001`, `.iso.001`, …; 3+ zero-padded digits); `.rar` or `.part1.rar` primary / `.r00+`,`.part2+.rar` cont; `.zip` primary / `.z01+` cont; `.zipx` primary / `.zx01+` cont; `.arj` primary / `.a01+` cont; `.ace` primary / `.c00+` cont (ACE is grouped/classified only — the bundled 7-Zip cannot extract ACE, so such sets fail extraction and parts are retained).

### Cloaked-file detection + signature gate

[CloakedFileDetector](complex_unzip_tool_v2/modules/cloaked_file_detector.py) normalizes disguised names (e.g. `11111.7z.00删1` → `11111.7z.001`) using priority-ordered JSON rules in [config/cloaked_file_rules.json](complex_unzip_tool_v2/config/cloaked_file_rules.json). Safety gate in `_verify_with_signature()`: if the name carries an explicit archive token (`.7z`/`.rar`/`.zip`, via `ARCHIVE_TOKEN_RE`) the rename is trusted (continuation parts legitimately have no signature); otherwise the type was only *guessed* from a trailing number and a real magic-byte signature (`archive_extension_utils.detect_archive_extension`) is required — this prevents renaming ordinary files into fake parts. Editing rules = edit the JSON, not the code.

### Rename-history revert-on-failure

[RenameHistory](complex_unzip_tool_v2/modules/rename_history.py) persists every uncloak rename eagerly (atomic temp+replace) to `<input_root>/.unzip-rename-history.tmp.json`. Per group: on extraction **success** the entries are cleared; on **failure** they are reverted so the user can recover the original (still-cloaked) files manually (`_reconcile_rename_history` in main.py mirrors `_should_delete_original_archives`). Leftover history from a crashed run is offered for recovery at startup (`_maybe_recover_pending_renames`).

### Other invariants

- **Never delete originals on password failure.** `_should_delete_original_archives()` gates all source deletion on an empty `password_failed_archives`. Deletion defaults to Recycle Bin (`send2trash`); `--permanent-delete` overrides.
- **Multipart retention on failure.** When a multipart set fails to extract, source parts are kept; only tool-created temp folders are removed.
- Domain errors live in [ArchiveExceptions.py](complex_unzip_tool_v2/classes/ArchiveExceptions.py) / [ArchiveTypes.py](complex_unzip_tool_v2/classes/ArchiveTypes.py); `_raise_for_7z_error()` maps 7-Zip output to them (notably "not an archive" → `ArchiveUnsupportedError`, **not** corruption, so regular files like `.mp4` aren't flagged as corrupt during nested scans).
- All user-facing strings are **bilingual (English 中文)**; output goes through [rich_utils.py](complex_unzip_tool_v2/modules/rich_utils.py) helpers — match that style, don't `print()` directly.

## Conventions & workflow

- Detailed conventions live in [AGENTS.md](AGENTS.md) (operating guide, passwords, uncloaking rules, nested handling) and [openspec/project.md](openspec/project.md). Read those before larger changes; if anything conflicts with [README.md](README.md), README wins.
- This project uses **OpenSpec** for spec-driven development. Specs are in `openspec/specs/`, proposed changes in `openspec/changes/`. For non-trivial features/changes, follow the OpenSpec workflow (the `openspec-*` skills) rather than ad-hoc edits.
- Keep PRs atomic (~<300 lines; a release is one PR from `release/vX.Y.Z`, so keep its commits atomic instead), reuse existing utilities, don't add dependencies without justification, and never modify bundled binaries under `7z/`.
