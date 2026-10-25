## Why

"Complex-unzip-tool-v2" is long and generic, carries a `v2` suffix, and is hard to remember, type and search for. Users run `complex-unzip-tool-v2.exe`; developers run `poetry run main` or `cuz`. The README exists only in Chinese and English, and shows no picture of what the tool actually prints.

v2.0.0 already changes the extraction flow and the terminal output, so it is the natural release for a new identity.

## What Changes

- **BREAKING (identity)** The project becomes **DeepUnzip** (Chinese name **深度解压**). The new names are:

  | What | Now | New |
  | --- | --- | --- |
  | Product name | Complex Unzip Tool v2 | DeepUnzip / 深度解压 |
  | Distribution name | `complex-unzip-tool-v2` | `deepunzip` |
  | Python package | `complex_unzip_tool_v2/` | `deepunzip/` |
  | CLI commands | `main`, `cuz` (Poetry scripts) | `deepunzip`, short alias `dz` |
  | Standalone executable | `complex-unzip-tool-v2(.exe)` | `deepunzip(.exe)` |
  | Release assets | `complex-unzip-tool-v2-vX.Y.Z-<target>.<ext>` | `deepunzip-vX.Y.Z-<target>.<ext>` |
  | Environment variables | – | `DEEPUNZIP_*` prefix (e.g. `DEEPUNZIP_LANG`) |
  | Run work directory | – | `temp.deepunzip-<run-id>` |
  | GitHub repository | `rozx/Complex-unzip-tool-v2` | `rozx/DeepUnzip` (renamed by the maintainer; GitHub redirects old URLs) |

  The developer aliases `main` and `cuz` keep working through 2.x, printing a deprecation notice, and are removed in 3.0.0. The rename-history file `.unzip-rename-history.tmp.json` keeps its name, so leftovers from 1.3.x are still recovered.
- **New description**, used in `pyproject.toml` and the README tagline, and offered for the GitHub About box:
  - "DeepUnzip extracts nested, password-protected, multipart and disguised archives in one pass."
  - "深度解压：一次解开套娃、加密、分卷和伪装的压缩包。"
- **README in five languages** with identical structure and a language switcher on top:
  - `README.md` (简体中文, default as today);
  - `README.en.md` (English);
  - `README.zh-TW.md` (繁體中文);
  - `README.ja.md` (日本語);
  - `README.ko.md` (한국어).

  The content is rewritten for 2.0.0: what it solves, a screenshot and demo, features, quick start, usage (`--json`, exit codes, `DEEPUNZIP_LANG`), how it works, the release package table, FAQ, license and acknowledgment.
- **Screenshots generated, not hand-made:**
  - `scripts/generate_screenshots.py` renders SVG screenshots of the real terminal renderer (Chinese and English) from a recorded demo event sequence.
  - A VHS tape (`docs/demo.tape`) records an animated GIF of a real run against synthetic demo archives created by `scripts/make_demo_archives.py`.
  - Assets live in `docs/images/`. The Traditional Chinese README uses the Chinese assets; the Japanese and Korean READMEs use the English ones.
- Repository docs and tooling follow the new name:
  - `CLAUDE.md`, `AGENTS.md`, `openspec/project.md`;
  - the build, release and smoke scripts, and the CI and release workflows;
  - the `release-ready` skill's package path, product name and asset names.

  Historical release notes and archived OpenSpec changes are left untouched.

## Capabilities

### New Capabilities
- `project-identity`: product, distribution, package, command, executable, asset and environment-variable names; the deprecated aliases; and continuity of the rename-history file name.
- `readme-docs`: the five README languages, language switcher, shared section structure, required content, and generated screenshot/GIF assets with their regeneration commands.

### Modified Capabilities
- `cross-platform-runtime`: the standalone build produces `dist/deepunzip(.exe)`.
- `github-release-ci`: release assets are named `deepunzip-vX.Y.Z-<target>.<ext>`.

## Impact

- **Code**:
  - `git mv complex_unzip_tool_v2 deepunzip` plus import updates: 275 occurrences in 55 files today, minus historical docs.
  - `pyproject.toml` (name, description, packages, scripts), `.bumpversion.cfg`, `scripts/build.py`, `scripts/release.py`, `scripts/smoke_test.py`, `scripts/standalone_main.py`, `scripts/generate_icon.py`, `.github/workflows/ci.yml`.
- **New files**: three README translations, `docs/images/*`, `docs/demo.tape`, `scripts/generate_screenshots.py`, `scripts/make_demo_archives.py`.
- **External, done by the maintainer**: rename the GitHub repository and update its About text. Badges and links in the README point at `rozx/DeepUnzip`.
- **Users**: the downloaded executable and archive names change. The v2.0.0 release notes explain the rename and the old→new mapping.
- **Depends on** `redesign-terminal-output` for the screenshots and the README usage section. Ships in **v2.0.0**.
