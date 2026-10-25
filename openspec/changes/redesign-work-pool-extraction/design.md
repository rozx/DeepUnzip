## Context

`extract_files()` in `main.py` runs a fixed pipeline. It uncloaks and groups the scanned input files once (Steps 4–5), then extracts single archives (Step 7) and then multipart groups (Step 8). Each single archive is handed to `extract_nested_archives()`, which recurses to the bottom of that one archive in a private temp folder. Anything that becomes visible only after a container is opened is handled by patch-up passes:

- `group_relocator` / `add_file_to_groups`: only works if the group already exists.
- `candidate_multipart_parts`: only scoped to the current archive's recursion.
- `relocate_multipart_parts_from_directory` and `ensure_contained_multipart_groups`: only see what reached the output folder.

The proposal's reproduction (cloaked `.7z.001删掉` primaries and `.7z.002` continuations split across four containers) defeats all of them. It loses the `.002` volumes while reporting success.

Constraints carried over unchanged:

- Primary/continuation naming rules.
- `nested-archive-classification`.
- Password book and prompt UX, including "skip all prompts".
- 7-Zip invocation.
- Output-path normalization.
- Recycle-Bin-by-default deletion.
- `cleanup-guardrails`.
- TDD with mocked 7-Zip.

## Goals / Non-Goals

**Goals:**
- Results do not depend on which container, directory or depth a file comes from, or on processing order.
- Every file surfaced by extraction gets the same treatment as an input file: uncloak, classify, group.
- Multipart volumes can be assembled across containers and directories within one input root, including resolving same-name ambiguity.
- No item is ever lost. Unresolved items always reach the output folder before work directories are removed.
- Originals are deleted only when everything derived from them is resolved.
- Nothing is ever moved across input roots, and so never across drives.

**Non-Goals:**
- New archive formats, a new classification policy, or changes to the password file format.
- Parallel extraction.
- CLI and console output changes. Those are specified in `redesign-terminal-output` (`--json`, exit codes, single-language output). Naming is specified in `rename-to-deepunzip`.
- Undoing renames of tool-extracted (derived) files.

## Decisions

### D1. One pool of work items

Every file is a `WorkItem`:

- `path`
- `origin`: `source` (found by the input scan) or `derived` (extracted by the tool)
- `lineage`: the set of source items it descends from
- `depth`
- `kind`: container, multipart volume, regular, or unknown
- `state`, plus a reason:
  - `pending`: not processed yet.
  - `consumed`: opened or assembled successfully.
  - `final`: a derived regular file, destined for the output.
  - `kept`: a **source** regular file. It stays in place, is never moved and never deleted.
  - `unresolved`: could not be resolved.

A derived item's lineage is the union of its parents' lineages, so a volume set assembled from two containers descends from both sources.

A source regular file (a `readme.txt` or an image next to the archives) is `kept`. This matches today's behavior, where top-level non-archives are skipped and left alone.

*Alternative considered:* keep `ArchiveGroup` as the unit and add more relocation passes. Rejected, because each pass only covers the cases its author foresaw.

### D2. One pool, work directory, output folder and history per input root

An **input root** is a folder passed on the command line, or the parent folder of a file passed. When one root lies inside another, they are merged into the outer root.

Each input root gets its own:

- pool;
- run work directory, `<root>/temp.deepunzip-<run-id>/`;
- output folder, `<root>/unzipped/`;
- rename-history file, `<root>/.unzip-rename-history.tmp.json`.

Roots are processed one after another, and passwords learned in one root are reused in the next. Items from different roots never meet: no grouping, no multipart combination, no moves between them. So nothing is ever moved across drives.

This is a user-visible change for invocations with several paths in different folders. Today all output goes to the first path's `unzipped/`; now each root gets its own.

The work directory sits on the same filesystem as the inputs, so the moves done during assembly and finalization are plain renames, not copies. Inside it:

