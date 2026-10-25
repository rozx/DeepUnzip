The tasks follow TDD (`CLAUDE.md`): write the failing test first, with 7-Zip mocked and `tmp_path` for the filesystem. Paths use today's package name `complex_unzip_tool_v2/`. The rename to `deepunzip/` is the last code PR (`rename-to-deepunzip`).

## 1. Branch and baseline

- [ ] 1.1 Cut `release/v2.0.0` from an up-to-date `main`. Record baseline results of `pytest -q`, `flake8` and `mypy`, so later diffs can be compared.
- [ ] 1.2 Inventory the existing nested and multipart scenarios in `tests/test_main.py`, `tests/test_archive_utils.py` and `tests/test_multipart_*.py` that the pool must keep passing (the parity list).

## 2. Exceptions and 7-Zip helpers (PR 1)

- [ ] 2.1 Add `ArchiveMissingVolumeError` to `classes/ArchiveExceptions.py`. In `_raise_for_7z_error`, map 7-Zip's missing-volume and unexpected-end messages to it, with tests using recorded 7-Zip output. The password loop stops on this error instead of trying further passwords.
- [ ] 2.2 Add a 7z start-header parser that returns `32 + NextHeaderOffset + NextHeaderSize`, or `None` for files that are not 7z or are too short. Include a test with a synthetic header.
- [ ] 2.3 Consolidate `get_archive_base_name` and `_multipart_key_from_basename` into one key helper that returns (base, family, index, is_primary) for every supported format. Test each format, including uncloaked names.

## 3. Multipart assembly module (PR 1)

- [ ] 3.1 `modules/multipart_assembly.py`, scope enumeration:
  - order: own folder → own subtree → each ancestor's subtree;
  - never above the input root;
  - candidates come only from pool items.
- [ ] 3.2 Combination enumeration: a contiguous range 1..N per scope, and a gap skips the scope. Order by proximity, then size hint, then path.
- [ ] 3.3 Prefilters:
  - hard size consistency for `.7z.NNN` / `.<ext>.NNN`;
  - the 7z start-header total;
  - for RAR/ZIP/ZIPX/ARJ, size affects ordering only.
- [ ] 3.4 Cap `MAX_ASSEMBLY_ATTEMPTS = 64` probes per set over the whole run, with reason "too many combinations".
- [ ] 3.5 Duplicate detection: same key and index, then equal size, then equal content hash, giving consumed with reason "duplicate".

## 4. Work pool module (PR 1)

- [ ] 4.1 `modules/work_pool.py`:
  - a `WorkItem` with path, origin, lineage, depth, kind, state and reason;
  - per-input-root pools;
  - input-root derivation, with nested roots merged into the outer one.
- [ ] 4.2 Intake:
  - uncloak with `CloakedFileDetector` (source renames recorded in `RenameHistory`, derived renames not);
  - classify by multipart name first, then `is_valid_archive`;
  - source regular files become `kept`.
- [ ] 4.3 Container opening:
  - one level deep, into a fresh folder that is discarded on failure;
  - consumed on success, with immediate cleanup of derived containers;
  - missing-volume errors are deferred;
  - password and other failures make the item unresolved;
  - an empty result is unresolved with reason "empty";
  - depth limit 10 (reason "max depth").
- [ ] 4.4 Re-classification: an unresolved ambiguous primary (`.rar`/`.zip`/`.zipx`/`.arj`/`.ace`) returns to pending when a continuation with its key enters the pool.
- [ ] 4.5 Assembly phase:
  - runs only when no container is pending;
  - each attempt uses an isolated `<work>/.assemble/<n>/`;
  - source volumes are recorded as `relocation` entries and moved back after every attempt;
  - each attempt extracts into a fresh output folder;
  - extracted output is placed at the primary's location.
- [ ] 4.6 Deferral: a failed set is retried only after a new volume with its key arrives. At quiescence:
  - one injected prompt per qualifying set (complete combination, password-type failures only);
  - resume the loop if a set unlocks;
  - otherwise mark the remaining sets failed.
- [ ] 4.7 Finalization:
  - `final` and unresolved derived items move to `<root>/unzipped/` through `normalize_output_relative_path`;
  - a failed set's volumes are placed together;
  - a failed move keeps the work directory and keeps the affected lineages' sources.
