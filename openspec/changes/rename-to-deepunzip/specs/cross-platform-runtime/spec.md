## MODIFIED Requirements

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
