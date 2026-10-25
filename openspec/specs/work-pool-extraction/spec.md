# work-pool-extraction Specification

## Purpose
Extract everything under an input root in rounds until nothing changes, assembling multipart sets from volumes found anywhere in the root.
## Requirements
### Requirement: Uniform processing of input and extracted files
The system SHALL keep one work pool per input root. An input root is a folder passed on the command line, or the parent folder of a file passed; a root nested inside another root is merged into the outer one. Every file found under an input root by the input scan, and every file extracted from such a file at any depth, SHALL be placed into that root's pool. Each newly added item SHALL be uncloaked, classified and grouped by the same rules, whichever directory, container or depth it came from. Items of different pools SHALL never be grouped, combined or moved between roots.

#### Scenario: Extracted file is classified like an input file
- **WHEN** a container is opened and yields `inner.rar`
- **THEN** `inner.rar` SHALL be added to the pool and classified with the same rules as a top-level `inner.rar`
- **AND** it SHALL be opened in a later round if it is a container

#### Scenario: Separate pools for separate input roots
- **WHEN** the user passes `D:\a\X.7z.001` and `E:\b\X.7z.002`
- **THEN** `D:\a` and `E:\b` SHALL be processed as two separate pools
- **AND** the two files SHALL NOT be combined into one set
- **AND** no file SHALL be moved between `D:` and `E:`

#### Scenario: Result does not depend on processing order
- **WHEN** the same set of containers is processed in two different orders
- **THEN** the set of files in the output folder and the set of deleted sources SHALL be identical

### Requirement: Leave source regular files in place
A source item that is not an archive or multipart volume (for example `readme.txt` or an image next to the archives) SHALL be kept at its original path. It SHALL NOT be moved to the output folder and SHALL NOT be deleted.

#### Scenario: Readme next to an archive
- **WHEN** the input root contains `A.7z` and `readme.txt`
- **AND** `A.7z` extracts successfully
- **THEN** `readme.txt` SHALL still exist at its original path
- **AND** no copy of it SHALL be created in the output folder

### Requirement: Classify multipart names before archive validation
The system SHALL classify a file whose name matches the multipart primary or continuation patterns as a multipart volume, without requiring archive validation. Archive validation (`is_valid_archive`) SHALL decide only between container and regular file for the remaining items.

#### Scenario: Lone first volume
- **WHEN** a container yields `X.7z.001`, and 7-Zip would list it alone as a one-volume `Split`
- **THEN** `X.7z.001` SHALL be classified as a multipart primary candidate
- **AND** it SHALL NOT be treated as a regular file

### Requirement: Open containers one level at a time
The system SHALL extract each container one level deep into its own folder under the run work directory, and SHALL return the extracted files to the pool instead of recursing into them inside the same extraction call. Each attempt SHALL extract into a fresh folder, and that folder SHALL be discarded if the attempt fails.

#### Scenario: Nested container is deferred to the pool
- **WHEN** container `A.7z` is opened and contains `B.zip` and `readme.txt`
- **THEN** `B.zip` and `readme.txt` SHALL be added to the pool
- **AND** `B.zip` SHALL NOT be opened until the next round

#### Scenario: Failed attempt leaves no partial output
- **WHEN** opening a container fails part-way, after some files were written
- **THEN** none of those files SHALL enter the pool or reach the output folder

### Requirement: Defer containers that fail for missing volumes
When opening a container fails because 7-Zip reports a missing or unexpected-end volume, the system SHALL treat the item as a multipart primary candidate awaiting volumes. It SHALL NOT mark the item as failed, and SHALL NOT keep trying further passwords for that error. An unresolved item with an ambiguous primary extension (`.rar`, `.zip`, `.zipx`, `.arj`, `.ace`) SHALL return to pending as a multipart primary when a continuation with its key later enters the pool.

#### Scenario: Standalone-looking RAR whose next volume is inside another container
- **WHEN** input `X.rar` fails to open because a volume is missing
- **AND** container `B.7z`, opened in the same or a later round, yields `X.r00`
- **THEN** `X.rar` and `X.r00` SHALL be assembled as a multipart set
- **AND** `X.rar` SHALL NOT be reported as a failed archive

