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

### Extraction flow: the work pool (the big picture)

[main.py](complex_unzip_tool_v2/main.py) `run()` picks the renderer, checks the engine and the paths, calls `extract_files()` and returns the exit code (see "Output" below). `extract_files()` loads the password book once ([password_util.py](complex_unzip_tool_v2/modules/password_util.py) → [PasswordBook](complex_unzip_tool_v2/classes/PasswordBook.py), which keeps file order so "password #N" is stable). Then, for each **input root** (a folder passed on the command line, or a file's folder; nested roots merge: `work_pool.group_input_roots`), it:

1. recovers what an interrupted run left behind (`_maybe_recover_pending_renames`): it reports `temp.deepunzip-*` work directories, restores `relocation` history entries automatically, and prompts (default "no") for `uncloak` entries;
2. scans the root with [file_utils.py](complex_unzip_tool_v2/modules/file_utils.py) `read_dir`, which skips `unzipped/` and work directories and adds the sibling volumes of a selected file;
3. runs a [WorkPool](complex_unzip_tool_v2/modules/work_pool.py) over the scanned sources with a [SevenZipEngine](complex_unzip_tool_v2/modules/pool_engine.py);
4. reconciles rename history from the result (clears the entries of deleted sources, reverts the rest).

Finally it saves newly learned passwords and returns the results; the renderer prints each root's lineage tree and summary from the `RootFinished` event.

The pool runs in **rounds until a round changes nothing**. Every file, scanned or extracted at any depth, becomes a `WorkItem` with a lineage (the set of sources it descends from), and goes through the same cycle:

- **Uncloak** ([cloaked_file_detector.py](complex_unzip_tool_v2/modules/cloaked_file_detector.py)). Only renames of sources are recorded in [RenameHistory](complex_unzip_tool_v2/modules/rename_history.py).
- **Classify**: first by multipart name ([multipart_assembly.py](complex_unzip_tool_v2/modules/multipart_assembly.py) `parse_volume_name`), then with `engine.classify` (container / regular / broken).
- **Containers** are opened **one level per round** into `<root>/temp.deepunzip-<run>/…`, and their contents re-enter the pool. A consumed derived archive is cleaned up at once.
- **Multipart sets** are assembled only when no container is pending, and only from pool items. The search widens scope (`iter_combinations`): the primary's folder, then its subtree, then each ancestor's subtree, never above the input root. Each combination goes through size and 7z-header prefilters, then a header-only probe, then extraction in an isolated `.assemble/<n>/` folder. Source volumes moved there are recorded as `relocation` entries and always moved back. A failed set waits for new volumes with its key, or for a newly learned password. At quiescence it prompts at most once, then fails.
- **Finalization**: final and unresolved derived items move to `<root>/unzipped/`, and the work directory is removed. A source is deleted only if it was consumed, has descendants, and none of them is unresolved.

Design and requirements: `openspec/changes/redesign-work-pool-extraction/` (moved to `openspec/specs/` when archived).

### Multipart: primary vs. continuation (cross-cutting invariant)

7-Zip must be invoked on the **primary** volume, never a continuation part. This distinction exists in a few places and must stay consistent:

- [multipart_assembly.py](complex_unzip_tool_v2/modules/multipart_assembly.py) `parse_volume_name`: the work pool's single source of truth. It returns base, family, index (1 is the entry point; continuations count up), primary, and *ambiguous*. `.rar`/`.zip`/`.zipx`/`.arj`/`.ace` are ambiguous: they are set primaries only while a matching continuation is in the pool, and otherwise single containers. A continuation is never opened as a container. It waits in the pool, joins a set, or is preserved to the output.
- [regex.py](complex_unzip_tool_v2/modules/regex.py) `multipart_regex` / `first_part_regex`: used by `read_dir`'s sibling-volume discovery and by `ArchiveGroup`.
- [ArchiveGroup.py](complex_unzip_tool_v2/classes/ArchiveGroup.py) and `file_utils.create_groups_by_name`: name-based grouping, kept for the `multipart-format-detection` spec. `_entry_point_priority()` picks the right entry point (spanned ZIP keeps `.zip`, volume RAR keeps `.rar`).

Primary/continuation rules per format: `.7z.001` primary / `.7z.002+` cont; `.tar.{gz,bz2,xz}.001` primary / `.002+` cont; **generic 7-Zip split `name.<ext>.001` primary / `name.<ext>.002+` cont** (any `<ext>` — covers `.zip.001`, `.rar.001`, `.iso.001`, …; 3+ zero-padded digits); `.rar` or `.part1.rar` primary / `.r00+`,`.part2+.rar` cont; `.zip` primary / `.z01+` cont; `.zipx` primary / `.zx01+` cont; `.arj` primary / `.a01+` cont; `.ace` primary / `.c00+` cont (ACE is grouped/classified only — the bundled 7-Zip cannot extract ACE, so such sets fail extraction and parts are retained).

### Cloaked-file detection + signature gate

[CloakedFileDetector](complex_unzip_tool_v2/modules/cloaked_file_detector.py) normalizes disguised names (e.g. `11111.7z.00删1` → `11111.7z.001`) using priority-ordered JSON rules in [config/cloaked_file_rules.json](complex_unzip_tool_v2/config/cloaked_file_rules.json). Safety gate in `_verify_with_signature()`: if the name carries an explicit archive token (`.7z`/`.rar`/`.zip`, via `ARCHIVE_TOKEN_RE`) the rename is trusted (continuation parts legitimately have no signature); otherwise the type was only *guessed* from a trailing number and a real magic-byte signature (`archive_extension_utils.detect_archive_extension`) is required — this prevents renaming ordinary files into fake parts. Editing rules = edit the JSON, not the code.

### Rename-history revert-on-failure

[RenameHistory](complex_unzip_tool_v2/modules/rename_history.py) keeps one file per input root, `<input_root>/.unzip-rename-history.tmp.json`, persisted eagerly (atomic temp+replace). It records renames of **source** files only, in two kinds:

- `uncloak`: a cloaked-name normalization;
- `relocation`: a source volume moved into an assembly folder (via `RelocationLog`). These are cleared as soon as the volume is moved back.

After a root finishes, `main._reconcile_history` clears the entries of deleted sources and reverts the rest, so kept originals get their recognizable names back. At startup, leftover `relocation` entries are restored without asking; leftover `uncloak` entries are offered for revert (`_maybe_recover_pending_renames`).

### Other invariants

- **Sources are deleted by lineage, at the end of the run only.** `WorkPool._cleanup_sources` deletes a source only if it was consumed, has at least one descendant, and no descendant is unresolved (password failure, missing volume, error, empty archive, failed move). Regular files in the input root are `kept` and never touched. Deletion defaults to the Recycle Bin (`send2trash`); `--permanent-delete` overrides.
- **Nothing is lost.** Before the work directory is removed, every unresolved derived item (orphan volume, failed set, password-failed archive, …) is moved to the output, with a failed set's volumes kept together. If a move fails, the work directory is kept.
- Domain errors live in [ArchiveExceptions.py](complex_unzip_tool_v2/classes/ArchiveExceptions.py) / [ArchiveTypes.py](complex_unzip_tool_v2/classes/ArchiveTypes.py); `_raise_for_7z_error()` maps 7-Zip output to them (notably "not an archive" → `ArchiveUnsupportedError`, **not** corruption, so regular files like `.mp4` aren't flagged as corrupt during nested scans).

### Output

- **Events, then exactly one renderer.** The work pool, the engine and library code never print: they emit typed events from [events.py](complex_unzip_tool_v2/modules/events.py) (`events.emit`, or `events.notice(level, key, **params)` for warnings and info). [render.py](complex_unzip_tool_v2/modules/render.py) turns them into output: `TreeRenderer` when stdout is a terminal (live progress, then the lineage tree), `PlainRenderer` when it is redirected, `JsonRenderer` with `--json` (JSON lines only on stdout, `schema_version` 1, `summary` last). File names are printed as `rich.text.Text`, never as markup. A failed write (closed pipe) silences the renderer; it never stops the run.
- **Message catalog, one language per run.** Every user-facing string, including Typer help, is a key in [i18n.py](complex_unzip_tool_v2/modules/i18n.py) `CATALOG` with both `en` and `zh` text and the same placeholders (`tests/test_i18n.py` enforces it). Code calls `t(key, **params)`; never write inline user-facing strings, and never bilingual ones. The language is `DEEPUNZIP_LANG` (`zh`/`en`), else the system UI language, else English; tests pin English in `tests/conftest.py`.
- **Passwords are never output**, only their position in the book (`password #N`, `password_index`) or "entered".
- **Exit codes:** `0` everything resolved, `1` something unresolved, `2` fatal or usage error (engine missing, no existing path, unexpected exception). A run is non-interactive with `--json` or when stdin is not a console (`main._stdin_is_terminal`; Windows reports `< NUL` as a TTY): no password prompt, recovery takes its default, no exit pause.
- **Progress:** extraction with a sink runs `7z x … -bsp2`; [seven_zip_progress.py](complex_unzip_tool_v2/modules/seven_zip_progress.py) parses the percentages from stderr and keeps the remaining lines as error text for `_raise_for_7z_error()`.

## Conventions & workflow

- Detailed conventions live in [AGENTS.md](AGENTS.md) (operating guide, passwords, uncloaking rules, nested handling) and [openspec/project.md](openspec/project.md). Read those before larger changes; if anything conflicts with [README.md](README.md), README wins.
- This project uses **OpenSpec** for spec-driven development. Specs are in `openspec/specs/`, proposed changes in `openspec/changes/`. For non-trivial features/changes, follow the OpenSpec workflow (the `openspec-*` skills) rather than ad-hoc edits.
- Keep PRs atomic (~<300 lines; a release is one PR from `release/vX.Y.Z`, so keep its commits atomic instead), reuse existing utilities, don't add dependencies without justification, and never modify bundled binaries under `7z/`.
