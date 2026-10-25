The tasks follow TDD (`CLAUDE.md`): write the failing test first, with 7-Zip mocked and `tmp_path` for the filesystem. Paths use today's package name `complex_unzip_tool_v2/`. The rename to `deepunzip/` is the last code PR (`rename-to-deepunzip`).

## 1. Branch and baseline

- [x] 1.1 Cut `release/v2.0.0` from an up-to-date `main`. Record baseline results of `pytest -q`, `flake8` and `mypy`, so later diffs can be compared.
- [x] 1.2 Inventory the existing nested and multipart scenarios in `tests/test_main.py`, `tests/test_archive_utils.py` and `tests/test_multipart_*.py` that the pool must keep passing (the parity list).

## 2. Exceptions and 7-Zip helpers (stage 1)

- [x] 2.1 Add `ArchiveMissingVolumeError` to `classes/ArchiveTypes.py` (the module the code imports; the duplicate `ArchiveExceptions.py` is kept identical). In `_raise_for_7z_error`, map 7-Zip's missing-volume and unexpected-end messages to it, with tests using recorded 7-Zip output. The password loop stops on this error instead of trying further passwords.
- [x] 2.2 Add a 7z start-header parser that returns `32 + NextHeaderOffset + NextHeaderSize`, or `None` for files that are not 7z or are too short. Include a test with a synthetic header.
- [x] 2.3 Consolidate `get_archive_base_name` and `_multipart_key_from_basename` into one key helper that returns (base, family, index, is_primary) for every supported format. Test each format, including uncloaked names. (`multipart_assembly.parse_volume_name`; the old helpers go with the old flow in 7.1.)

## 3. Multipart assembly module (stage 1)

- [x] 3.1 `modules/multipart_assembly.py`, scope enumeration:
  - order: own folder → own subtree → each ancestor's subtree;
  - never above the input root;
  - candidates come only from pool items.
- [x] 3.2 Combination enumeration: a contiguous range 1..N per scope, and a gap skips the scope. Order by proximity, then size hint, then path.
- [x] 3.3 Prefilters:
  - hard size consistency for `.7z.NNN` / `.<ext>.NNN`;
  - the 7z start-header total;
  - for RAR/ZIP/ZIPX/ARJ, size affects ordering only.
- [x] 3.4 Cap `MAX_ASSEMBLY_ATTEMPTS = 64` probes per set over the whole run, with reason "too many combinations".
- [x] 3.5 Duplicate detection: same key and index, then equal size, then equal content hash, giving consumed with reason "duplicate".

## 4. Work pool module (stage 1)

- [x] 4.1 `modules/work_pool.py`:
  - a `WorkItem` with path, origin, lineage, depth, kind, state and reason;
  - per-input-root pools;
  - input-root derivation, with nested roots merged into the outer one.
- [x] 4.2 Intake:
  - uncloak through an injected uncloaker that knows whether the item is a source (the `CloakedFileDetector` + `RenameHistory` wiring is task 6.3);
  - classify by multipart name first, then `is_valid_archive`;
  - source regular files become `kept`.
- [x] 4.3 Container opening:
  - one level deep, into a fresh folder that is discarded on failure;
  - consumed on success, with immediate cleanup of derived containers;
  - missing-volume errors are deferred;
  - password and other failures make the item unresolved;
  - an empty result is unresolved with reason "empty";
  - depth limit 10 (reason "max depth").
- [x] 4.4 Re-classification: an unresolved ambiguous primary (`.rar`/`.zip`/`.zipx`/`.arj`/`.ace`) returns to pending when a continuation with its key enters the pool.
- [x] 4.5 Assembly phase:
  - runs only when no container is pending;
  - each attempt uses an isolated `<work>/.assemble/<n>/`;
  - source volumes are recorded as `relocation` entries and moved back after every attempt;
  - each attempt extracts into a fresh output folder;
  - extracted output is placed at the primary's location.
- [x] 4.6 Deferral: a failed set is retried only after a new volume with its key arrives. At quiescence:
  - one injected prompt per qualifying set (a complete combination; at least one password failure and otherwise only missing-volume failures);
  - resume the loop if a set unlocks;
  - otherwise mark the remaining sets failed.