#### Scenario: Spanned ZIP opened alone fails as not-an-archive
- **WHEN** input `X.zip` fails to open with a "cannot open as archive" error and becomes unresolved
- **AND** a later container yields `X.z01`
- **THEN** `X.zip` SHALL return to pending as the primary of set `X|zip`

### Requirement: Assemble multipart sets only after containers are exhausted
The system SHALL attempt multipart assembly only in a round in which no container in the pool is still pending.

#### Scenario: Volume surfaced by a later container
- **WHEN** the pool contains `X.7z.001` and an unopened container `C.rar`
- **AND** `C.rar` contains `X.7z.002`
- **THEN** the system SHALL open `C.rar` before attempting to extract `X.7z.001`
- **AND** extraction of `X.7z.001` SHALL include `X.7z.002`

### Requirement: Defer failed sets until quiescence
A multipart set whose assembly fails during the loop SHALL be deferred, not failed. It SHALL be retried only after a new volume with its key has entered the pool since its last attempt. Only when the loop reaches quiescence, after any interactive prompt, SHALL a remaining deferred set be marked failed.

#### Scenario: Missing volume is inside another multipart set
- **WHEN** the input root contains `X.7z.001` and the set `Y.part1.rar` + `Y.part2.rar`
- **AND** extracting the set `Y` yields `X.7z.002`
- **AND** `X` is attempted before `Y`
- **THEN** `X` SHALL be deferred after its first attempt
- **AND** `X` SHALL be retried after `X.7z.002` enters the pool
- **AND** `X` SHALL extract successfully

#### Scenario: No retry without new volumes
- **WHEN** a deferred set's key receives no new volume in a round
- **THEN** the set SHALL NOT be attempted again in that round

### Requirement: Multipart assembly by widening scope
For each multipart key (base name and format family) that has a primary candidate, the system SHALL search for a working volume combination in progressively wider scopes:

1. The primary's own folder.
2. The primary's own folder and its whole subtree.
3. Each ancestor folder's subtree in turn, up to and including the input root.

The search SHALL NOT go above the input root. Candidates SHALL be pool items only; files on disk that are not in the pool SHALL never be used. Within a scope, the system SHALL try combinations of one volume per index from the contiguous range present in that scope, ordered by proximity to the primary and then by path. It SHALL stop at the first combination that extracts successfully.

#### Scenario: Complete set in the primary's folder
- **WHEN** `X.7z.001` and `X.7z.002` are in the same folder
- **THEN** that combination SHALL be tried first, and no wider scope SHALL be searched if it succeeds

#### Scenario: Source primary with its continuation inside a container
- **WHEN** source `X.7z.001` is in the input root
- **AND** container `A.rar` (also in the root) yields `X.7z.002` into the run work directory
- **THEN** the subtree scope of the input root SHALL yield the combination (`X.7z.001`, `<work>/A/X.7z.002`)
- **AND** the set SHALL be extracted successfully

#### Scenario: Volumes split across sibling containers
- **WHEN** `X.7z.001` was extracted into `<work>/A/` and `X.7z.002` into `<work>/B/`
- **THEN** neither the primary's folder nor its subtree SHALL yield a `.002`
- **AND** the parent scope `<work>/` SHALL yield the combination (`A/X.7z.001`, `B/X.7z.002`)
- **AND** the set SHALL be extracted successfully

