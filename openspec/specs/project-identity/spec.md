# project-identity Specification

## Purpose
Define the DeepUnzip names for the product, package, commands, executables and assets, and keep older names and files working.
## Requirements
### Requirement: DeepUnzip names
The project SHALL use these names:

| What | Name |
| --- | --- |
| Product (English) | DeepUnzip |
| Product (Chinese) | 深度解压 |
| Distribution | `deepunzip` |
| Python package | `deepunzip` |
| CLI commands | `deepunzip`, plus the short alias `dz` |
| Standalone executable | `deepunzip` (`deepunzip.exe` on Windows) |
| Environment variable prefix | `DEEPUNZIP_` |

User-facing output, help text and documentation SHALL NOT use the old name, except in historical release notes, archived OpenSpec changes, and the rename notice of the v2.0.0 release notes.

#### Scenario: Version output
- **WHEN** the user runs `deepunzip --version`
- **THEN** the output SHALL name the product DeepUnzip (or 深度解压 in Chinese) and the version

#### Scenario: Short alias
- **WHEN** the user runs `dz <path>` in a Poetry environment
- **THEN** it SHALL behave exactly like `deepunzip <path>`

### Requirement: Deprecated developer aliases
The Poetry scripts `main` and `cuz` SHALL remain available throughout 2.x and behave like `deepunzip`. Each SHALL print a one-line deprecation notice to stderr naming `deepunzip`, unless `--json` is set.

#### Scenario: Old alias
- **WHEN** a developer runs `poetry run cuz <path>`
- **THEN** extraction SHALL run as with `deepunzip`
- **AND** stderr SHALL contain a deprecation notice that names `deepunzip`

### Requirement: Rename-history continuity
The rename-history file SHALL keep the name `.unzip-rename-history.tmp.json`, so that leftover history from a 1.3.x run is detected and recovered by DeepUnzip.

#### Scenario: Leftover from 1.3.2
- **WHEN** an input root contains a `.unzip-rename-history.tmp.json` written by 1.3.2
- **THEN** DeepUnzip SHALL detect it and offer recovery at startup

### Requirement: Project description
`pyproject.toml` SHALL describe the project as "DeepUnzip extracts nested, password-protected, multipart and disguised archives in one pass." Each README's tagline SHALL be that sentence in its language.

#### Scenario: Package metadata
- **WHEN** the package metadata is built
- **THEN** its name SHALL be `deepunzip` and its summary SHALL be the sentence above

