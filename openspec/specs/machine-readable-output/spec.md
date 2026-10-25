# machine-readable-output Specification

## Purpose
Give scripts a stable, language-independent JSON event stream, non-interactive runs and meaningful exit codes.
## Requirements
### Requirement: JSON lines event stream
With `--json`, the system SHALL write newline-delimited JSON to stdout, one object per line, and nothing else. Each object SHALL carry `event` and `schema_version`. The first line SHALL be a `start` event and the last line SHALL be a `summary` event, including after a fatal error. The event types are `start`, `root`, `round`, `item`, `set`, `progress`, `unresolved`, `error` and `summary`. `progress` events SHALL be throttled to at most one per 200 ms or 1% change per item.

#### Scenario: Successful run
- **WHEN** `deepunzip --json E:\testDir` extracts everything
- **THEN** every stdout line SHALL parse as a JSON object
- **AND** the last line SHALL be `{"event": "summary", "status": "ok", ..., "exit": 0}`

#### Scenario: Fatal error
- **WHEN** `deepunzip --json` runs and the 7-Zip engine is missing
- **THEN** stdout SHALL contain a `start`, an `error` with a machine-readable code, and a final `summary` with `"status": "error"` and `"exit": 2`

#### Scenario: Set event describes provenance
- **WHEN** a set is assembled from volumes of two containers
- **THEN** its `set` event SHALL list each volume's index, path, source container and, if renamed, its original name

### Requirement: No human output in JSON mode
With `--json`, stdout SHALL contain no human-readable text, color codes or progress animation. Diagnostics that are not events (Python warnings, tracebacks) SHALL go to stderr.

#### Scenario: Piping to a JSON tool
- **WHEN** `deepunzip --json <dir>` is piped into a JSON lines parser
- **THEN** the parser SHALL read every line without error

### Requirement: Non-interactive operation
A run SHALL be non-interactive when `--json` is set or stdin is not a TTY. A non-interactive run SHALL NOT prompt:

- a password prompt SHALL be skipped and its item becomes unresolved with reason `password`;
- the leftover-history prompt SHALL take its default ("no");
- the exit pause SHALL be skipped.

Every prompt SHALL treat end-of-input as its default, and SHALL NOT raise.

#### Scenario: Unknown password under --json
- **WHEN** an archive needs a password that is not in the password book and `--json` is set
- **THEN** no prompt SHALL be shown
- **AND** an `unresolved` event with reason `password` SHALL be emitted

#### Scenario: Closed stdin without --json
- **WHEN** the tool runs with stdin redirected from an empty file and an archive needs an unknown password
- **THEN** the run SHALL complete without an exception
- **AND** the archive SHALL be reported as unresolved

### Requirement: Meaningful exit codes
In every output mode, the process SHALL exit with:

- `0` when every item was resolved (or there was nothing to do);
- `1` when the run completed but at least one item is unresolved;
- `2` on a fatal or usage error (engine missing or unusable, no valid input path, unexpected exception).

`--help` and `--version` SHALL exit 0.

#### Scenario: Partial run
- **WHEN** one of four archives stays unresolved
- **THEN** the exit code SHALL be 1

#### Scenario: No valid path
- **WHEN** every given path does not exist
- **THEN** the exit code SHALL be 2

### Requirement: Never include passwords in JSON
JSON events SHALL identify a password only as `password_index` (its 1-based position in the password book; `0` for the empty password), as `"entered"` for a user-entered password, or as `null` when no password was needed.

#### Scenario: Item opened with a password
- **WHEN** an archive opens with the fourth password
- **THEN** its `item` event SHALL contain `"password_index": 4`
- **AND** the password text SHALL NOT appear in any event

