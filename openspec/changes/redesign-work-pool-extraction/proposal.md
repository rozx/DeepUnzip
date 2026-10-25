## Why

The extraction flow is a fixed pipeline: uncloak and group the *input* files once (Steps 4–5), then extract singles (Step 7), each one recursing to the bottom on its own, then multipart sets (Step 8). Anything that only becomes visible after a container is opened — a cloaked name, a volume whose sibling lives in another container — depends on processing order and on ad-hoc patch-up passes (`group_relocator`, `relocate_multipart_parts_from_directory`, `ensure_contained_multipart_groups`). Real input breaks it, and loses data.

Reproduction: four encrypted containers (two `.7z`, two `.rar`) hold two 7z volume sets split across containers. Each `.rar` holds a cloaked primary `X.7z.001删掉`, and each `.7z` holds the matching `X.7z.002`. The run reported "4/4 successful" and recycled all four sources. But:

- each `.7z.002` was extracted before any group for its set existed, so it was skipped as an orphan continuation, never added to `final_files`, and permanently deleted with the temp folder. This violates `contained-multipart-preservation` ("Skipping recursion MUST NOT imply deletion");
- each `X.7z.001删掉` was never uncloaked, because uncloaking only runs on input files, so it reached the output as an opaque regular file and no multipart group was ever created.

Patching each symptom adds another special-case pass. The flow itself has to stop depending on where and when a file appears.

## What Changes

- **BREAKING (internal flow)** Replace Steps 5–8 with a **work pool** loop. Every file, whether an input or something extracted at any depth, enters one pool and goes through the same cycle: uncloak → classify → group → extract. The loop repeats until a round makes no progress.
  - Containers (single archives) are opened **one level at a time**; their contents go back into the pool instead of being recursed privately inside `extract_nested_archives`.
  - Each **input root** (the folder passed on the command line, or the parent folder of a file passed) has its own pool, work directory, output folder (`<root>/unzipped/`) and rename-history file. Volumes from different input roots are never combined, and nothing is ever moved across drives. **User-visible:** with several input paths in different folders, output is no longer all written to the first path's `unzipped/`.
  - Files are classified by multipart **name first**, then by archive validation, so a lone `X.7z.001` is never mistaken for a regular file.
  - Multipart sets are assembled by **widening scope ("mix & match")**, stopping at the first combination that extracts:
    1. combinations in the primary's own folder;
    2. then its subtree;
    3. then each parent folder's subtree in turn, **up to the input root at most**.

    Only scanned or extracted files are candidates, never unrelated files on disk. This also resolves same-name sets coming from different containers. Each attempt runs in an isolated assembly folder holding exactly the chosen volumes; source volumes are moved back after every attempt. Byte-identical duplicate volumes are treated as used.
  - A set whose volumes are still missing **waits**. Assembly runs only after no unopened containers remain. A failed set is retried whenever a new volume with its key appears, and is finally marked failed only when the whole pool is quiescent. An ambiguous `.zip`/`.rar` that failed as a single archive becomes a set primary if a matching continuation appears later.
  - Recursion depth is tracked per item lineage (default 10, as today) to bound archive bombs and loops.
- **Uncloaking applies to extracted files**, not only to inputs: a cloaked name surfaced from a container (e.g. `X.7z.001删掉`) is normalized under the same rules and signature gate as a top-level file.
- **No orphan is ever dropped.** When the pool goes quiet, every item that could not be resolved is moved to the output folder before any tool-created work directory is removed: an orphan continuation part, an incomplete set, a password-failed archive, an unsupported format.
- **Source deletion is decided by lineage at the end of the run**, not per group as each one finishes. An original input archive is deleted (Recycle Bin by default, `--permanent-delete` to override) only if every item derived from it was either extracted or emitted as a final regular file. The source is kept in these cases:
  - any descendant is unresolved (password failure, missing volume, error);
  - the archive extracted to nothing, which matches today.

  A multipart set built from volumes of several containers resolves all of them together. Regular files in the input root (`readme.txt`, images) are left in place and never deleted.
