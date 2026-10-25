## ADDED Requirements

### Requirement: Release preparation through one skill
The repository SHALL provide a `release-ready` skill at `.claude/skills/release-ready/SKILL.md`, with `.agents/skills/release-ready` as a symlink to it. The skill SHALL be the single documented way to prepare a release.

The skill SHALL turn the work on a `release/X.Y.Z` (or `release/vX.Y.Z`) branch into exactly one pull request into `main` that carries the `release` label. All release work SHALL be committed on that branch.

#### Scenario: Preparing a release
- **WHEN** the maintainer runs the skill on `release/v2.0.0` with a clean working tree
- **THEN** the skill SHALL end by pushing the branch and opening one PR `release: v2.0.0` into `main` with the `release` label

### Requirement: Version and branch rules
The skill SHALL require a clean working tree. Its target version is:

- **on a release branch**: the version in the branch name;
- **otherwise**: the version inferred from the commits since the last `v*` tag, using semver (`BREAKING` / `!` → major, `feat` → minor, otherwise patch), after which the skill SHALL cut `release/X.Y.Z`.

The target version SHALL be a stable `X.Y.Z`, higher than the last tag, and its tag SHALL NOT exist on `origin`. When the project version differs from the target, the skill SHALL bump all three version declarations with the project's bump commands, in a single `chore: bump version to X.Y.Z` commit.

The skill SHALL stop and ask the maintainer when:

- the tree is dirty;
- the branch name is not a release-version name;
- the branch version is lower than the project version, or not higher than the last tag;
- the tag already exists.

#### Scenario: Version needs a bump
- **WHEN** the branch is `release/v2.0.0` and the project version is `1.3.2`
- **THEN** the skill SHALL commit `chore: bump version to 2.0.0`, with `pyproject.toml`, `__init__.py` and `.bumpversion.cfg` all reading `2.0.0`

#### Scenario: Tag already published
- **WHEN** `v2.0.0` already exists on `origin`
- **THEN** the skill SHALL stop without committing or pushing

### Requirement: Release notes from the template
The skill SHALL write `docs/releaseNotes/vX.Y.Z.md` from:

- the commits since the last tag;
- the OpenSpec changes archived since then (their proposals, and their unchecked tasks);
- the OpenSpec changes still open.

The notes SHALL be bilingual (Chinese, then English, per section) and SHALL use these sections, dropping any that are empty:

1. title
2. date
3. summary
4. new features
5. improvements
6. fixes
7. downloads
8. upgrade notes
9. known issues and pending verification

The download table SHALL match the release targets in `scripts/release.py`. The notes SHALL describe user-visible behavior. They SHALL NOT list commit hashes or internal refactors, and they SHALL NOT contain passwords, tokens, share links or real user file names.

#### Scenario: Unchecked OpenSpec task
- **WHEN** an archived change of this release still has an unchecked task
- **THEN** the notes SHALL list it under known issues and pending verification

### Requirement: Documentation and checks before the PR
Before opening the PR, the skill SHALL:

- bring every README language file, `AGENTS.md`, `CLAUDE.md` and `docs/*.md` in line with the release (`openspec/specs/`, the OpenSpec archive and older release notes excluded);
- run the test suite, the source smoke test, release version, notes, engine and branch verification, the CLI `--help`, and `openspec validate --specs --strict`;
- commit the notes as `docs: add release notes for vX.Y.Z` and the doc updates as `docs: update docs for vX.Y.Z`.

A failing check SHALL stop the skill, and it SHALL NOT open the PR.

#### Scenario: Failing test
- **WHEN** `pytest` reports a failure during release preparation
- **THEN** the skill SHALL stop without pushing or opening the PR

### Requirement: Labeled release PR
The skill SHALL ensure the repository has a `release` label, creating it if missing. It SHALL push the release branch and open the PR with:

- base `main`;
- title `release: vX.Y.Z`;
- the `release` label;
- a body containing the release notes plus the session's attribution, written from a temporary file that is not committed.

The skill SHALL report the PR link and state that merging triggers the release workflow.

#### Scenario: Label missing
- **WHEN** the repository has no `release` label
- **THEN** the skill SHALL create it before opening the PR
