# Project Context

## Purpose

Complex Unzip Tool v2 is a robust and intelligent command-line archive extraction utility for Windows x64, macOS Intel/Apple Silicon, and Linux x64/ARM64. It handles complex archive scenarios including password-protected files, multipart archives, nested structures, and cloaked/obfuscated filenames. The tool provides automated extraction with smart features like drag-and-drop support, intelligent password management, and multilingual support (English/Chinese).

Inspired by: https://github.com/TR-Supowe/Complex-Unzip-Tool

## Tech Stack

### Core Technologies
- **Python**: 3.11+ (primary language)
- **Poetry**: Dependency management and packaging
- **Typer**: CLI framework (version ^0.17.3)
- **Rich**: Rich terminal output and progress display (version ^14.1.0)
- **send2trash**: Safe file deletion to recycle bin (version ^1.8.3)
- **7-Zip**: Archive extraction engine (26.03; native assets and licenses under `7z/`, selected by `modules/seven_zip_runtime.py`)

### Development Tools
- **pytest**: Testing framework (version ^7.4.0)
- **black**: Code formatter (line-length: 88, target: py38+)
- **flake8**: Linter (max-line-length: 88, ignores E203, W503)
- **mypy**: Static type checker (python_version: 3.11, strict mode)
- **PyInstaller**: Standalone executable builder (version ^6.15.0)

### Build & Packaging
- **Poetry scripts**: `main`, `cuz`, `build`, `bump`, `bump-patch`, `bump-minor`, `bump-major`
- **Custom build scripts**: `scripts/build.py`, `scripts/build.bat`, `scripts/generate_icon.py`
- **Version management**: `bump2version` (version ^1.0.1)

## Project Conventions

### Code Style

**Formatting**:
- Use **black** for code formatting (88 character line length)
- Target Python 3.8+ compatibility for broader deployment
- Follow PEP 8 style guidelines where applicable

**Naming Conventions**:
- **Files**: snake_case (e.g., `archive_utils.py`, `cloaked_file_detector.py`)
- **Classes**: PascalCase (e.g., `ArchiveGroup`, `PasswordBook`, `CloakedFileDetector`)
- **Functions/Variables**: snake_case (e.g., `extract_nested_archives`, `is_valid_archive`)
- **Constants**: UPPER_SNAKE_CASE (e.g., in `modules/const.py`)

**Type Hints**:
- Use type hints for all function signatures (mypy strict mode enabled)
- Import from `typing` module as needed
- Return types are mandatory for all functions

**Documentation**:
- Use docstrings for all public functions and classes
- Inline comments for complex logic
- Keep functions small and focused (prefer pure helpers in `modules/`)

### Architecture Patterns

**Module Organization**:
```
complex_unzip_tool_v2/
├── __main__.py          # Entry point for poetry run main
├── main.py              # CLI application (Typer app)
├── classes/             # Domain models and business logic
│   ├── ArchiveExceptions.py  # Custom exception hierarchy
│   ├── ArchiveGroup.py        # Archive grouping logic
│   ├── ArchiveTypes.py        # Archive type definitions
│   └── PasswordBook.py        # Password management
├── modules/             # Utility functions and helpers
│   ├── archive_utils.py       # Core archive operations
│   ├── archive_extension_utils.py  # Archive type detection
│   ├── file_utils.py          # File operations
│   ├── password_util.py       # Password file handling
│   ├── cloaked_file_detector.py  # Filename uncloaking
│   ├── const.py               # Constants
│   ├── regex.py               # Regex patterns
│   ├── rich_utils.py          # Rich UI utilities
│   └── utils.py               # General utilities
└── config/              # Configuration files
    └── cloaked_file_rules.json  # Cloaked file detection rules
```

**Design Principles**:
- **Separation of Concerns**: Domain logic in `classes/`, utilities in `modules/`
- **Single Responsibility**: Each module has a clear, focused purpose
- **Error Handling**: Raise domain exceptions from `classes/ArchiveExceptions.py`
- **Path Handling**: Prefer `pathlib.Path` over string paths
- **Configuration-Driven**: Cloaked file rules in JSON config file
- **Dependency Injection**: Pass dependencies (like group_relocator) as callbacks

**Key Patterns**:
- **Archive Operations**: Centralized in `archive_utils.py` and `archive_extension_utils.py`
- **File Operations**: Use utilities in `file_utils.py` for consistency
- **Password Management**: Multi-source discovery (target dir + tool root)
- **Cloaked File Detection**: Rule-based system with priority ordering
- **Multipart Handling**: Primary vs continuation part identification
- **Nested Extraction**: Recursive extraction with continuation part relocation

### Testing Strategy

**Test Structure**:
```
tests/
├── test_archive_utils.py      # Archive operation tests
├── test_cloaked_file_detector.py  # Cloaked file detection tests
├── test_file_utils.py         # File utility tests
└── test_main.py               # CLI integration tests
```