- [x] 4.7 Finalization:
  - `final` and unresolved derived items move to `<root>/unzipped/` through `normalize_output_relative_path`;
  - a failed set's volumes are placed together;
  - a failed move keeps the work directory and keeps the affected lineages' sources.
- [x] 4.8 Lineage source cleanup:
  - delete a source only if it is consumed, has at least one descendant, and no descendant is unresolved;
  - use an injected remover (`safe_remove` with the user's deletion mode is wired in 6.3);
  - `kept` items are never deleted;
  - remove emptied source subfolders.

  Clearing or reverting history entries per source moved to 5.3.
- [x] 4.9 Emit typed events (round, item opened, set assembled, unresolved, root finished with the full result). The thin `rich_utils` adapter moved to 6.3, and `Progress` events come with `redesign-terminal-output` task 3.3.
- [x] 4.10 Regression tests from the specs:
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
- [x] 4.11 Parity tests: every scenario from 1.2 passes against the pool.

## 5. Rename history (stage 2)

- [x] 5.1 Add an entry `kind` (`uncloak` / `relocation`). Files written by 1.3.x without `kind` load as `uncloak`.
- [x] 5.2 Startup recovery:
  - `relocation` entries are restored automatically, without a prompt;
  - `uncloak` entries keep the default-"no" prompt.
- [x] 5.3 One history file per input root. Bind entries to source items instead of group names. Clear the entries of deleted sources, and revert those of kept ones (`PoolResult.deleted_sources` / `kept_sources`).

## 6. Switch the extraction flow (stage 2)

- [x] 6.1 Extract `extract_one_level()` (the password loop, including "skip all prompts" for the rest of the run) from the `extract_nested_archives` closure.
- [x] 6.2 Make `read_dir` skip `temp.deepunzip-*` work directories. Report a leftover work directory at startup.
- [x] 6.3 Replace Steps 5–8 of `main.extract_files()` with per-root pool runs, each writing to its own `<root>/unzipped/`. Wire up:
  - the real engine (`extract_one_level`, a probe that rejects a bare one-volume `Split` and reports `Volumes = N`);
  - `CloakedFileDetector` with `RenameHistory` for sources;
  - `safe_remove` with the deletion mode;
  - the relocation log;
  - a thin adapter from pool events to today's `rich_utils` helpers.
- [x] 6.4 Rewrite the affected `tests/test_main.py` tests against the new flow.
- [x] 6.5 Manual end-to-end check on a copy of the reproduction set:
  - both sets extract;
  - no `.002` is lost;
  - all four sources go to the Recycle Bin;
  - exit is clean.

## 7. Remove superseded code (stage 3)

- [ ] 7.1 Remove `extract_nested_archives`, `add_file_to_groups`, `relocate_multipart_parts_from_directory`, `ensure_contained_multipart_groups` and their tests.
- [ ] 7.2 Update the pipeline description in `CLAUDE.md`, `AGENTS.md` and `openspec/project.md`.
- [ ] 7.3 Quality gates: `pytest -q`, `flake8`, `mypy` (no new diagnostics against the 1.1 baseline), `black`, and `--help`.

## 8. Release v2.0.0 (after `redesign-terminal-output`, `rename-to-deepunzip` and `adopt-release-ready-workflow`)

- [ ] 8.1 Archive the four v2.0.0 OpenSpec changes once their tasks are complete, then run `openspec validate --specs --strict`.
- [ ] 8.2 After the maintainer approves, run the `release-ready` skill on `release/v2.0.0`. It:
  - bumps the version (`poetry run bump-major`) in its own commit;
  - writes `docs/releaseNotes/v2.0.0.md`, which opens with the rename and the old→new mapping;
  - updates the version summary, package table and release-notes link in all five READMEs;
  - runs the checks;
  - pushes;
  - opens the single release PR `release: v2.0.0`.
- [ ] 8.3 The upgrade notes of `docs/releaseNotes/v2.0.0.md` cover:
  - the new executable and asset names;
  - one `unzipped/` per root;
  - end-of-run source deletion;
  - exit codes 0/1/2;
  - single-language output and `DEEPUNZIP_LANG`;
  - `--json`;
  - relocation auto-restore;
  - the new release-notes location.
