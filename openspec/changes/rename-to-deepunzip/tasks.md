These tasks land on `release/v2.0.0` as the last code changes, after `redesign-terminal-output`.

## 1. Mechanical rename (rename PR)

- [ ] 1.1 Run `git mv complex_unzip_tool_v2 deepunzip` and rewrite every import in the package, `tests/` and `scripts/`. The PR contains no behavior changes.
- [ ] 1.2 `pyproject.toml`:
  - name `deepunzip`, the new description, and `packages = [{include = "deepunzip"}]`;
  - scripts `deepunzip` and `dz`, plus `main` and `cuz` as deprecated aliases.

  Each alias prints a one-line stderr notice that names `deepunzip`, suppressed under `--json`. Test both aliases.
- [ ] 1.3 Point the tooling at the new names:
  - `.bumpversion.cfg` file path;
  - `scripts/build.py` (spec name, hidden imports, data path, `dist/deepunzip(.exe)`);
  - `scripts/release.py` (executable and `deepunzip-vX.Y.Z-<target>` asset names);
  - `scripts/smoke_test.py`, `scripts/standalone_main.py` and `scripts/generate_icon.py`.
- [ ] 1.4 Update the executable paths and the `compileall` package path in `.github/workflows/ci.yml`. Check that `release.yml` uses no hardcoded repository name.
- [ ] 1.5 Set the product name in the catalog (version output, help header) to DeepUnzip / 深度解压. Test `deepunzip --version` in both languages.
- [ ] 1.6 Move the release-prep skill to `.agents/skills/deepunzip-release/`, update its package-name check, and update every reference to it.
- [ ] 1.7 Update `CLAUDE.md`, `AGENTS.md`, `openspec/project.md` and current specs to the new names. Add a test that fails if the old name appears outside the allowlist (historical release notes, archived OpenSpec changes, the v2.0.0 rename notice).
- [ ] 1.8 Add a test that a `.unzip-rename-history.tmp.json` written by 1.3.2 is still detected and recovered.
- [ ] 1.9 Quality gates: `pytest -q`, `flake8`, `mypy`, `black`. Build `dist/deepunzip.exe` locally on Windows and run it with `--version` / `--help`.

## 2. Demo archives and screenshots (docs PR)

- [ ] 2.1 `scripts/make_demo_archives.py`: build the demo set with the bundled 7-Zip into a given folder. It contains:
  - only generated placeholder files;
  - a demo `passwords.txt`;
  - a cloaked volume name;
  - a volume set split across two containers.
- [ ] 2.2 Record the demo run's event sequence as a fixture (from the real pool on the demo set).
- [ ] 2.3 `scripts/generate_screenshots.py`: render the fixture through `TreeRenderer` with `Console(record=True, width=100)` for `zh` and `en`, and write `docs/images/terminal-zh.svg` and `terminal-en.svg`. Add a test that two consecutive runs produce identical files.
- [ ] 2.4 `docs/demo.tape` (VHS): record `docs/images/demo-zh.gif` and `demo-en.gif` on macOS or Linux, each under 2 MB. Document the VHS install and run steps.

## 3. Five-language README (docs PR)

- [ ] 3.1 Rewrite `README.md` (简体中文) in the shared section order:
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
- [ ] 3.2 Write `README.en.md` with the same structure.
- [ ] 3.3 Write `README.zh-TW.md` (using the `-zh` assets), plus `README.ja.md` and `README.ko.md` (using the `-en` assets). Ask for a native-speaker review of ja/ko in the PR description.
- [ ] 3.4 README structure test:
  - all five files exist;
  - each has the switcher with the current language marked;
  - each has the same number of `##` sections as `README.md`;
  - every referenced image exists.
- [ ] 3.5 Update badges and links to `rozx/DeepUnzip`.

## 4. Repository identity (with the release)

- [ ] 4.1 In the release PR, propose the GitHub About text (the new description) and topics (`archive`, `unzip`, `7zip`, `multipart`, `password`, `cli`) for the maintainer to apply.
- [ ] 4.2 After the release merges, the maintainer renames the repository to `rozx/DeepUnzip`. Then confirm that old URLs redirect and that the README badges resolve.
