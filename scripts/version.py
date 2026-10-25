"""Version bumping utilities using bump2version."""

import subprocess
import sys

from deepunzip.modules.render import configure_redirected_output


def run_bump2version(part: str, allow_dirty: bool = True) -> None:
    """Run bump2version command with specified part.

    Args:
        part: Version part to bump (patch, minor, major)
        allow_dirty: Allow running with uncommitted changes
    """
    configure_redirected_output()  # ✓/✗ must survive a GBK pipe on Windows
    cmd = ["bump2version"]
    if allow_dirty:
        cmd.append("--allow-dirty")
    cmd.append(part)

    try:
        subprocess.run(cmd, check=True)
        print(f"✓ Successfully bumped {part} version")
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to bump version: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(
            "✗ bump2version not found. Install with: poetry add bump2version",
            file=sys.stderr,
        )
        sys.exit(1)


def bump_version() -> None:
    """Interactive version bump - prompts for version part."""
    print("Select version part to bump:")
    print("1. patch (x.x.X)")
    print("2. minor (x.X.0)")
    print("3. major (X.0.0)")

    choice = input("Enter choice (1-3): ").strip()

    parts = {"1": "patch", "2": "minor", "3": "major"}
    part = parts.get(choice)

    if not part:
        print("Invalid choice", file=sys.stderr)
        sys.exit(1)

    run_bump2version(part)


def bump_patch() -> None:
    """Bump patch version (x.x.X)."""
    run_bump2version("patch")


def bump_minor() -> None:
    """Bump minor version (x.X.0)."""
    run_bump2version("minor")


def bump_major() -> None:
    """Bump major version (X.0.0)."""
    run_bump2version("major")


if __name__ == "__main__":
    bump_version()
