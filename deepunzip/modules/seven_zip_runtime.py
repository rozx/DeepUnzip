"""Native bundled 7-Zip selection shared by archive operations and packaging."""

import os
import platform
import sys
from pathlib import Path
from typing import Optional

from deepunzip.classes.ArchiveTypes import SevenZipNotFoundError


def bundled_engine_path(root: Optional[Path] = None) -> Path:
    """Locate the host engine in a source checkout or PyInstaller bundle."""
    if root is None:
        root = (
            Path(getattr(sys, "_MEIPASS"))
            if getattr(sys, "frozen", False)
            else Path(__file__).resolve().parents[2]
        )
    system = platform.system()
    machine = platform.machine().lower()
    architecture = {
        "amd64": "x64",
        "x86_64": "x64",
        "arm64": "arm64",
        "aarch64": "arm64",
    }.get(machine)
    if system == "Windows" and architecture == "x64":
        return root / "7z" / "windows-x64" / "7z.exe"
    if system == "Darwin" and architecture in {"x64", "arm64"}:
        return root / "7z" / "macos" / "7zz"
    if system == "Linux" and architecture in {"x64", "arm64"}:
        return root / "7z" / f"linux-{architecture}" / "7zzs"
    raise SevenZipNotFoundError(
        f"Unsupported 7-Zip platform: {system}/{machine}. "
        "Supported: Windows x64, macOS x64/arm64, Linux x64/arm64."
    )


def validate_engine(path: Path, *, bundled: bool = False) -> str:
    """Validate an engine before invoking it, without changing permissions."""
    if not path.is_file():
        raise SevenZipNotFoundError(f"7-Zip executable not found at: {path}")
    if platform.system() != "Windows" and not os.access(path, os.X_OK):
        raise SevenZipNotFoundError(
            f"7-Zip executable lacks execute permission: {path}. "
            "Restore its executable permission (chmod +x)."
        )
    if bundled and platform.system() == "Windows":
        dll = path.with_suffix(".dll")
        if not dll.is_file():
            raise SevenZipNotFoundError(f"Required 7-Zip library not found at: {dll}")
    return str(path)


def resolve_seven_zip_path(seven_zip_path: Optional[str] = None) -> str:
    """Return an explicit engine file or the validated native bundled engine."""
    if seven_zip_path:
        return validate_engine(Path(seven_zip_path))
    return validate_engine(bundled_engine_path(), bundled=True)