- each container is extracted one level deep into `<work>/<derived-folder-name>/`, reusing the existing `_derive_folder_name` and uniqueness suffixing;
- assembly attempts run under `<work>/.assemble/` (D4). The leading dot keeps it from colliding with a derived folder name.

`read_dir` skips the work directory as well as `unzipped/`. A leftover work directory from a crash is reported at startup (D6).

### D3. Round structure

The pool driver repeats one round until a round changes no item's state.

**1. Intake.** Newly added items are uncloaked (D6), then classified, in this order:

1. **By name first.** If the multipart regexes say a file is a primary or continuation volume, it is a `multipart volume`. `is_valid_archive` is not consulted, because a lone `X.7z.001` opens as a one-volume `Split` and would be rejected as a regular file.
2. **Otherwise, by content.** `is_valid_archive` decides between container and regular file.

An ambiguous primary (`.rar`, `.zip`, `.zipx`, `.arj`, `.ace`) counts as a multipart primary while a continuation with the same key exists in the pool. Otherwise it is a container.

**2. Open containers.** Every pending container is opened one level, in stable sorted-path order, using the existing password search. The search honors "skip all prompts" for the rest of the run. Each attempt extracts into a fresh folder, and that folder is discarded if the attempt fails. Outcomes:

- **Success:** the container is `consumed` and its contents enter intake. If the container is derived, it is cleaned up right away, honoring the deletion mode (D5).
- **Missing volume:** a failure that 7-Zip reports as a missing or unexpected-end volume is **deferred**. The item becomes a multipart-primary candidate instead of failing. This needs a new `ArchiveMissingVolumeError`, mapped in `_raise_for_7z_error`. Without it, the failure falls into the generic `ArchiveError`, and the password loop keeps trying every password.
- **Password or other failure:** the item becomes `unresolved`.

**Re-classification.** An `unresolved` item with an ambiguous primary extension returns to `pending` as a multipart primary when a continuation with its key later enters the pool. A spanned `.zip` opened alone can fail with "cannot open as archive" rather than "missing volume", and this rule covers it.

**3. Assemble multipart sets** (D4). This runs only in a round where no container was pending, so a volume that an unopened container might still contain is never declared missing.

- A set that fails is **deferred**, not failed.
- It is retried only after a new volume with its key has entered the pool since its last attempt.

**4. Depth limit.** An item whose depth exceeds `max_depth` (default 10) is not opened. It becomes `unresolved` with reason "max depth".

**Quiescence.** The loop stops after a round in which no container was opened and no set was attempted. Only then:

1. Each deferred set gets its single interactive password prompt (D4), if it qualifies.
2. If that prompt unlocks a set, the loop resumes.
3. Otherwise every remaining deferred set is finally marked failed.

**Termination** is guaranteed because:

- each container is opened at most once;
- a set is retried only after new volumes arrive, and new volumes only come from consuming an item;
- each set prompts at most once;
- the combination search is capped (D4).

### D4. Multipart assembly by widening scope ("mix & match")

Volumes are keyed by (base name, format family), consolidating `get_archive_base_name` and `_multipart_key_from_basename` into one helper.

