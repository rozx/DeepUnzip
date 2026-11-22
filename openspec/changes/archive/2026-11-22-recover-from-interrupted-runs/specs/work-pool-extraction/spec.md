## MODIFIED Requirements

### Requirement: One output folder and work directory per input root
For each input root, the system SHALL write extracted output to `<root>/unzipped/`, and SHALL create a run work directory inside that root. The system SHALL exclude both from the input scan, and SHALL report a leftover work directory from an interrupted run at startup. After the root's run, the system SHALL remove each leftover work directory it reported, to the recycle bin unless permanent deletion was chosen, unless the run kept its own work directory or a rename-history entry still points into the leftover.

#### Scenario: Two input roots
- **WHEN** the user passes `D:\a` and `E:\b`
- **THEN** output from `D:\a` SHALL be written under `D:\a\unzipped\`
- **AND** output from `E:\b` SHALL be written under `E:\b\unzipped\`

#### Scenario: Leftover work directory
- **WHEN** a `temp.deepunzip-<run-id>` directory from a previous run exists in the input root at startup
- **THEN** its files SHALL NOT be scanned as inputs
- **AND** the user SHALL be told about it

#### Scenario: Leftover removed after the next run
- **GIVEN** a `temp.deepunzip-<run-id>` directory from an interrupted run exists in the input root
- **WHEN** a run of that root finishes and removes its own work directory
- **THEN** the leftover SHALL be moved to the recycle bin, or deleted with `--permanent-delete`
- **AND** the user SHALL be told about it

#### Scenario: Leftover still holding a source volume
- **GIVEN** a leftover work directory holds a source volume that could not be moved back
- **AND** its relocation entry is still in the rename history when the run finishes
- **WHEN** the run finishes
- **THEN** the leftover SHALL be kept

#### Scenario: This run keeps its own work directory
- **WHEN** a run keeps its own work directory (a move failed, or a volume could not be moved back)
- **THEN** every leftover work directory SHALL be kept

## ADDED Requirements

### Requirement: Save a typed password as soon as it works
A password the user typed at a prompt SHALL be saved to the password book as soon as it opens an archive or a set, not at the end of the run.

#### Scenario: Run interrupted after a password was typed
- **WHEN** the user types a password that opens `A.7z`
- **AND** the run is interrupted while extracting `B.7z`
- **THEN** the password SHALL already be in `passwords.txt`
