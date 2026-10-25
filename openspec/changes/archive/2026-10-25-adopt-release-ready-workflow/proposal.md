## Why

The maintainer's other CLI project, pikpak-dl-cli, prepares releases with a `release-ready` skill. That skill:

- checks the version against the `release/x.y.z` branch;
- writes notes from a fixed template, from what changed since the last tag;
- updates the docs;
- runs the checks;
- opens a labeled release PR.

This repository does the same job differently. Its `complex-unzip-release` skill neither cuts the branch nor gathers the changes. Notes live elsewhere and follow no template. The release workflow differs too:

- it triggers on `pull_request_target`, a known footgun;
- it accepts release branches from forks;
- it does not check the branch name against the version;
- CI builds and smoke-tests five platforms on every push.

The maintainer wants one release process across both projects, starting with v2.0.0.

## What Changes

- **New `release-ready` skill**, modeled on pikpak-dl-cli and adapted to Poetry/pytest. It lives at `.claude/skills/release-ready/SKILL.md`, with `.agents/skills/release-ready` as a symlink to it. It replaces `.agents/skills/complex-unzip-release`. Its steps:
  1. **Version and branch**: require a clean tree; use the `release/x.y.z` branch, or cut one; the target version must be higher than the last tag and its tag must not exist yet; bump the version in its own `chore: bump version to x.y.z` commit with the existing bump commands.
  2. **Changes**: collect commits since the last tag, the OpenSpec changes archived since then, and unchecked tasks.
  3. **Notes**: write the release notes from the template.
  4. **Docs**: update the README files and docs to match.
  5. **Checks**: run tests, the smoke test, release verification and `openspec validate --specs --strict`.
  6. **PR**: ensure the `release` label exists, push, and open `release: vX.Y.Z` with the notes as its body.
- **Release notes move to `docs/releaseNotes/vX.Y.Z.md`.** They are written in Chinese and English, using pikpak's section template: date, summary, new features, improvements, fixes, downloads, upgrade notes, known issues and pending verification. **BREAKING (maintainers):** existing `ReleaseNotes/RELEASE_NOTES_v*.md` files move there with `git mv`, so their history is kept.
- **`release.yml`** adopts pikpak's gates:
  - it triggers on `pull_request` (closed), not `pull_request_target`;
  - the release branch must be in this repository;
  - a version-like branch suffix (`release/2.0.0` or `release/v2.0.0`) must equal the project version;
  - one global `release` concurrency group, never cancelled.

  The reusable five-platform build, SHA-pinned actions, archives that include the 7-Zip license, the `SHA256SUMS` index and the resumable draft publication all stay.
- **`ci.yml`** splits in two:
  - pushes and PRs run fast checks on Ubuntu and Windows: version and engine verification, `compileall`, `node --check`, `pytest`;
  - the five-platform build, standalone smoke test and packaging run only when the release workflow calls them, or on manual dispatch.
- `AGENTS.md`, both README development sections, and `openspec/project.md` describe the new process:
  - release work is committed on `release/vX.Y.Z`;
  - it merges through exactly one labeled release PR;
  - the `release-ready` skill prepares it.

## Capabilities

### New Capabilities
- `release-ready`: the release preparation procedure. That covers the version and branch rules and their stop conditions, change collection, the notes template and its content rules, doc updates, the required checks, and creation of the labeled release PR.

### Modified Capabilities
- `github-release-ci`: CI scope (fast checks on push/PR, full builds for releases), release trigger and eligibility (`pull_request` from a same-repository `release/*` branch whose version-like suffix matches the project version), and the release-notes path (`docs/releaseNotes/vX.Y.Z.md`).

## Impact

- **Workflows**: `.github/workflows/release.yml`, `.github/workflows/ci.yml`.
- **Scripts**:
  - `scripts/release.py`: notes path, plus a new `verify-branch` command;
  - `scripts/publish_release.cjs`: notes path.
- **Tests**: `tests/test_release.py`, `tests/test_publish_release.py`.
- **Files**:
  - `ReleaseNotes/*` → `docs/releaseNotes/v*.md`;
  - new `.claude/skills/release-ready/SKILL.md` and its `.agents/` symlink;
  - removed `.agents/skills/complex-unzip-release/`.
- **Docs**: `AGENTS.md`, `README.md`, `README.en.md`, `openspec/project.md`. References in the other v2.0.0 changes (`RELEASE_NOTES_v2.0.0.md`, `deepunzip-release`) are updated to `docs/releaseNotes/v2.0.0.md` and `release-ready`.
- **Release**: committed on `release/v2.0.0`, ships with v2.0.0. The trigger switch takes effect with that merge itself, because `pull_request` workflows run from the merge commit.
