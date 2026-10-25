"""Version, native archive packaging, and checksum checks for GitHub releases."""

import argparse
import ast
import configparser
import hashlib
import json
import re
import tarfile
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = {
    "windows-x64": (".exe", "7z/windows-x64", ".zip"),
    "macos-x64": ("", "7z/macos", ".tar.gz"),
    "macos-arm64": ("", "7z/macos", ".tar.gz"),
    "linux-x64": ("", "7z/linux-x64", ".tar.gz"),
    "linux-arm64": ("", "7z/linux-arm64", ".tar.gz"),
}


def read_version(root: Path = ROOT) -> str:
    """Require one stable version across the project's version declarations."""
    version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))[
        "tool"
    ]["poetry"]["version"]
    if not re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", version):
        raise ValueError("Releases require a stable X.Y.Z project version")
    module = ast.parse(
        (root / "deepunzip/__init__.py").read_text(encoding="utf-8")
    )
    package_versions = [
        ast.literal_eval(node.value)
        for node in module.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "__version__" for t in node.targets)
    ]
    config = configparser.ConfigParser()
    config.read(root / ".bumpversion.cfg", encoding="utf-8")
    if (
        package_versions != [version]
        or config["bumpversion"]["current_version"] != version
    ):
        raise ValueError("Project, package, and bumpversion versions must match")
    return str(version)


def verify_branch(ref: str, root: Path = ROOT) -> None:
    """Require a release branch whose version-like suffix matches the project.

    `release/2.0.0` and `release/v2.0.0` must name the project version; a
    suffix that is not a version (`release/rename`) is accepted.
    """
    if not ref.startswith("release/"):
        raise ValueError(f"Release branches must start with release/: {ref}")
    suffix = ref[len("release/") :]
    suffix = suffix[1:] if suffix.startswith("v") else suffix
    version = read_version(root)
    if re.fullmatch(r"\d+\.\d+\.\d+", suffix) and suffix != version:
        raise ValueError(f"Branch {ref} does not match the project version {version}")


def read_release_notes(root: Path = ROOT) -> str:
    """Read the required release notes for the exact project version."""
    path = root / "docs" / "releaseNotes" / f"v{read_version(root)}.md"
    if not path.is_file():
        raise ValueError(f"Release notes not found: {path}")
    notes = path.read_text(encoding="utf-8")
    if not notes.strip():
        raise ValueError(f"Release notes are empty: {path}")
    return notes


def verify_engines(root: Path = ROOT) -> None:
    """Check the bundled official files against their recorded hashes."""
    manifest = json.loads((root / "7z/manifest.json").read_text(encoding="utf-8"))
    for package_info in manifest["packages"]:
        for name, digest in package_info["files"].items():
            if hashlib.sha256((root / "7z" / name).read_bytes()).hexdigest() != digest:
                raise ValueError(f"Bundled 7-Zip checksum mismatch: {name}")


def package(root: Path, target: str, output: Path) -> Path:
    """Archive a tested standalone executable with its redistribution notices."""
    suffix, engine_dir, extension = TARGETS[target]
    version = read_version(root)
    executable = f"complex-unzip-tool-v2{suffix}"
    files = {
        executable: root / "dist" / executable,
        "LICENSE": root / "LICENSE",
        "README.md": root / "README.md",
        "README.en.md": root / "README.en.md",
        "7-Zip-License.txt": root / engine_dir / "License.txt",
        "7-Zip-manifest.json": root / "7z/manifest.json",
    }
    for path in files.values():
        if not path.is_file():
            raise FileNotFoundError(path)
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f"complex-unzip-tool-v2-v{version}-{target}{extension}"
    if extension == ".zip":
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zipped:
            for name, path in files.items():
                zipped.write(path, name)
    else:
        with tarfile.open(archive, "w:gz") as tar:
            for name, path in files.items():
                tar.add(path, arcname=name)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_name(archive.name + ".sha256").write_text(
        f"{digest}  {archive.name}\n", encoding="utf-8"
    )
    return archive


def verify_assets(directory: Path, version: str) -> Path:
    """Reject incomplete or mixed releases before producing the public index."""
    names = [
        f"complex-unzip-tool-v2-v{version}-{target}{values[2]}"
        for target, values in TARGETS.items()
    ]
    expected = set(names) | {name + ".sha256" for name in names}
    actual = {p.name for p in directory.iterdir()} - {"SHA256SUMS"}
    if actual != expected:
        raise ValueError("Release must contain exactly five archives and their hashes")
    lines = []
    for name in sorted(names):
        digest = hashlib.sha256((directory / name).read_bytes()).hexdigest()
        line = f"{digest}  {name}\n"
        if (directory / (name + ".sha256")).read_text(encoding="utf-8") != line:
            raise ValueError(f"Release checksum mismatch: {name}")
        lines.append(line)
    index = directory / "SHA256SUMS"
    index.write_text("".join(lines), encoding="utf-8")
    return index


def main() -> None:
    """Run release helpers without network access."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("version")
    commands.add_parser("verify-notes")
    commands.add_parser("verify-engines")
    branch = commands.add_parser("verify-branch")
    branch.add_argument("ref")
    pack = commands.add_parser("package")
    pack.add_argument("target", choices=TARGETS)
    pack.add_argument("--output", type=Path, default=ROOT / "artifacts")
    verify = commands.add_parser("verify-assets")
    verify.add_argument("directory", type=Path)
    args = parser.parse_args()
    if args.command == "version":
        print(read_version())
    elif args.command == "verify-notes":
        read_release_notes()
    elif args.command == "verify-engines":
        verify_engines()
    elif args.command == "verify-branch":
        verify_branch(args.ref)
    elif args.command == "package":
        print(package(ROOT, args.target, args.output))
    else:
        print(verify_assets(args.directory, read_version()))


if __name__ == "__main__":
    main()