#### Scenario: Search stops at the input root
- **WHEN** the input root is `D:\in` and contains `X.7z.001`
- **AND** `X.7z.002` exists only in `D:\` (outside the input root)
- **THEN** no scope SHALL include `D:\X.7z.002`
- **AND** the set SHALL be marked failed at quiescence

#### Scenario: Unscanned file on disk is not used
- **WHEN** the user passes only `D:\Downloads\X.7z.001` (with no sibling volumes)
- **AND** `D:\Downloads\old\X.7z.002` exists on disk but was not scanned
- **THEN** `D:\Downloads\old\X.7z.002` SHALL NOT be used in any combination

#### Scenario: Two different sets share a name
- **WHEN** the pool contains two `X.7z.001` primaries and two `X.7z.002` volumes from four different containers
- **AND** only two specific pairings are valid archives
- **THEN** the system SHALL find a valid pairing for one primary
- **AND** the remaining primary and volume SHALL stay pending and SHALL be assembled in a later attempt

### Requirement: Assemble each attempt in an isolated folder
The system SHALL run every assembly attempt in a fresh assembly folder under the run work directory that contains exactly the chosen volumes, so that 7-Zip cannot pick up a non-chosen volume of the same name. Each source volume moved into the assembly folder SHALL be moved back to its original location after the attempt, whether the attempt succeeds or fails.

#### Scenario: Non-chosen same-name volume next to the primary
- **WHEN** the combination being tried is (`in/X.7z.001`, `<work>/B/X.7z.002`)
- **AND** a different `in/X.7z.002` exists next to the primary
- **THEN** 7-Zip SHALL see only `X.7z.001` and the volume from `<work>/B/`

#### Scenario: Source volume returns after a successful attempt
- **WHEN** source volume `in/sub/X.7z.002` is used in a successful combination
- **THEN** after the attempt it SHALL be back at `in/sub/X.7z.002`
- **AND** any deletion of it SHALL happen at that path

### Requirement: Never consume a volume 7-Zip did not use
When a probe reports that 7-Zip used fewer volumes than the combination holds, the system SHALL NOT mark the unused volumes as consumed:

- if more than one volume was used, it SHALL retry with only the used volumes;
- if only an ambiguous primary (`.rar`, `.zip`, `.zipx`, `.arj`, `.ace`) was used, it SHALL reject the combination.

An ambiguous primary whose set fails, and that was never opened as a single container, SHALL then be opened as a single container.

#### Scenario: Standalone zip next to an unrelated continuation
- **WHEN** the input root contains a standalone `X.zip` and an unrelated `X.z01`
- **THEN** `X.zip` SHALL be extracted as a single container
- **AND** `X.z01` SHALL NOT be deleted

### Requirement: Bound and pre-filter the combination search
Before invoking 7-Zip on a combination of 7z or generic numbered split volumes (`.7z.NNN`, `.<ext>.NNN`), the system SHALL reject it without invoking 7-Zip when the volume sizes are inconsistent:

- every volume except the last SHALL have the same size, and the last SHALL be no larger;
- for a `.7z.001` primary, the sum of the volume sizes SHALL equal the archive size recorded in the 7z start header.

For RAR, ZIP, ZIPX and ARJ volumes, size consistency SHALL only affect the order in which combinations are tried. It SHALL NOT reject a combination.

The system SHALL make at most `MAX_ASSEMBLY_ATTEMPTS` (a fixed constant of 64, not configurable from the CLI) 7-Zip probes per set over the whole run. When the limit is reached, the set SHALL be unresolved with reason "too many combinations".

#### Scenario: Size mismatch rejected without 7-Zip
- **WHEN** a combination has `X.7z.001` of 100 MB and `X.7z.002` of 100 MB, but the start header of `X.7z.001` records 150 MB in total
- **THEN** the combination SHALL be rejected without running 7-Zip

#### Scenario: RAR volumes of different sizes are still tried
- **WHEN** a RAR combination has volumes of different non-final sizes
- **THEN** the combination SHALL still be probed

#### Scenario: Attempt cap reached
- **WHEN** `MAX_ASSEMBLY_ATTEMPTS` probes have failed for a set
- **THEN** no further combination SHALL be tried
- **AND** the set SHALL be unresolved with reason "too many combinations"

### Requirement: Prompt for a multipart password at most once per set
The system SHALL prompt the user for a multipart set's password at most once per run. It SHALL prompt only when all of these hold:

- the loop has reached quiescence;
- the set has a complete combination, with no missing index;
- at least one probe failed with a password-type error, and every other probe failed only for a missing volume (missing-volume failures carry no password information).

A password the user enters SHALL be retried across the combinations in the same order, and SHALL be added to the password book.

#### Scenario: Encrypted set with an unknown password
- **WHEN** at quiescence every combination of a complete set fails with a password-type error using every known password
- **AND** interactive mode is enabled
- **THEN** the user SHALL be prompted once for the set
- **AND** the entered password SHALL be tried against each combination in proximity order

#### Scenario: No prompt for an incomplete set
- **WHEN** a deferred set still has a missing volume index at quiescence
- **THEN** the user SHALL NOT be prompted for its password

### Requirement: Treat identical duplicate volumes as consumed
After a set extracts successfully, a leftover volume with the same key and index as one of the consumed volumes SHALL be marked consumed, with reason "duplicate", when its size and content hash both equal that consumed volume's. Content hashes SHALL be computed only for volumes whose sizes already match.

#### Scenario: Reposted duplicate part
- **WHEN** containers `A.7z` and `B.7z` both yield a byte-identical `X.7z.002`
- **AND** the set `X` extracts successfully using the copy from `A.7z`
- **THEN** the copy from `B.7z` SHALL be marked consumed as a duplicate
- **AND** it SHALL NOT cause `B.7z` to be kept

### Requirement: Terminate when a round makes no progress
The system SHALL repeat rounds until a round opens no container and attempts no set, and SHALL then run the quiescence steps (prompts, then final failure marking). The system SHALL open each container at most once.

#### Scenario: Pool becomes quiescent
- **WHEN** a round opens no container and attempts no set
- **AND** no quiescence prompt unlocks a set
- **THEN** the loop SHALL stop and finalization SHALL begin

### Requirement: Limit lineage depth
The system SHALL NOT open an item whose extraction depth exceeds `max_depth` (default 10). Such an item SHALL become unresolved with reason "max depth".

#### Scenario: Deeply nested archive
- **WHEN** an archive is found at depth 11 with `max_depth` 10
- **THEN** it SHALL NOT be opened
- **AND** it SHALL be preserved to the output folder as unresolved

### Requirement: Clean up consumed derived archives immediately
The system SHALL clean up a derived container or derived multipart volume as soon as it is consumed, honoring the user's deletion mode. It SHALL NOT wait for the end of the run to do so.

#### Scenario: Intermediate container after opening
- **WHEN** derived container `<work>/A/B.zip` is opened successfully
- **THEN** `B.zip` SHALL be removed before the next round starts

### Requirement: Preserve every unresolved item before work cleanup
Before removing the run work directory, the system SHALL move every unresolved derived item to the output folder, preserving its relative path. This covers orphan continuation volumes, failed sets, password-failed, unsupported or empty archives, and depth-limited items.

- The volumes of a failed set SHALL be placed together at the primary's output location.
- Unresolved and kept source items SHALL stay at their original location.
- If any move to the output folder fails, the system SHALL NOT remove the work directory, SHALL keep every source in the affected lineages, and SHALL report the work directory's path.

#### Scenario: Orphan continuation volume
- **WHEN** container `A.7z` yields `X.7z.002`
- **AND** no `X.7z.001` exists anywhere in the pool
- **THEN** `X.7z.002` SHALL exist in the output folder after the run

#### Scenario: Failed cross-container set is kept together
- **WHEN** set `X` with `A/X.7z.001` and `B/X.7z.002` is marked failed
- **THEN** both volumes SHALL be placed in the same output folder, at the primary's output location

#### Scenario: Move to output fails
- **WHEN** moving a final file to the output folder fails
- **THEN** the work directory SHALL still exist after the run
- **AND** no source in that file's lineage SHALL be deleted

#### Scenario: Reproduction of cross-container cloaked volumes
- **WHEN** `A.7z` yields `X.7z.002` and `B.rar` yields `X.7z.001删掉`
- **THEN** `X.7z.001删掉` SHALL be uncloaked to `X.7z.001`
- **AND** the set SHALL be assembled and extracted
- **AND** the extracted files SHALL be in the output folder
- **AND** no volume SHALL be deleted unless the set extracted successfully

### Requirement: One output folder and work directory per input root
For each input root, the system SHALL write extracted output to `<root>/unzipped/`, and SHALL create a run work directory inside that root. The system SHALL exclude both from the input scan, and SHALL report a leftover work directory from an interrupted run at startup.

#### Scenario: Two input roots
- **WHEN** the user passes `D:\a` and `E:\b`
- **THEN** output from `D:\a` SHALL be written under `D:\a\unzipped\`
- **AND** output from `E:\b` SHALL be written under `E:\b\unzipped\`

#### Scenario: Leftover work directory
- **WHEN** a `temp.deepunzip-<run-id>` directory from a previous run exists in the input root at startup
- **THEN** its files SHALL NOT be scanned as inputs
- **AND** the user SHALL be told about it

