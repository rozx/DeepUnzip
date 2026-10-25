# lineage-source-cleanup Specification

## Purpose
Delete a source only when everything extracted from it succeeded, at the end of the run, so nothing that cannot be extracted is ever lost.
## Requirements
### Requirement: Track lineage from sources to derived items
The system SHALL record, for every work item, the set of source items it descends from. A source item's lineage SHALL be itself. A derived item's lineage SHALL be the union of the lineages of the items it was extracted from. For a multipart set, that is all of the set's chosen volumes.

#### Scenario: Set assembled from two containers
- **WHEN** `X.7z.001` (from source `B.rar`) and `X.7z.002` (from source `A.7z`) are extracted together and yield `movie.mp4`
- **THEN** the lineage of `movie.mp4` SHALL be {`A.7z`, `B.rar`}

### Requirement: Delete a source only when all its descendants are resolved
After finalization, the system SHALL delete a source item if and only if all of these hold:

- the source was consumed (opened, or used in a successful multipart set);
- at least one item descends from it;
- no item whose lineage contains it is unresolved.

Deletion SHALL use the user's deletion mode: the Recycle Bin by default, or permanent with `--permanent-delete`. A kept source (a regular file left in place) SHALL never be deleted.

#### Scenario: Everything resolved
- **WHEN** every item descending from source `A.7z` is consumed or final
- **THEN** `A.7z` SHALL be deleted using the user's deletion mode

#### Scenario: Descendant password failure keeps the source
- **WHEN** source `A.7z` yields `inner.rar`, and no password works for `inner.rar`
- **THEN** `A.7z` SHALL NOT be deleted
- **AND** `inner.rar` SHALL be in the output folder

#### Scenario: Empty archive keeps the source
- **WHEN** source `A.7z` opens successfully but yields no files
- **THEN** `A.7z` SHALL be unresolved with reason "empty"
- **AND** `A.7z` SHALL NOT be deleted

#### Scenario: Regular file in the input root is never deleted
- **WHEN** the input root contains `readme.txt` next to archives that all extract successfully
- **THEN** `readme.txt` SHALL NOT be deleted

#### Scenario: Failed cross-container set keeps every contributing source
- **WHEN** the volumes of set `X|7z` come from sources `A.7z` and `B.rar`, and the set fails
- **THEN** neither `A.7z` nor `B.rar` SHALL be deleted

#### Scenario: Successful cross-container set releases every contributing source
- **WHEN** the volumes of set `X|7z` come from sources `A.7z` and `B.rar`
- **AND** the set and all of its descendants are resolved
- **AND** no other item descending from either source is unresolved
- **THEN** both `A.7z` and `B.rar` SHALL be deleted

### Requirement: No source deletion before the run ends
The system SHALL NOT delete or recycle any source item before the extraction loop has terminated and finalization has completed.

#### Scenario: Interrupted run
- **WHEN** the run is interrupted during the extraction rounds
- **THEN** every source item SHALL still exist at its original path, or be restorable from `RenameHistory`

### Requirement: Remove source subfolders emptied by cleanup
After source deletion, the system SHALL remove a source subfolder that became empty. It SHALL NOT remove the input root, the output folder or the run work directory this way.

#### Scenario: Subfolder holding only the deleted archive
- **WHEN** `in/sub/A.7z` is deleted by lineage cleanup and `in/sub/` is then empty
- **THEN** `in/sub/` SHALL be removed
- **AND** `in/` SHALL NOT be removed

