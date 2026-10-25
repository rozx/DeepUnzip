# terminal-output Specification

## Purpose
Show what a run did in a terminal: one line per finished item, live progress, and a lineage tree with a summary at the end.
## Requirements
### Requirement: One line per finished item
The human output SHALL print one line per finished item:

- a container opened, with its output count;
- a multipart set assembled, with its volume and output counts;
- an item kept;
- an item unresolved, with its reason.

It SHALL NOT print per-password attempts, per-step headers or repeated status lines. When a root has more than 200 finished items, further item lines SHALL be summarized as a count.

#### Scenario: Four containers and two sets
- **WHEN** a root's run opens four containers and assembles two sets
- **THEN** the output SHALL contain exactly six item lines before the final tree
- **AND** no line SHALL mention individual password attempts

#### Scenario: Very many items
- **WHEN** a root produces 1,000 finished items
- **THEN** at most 200 item lines SHALL be printed for that root, followed by a line stating how many more finished

### Requirement: Live progress in an interactive terminal
When stdout is a TTY and `--json` is not set, the system SHALL keep two live lines at the bottom of the output, refreshed in place:

- **overall progress**: items resolved out of items known, the round number and elapsed time;
- **current item**: percentage, name, bytes done and total, and speed, taken from 7-Zip's progress stream.

The live lines SHALL be removed when the root finishes.

#### Scenario: Extracting a large set
- **WHEN** a 2.9 GB set is 41% extracted in an interactive terminal
- **THEN** the current-item line SHALL show 41% and about 1.2 GB of 2.9 GB
- **AND** the overall line SHALL show resolved and known item counts

### Requirement: Final lineage tree and summary
When a root finishes, the human output SHALL print a lineage tree:

- every multipart set SHALL list each volume's index and the source container (or input file) it came from;
- each renamed volume SHALL also show its original cloaked name;
- every unresolved item SHALL be listed with its reason and where it was preserved.

The tree SHALL be followed by a summary: output file count, output folder, sources deleted (and whether to the Recycle Bin) and kept, elapsed time, and exit code.

#### Scenario: Cross-container set with a cloaked volume
- **WHEN** set `X.7z` was assembled from `.7z.001` (from `B.rar`, originally `X.7z.001删掉`) and `.7z.002` (from `A.7z`)
- **THEN** the tree SHALL show `X.7z` with child `.7z.001 ← B.rar`, marked as uncloaked from `X.7z.001删掉`
- **AND** a child `.7z.002 ← A.7z`

#### Scenario: Unresolved item in the summary
- **WHEN** `inner.rar` stays unresolved because no password worked
- **THEN** the tree SHALL list `inner.rar` with reason "password" and its location in the output folder
- **AND** the summary SHALL report its source as kept

### Requirement: Plain output when stdout is not a terminal
When stdout is not a TTY, the system SHALL print the same item lines, tree and summary without live rendering, spinners or progress-bar frames. It SHALL emit no color codes when `NO_COLOR` is set.

#### Scenario: Output redirected to a file
- **WHEN** the tool runs with stdout redirected to a file
- **THEN** the file SHALL contain no repeated progress lines and no cursor-movement escape sequences
- **AND** each finished item SHALL appear exactly once

### Requirement: Never print passwords
No output mode SHALL contain a password from the password book or a password entered by the user. A working password SHALL be identified by its 1-based position in the password book, as "empty password", or as "entered".

#### Scenario: Archive opened with the fourth password
- **WHEN** an archive opens with the fourth password in the password book
- **THEN** the item line SHALL show `password #4`
- **AND** the password text SHALL NOT appear anywhere in the output

