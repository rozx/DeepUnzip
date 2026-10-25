# contained-zip-rar-autogrouping Specification

## Purpose
Register multi-volume sets (spanned ZIP, RAR, ZIPX, ARJ, ACE and generic numbered splits) that appear after extracting a container as multipart groups, so they are extracted in the same run.
## Requirements
### Requirement: Auto-group spanned ZIP sets discovered from containers

When a spanned ZIP set is present in the work pool, whichever containers or directories its parts came from, the tool MUST treat it as a multipart set for assembly in the same run. Because `.zip` is ambiguous, the tool MUST NOT treat a `.zip` as a multipart primary unless at least one `.zNN` continuation part with the same base name is present in the pool. A `.zip` that already failed as a single container MUST become the set's primary when such a continuation enters the pool later.

#### Scenario: Create a multipart group when both `.zip` and `.z01` exist
- **WHEN** the pool contains `X.zip` and at least one `X.zNN` continuation part (e.g., `X.z01`), possibly from different containers
- **THEN** a multipart set MUST be formed for key `X|zip` with `X.zip` as its primary
- **AND** assembly MUST consider the discovered `.zNN` parts

#### Scenario: Continuation appears after the `.zip` failed as a container
- **WHEN** `X.zip` failed to open as a single container and became unresolved
- **AND** a later container yields `X.z01`
- **THEN** `X.zip` MUST become the primary of set `X|zip` and be assembled with `X.z01`

#### Scenario: Do not create a multipart group for a standalone `.zip`
- **WHEN** the pool contains `X.zip` but no `X.zNN` continuation part
- **THEN** `X.zip` MUST be treated as a single container, not as a multipart primary

### Requirement: Auto-group RAR volume sets discovered from containers

When a RAR volume set is present in the work pool, whichever containers or directories its parts came from, the tool MUST treat it as a multipart set for assembly in the same run. Because `.rar` is ambiguous, the tool MUST NOT treat a `.rar` as a multipart primary unless at least one `.rNN` continuation part with the same base name is present in the pool, or opening it failed for a missing volume.

#### Scenario: Create a multipart group when both `.rar` and `.r00` exist
- **WHEN** the pool contains `X.rar` and at least one `X.rNN` continuation part (e.g., `X.r00`), possibly from different containers
- **THEN** a multipart set MUST be formed for key `X|rar` with `X.rar` as its primary
- **AND** assembly MUST consider the discovered `.rNN` parts

#### Scenario: Do not create a multipart group for a standalone `.rar`
- **WHEN** the pool contains `X.rar` but no `X.rNN` continuation part
- **AND** `X.rar` opens without a missing-volume error
- **THEN** `X.rar` MUST be treated as a single container, not as a multipart primary

### Requirement: Auto-group generic numbered volume sets discovered from containers

The tool MUST treat a generic 7-Zip numbered volume set present in the work pool as a multipart set for assembly in the same run. A `name.{ext}.001` part is an unambiguous primary, so the set MAY be formed from the `.001` alone, with no continuation required, and with the `.001` as its primary.

#### Scenario: Create a multipart group from a contained split ZIP volume set
- **WHEN** the pool contains `X.zip.001` and any `X.zip.002`, …, possibly from different containers
- **THEN** a multipart set MUST be formed for key `X|zip` (numbered) with `X.zip.001` as its primary

#### Scenario: Create a multipart group from a contained split set of arbitrary extension
- **WHEN** the pool contains `X.iso.001` and `X.iso.002`
- **THEN** a multipart set MUST be formed for base `X` with `X.iso.001` as its primary

### Requirement: Auto-group ZIPX, ARJ, and ACE sets discovered from containers

The tool MUST treat a ZIPX, ARJ or ACE multi-volume set present in the work pool as a multipart set. Because the `.zipx`, `.arj` and `.ace` primaries are ambiguous (they can also be standalone single archives), the tool MUST NOT treat one of them as a multipart primary unless at least one of its continuation parts (`.zxNN`, `.aNN`, `.cNN` respectively) with the same base name is present in the pool.

#### Scenario: Create a multipart group when both .zipx and .zx01 exist
- **WHEN** the pool contains `X.zipx` and at least one `X.zxNN` continuation part
- **THEN** a multipart set MUST be formed for base `X` with `X.zipx` as its primary

#### Scenario: Create a multipart group when both .arj and .a01 exist
- **WHEN** the pool contains `X.arj` and at least one `X.aNN` continuation part
- **THEN** a multipart set MUST be formed for base `X` with `X.arj` as its primary

#### Scenario: Do not auto-group a standalone .arj
- **WHEN** the pool contains `X.arj` but no `X.aNN` continuation part
- **THEN** `X.arj` MUST be treated as a single container

#### Scenario: Create a multipart group when both .ace and .c00 exist
- **WHEN** the pool contains `X.ace` and at least one `X.cNN` continuation part
- **THEN** a multipart set MUST be formed for base `X` with `X.ace` as its primary

