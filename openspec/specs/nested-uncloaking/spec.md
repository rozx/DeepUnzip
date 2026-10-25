# nested-uncloaking Specification

## Purpose
Restore disguised file names at every depth, while recording only the renames of source files.
## Requirements
### Requirement: Uncloak files surfaced by extraction
The system SHALL apply cloaked-name normalization to every file produced by extraction at any depth, using the same rules (`config/cloaked_file_rules.json`), priority order and collision handling as for input files. It SHALL do so before the file is classified and grouped.

#### Scenario: Cloaked primary inside a container
- **WHEN** container `B.rar` yields `X.7z.001删掉`
- **THEN** the file SHALL be renamed to `X.7z.001` before classification
- **AND** it SHALL take part in multipart assembly for key `X|7z`

#### Scenario: Collision with an already-normalized derived file
- **WHEN** extraction yields both `9.7z(1).001` and `9.7z.001` in the same folder
- **THEN** the normalized `9.7z.001` SHALL be preferred
- **AND** the cloaked duplicate SHALL be renamed to a unique name, as for input files

### Requirement: Apply the signature gate to extracted files
For an extracted file whose archive type was only guessed from a trailing number, the system SHALL require a real archive signature before renaming it. This is the same gate as for input files.

#### Scenario: Ordinary numbered file inside a container
- **WHEN** a container yields `photo.001` with no archive signature and no explicit archive token
- **THEN** the file SHALL NOT be renamed
- **AND** it SHALL be treated as a regular file

### Requirement: Do not record renames of derived files
The system SHALL NOT record renames of tool-extracted (derived) files in `RenameHistory`. A derived file is a copy produced during the run, and its source archive is the recovery point.

#### Scenario: Derived rename leaves history unchanged
- **WHEN** an extracted `X.7z.001删掉` is renamed to `X.7z.001`
- **THEN** `RenameHistory` SHALL contain no entry for that rename

