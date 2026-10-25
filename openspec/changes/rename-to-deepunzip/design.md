## Context

The current name appears 275 times in 55 files:

- the package directory;
- imports in every module and test;
- `pyproject.toml`, `.bumpversion.cfg`;
- the build, release and smoke scripts;
- CI (`dist/complex-unzip-tool-v2*`);
- README, `CLAUDE.md`, `AGENTS.md`, `openspec/project.md`;
- historical release notes and archived OpenSpec changes.

The README has a Chinese default (`README.md`) and an English version (`README.en.md`), with no screenshots. The user chose the name DeepUnzip (深度解压), a five-language README, and screenshots as SVG plus an animated GIF.

## Goals / Non-Goals

**Goals:**
- One consistent new identity across package, commands, executables, assets and docs.
- Nothing breaks silently for existing developers or users within 2.x.
- READMEs in five languages that stay structurally in sync.
- Screenshots that can be regenerated with one command and always match the real output.

**Non-Goals:**
- Publishing to PyPI. The distribution name is chosen so that it would be possible later.
- Translating the terminal output beyond zh/en (see `redesign-terminal-output`).
- Rewriting historical release notes or archived specs.

## Decisions

### D1. Mechanical rename in one PR

The package moves with `git mv`, so history is kept, and all imports are rewritten in the same commit. The PR contains no behavior changes. That keeps it reviewable as "rename only": the diff of a rename-aware review is just the import lines.

The rename is applied to:
- the package, imports and `pyproject.toml`;
- `.bumpversion.cfg`;
- the build, release, smoke and icon scripts;
- CI;
- `CLAUDE.md`, `AGENTS.md` and `openspec/project.md`;
- current (non-archived) specs, where the name is part of a requirement.

### D2. Compatibility

- **Poetry scripts**: `deepunzip` and `dz` are the commands. `main` and `cuz` stay as aliases through 2.x and print a one-line deprecation notice to stderr. The notice is suppressed with `--json`.
- **Rename-history file**: `.unzip-rename-history.tmp.json` keeps its name, so a crash under 1.3.x is still recovered by 2.0.0.
- **GitHub**: the maintainer renames the repository. GitHub redirects the old web and git URLs, and the release workflow uses the repository context rather than a hardcoded name.
- **Release assets**: older releases keep their old names. Only v2.0.0 and later use `deepunzip-…`.

### D3. Five-language README

Files:

| File | Language |
| --- | --- |
| `README.md` | 简体中文 (default) |
| `README.en.md` | English |
| `README.zh-TW.md` | 繁體中文 |
| `README.ja.md` | 日本語 |
| `README.ko.md` | 한국어 |

The default stays Chinese, as today; the core audience is Chinese-speaking.

Every file starts with the same language switcher line and follows the same section order:

1. Title, tagline and badges.
2. Screenshot and demo GIF.
3. What it solves.
4. Features.
5. Quick start.
6. Usage (CLI, `--json`, exit codes, `DEEPUNZIP_LANG`, password file).
7. How it works (rounds, mix & match assembly, lineage cleanup).
8. Release packages.
9. FAQ.
10. Development.
11. License and acknowledgment.

A unit test checks that all five files exist, contain the switcher, have the same number of `##` sections, and reference existing images. This keeps translations from silently drifting in structure.

Translations are written from the Chinese and English masters. Japanese and Korean get a native-speaker review note in the PR description.

### D4. Screenshot pipeline

- **SVG**: `scripts/generate_screenshots.py` feeds a recorded event sequence (the demo run) into `TreeRenderer` with `Console(record=True, width=100)`, once per language (`DEEPUNZIP_LANG=zh` and `en`), and writes them with `console.save_svg(...)`:
  - `docs/images/terminal-zh.svg`;
  - `docs/images/terminal-en.svg`.

  No 7-Zip and no real archives are needed, so the output is deterministic.
- **GIF**: `docs/demo.tape` (a [VHS](https://github.com/charmbracelet/vhs) script) runs the real `deepunzip` on demo archives:
  - `scripts/make_demo_archives.py` builds the demo archives with the bundled 7-Zip: synthetic content, demo passwords in a demo `passwords.txt`, cloaked names, and a cross-container volume set, mirroring the real-world case;
  - the tape writes `docs/images/demo-zh.gif` and `docs/images/demo-en.gif`.

  VHS is a developer-only external tool, not a Python dependency. The development section of `README` documents how to install and run it.
- **Which README uses which assets**: the Traditional Chinese README uses the `-zh` assets; the Japanese and Korean READMEs use the `-en` assets.
- **Size**: the GIFs target under 2 MB each (short tape, 100×28 terminal).

*Alternatives considered:*
- Hand-made PNG screenshots. Rejected: they go stale with every output change.
- asciinema plus agg. Rejected: no native Windows support.

### D5. Description and About text

- `pyproject.toml` description: "DeepUnzip extracts nested, password-protected, multipart and disguised archives in one pass."
- The README tagline uses the same sentence per language. The GitHub About text and topics (`archive`, `unzip`, `7zip`, `multipart`, `password`, `cli`) are proposed in the release PR for the maintainer to apply.

## Risks / Trade-offs

- [Contributors with open branches get large conflicts] → Commit the rename after the work-pool and terminal-output commits, as the last code change on `release/v2.0.0`, and announce it in the release PR.
- [Users looking for `complex-unzip-tool-v2.exe`] → The release notes start with the rename and the old→new mapping. README badges and links use the new repository. GitHub redirects old links.
- [Translation quality in ja/ko] → Request a native review. The structure test keeps sections aligned, even if a wording is later improved.
- [VHS availability on Windows] → Record the GIF on macOS/Linux, or in the CI job; the SVGs can be generated anywhere.

## Migration Plan

This change is committed directly on `release/v2.0.0`, after the terminal-output commits. It ships through the single release PR (`release/v2.0.0` → `main`). The commit stages are:

1. **Rename (mechanical)**: package move, imports, `pyproject.toml`, scripts, CI, aliases with deprecation notice, release-prep skill, and developer docs.
2. **Docs**:
   - the five READMEs;
   - `scripts/generate_screenshots.py`, `scripts/make_demo_archives.py`, `docs/demo.tape`;
   - the generated `docs/images/*`;
   - the README structure test.
3. **Release preparation**, as in `redesign-work-pool-extraction`'s migration plan: version bump to 2.0.0, and release notes that open with the rename.

After merge, the maintainer renames the GitHub repository and updates its About text.

## Open Questions

None.
