## ADDED Requirements

### Requirement: Preserve cross-container volume sets on failure
When a multipart set whose volumes come from several containers or directories fails to extract, the tool MUST preserve every volume it gathered and MUST NOT delete any source that contributed a volume. Every source volume moved for an assembly attempt MUST be returned to its original location after that attempt. Every derived volume of the failed set MUST be moved to the output folder, and all of them MUST be placed together at the primary's output location.

#### Scenario: Set assembled from two containers fails
- **WHEN** `X.7z.001` (from `B.rar`) and `X.7z.002` (from `A.7z`) are gathered and every assembly scope fails at quiescence
- **THEN** both volumes MUST exist in the same folder of the output after the run
- **AND** `A.7z` and `B.rar` MUST NOT be deleted

#### Scenario: Source volume moved for assembly is restored
- **WHEN** source volume `in/sub/X.7z.002` was moved into an assembly folder for an attempt
- **THEN** after the attempt `X.7z.002` MUST be back at `in/sub/X.7z.002`, whether the attempt succeeded or failed
