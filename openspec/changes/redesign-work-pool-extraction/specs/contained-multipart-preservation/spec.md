## MODIFIED Requirements

### Requirement: Preserve multipart parts extracted from containers
The system SHALL ensure multipart archive parts that are extracted from within a container archive are not lost when the run work directory is removed. This includes continuation parts such as `.7z.002+`, `.r00/.r01+`, `.z01/.z02+`, `.part2+.rar` and `.tar.gz.002+`. A part SHALL stay in the work pool until it is either consumed by a successful multipart extraction or preserved to the output folder, regardless of whether its primary is surfaced before it, after it, or never.

#### Scenario: Try extraction first, then preserve on failure
- **GIVEN** an outer archive is extracted into the run work directory
- **AND** the extracted contents include a multipart set containing `x.7z.001` and `x.7z.002`
- **WHEN** the tool attempts to extract `x.7z.001` and every assembly scope fails
- **THEN** `x.7z.002` SHALL be moved to the target output folder before the work directory is removed
- **AND** `x.7z.002` SHALL exist on disk after the run completes

#### Scenario: Candidate part is cleaned after enabling successful extraction
- **GIVEN** an outer archive is extracted into the run work directory
- **AND** the extracted contents include `x.7z.002`
- **WHEN** a combination that includes `x.7z.002` extracts successfully
- **THEN** `x.7z.002` SHALL be eligible for cleanup as a consumed, tool-extracted artifact

#### Scenario: Continuation part extracted before its primary
- **GIVEN** container `A.7z` is opened first and yields `x.7z.002`
- **AND** container `B.rar` is opened later and yields `x.7z.001`
- **WHEN** multipart assembly runs
- **THEN** `x.7z.002` SHALL still be in the pool
- **AND** it SHALL be combined with `x.7z.001`

### Requirement: Skipping recursion MUST NOT imply deletion
The system SHALL ensure that not opening a file, for whatever reason (continuation part, depth limit, unsupported format, password failure), never implicitly deletes it, unless the file is a consumed tool-created artifact.

#### Scenario: Work directory cleanup runs after the extraction loop
- **GIVEN** the extraction loop has terminated and the run work directory is about to be removed
- **WHEN** files in it were never opened or were never consumed
- **THEN** those files SHALL already have been moved to the output folder