- After a crash, source volumes that were moved for assembly are restored **automatically** at startup. Reverting cloaked-name renames still asks.
- Unchanged: password book and prompts, archive classification (`nested-archive-classification`), 7-Zip invocation (one new mapping: "missing volume" becomes its own error instead of a generic failure), primary/continuation naming rules, and output-path normalization. Console output, `--json` and exit codes are specified separately in `redesign-terminal-output`.

## Capabilities

### New Capabilities
- `work-pool-extraction`: the pool-driven extraction loop. One pool per input root, one-level container opening, multipart assembly by widening scope up to the input root, waiting on incomplete sets until containers are exhausted, the termination (no-progress) rule, the lineage depth limit, and preservation of every unresolved item to the output folder.
- `nested-uncloaking`: cloaked-name normalization for files surfaced by extraction at any depth, with the same rules and signature gate as input files.
- `lineage-source-cleanup`: end-of-run deletion of original inputs based on the resolution state of all their descendants, including sets assembled across several sources.

### Modified Capabilities
- `contained-multipart-preservation`: requirements are restated in pool terms. The `group_relocator` scenario is replaced, and an orphan continuation part is held in the pool and preserved to output if it is still unmatched at quiescence, regardless of extraction order.
- `contained-zip-rar-autogrouping`: the ambiguity rules (a `.zip`/`.rar`/`.zipx`/`.arj`/`.ace` primary needs a continuation part; `.7z.001`/`.<ext>.001` may stand alone) now apply to pool grouping across containers. They no longer apply to a Step 7 output-folder bucket via `ensure_contained_multipart_groups`.
- `multipart-retention`: adds the cross-container case. When a set assembled from several containers fails, every gathered volume is preserved and none of the contributing sources is deleted.
- `rename-history`: binding and revert are tied to lineage resolution instead of "after Step 5" / "Step 7 or Step 8" group outcomes. There is one history file per input root. Moves of source volumes made for assembly are recorded as `relocation` entries, which are restored automatically at startup after a crash. Renames of tool-extracted files are **not** recorded: they are derived copies, and the source container is the recovery point.

## Impact

- **Code**:
  - `main.py` `extract_files()`: Steps 5–8 (~800 lines, including four `extract_nested_archives` call sites and their duplicated retry/cleanup branches) are replaced by a pool driver.
  - `modules/archive_utils.py` `extract_nested_archives()`: split into a single-level extract plus classification; the private recursion, the candidate-part matching and `_move_parts_next_to_primary` move into the pool.
  - `modules/file_utils.py`: `add_file_to_groups`, `relocate_multipart_parts_from_directory` and `ensure_contained_multipart_groups` are superseded by pool grouping (the reusable regex and base-name helpers stay).
  - `classes/ArchiveGroup.py`: reused, gaining lineage.
  - `classes/ArchiveExceptions.py`: new `ArchiveMissingVolumeError`. `modules/rename_history.py`: entry kind and relocation auto-restore.
  - New: `modules/work_pool.py` (work items and the round driver) and `modules/multipart_assembly.py` (scopes, combinations, prefilters).
- **Tests**: `tests/test_main.py` and the nested parts of `tests/test_archive_utils.py` are largely rewritten against the pool, keeping the mocked-7-Zip / `tmp_path` style. A regression test reproduces the cross-container cloaked-volume case above.
- **Behavior**:
  - Sources are no longer deleted mid-run, so an interrupted run leaves every original in place.
  - For a single input path, output for previously working inputs is expected to be identical.
  - With several input roots, each root gets its own `unzipped/`.
  - Console structure changes; README step descriptions need updating.
- **Release**: ships as **v2.0.0**, a major bump from 1.3.2 (the three changes together break names, exit codes and output conventions), together with `redesign-terminal-output` (new output, `--json`, exit codes) and `rename-to-deepunzip` (DeepUnzip identity, five-language README). This change brings the new extraction behavior and a user-visible output-folder change for multi-root invocations. The release includes bilingual release notes with upgrade notes.
- **Delivery**: the change exceeds the ~300-line PR guideline, so it lands in stages on the integration branch `release/v2.0.0`:
  1. pool core + tests, behind an internal entry point;
  2. switch `extract_files()` to it;
  3. remove the superseded helpers, update the developer docs, and archive this change.

  A final release PR (`release/v2.0.0` → `main`, with the `release` label) then performs the version bump, adds the release notes and README updates, and triggers the automated release.