**Testing Guidelines**:
- Use **pytest** for all tests
- Test files named `test_*.py`
- Cover happy path and at least one edge case per feature
- Prefer small, deterministic test fixtures
- Test error cases (missing password, invalid archive, cloaked files)

**Test Execution**:
```bash
# Run all tests
poetry run pytest -q

# Run specific test file
poetry run pytest tests/test_archive_utils.py -q

# Run with verbose output
poetry run pytest -v
```

**Quality Gates**:
- All tests must pass before committing
- New behavior must be covered by tests
- Regression tests for bug fixes

### Git Workflow

**Branching Strategy**:
- `main` / `master`: Production-ready code
- `feature/*`: Feature development
- `bugfix/*`: Bug fixes
- `hotfix/*`: Critical production fixes

**Commit Conventions**:
- Use concise, descriptive commit messages
- Format: `[type] brief description`
- Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`
- Include checklist status in PR descriptions

**Pull Request Template**:
```markdown
- Summary: what changed and why
- Tests: added/updated tests and results (pytest -q passes)
- Impact: user-facing behavior changes? update README.md
- Risks: edge cases considered; rollback plan if needed
```

**Change Workflow**:
1. Branch and plan minimal change set
2. Add/adjust tests (write failing test first if practical)
3. Implement changes (keep diffs small and focused)
4. Run quality gates: build, tests, lint/typecheck
5. Update docs if user-facing behavior changes
6. Commit with clear message and open PR

## Domain Context

### Archive Types Supported

**Primary Formats**:
- ZIP (including spanned multipart: .zip, .z01, .z02, ...)
- RAR (including multipart: .rar, .r00, .r01, ..., .part1.rar, .part2.rar)
- 7z (including multipart: .7z, .7z.001, .7z.002, ...)
- TAR (including compressed: .tar, .tar.gz, .tar.bz2, .tar.xz)
- GZIP, BZIP2, XZ, ARJ, CAB, LZH, LHA, ACE, ISO, IMG, BIN

**Multipart Archive Patterns**:
- 7z volumes: `.7z.001` (primary), `.7z.002+` (continuation)
- TAR multipart: `.tar.gz/.tar.bz2/.tar.xz.001` (primary), `.002+` (continuation)
- RAR volumes: `.rar` or `.part1.rar` (primary), `.r00`, `.r01`, ... (continuation)
- ZIP spanned: `.zip` (primary), `.z01`, `.z02`, ... (continuation)

### Cloaked File Detection

**Purpose**: Detect and normalize disguised archive filenames

**Safety Guards** (never rename these):
- Files already with proper multipart format (`.7z.001`, `.r00`, `.z01`, etc.)
- Files ending with proper single archive extension (`.7z`, `.rar`, `.zip`, etc.)

**Rule Schema**:
```json
{
  "name": "rule-identifier",
  "matching_type": "both|filename|ext",
  "filename_pattern": "regex-pattern",
  "ext_pattern": "regex-pattern",
  "priority": 100,
  "type": "7z|rar|zip|auto",
  "enabled": true
}
```

**Examples**:
- `11111.7z删除` → `11111.7z`
- `11111.7z.00删1` → `11111.7z.001`
- `archive.zip.z0隐藏1` → `archive.zip.z01`
- `file.rar.r00删除` → `file.rar.r00`

### Password Management

**Discovery Order**:
1. Target directory: `passwords.txt` in the directory being processed
2. Tool root directory: `passwords.txt` at repository root

**File Format**:
- One password per line
- Blank lines ignored
- Encoding support: `utf-8-sig`, `utf-8`, `gbk`, `gb2312`, `big5`, `utf-16`, `utf-16-le`, `utf-16-be`
- BOM handling: Stripped automatically
- Saving: New passwords saved to local `passwords.txt` in UTF-8

### Nested Archive Handling

**Behavior**:
- Primary parts extracted recursively
- Continuation parts relocated to multipart group directory
- Reconciliation pass after single-archive extraction to catch missed parts
- Non-archive files (e.g., .mp4) not flagged as corrupted

**Key Functions**:
- `extract_nested_archives()` - Main nested extraction logic
- `relocate_multipart_parts_from_directory()` - Reconciliation pass
- `is_valid_archive()` - Archive validation with 7-Zip

## Important Constraints

### Technical Constraints
- **Platform**: Windows x64, macOS Intel/Apple Silicon, Linux x64/ARM64
- **Python Version**: 3.11+ required for development
- **Shell**: PowerShell on Windows; bash/zsh on macOS/Linux
- **File System**: Use host-native paths via pathlib/os.path
- **Encoding**: Multiple encoding support for password files (Chinese character support)

### Business Constraints
- **No Network Calls**: Do not exfiltrate secrets or make network calls unless explicitly required
- **Local Execution**: Offline execution on supported platforms
- **Backward Compatibility**: Preserve existing behavior unless intentionally modified
- **Stability**: Keep the app stable and easy to maintain
- **Minimal Changes**: Prefer minimal, well-scoped changes with tests

### Regulatory/Security Constraints
- **No Secret Leakage**: Build scripts must not leak secrets
- **Safe File Deletion**: Default behavior moves files to Recycle Bin, not permanent deletion
- **Password Security**: Passwords stored in plain text files (user's responsibility)
- **7-Zip License**: Must include 7-Zip license in standalone executable

### Development Constraints
- **PR Size**: Keep PRs atomic and under ~300 lines when possible
- **Dependencies**: Avoid introducing new dependencies unless clearly justified
- **Bundled Binaries**: Upgrade only when explicitly requested; preserve upstream bytes, platform licenses, and provenance in `7z/manifest.json`
- **Public APIs**: Keep public APIs stable unless change is intentional and documented

## External Dependencies

### Runtime Dependencies
- **7-Zip**: Native bundled engine for the host platform (required for archive operations)
  - Locations: `7z/windows-x64/7z.exe` + `7z.dll`, `7z/macos/7zz`, `7z/linux-x64/7zzs`, `7z/linux-arm64/7zzs`
  - License: Must include the `License.txt` next to the selected engine in distribution
  - Version: 26.03 (managed separately from Python dependencies)

### Python Dependencies (via Poetry)
- **typer** (^0.17.3): CLI framework for command-line interface
- **rich** (^14.1.0): Rich terminal output and progress bars
- **send2trash** (^1.8.3): Safe file deletion to Recycle Bin

### Development Dependencies
- **pytest** (^7.4.0): Testing framework
- **black** (^23.7.0): Code formatter
- **flake8** (^6.0.0): Linter
- **mypy** (^1.5.0): Static type checker
- **PyInstaller** (^6.15.0): Standalone executable builder
- **bump2version** (^1.0.1): Version management

### Build Tools
- **Poetry**: Dependency management and packaging
- **Python**: 3.11+ interpreter
- **PowerShell**: Default shell for Windows development

### No External Services
- **No APIs**: No external API calls
- **No Databases**: No database dependencies
- **No Cloud Services**: No cloud service integrations
- **Offline Capable**: Fully functional offline

### Configuration Files
- **pyproject.toml**: Poetry configuration and tool settings
- **poetry.lock**: Locked dependency versions
- **.flake8**: Flake8 configuration
- **.bumpversion.cfg**: Bump2version configuration
- **cloaked_file_rules.json**: Cloaked file detection rules (in `complex_unzip_tool_v2/config/`)

### Entry Points
- **CLI Entry**: `complex_unzip_tool_v2/__main__.py` and `complex_unzip_tool_v2/main.py`
- **Poetry Scripts**: `main`, `cuz`, `build`, `bump`, `bump-patch`, `bump-minor`, `bump-major`
- **Standalone Executable**: `dist/complex-unzip-tool-v2.exe` on Windows; `dist/complex-unzip-tool-v2` on macOS/Linux (build on the target OS/architecture)

### Testing Infrastructure
- **Test Runner**: pytest
- **Test Location**: `tests/` directory
- **Test Coverage**: Archive operations, cloaked file detection, file utilities, CLI integration

### Documentation
- **README.md**: User-facing documentation (bilingual: English/Chinese)
- **AGENTS.md**: AI agent guidelines and project conventions
- **Release Notes**: `docs/releaseNotes/vX.Y.Z.md`, bilingual, written by the `release-ready` skill (`.claude/skills/release-ready/`) on the `release/vX.Y.Z` branch
- **OpenSpec**: `openspec/` directory for spec-driven development

## Quick Reference

### Common Commands
```powershell
# Run the tool
poetry run main "C:\path\to\archives"

# Run tests
poetry run pytest -q

# Build standalone executable
poetry run build

# Format code
poetry run black complex_unzip_tool_v2/ tests/

# Lint code
poetry run flake8 complex_unzip_tool_v2/ tests/

# Type check
poetry run mypy complex_unzip_tool_v2/
```

### Key File Locations
- **7-Zip Binary**: See `7z/README.md` for the native platform paths
- **Config**: `complex_unzip_tool_v2/config/cloaked_file_rules.json`
- **CLI Entry**: `complex_unzip_tool_v2/__main__.py`
- **Main Logic**: `complex_unzip_tool_v2/main.py`
- **Core Modules**: `complex_unzip_tool_v2/modules/`
- **Domain Classes**: `complex_unzip_tool_v2/classes/`
- **Tests**: `tests/`

### Quality Gates Checklist
- [ ] CLI `--help` works without errors
- [ ] All tests pass (`poetry run pytest -q`)
- [ ] No syntax/type errors
- [ ] No unnecessary refactors
- [ ] Docs updated if behavior changed
- [ ] Linting passes (`flake8`)
- [ ] Type checking passes (`mypy`)
- [ ] Formatting applied (`black`)