- [ ] 4.8 Lineage source cleanup:
  - delete a source only if it is consumed, has at least one descendant, and no descendant is unresolved;
  - use `safe_remove` with the user's deletion mode;
  - `kept` items are never deleted;
  - remove emptied source subfolders;
  - clear or revert history entries per source.
- [ ] 4.9 Emit typed events (round, item opened, set assembled, unresolved, progress, root finished with lineage snapshot). Add a thin adapter that maps them onto today's `rich_utils` helpers until `redesign-terminal-output` lands.
- [ ] 4.10 Regression tests from the specs:
  - the reproduction case (two cross-container sets with cloaked `.7z.001删掉` primaries);
  - a volume hidden inside the `Y.part*.rar` set;
  - same-name sets;
  - the input-root ceiling;
  - an unscanned file on disk;
  - `readme.txt` kept;
  - a byte-identical duplicate volume;
  - a non-chosen same-name volume next to the primary;
  - a spanned `.zip` that failed as a container;
  - a failed move to the output folder.
- [ ] 4.11 Parity tests: every scenario from 1.2 passes against the pool.

## 5. Rename history (PR 2)

- [ ] 5.1 Add an entry `kind` (`uncloak` / `relocation`). Files written by 1.3.x without `kind` load as `uncloak`.
- [ ] 5.2 Startup recovery:
  - `relocation` entries are restored automatically, without a prompt;
  - `uncloak` entries keep the default-"no" prompt.
- [ ] 5.3 One history file per input root. Bind entries to source items instead of group names.

## 6. Switch the extraction flow (PR 2)

- [ ] 6.1 Extract `extract_one_level()` (the password loop, including "skip all prompts" for the rest of the run) from the `extract_nested_archives` closure.
- [ ] 6.2 Make `read_dir` skip `temp.deepunzip-*` work directories. Report a leftover work directory at startup.
- [ ] 6.3 Replace Steps 5–8 of `main.extract_files()` with per-root pool runs, each writing to its own `<root>/unzipped/`.
- [ ] 6.4 Rewrite the affected `tests/test_main.py` tests against the new flow.
- [ ] 6.5 Manual end-to-end check on a copy of the reproduction set:
  - both sets extract;
  - no `.002` is lost;
  - all four sources go to the Recycle Bin;
  - exit is clean.

## 7. Remove superseded code (PR 3)

- [ ] 7.1 Remove `extract_nested_archives`, `add_file_to_groups`, `relocate_multipart_parts_from_directory`, `ensure_contained_multipart_groups` and their tests.
- [ ] 7.2 Update the pipeline description in `CLAUDE.md`, `AGENTS.md` and `openspec/project.md`.
- [ ] 7.3 Quality gates: `pytest -q`, `flake8`, `mypy` (no new diagnostics against the 1.1 baseline), `black`, and `--help`.

## 8. Release v2.0.0 (after `redesign-terminal-output` and `rename-to-deepunzip`)

- [ ] 8.1 Run `poetry run bump-major`. Check that `pyproject.toml`, `__init__.py` and `.bumpversion.cfg` all read 2.0.0.
- [ ] 8.2 Write `ReleaseNotes/RELEASE_NOTES_v2.0.0.md`, bilingual, in the v1.3.x format. It opens with the rename and the old→new mapping. Its upgrade notes cover:
  - the new executable and asset names;
  - one `unzipped/` per root;
  - end-of-run source deletion;
  - exit codes 0/1/2;
  - single-language output and `DEEPUNZIP_LANG`;
  - `--json`;
  - relocation auto-restore.
- [ ] 8.3 Set the version summary, package table and release-notes link to 2.0.0 in all five READMEs.
- [ ] 8.4 Local verification:
  - `scripts.release version` / `verify-notes` / `verify-engines`;
  - `--version` / `--help`;
  - `pytest -q`;
  - `scripts.smoke_test`;
  - `git diff --check`.
- [ ] 8.5 Archive the three OpenSpec changes, then run `openspec validate --strict` on the merged specs.
- [ ] 8.6 Open the release PR `release/v2.0.0` → `main` with the `release` label, after the maintainer approves.
