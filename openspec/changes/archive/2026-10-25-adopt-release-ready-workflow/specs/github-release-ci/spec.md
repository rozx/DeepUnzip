## MODIFIED Requirements

### Requirement: Five native build targets
CI SHALL run fast checks on every push and pull request to `main` or `release/**`, on Ubuntu and Windows. The fast checks are version and engine verification, compilation, the publisher syntax check, and the full unit test suite.

The release workflow SHALL test and build Windows x64, macOS x64/ARM64 and Linux x64/ARM64 on native hosted runners. A maintainer SHALL be able to request the same full build manually. Each full build SHALL verify the bundled engines, the existing test suite, and real source/standalone archive extraction before uploading an artifact.

#### Scenario: Ordinary push
- **WHEN** a commit is pushed to `release/v2.0.0`
- **THEN** CI SHALL run the fast checks on Ubuntu and Windows
- **AND** it SHALL NOT build or package the five standalone targets

#### Scenario: A platform fails
- **WHEN** any platform's tests, build, or smoke check fails during a release build
- **THEN** the run SHALL fail and SHALL NOT publish a release

#### Scenario: A newer commit supersedes ordinary CI
- **WHEN** another push or PR update starts checks for the same event and ref
- **THEN** the older ordinary CI run SHALL be cancelled
- **AND** reusable release builds SHALL remain isolated from ordinary CI cancellation and publish only artifacts from their own workflow run

### Requirement: Release trigger is an eligible merged PR
Publication SHALL occur only after a pull request whose source branch is `release/*` *in this repository* merges into `main` with the `release` label present at merge time. The workflow SHALL be triggered by the `pull_request` closed event, not `pull_request_target`. When the branch suffix after `release/`, with an optional leading `v` removed, has the form `X.Y.Z`, it SHALL equal the project version. Every release build and tag SHALL correspond to that PR's merge commit. Release runs SHALL be serialized in a single concurrency group and never cancelled.

#### Scenario: Eligible merge
- **WHEN** a labeled `release/v2.0.0` PR from this repository merges into `main` with project version `2.0.0`
- **THEN** the release pipeline SHALL build all five targets from that merge commit

#### Scenario: Branch version differs from the project version
- **WHEN** a labeled `release/v2.0.1` PR merges while the project version is `2.0.0`
- **THEN** the release workflow SHALL fail before any platform build

#### Scenario: Non-version branch suffix
- **WHEN** a labeled `release/rename` PR merges
- **THEN** the branch suffix SHALL NOT be compared with the project version

#### Scenario: Non-release event
- **WHEN** a PR is closed without merging, lacks the label, uses another source branch, comes from a fork, or targets another base branch
- **THEN** no release SHALL be published

### Requirement: Version-specific repository release notes
The release body SHALL use the exact Markdown contents of `docs/releaseNotes/vX.Y.Z.md` from the same merge commit being built. Missing or empty notes SHALL fail before platform builds begin. GitHub-generated notes and files for other versions SHALL NOT be used as fallbacks.

#### Scenario: Matching release notes exist
- **WHEN** the project version is `2.0.0` and `docs/releaseNotes/v2.0.0.md` is nonempty
- **THEN** a new release or resumed draft SHALL publish that file's contents as its body

#### Scenario: Release notes are missing or empty
- **WHEN** the exact version's release notes file is missing or contains only whitespace
- **THEN** the release workflow SHALL fail during prepare without building or creating a release
