## MODIFIED Requirements

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
