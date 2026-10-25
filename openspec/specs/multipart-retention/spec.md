# multipart-retention Specification

## Purpose
Keep all source volumes of a multipart archive when its extraction fails, so the user can add missing parts or passwords and retry.
## Requirements
### Requirement: Preserve multipart source volumes on extraction failure
When extracting multipart archives, if extraction fails for any reason (missing volumes, bad password, I/O error), the tool MUST NOT delete, recycle, or move away the source multipart files. Only temporary files created by the tool during the current run MAY be cleaned.

#### Scenario: 7z volumes missing continuation
Given: A directory containing `data.7z.001` but missing `data.7z.002`
When: The tool attempts multipart extraction and fails due to missing continuation
Then: `data.7z.001` remains in place (not deleted/recycled), and any tool‑created temp files are cleaned; log states failure and retention of source parts

#### Scenario: RAR multi‑part missing later part
Given: A directory containing `archive.part1.rar` but missing `archive.part2.rar`
When: Extraction fails due to missing part2
Then: `archive.part1.rar` remains; no source parts are deleted; temp cleanup applies only to tool‑created paths; log clarifies retained items

#### Scenario: ZIP spanned set with missing `.z01`
Given: `set.zip` exists but `set.z01` is missing
When: Extraction fails
Then: `set.zip` remains untouched; no source deletions occur; temp dirs may be cleaned; logs indicate retention

### Requirement: Preserve cross-container volume sets on failure
When a multipart set whose volumes come from several containers or directories fails to extract, the tool MUST preserve every volume it gathered and MUST NOT delete any source that contributed a volume. Every source volume moved for an assembly attempt MUST be returned to its original location after that attempt. Every derived volume of the failed set MUST be moved to the output folder, and all of them MUST be placed together at the primary's output location.

#### Scenario: Set assembled from two containers fails
- **WHEN** `X.7z.001` (from `B.rar`) and `X.7z.002` (from `A.7z`) are gathered and every assembly scope fails at quiescence
- **THEN** both volumes MUST exist in the same folder of the output after the run
- **AND** `A.7z` and `B.rar` MUST NOT be deleted

#### Scenario: Source volume moved for assembly is restored
- **WHEN** source volume `in/sub/X.7z.002` was moved into an assembly folder for an attempt
- **THEN** after the attempt `X.7z.002` MUST be back at `in/sub/X.7z.002`, whether the attempt succeeded or failed

