## MODIFIED Requirements

### Requirement: Engine errors precede CLI file mutations
The CLI SHALL report an actionable error and exit with code 2 before modifying input files when its bundled engine is missing, lacks execute permission, lacks required companion files, or the platform is unsupported. Help and version SHALL remain available without an engine.

#### Scenario: Missing or unusable engine
- **WHEN** extraction is requested with an unavailable engine
- **THEN** input names and contents SHALL remain unchanged
- **AND** the CLI SHALL identify the engine or platform problem
- **AND** an interactive frozen Windows invocation SHALL pause so the error remains readable, then exit with code 2

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
