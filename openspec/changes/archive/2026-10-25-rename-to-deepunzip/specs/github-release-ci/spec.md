## MODIFIED Requirements

### Requirement: Consistent version and complete downloadable assets
The release SHALL use `vX.Y.Z` from the consistent project version declarations, include five platform archives and a checksum index, preserve Unix execute permissions, and include redistribution notices. Missing assets, inconsistent versions, or checksum mismatches SHALL block publication. Platform archives SHALL be named `deepunzip-vX.Y.Z-<target>.<ext>`, where:

- `<target>` is one of `windows-x64`, `macos-x64`, `macos-arm64`, `linux-x64`, `linux-arm64`;
- `<ext>` is `.zip` for Windows and `.tar.gz` otherwise.

Each archive SHALL contain the `deepunzip` executable.

#### Scenario: All builds succeed
- **WHEN** all five verified platform archives are available for one version
- **THEN** the release SHALL publish them together with release notes and `SHA256SUMS`

#### Scenario: Asset names for 2.0.0
- **WHEN** version 2.0.0 is released
- **THEN** the Windows asset SHALL be `deepunzip-v2.0.0-windows-x64.zip` containing `deepunzip.exe`
- **AND** the Linux ARM64 asset SHALL be `deepunzip-v2.0.0-linux-arm64.tar.gz` containing `deepunzip`
