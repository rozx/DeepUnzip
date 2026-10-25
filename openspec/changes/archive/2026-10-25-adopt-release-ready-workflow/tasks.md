These tasks are committed directly on `release/v2.0.0` (single release PR) and ship with v2.0.0.

## 1. Release notes location

- [x] 1.1 Change the tests first: `tests/test_release.py` and `tests/test_publish_release.py` expect `docs/releaseNotes/vX.Y.Z.md`.
- [x] 1.2 Point `scripts/release.py read_release_notes` and `scripts/publish_release.cjs` at `docs/releaseNotes/v<version>.md`.
- [x] 1.3 `git mv` every `ReleaseNotes/RELEASE_NOTES_vX.Y.Z.md` to `docs/releaseNotes/vX.Y.Z.md`, without changing contents. Update the links in `README.md` and `README.en.md`.

## 2. Release workflow gates

- [x] 2.1 Add a test-first `scripts.release verify-branch <ref>`. A version-like suffix (`release/X.Y.Z` or `release/vX.Y.Z`) must equal the project version; non-version suffixes pass.
- [x] 2.2 `.github/workflows/release.yml`:
  - trigger on `pull_request` closed on `main`;
  - require `head.repo.full_name == github.repository`;
  - run `verify-branch` in prepare;
  - use a single workflow-level concurrency group `release` (`cancel-in-progress: false`) and drop the per-tag group;
  - keep the reusable build and the resumable publisher.

## 3. CI split

- [x] 3.1 `.github/workflows/ci.yml`: add a `checks` job for push/PR/dispatch on `ubuntu-24.04` and `windows-2025` (version and engine verification, `node --check`, `compileall`, `pytest -q`).
- [x] 3.2 Run the existing five-target `build` job only for `workflow_call`, or for `workflow_dispatch` with `full_build: true`.
- [x] 3.3 Parse both workflow files as YAML locally, and check that every `uses:` stays SHA-pinned.

## 4. Skill and docs

- [x] 4.1 Write `.claude/skills/release-ready/SKILL.md`: pikpak-dl-cli's six steps, stop conditions and workflow constraints, adapted to Poetry, the three version declarations, bump commands, bilingual notes, five README languages, and this repo's checks.
- [x] 4.2 Add `.agents/skills/release-ready` as a git symlink (mode 120000) to `../../.claude/skills/release-ready`. Remove `.agents/skills/complex-unzip-release/`.
- [x] 4.3 Update `AGENTS.md` "CI and releases", the development sections of `README.md` and `README.en.md`, and `openspec/project.md`: release work on `release/vX.Y.Z`, one labeled release PR, the `release-ready` skill, fast CI versus release builds, and the notes path.
- [x] 4.4 Update references in the other v2.0.0 changes: `RELEASE_NOTES_v2.0.0.md` → `docs/releaseNotes/v2.0.0.md`, and `deepunzip-release` → `release-ready`.
- [x] 4.5 Quality gates: `pytest -q` and `openspec validate --strict` for all changes.