**Candidates** are only pool items: scanned inputs (including today's same-set sibling discovery) and derived files. Other files on disk under the root are never used. This matters when a single dragged file makes a large folder such as Downloads the input root.

**Scopes.** For each key with a primary candidate, assembly searches progressively wider scopes and stops at the first success:

1. The primary's own folder.
2. The primary's own folder **and its whole subtree**. This covers a source primary in the root whose continuation was extracted into the work directory beneath it.
3. Each ancestor folder's subtree in turn, up to and including the **input root**, which is the widest scope. The search never goes above the input root (decided with the user).

**Combinations.** Within a scope, a combination picks one volume per index from the contiguous range 1..N available in the scope, where N is the highest index reached without a gap. If an index is missing, the scope cannot succeed, so the search moves to the next scope.

Combinations are ordered:

1. By proximity: total folder distance from the primary.
2. Then by size consistency: for formats where size is only a hint.
3. Then by path, for determinism.

Each combination goes through, in order:

1. **Cheap prefilters, without 7-Zip:**
   - For 7z splits and generic numbered splits (`.7z.NNN`, `.<ext>.NNN`), split-size consistency is a **hard filter**: all volumes except the last have the same size, and the last is not larger.
   - For a `.7z.001` primary, the sum of the volume sizes must equal `32 + NextHeaderOffset + NextHeaderSize` from the 7z start header. This header is never encrypted. It was verified against the reproduction files.
   - RAR, ZIP, ZIPX and ARJ volumes can legitimately differ in size (e.g. volume-size autodetect), so for them size only affects ordering.
2. **Probe**: `7z l` with the password list. This only reads the headers and is cheap.
3. **Full extraction**, with the password that passed the probe, into a fresh attempt folder. A data or CRC error is treated as a wrong combination: the attempt folder is discarded, and the search moves to the next combination.

At most `MAX_ASSEMBLY_ATTEMPTS` probes are made per set across the whole run. This is a fixed internal constant of 64 and is not exposed as a CLI option (decided with the user). After that the set is unresolved, with reason "too many combinations".

**Passwords**: a wrong combination can look exactly like a wrong password. With encrypted 7z headers, a mismatched last volume fails as "Wrong password?". So the interactive prompt is shown **at most once per set**, and only when all of these hold:

- the loop has reached quiescence;
- the set has a complete combination, with no gap;
- every probe failed with a password-type error.

The entered password is retried across the combinations in the same order, and joins the password book as today.

**Physical assembly in an isolated folder**: 7-Zip discovers sibling volumes by name, so a non-chosen same-name volume next to the primary would silently replace a chosen one. Every attempt therefore runs in a fresh `<work>/.assemble/<n>/` folder that contains exactly the chosen volumes.

- Derived volumes are moved in freely.
- A source volume moved in is recorded in `RenameHistory` as a `relocation` entry.
- After **every** attempt, success or failure, each source volume is moved back to its original location. Source files are therefore only ever deleted from where the user put them (D7). Derived volumes stay in the assembly folder only if the attempt succeeded and they are consumed.

**Outcome:**

- **On success:**
  - The chosen volumes are `consumed`.
  - The extracted contents enter intake. Their folder is placed at the primary's location, under a derived name, so output paths follow the primary.
  - Unchosen volumes of the same key stay `pending`, so a second, same-name set is attempted later.
  - **Duplicates**: a leftover volume of the same key and index whose size and content hash both equal a consumed volume's is marked `consumed` (reason "duplicate"). Hashes are computed only when the sizes already match. This stops reposted duplicate parts from pinning their source as unresolved.
  - A volume with no primary left is an orphan.
- **If every scope fails at quiescence:**
  - The set is marked failed.
  - Its primary and its unconsumed volumes become `unresolved`.
  - In the output, the set's derived volumes are placed **together** at the primary's output location, so the user can retry the set by hand.

*Alternatives considered:*
- Merge by name only. Wrong when two sets share a name.
- Refuse ambiguity. Loses the cross-container case.
- Assemble beside the primary. 7-Zip would pick up non-chosen same-name siblings.
- Hardlinks instead of moves. Not available on FAT/exFAT.

### D5. Cleanup during the run and finalization

**During the run**, a derived container or derived volume is cleaned up as soon as it is consumed, honoring the deletion mode, as nested cleanup does today. This keeps peak disk usage at roughly the sources plus the levels being worked on. Its source is still on disk (D7) if anything below it later fails.

**When the loop stops:**

1. **`final` items** are moved to `<root>/unzipped/`. Their relative path is computed below the extraction folder of their outermost source container, with `normalize_output_relative_path` applied as today. Contents of a top-level source container therefore land directly in `unzipped/`, as today.
2. **`unresolved` derived items** (orphan continuations, failed sets, password-failed, unsupported or empty nested archives, depth-limited items) are moved to the output in the same way. A failed set's volumes are placed together (D4).
3. **`kept` and `unresolved` source items** stay where they are.
4. **If any move to the output fails** (permissions, path length, …):
   - the work directory is **not** removed;
   - every source in the affected lineages is treated as unresolved, so it is kept;
   - the path of the work directory is reported.
5. **Otherwise**, the work directory is removed.

### D6. Uncloaking, rename history and recovery

Intake runs `CloakedFileDetector` on every new item, with the same rules and the same signature gate.

- Renames of **source** items are recorded in `RenameHistory` as `uncloak` entries, bound to that source.
- Renames of **derived** items are not recorded: they are tool-created copies, and their source is the recovery point.
- Source moves made for assembly are recorded as `relocation` entries (D4).

At startup, if a leftover history file is found:

- `relocation` entries are restored **automatically**, without a prompt. They are tool moves that, if left in place, would strand a source volume inside an excluded work directory.
- `uncloak` entries keep today's prompt, which defaults to "no".

A leftover work directory is reported together with the path it occupies.

### D7. Lineage-based source cleanup

After finalization, each source item `S` is deleted, by `safe_remove` with the user's deletion mode, if and only if:

- `S` is `consumed` (opened, or used in a successful set), and
- at least one item descends from `S`, and
- no item whose lineage contains `S` is `unresolved`.

Cases:

- `kept` sources are never deleted.
- A container that extracts to nothing is `unresolved` with reason "empty", so its source is kept. This matches today, where an empty result counts as failure.

For each source, the history entries bound to it are cleared if it is deleted, and reverted if it is kept. Sources are never deleted mid-run, so an interrupted run keeps every original.

After deletion, a source subfolder that became empty is removed, as today. The input root, the output folder and the work directory are never removed this way.

This replaces the per-group `_should_delete_original_archives` and `_reconcile_rename_history` calls.

### D8. Module layout

- `modules/work_pool.py`: `WorkItem` and the round driver. 7-Zip access is injected (extract-one-level, list, classify), so unit tests drive the whole loop with fakes and `tmp_path`.
- `modules/multipart_assembly.py`: pure logic for scopes, combinations and ordering, prefilters, 7z start-header parsing and duplicate detection.
- `modules/archive_utils.py`:
  - the password loop moves out of the `extract_nested_archives` closure into a reusable `extract_one_level()`;
  - `_raise_for_7z_error` gains the missing-volume mapping;
  - `extract_nested_archives` is removed once nothing calls it.
- `classes/ArchiveExceptions.py`: `ArchiveMissingVolumeError`.
- `modules/rename_history.py`: an entry `kind` (`uncloak` or `relocation`), and auto-restore of relocations at startup.
- `main.py`: `extract_files()` becomes: per root (setup → scan → pool run → finalize → source cleanup) → summary.
- Console output: the pool does not print. It emits typed events (round started, item opened, set assembled, item unresolved, progress, root finished with a lineage snapshot), and the renderers of `redesign-terminal-output` turn them into the terminal view or the `--json` stream. Until that change lands, a thin adapter maps these events onto the existing `rich_utils` helpers.

## Risks / Trade-offs

- [Combination explosion with many same-name candidates] → Proximity ordering, the size and 7z-header prefilters, a header-only probe, re-attempts only when new volumes arrive, and the `MAX_ASSEMBLY_ATTEMPTS` cap.
- [A wrong combination is detected only late in a large extraction (CRC at the end)] → The prefilters reject most wrong 7z and split combinations before any extraction. Accepted for RAR, where the probe lists the headers of every volume.
- [Moving source volumes during assembly] → Each move is recorded in `RenameHistory` (atomic and crash-recoverable), reversed after every attempt, and auto-restored at startup after a crash.
- [Hashing large duplicate candidates] → A hash is computed only for same-key, same-index volumes whose sizes already match, and only after a set succeeded.
- [Behavior drift for inputs that work today] → Port the existing `test_main.py` and nested `test_archive_utils.py` scenarios as parity tests against the pool before switching `extract_files()`.
- [Several input roots now produce several output folders] → Called out in the README and release notes. A single-path invocation is unaffected.
- [The work directory lives inside the input root] → It is excluded from the scan. Leftovers from a crash are reported, and stranded source volumes are auto-restored.

## Migration Plan

This change ships as **v2.0.0**, a major release from 1.3.2 (decided with the user), together with `redesign-terminal-output` and `rename-to-deepunzip`. This plan is the release plan for all three.

The release is major because it breaks compatibility under semver:
- new executable, asset and package names;
- new exit codes;
- single-language output;
- one output folder per input root;
- sources deleted only at the end of the run.

It also coincides with dropping the `v2` suffix from the old name. Together the three changes bring:

- new extraction behavior;
- a user-visible output-folder change for multi-root invocations;
- the new terminal output, `--json` and exit codes;
- the rename to DeepUnzip.

The integration branch is `release/v2.0.0`, cut from `main`. All staged PRs target it, so `main` never holds a half-switched flow. The order is: this change's PRs 1–3, then the terminal-output PRs, then the rename PRs, and finally the release PR. This change's PRs are:

1. **PR 1**: `multipart_assembly.py`, `work_pool.py` and `ArchiveMissingVolumeError` with unit tests, including the reproduction case and the parity scenarios. Nothing calls them yet.
2. **PR 2**:
   - switch `extract_files()` to per-root pools;
   - extract `extract_one_level()`;
   - add the history entry `kind` and relocation auto-restore;
   - rewrite the affected `test_main.py` tests.
3. **PR 3**:
   - remove `extract_nested_archives`, `add_file_to_groups`, `relocate_multipart_parts_from_directory` and `ensure_contained_multipart_groups`;
   - update `CLAUDE.md` / `AGENTS.md` and `openspec/project.md` for the new flow.
4. **Release PR** `release/v2.0.0` → `main`, after the terminal-output and rename PRs, following the project's release-prep process (`.agents/skills/deepunzip-release` after the rename):
   - `poetry run bump-major`. The version in `pyproject.toml`, `__init__.py` and `.bumpversion.cfg` must read 2.0.0 in all three.
   - `ReleaseNotes/RELEASE_NOTES_v2.0.0.md`, bilingual, in the v1.3.x format. It opens with the rename to DeepUnzip and the old→new mapping. Its upgrade notes cover:
     - the new executable and asset names;
     - one `unzipped/` per input root;
     - sources deleted only at the end of the run;
     - exit codes 0/1/2 (a missing engine is now 2);
     - single-language output and `DEEPUNZIP_LANG`;
     - `--json`;
     - relocation auto-restore after a crash.
   - README: the five-language READMEs from `rename-to-deepunzip`, with version summary, package table and release-notes link set to 2.0.0.
   - Archive all three OpenSpec changes into `openspec/specs/` once their tasks are complete.
   - Local verification:
     - `scripts.release version` / `verify-notes` / `verify-engines`;
     - `--version` / `--help`;
     - `pytest -q`;
     - `scripts.smoke_test`;
     - `git diff --check`.
     Then run a manual end-to-end run against a copy of the reproduction set.
   - Add the `release` label. The release workflow builds all platforms from the merge commit.

Rollback: before the release PR merges, revert PR 2 on `release/v2.0.0`, since PR 1 is inert on its own. After release, ship a 2.0.x fix.

## Open Questions

None. `MAX_ASSEMBLY_ATTEMPTS` is fixed at 64 and not exposed as a CLI option.
