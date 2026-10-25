# Rename History Specification

## Purpose
Preserve the recognizability of source archive files by tracking uncloaking renames, restoring names when originals are retained, and supporting recovery after interrupted runs.
## Requirements
### Requirement: Track every successful uncloak rename
The system SHALL record every in-place rename of a **source** file performed during a run. Each entry SHALL capture the original path, the renamed path, a stable identifier for the run, and an entry kind:

- `uncloak`: a cloaked-name normalization;
- `relocation`: a move of a source volume into an assembly folder for multipart assembly.

Renames of tool-extracted (derived) files SHALL NOT be recorded.

#### Scenario: Single cloaked file renamed
- **WHEN** the detector renames source file `1525.zip.001.bin` to `1525.7z.001` during intake
- **THEN** the rename history SHALL contain an entry with `original=1525.zip.001.bin` and `renamed=1525.7z.001`

#### Scenario: Duplicate-collision rename
- **WHEN** the detector encounters a collision target and renames a cloaked source file to a `__duplicate_<token>` variant via `_build_collision_path`
- **THEN** the rename history SHALL contain an entry mapping the original cloaked name to the duplicate variant

#### Scenario: Failed rename is not recorded
- **WHEN** `os.rename` raises an exception during uncloaking
- **THEN** the rename history SHALL NOT contain an entry for that file

#### Scenario: Source volume moved for assembly
- **WHEN** source volume `in/sub/X.7z.002` is moved to `<work>/.assemble/1/X.7z.002` for a multipart assembly attempt
- **THEN** the rename history SHALL contain a `relocation` entry with `original=in/sub/X.7z.002` and `renamed=<work>/.assemble/1/X.7z.002`
- **AND** the entry SHALL be removed once the volume has been moved back after the attempt

#### Scenario: Derived file renamed
- **WHEN** an extracted file `X.7z.001删掉` in the run work directory is renamed to `X.7z.001`
- **THEN** the rename history SHALL NOT contain an entry for it

### Requirement: Bind tracked renames to archive groups
The system SHALL associate every tracked rename with the source work item whose current path is its `renamed` path.

#### Scenario: Bind to the source item
- **WHEN** source item `1525.7z.001` was produced by an uncloak rename
- **THEN** that rename entry SHALL be bound to the `1525.7z.001` source item

#### Scenario: Renamed file not present in any group
- **WHEN** a tracked entry's `renamed` path matches no source item at the end of the run
- **THEN** the entry SHALL remain unbound and SHALL be reverted at end-of-run

### Requirement: Revert renames when group originals are preserved
The system SHALL revert every rename history entry bound to a source item whenever lineage-based cleanup keeps that source (it is not deleted).

#### Scenario: Group fails with password skip
- **WHEN** a descendant of source `1525.7z.001` is unresolved because of a password failure, so the source is kept
- **THEN** the system SHALL rename every bound file from `renamed` back to `original`
- **AND** SHALL emit a warning indicating how many renames were reverted

#### Scenario: Group raises an exception
- **WHEN** processing an item raises an exception that leaves a descendant of the source unresolved
- **THEN** the system SHALL revert every rename bound to that source

#### Scenario: Revert encounters missing renamed file
- **WHEN** revert is asked to rename `renamed → original` but `renamed` no longer exists on disk
- **THEN** the system SHALL skip that entry, log an info message, and continue with the remaining entries

#### Scenario: Revert encounters existing original
- **WHEN** revert is asked to rename `renamed → original` but `original` already exists on disk
- **THEN** the system SHALL pick a unique fallback path using the same collision-suffix scheme as the cloaked detector and complete the rename without raising

### Requirement: Drop history entries for successful groups
The system SHALL remove every rename history entry bound to a source item whenever lineage-based cleanup deletes that source.

#### Scenario: Group succeeds and originals are deleted
- **WHEN** lineage-based cleanup deletes source `1525.7z.001`
- **THEN** the system SHALL clear the history entries bound to it
- **AND** SHALL NOT attempt to revert any of those renames

### Requirement: Persist history across crashes
The system SHALL persist the rename history of each input root to a JSON file in that input root, updated eagerly after every record / revert / clear operation, and removed on clean program completion when the history contains no remaining entries.

#### Scenario: History written on each record
- **WHEN** a new rename is recorded
- **THEN** the file `<input_root>/.unzip-rename-history.tmp.json` of the root that owns the renamed file SHALL exist on disk and SHALL contain the entry
- **AND** the write SHALL be atomic (write to temp + `os.replace`)

#### Scenario: File removed on clean exit
- **WHEN** the run completes with all items processed and no entries remaining
- **THEN** `.unzip-rename-history.tmp.json` SHALL be deleted

#### Scenario: File survives crash
- **WHEN** the program is terminated abnormally (SIGINT, exception in unrelated code, OS kill) after at least one rename was recorded
- **THEN** the JSON file SHALL remain on disk reflecting all renames that had been recorded up to the moment of termination

#### Scenario: Separate files for separate roots
- **WHEN** renames are recorded for files under input roots `D:\a` and `E:\b`
- **THEN** each root SHALL have its own history file containing only its own entries

### Requirement: Recover from leftover history on startup
The system SHALL detect a pre-existing `.unzip-rename-history.tmp.json` in each input root before the input scan.

- `relocation` entries SHALL be restored automatically, without a prompt.
- For `uncloak` entries, the system SHALL summarize them to the user and prompt for revert with a default of "no".

#### Scenario: Leftover relocation restored without a prompt
- **WHEN** a leftover history file contains a `relocation` entry whose `renamed` path `<work>/.assemble/1/X.7z.002` still exists
- **THEN** the system SHALL move the file back to its `original` path without asking
- **AND** SHALL apply the same missing-file and clobber-safety rules as in-run revert

#### Scenario: Leftover detected, user accepts
- **WHEN** a leftover history file with non-empty `uncloak` entries is detected at startup
- **AND** the user enters `y` at the recovery prompt
- **THEN** the system SHALL revert each `uncloak` entry whose `renamed` path still exists, applying the same missing-file and clobber-safety rules as in-run revert
- **AND** SHALL delete the history file before continuing
- **AND** SHALL then proceed with the normal flow

#### Scenario: Leftover detected, user declines
- **WHEN** a leftover history file with `uncloak` entries is detected and the user enters `n` (or accepts the default)
- **THEN** the system SHALL leave the `uncloak` entries in place
- **AND** SHALL proceed with the normal flow, where any new records during the run will overwrite the file

#### Scenario: Leftover with mismatched input root
- **WHEN** a leftover history file is detected but its `input_root` field does not match the current input root
- **THEN** the system SHALL warn the user about the mismatch in the recovery prompt before asking for confirmation

