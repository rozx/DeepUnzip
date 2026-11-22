## ADDED Requirements

### Requirement: Remove leftover work directories after a run
After a root's run, the system SHALL remove each leftover work directory it reported at startup, to the recycle bin unless permanent deletion was chosen. It SHALL keep a leftover while a rename-history entry still points into it or while the run that owns it is still running, and SHALL keep all of them when the run kept its own work directory.

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

#### Scenario: Leftover of a run that is still going
- **GIVEN** another run on the same folder is still extracting into its work directory
- **WHEN** this run finishes first
- **THEN** that work directory SHALL be kept
- **AND** the user SHALL be told it belongs to a run that is still going

#### Scenario: This run keeps its own work directory
- **WHEN** a run keeps its own work directory (a move failed, or a volume could not be moved back)
- **THEN** every leftover work directory SHALL be kept

### Requirement: Save a typed password as soon as it works
A password the user typed at a prompt SHALL be saved to the password book as soon as it opens an archive or a set, not at the end of the run.

#### Scenario: Run interrupted after a password was typed
- **WHEN** the user types a password that opens `A.7z`
- **AND** the run is interrupted while extracting `B.7z`
- **THEN** the password SHALL already be in `passwords.txt`
