# output-path-normalization Specification

## Purpose
Make extracted output easier to browse by flattening meaningless leading folders under the output root, while preserving meaningful folder names and every distinct file on name collisions.
## Requirements
### Requirement: Flatten meaningless leading folders under the output root
The system SHALL normalize extracted file output paths by removing meaningless **leading** directory segments under the final output folder.

#### Scenario: Numeric-only folder is flattened
- **GIVEN** a file would be placed at `unzipped/1/aaa.jpg`
- **WHEN** the tool finalizes the destination path under the output root
- **THEN** the file SHALL be placed at `unzipped/aaa.jpg`

#### Scenario: Numeric+symbol folder chain is flattened
- **GIVEN** a file would be placed at `unzipped/1/5555+/222.jpg`
- **WHEN** the tool finalizes the destination path under the output root
- **THEN** the file SHALL be placed at `unzipped/222.jpg`

### Requirement: Meaningful folders MUST be preserved
The system SHALL NOT flatten folders that contain letters or CJK characters.

#### Scenario: Meaningful folder is preserved
- **GIVEN** a file would be placed at `unzipped/photos/1/aaa.jpg`
- **WHEN** the tool finalizes the destination path under the output root
- **THEN** the file SHALL remain under `unzipped/photos/1/aaa.jpg`

### Requirement: Collisions MUST be handled safely
If a file would be placed at an output path that is already taken, the system SHALL compare it with the existing file, and with each numbered alternative of that path, by size and then by MD5 hash. If one of them has the same content, the system SHALL NOT write a second copy, SHALL report the item at that existing file, and SHALL count it as an identical file skipped. Otherwise the system SHALL preserve all files by applying existing name-collision handling.

#### Scenario: Two inputs collide after flattening
- **GIVEN** two different extracted files would be placed at `unzipped/1/aaa.jpg` and `unzipped/2/aaa.jpg`
- **WHEN** the tool applies output-path normalization
- **THEN** both files SHALL exist under the output root
- **AND** at least one of them SHALL be renamed with a suffix to avoid overwriting

#### Scenario: Identical file already in the output
- **GIVEN** `unzipped/a.txt` exists
- **AND** an extracted `a.txt` has the same size and MD5 hash
- **WHEN** the tool moves it to the output
- **THEN** no `unzipped/a_1.txt` SHALL be created
- **AND** the item's output path SHALL be `unzipped/a.txt`
- **AND** the summary SHALL count one identical file skipped

#### Scenario: Identical copy under a numbered name
- **GIVEN** `unzipped/a.txt` and `unzipped/a_1.txt` exist with different contents
- **AND** an extracted `a.txt` has the same content as `unzipped/a_1.txt`
- **WHEN** the tool moves it to the output
- **THEN** no `unzipped/a_2.txt` SHALL be created

#### Scenario: Same name, different content
- **GIVEN** `unzipped/a.txt` exists
- **AND** an extracted `a.txt` has different content
- **WHEN** the tool moves it to the output
- **THEN** it SHALL be placed at `unzipped/a_1.txt`
