These tasks are committed directly on `release/v2.0.0` (single release PR) as the last code changes, after `redesign-terminal-output`.

## 1. Mechanical rename (rename stage)

- [x] 1.1 Run `git mv complex_unzip_tool_v2 deepunzip` and rewrite every import in the package, `tests/` and `scripts/`. The commit contains no behavior changes.
- [x] 1.2 `pyproject.toml`:
  - name `deepunzip`, the new description, and `packages = [{include = "deepunzip"}]`;
  - scripts `deepunzip` and `dz`, plus `main` and `cuz` as deprecated aliases.

  Each alias prints a one-line stderr notice that names `deepunzip`, suppressed under `--json`. Test both aliases.
- [x] 1.3 Point the tooling at the new names:
  - `.bumpversion.cfg` file path;
  - `scripts/build.py` (spec name, hidden imports, data path, `dist/deepunzip(.exe)`);
  - `scripts/release.py` (executable and `deepunzip-vX.Y.Z-<target>` asset names);
  - `scripts/smoke_test.py`, `scripts/standalone_main.py` and `scripts/generate_icon.py`.
- [x] 1.4 Update the executable paths and the `compileall` package path in `.github/workflows/ci.yml`. Check that `release.yml` uses no hardcoded repository name.
- [x] 1.5 Set the product name in the catalog (version output, help header) to DeepUnzip / 深度解压. Test `deepunzip --version` in both languages.
- [x] 1.6 Update the `release-ready` skill for the new names: the package path `deepunzip/__init__.py`, the product name, and the `deepunzip-v…` asset names in its download table.
- [x] 1.7 Update `CLAUDE.md`, `AGENTS.md`, `openspec/project.md` and current specs to the new names. Add a test that fails if the old name appears outside the allowlist (historical release notes, archived OpenSpec changes, the v2.0.0 rename notice).
- [x] 1.8 Add a test that a `.unzip-rename-history.tmp.json` written by 1.3.2 is still detected and recovered.
- [x] 1.9 Quality gates: `pytest -q`, `flake8`, `mypy`, `black`. Build `dist/deepunzip.exe` locally on Windows and run it with `--version` / `--help`.

## 2. Demo archives and screenshots (docs stage)

- [x] 2.1 `scripts/make_demo_archives.py`: build the demo set with the bundled 7-Zip into a given folder. It contains:
  - only generated placeholder files;
  - a demo `passwords.txt`;
  - a cloaked volume name;
  - a volume set split across two containers.
- [x] 2.2 Record the demo run's event sequence as a fixture (from the real pool on the demo set).
- [x] 2.3 `scripts/generate_screenshots.py`: render the fixture through `TreeRenderer` with `Console(record=True, width=100)` for `zh` and `en`, and write `docs/images/terminal-zh.svg` and `terminal-en.svg`. Add a test that two consecutive runs produce identical files.
- [ ] 2.4 `docs/demo.tape` (VHS) and `scripts/record_demo.py`: record `docs/images/demo-<lang>.gif` for the five output languages in WSL (or on macOS/Linux), each under 2 MB. Document the VHS install and run steps.
- [x] 2.5 Render `terminal-<lang>.svg` for all five output languages.

## 3. Five-language README (docs stage)

- [x] 3.1 Rewrite `README.md` (简体中文) in the shared section order:
  1. Screenshot and demo
  2. What it solves
  3. Features
  4. Quick start
  5. Usage (CLI, `--json`, exit codes, `DEEPUNZIP_LANG`, password file)
  6. How it works
  7. Release packages
  8. FAQ
  9. Development
  10. License and acknowledgment

  Start with the language switcher and the new tagline.
- [x] 3.2 Write `README.en.md` with the same structure.
- [x] 3.3 Write `README.zh-TW.md`, `README.ja.md` and `README.ko.md`, each using its own language's assets. Ask for a native-speaker review of ja/ko in the PR description.
- [x] 3.4 README structure test:
  - all five files exist;
  - each has the switcher with the current language marked;
  - each has the same number of `##` sections as `README.md`;
  - every referenced image exists.
- [x] 3.5 Update badges and links to `rozx/DeepUnzip`. Badges: latest release, total downloads, latest-release downloads, release date, CI status, stars, license, platforms.

## 4. Repository identity (with the release)

- [ ] 4.1 In the release PR, propose the GitHub About text (the new description) and topics (`archive`, `unzip`, `7zip`, `multipart`, `password`, `cli`) for the maintainer to apply.
- [ ] 4.2 After the release merges, the maintainer renames the repository to `rozx/DeepUnzip`. Then confirm that old URLs redirect and that the README badges resolve.
