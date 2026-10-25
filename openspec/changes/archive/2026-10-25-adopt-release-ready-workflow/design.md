## Context

pikpak-dl-cli (Bun/TypeScript) releases through a `release-ready` skill and one `release.yml`. It has no other workflow. This repository (Python/Poetry) has:

- a `complex-unzip-release` skill;
- `ci.yml`, which builds five platforms on every push/PR and is reusable by the release workflow;
- `release.yml`, triggered by `pull_request_target`, with a resumable draft publisher (`scripts/publish_release.cjs`).

The user asked for the same workflow here, using pikpak-dl-cli as the reference. They chose:

- release notes in `docs/releaseNotes/` with pikpak's template, bilingual;
- fast CI on push/PR, full builds only for releases;
- keeping the resumable publication.

## Goals / Non-Goals

**Goals:**
- One release procedure, the `release-ready` skill, with the same steps and stop conditions as pikpak-dl-cli.
- pikpak's eligibility gates in `release.yml`: same-repository branch, branch version equals project version, `pull_request` trigger.
- Faster feedback on ordinary pushes, without weakening what a release verifies.

**Non-Goals:**
- Making flake8/mypy blocking. The baseline has 191 flake8 and 123 mypy findings; clearing them is separate work.
- Changing asset formats, the checksum index name (`SHA256SUMS`), or the archive contents.
- Changing day-to-day commit rules outside releases.

## Decisions

### D1. The skill mirrors pikpak's six steps, adapted to this toolchain

`.claude/skills/release-ready/SKILL.md` holds the skill. `.agents/skills/release-ready` is a git symlink (mode 120000) to it, exactly as in pikpak-dl-cli, so Claude Code and Codex share one file. The skill is written in Chinese like pikpak's, and replaces `.agents/skills/complex-unzip-release`. Differences from pikpak:

- **Version source**: three declarations instead of `package.json`. They are read with `poetry run python -m scripts.release version`, and bumped with `poetry run bump-major|bump-minor|bump-patch`, or with `bump2version --new-version X.Y.Z` for an explicit version, in its own `chore: bump version to X.Y.Z` commit.
- **Inference**: this project is past 1.0, so inference follows semver. `BREAKING`/`!` means major, `feat` means minor, `fix` means patch.
- **Checks**:
  - `poetry run pytest -q`;
  - `poetry run python -m scripts.smoke_test`;
  - `scripts.release version` / `verify-notes` / `verify-engines` / `verify-branch`;
  - `--help`;
  - `openspec validate --specs --strict`.
- **Docs pass**: every README language file, plus `AGENTS.md`, `CLAUDE.md` and `docs/*.md`. It never edits `openspec/specs/`, the archive, or `docs/releaseNotes/` of older versions.
- **Notes**: bilingual, with each section in Chinese then English. The download table must match `TARGETS` in `scripts/release.py`.
- **PR**: title `release: vX.Y.Z`; the body is the notes plus the session's attribution, written to a temp file. The skill creates the `release` label if it is missing. The release work itself has already been committed on the branch.

### D2. Notes move to `docs/releaseNotes/vX.Y.Z.md`

Historical files are moved with `git mv ReleaseNotes/RELEASE_NOTES_vX.Y.Z.md docs/releaseNotes/vX.Y.Z.md`, which keeps their history; their contents are untouched. `scripts/release.py read_release_notes`, `publish_release.cjs` and README links follow the new path. *Alternative considered:* keep the old path. Rejected by the user, in favor of matching pikpak.

### D3. `release.yml` gates

- **Trigger**: `on: pull_request: types: [closed], branches: [main]`. Release branches are always in this repository, so the extra power of `pull_request_target` (a base-branch workflow with write access, triggerable from forks) is not needed. The job condition adds `github.event.pull_request.head.repo.full_name == github.repository`.
- **Branch check**: a new `python -m scripts.release verify-branch "$HEAD_REF"` fails when the suffix after `release/` (an optional `v` is stripped) looks like `X.Y.Z` but differs from the project version. A non-version suffix such as `release/rename` is allowed, as in pikpak.
- **Concurrency**: one workflow-level group `release`, with `cancel-in-progress: false`, so two release merges never publish concurrently. The publish job's per-tag group is removed as redundant.
- **Kept from this repo**:
  - `build` reuses `ci.yml` through `workflow_call` at the merge SHA;
  - `verify-assets` plus the resumable draft publisher;
  - the tag-at-another-commit check;
  - SHA-pinned actions;
  - only the publish job holds `contents: write`.

*Rationale for keeping these:* pikpak's `gh release create` cannot resume after a partial upload, and its unpinned action tags are weaker supply-chain hygiene.

### D4. `ci.yml` split

- **`checks` job**: runs on `push` / `pull_request` to `main` and `release/**`, and on `workflow_dispatch`. Matrix: `ubuntu-24.04` and `windows-2025`. Steps: install, then `scripts.release version` and `verify-engines`, `node --check scripts/publish_release.cjs`, `compileall`, `pytest -q`.
- **`build` job**: runs only for `workflow_call` (the release) or `workflow_dispatch` with `full_build: true`. It does the existing five-target build, source and standalone smoke tests, packaging and artifact upload, unchanged.

The concurrency rule is unchanged: ordinary runs cancel older ones, release builds never do.

## Risks / Trade-offs

- [Platform-specific breakage is found only at release time] → Windows runs the full unit test suite on every push. The release build still runs the native smoke tests on all five targets before anything is published. A maintainer can trigger the full build on any branch with `workflow_dispatch` (`full_build`).
- [The trigger switch must work on the very merge that introduces it] → For `pull_request` events, GitHub runs the workflow file from the event's commit, which here is the merge, so v2.0.0 already uses the new gates. The v2.0.0 run is the verification. If it does not trigger, the draft publisher can be re-run safely, because the publication is resumable.
- [Symlinks on Windows checkouts (`core.symlinks=false`)] → Git stores the symlink as mode 120000. Windows checkouts get a small text file with the link target, the same as pikpak-dl-cli today. The real `SKILL.md` lives under `.claude/`.

## Migration Plan

All of this is committed directly on `release/v2.0.0` (single release PR) and ships with v2.0.0:

1. Move the notes and update their consumers (scripts, tests, README links).
2. Add `verify-branch` and update `release.yml`.
3. Split `ci.yml`.
4. Add the `release-ready` skill and symlink, remove `complex-unzip-release`, and update `AGENTS.md`, both README development sections and `openspec/project.md`.

The v2.0.0 release itself is then prepared by running `release-ready` on `release/v2.0.0`.

## Open Questions

None.
