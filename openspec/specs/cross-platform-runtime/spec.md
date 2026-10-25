# cross-platform-runtime Specification

## Purpose
Provide offline archive extraction and standalone command-line distribution using native 7-Zip engines on supported Windows, macOS, and Linux systems.
## Requirements
### Requirement: Native offline archive engine
The system SHALL bundle official 7-Zip 26.03 for Windows x64, macOS x64/ARM64, and Linux x64/ARM64 and automatically select the compatible engine without network access or a system installation. Existing explicit executable-path overrides SHALL remain supported.

#### Scenario: Source and standalone execution
- **WHEN** the application lists or extracts an archive on a supported platform from any working directory
- **THEN** it SHALL use the matching bundled native engine in both source and standalone execution
- **AND** password, multipart, nested extraction, and source retention behavior SHALL be preserved

#### Scenario: Explicit executable override
- **WHEN** a caller supplies an executable file path
- **THEN** listing and extraction SHALL use that file instead of the bundled default

### Requirement: Engine errors precede CLI file mutations
The CLI SHALL report an actionable error and exit with code 2 before modifying input files when its bundled engine is missing, lacks execute permission, lacks required companion files, or the platform is unsupported. Help and version SHALL remain available without an engine.

#### Scenario: Missing or unusable engine
- **WHEN** extraction is requested with an unavailable engine
- **THEN** input names and contents SHALL remain unchanged
- **AND** the CLI SHALL identify the engine or platform problem
- **AND** an interactive frozen Windows invocation SHALL pause so the error remains readable, then exit with code 2

### Requirement: Platform-native standalone distribution
The build command SHALL produce a standalone console program named `deepunzip` for the host platform, including only its native engine and required redistribution notices. It SHALL validate required assets before removing previous build output.

#### Scenario: Building on macOS or Linux
- **WHEN** the build command runs on a supported macOS or Linux host
- **THEN** it SHALL produce `dist/deepunzip` with an executable bundled engine

#### Scenario: Building on Windows
- **WHEN** the build command runs on Windows x64
- **THEN** it SHALL produce `dist/deepunzip.exe` with the updated engine and its DLL

#### Scenario: Incomplete build inputs
- **WHEN** a required engine file or license is missing
- **THEN** the build SHALL fail clearly without deleting existing output

### Requirement: Terminal-compatible exit
Standalone programs SHALL pause on exit only for interactive Windows terminals, and never when `--json` is set. The pause SHALL NOT change the exit code.

#### Scenario: POSIX or redirected invocation
- **WHEN** a macOS/Linux standalone command completes or Windows stdin or stdout is redirected
- **THEN** the application SHALL exit without requesting an additional Enter key

#### Scenario: JSON mode in an interactive Windows terminal
- **WHEN** the frozen Windows program runs with `--json` in an interactive terminal
- **THEN** it SHALL exit without requesting an additional Enter key

#### Scenario: Windows output uses a legacy code page
- **WHEN** Windows stdout or stderr is redirected to a pipe or file under a legacy encoding such as GBK
- **THEN** the CLI SHALL emit UTF-8 output without an encoding error for Chinese text or emoji
- **AND** both source and standalone invocations SHALL support this behavior without requiring Python environment variables

