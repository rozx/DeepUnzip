#!/usr/bin/env python3
"""
Build script for creating standalone executable of Complex Unzip Tool v2
"""

import platform
import shutil
import subprocess
import sys
from pathlib import Path

from complex_unzip_tool_v2.modules.seven_zip_runtime import (
    SevenZipNotFoundError,
    bundled_engine_path,
    validate_engine,
)


def generate_spec_content(project_root: Path, scripts_dir: Path) -> str:
    """Generate the PyInstaller spec file content dynamically."""

    # Define paths
    main_script = scripts_dir / "standalone_main.py"

    # Define data files to include
    data_files = []

    # Include only the native engine; PyInstaller preserves executable mode.
    engine = bundled_engine_path(project_root)
    validate_engine(engine, bundled=True)
    destination = engine.parent.relative_to(project_root).as_posix()
    binaries = [(str(engine), destination)]
    if platform.system() == "Windows":
        binaries.append((str(engine.with_suffix(".dll")), destination))
    license_file = engine.parent / "License.txt"
    if not license_file.is_file():
        raise SevenZipNotFoundError(f"7-Zip license not found at: {license_file}")
    data_files.append(f"    ({str(license_file)!r}, {destination!r}),")

    # Add config files
    config_dir = project_root / "complex_unzip_tool_v2" / "config"
    cloaked_rules_file = config_dir / "cloaked_file_rules.json"
    if cloaked_rules_file.exists():
        data_files.append(
            f'    (r"{cloaked_rules_file}", "complex_unzip_tool_v2/config"),'
        )

    data_files_str = "\n".join(data_files)

    # Check for icon file
    icon_path = project_root / "icons" / "app_icon.ico"
    icon_line = (
        repr(str(icon_path))
        if platform.system() == "Windows" and icon_path.exists()
        else "None"
    )

    spec_content = f"""# -*- mode: python ; coding: utf-8 -*-
# This file is generated automatically by the build script

import os

# Project paths
project_root = r"{project_root}"
scripts_dir = r"{scripts_dir}"
main_script = r"{main_script}"

# Data files to include
datas = [
{data_files_str}
]

a = Analysis(
    [main_script],
    pathex=[project_root],
    binaries={binaries!r},
    datas=datas,
    hiddenimports=[
        'complex_unzip_tool_v2',
        'complex_unzip_tool_v2.main',
        'complex_unzip_tool_v2.modules.archive_utils',
        'complex_unzip_tool_v2.modules.file_utils',
        'complex_unzip_tool_v2.modules.password_util',
        'complex_unzip_tool_v2.modules.events',
        'complex_unzip_tool_v2.modules.i18n',
        'complex_unzip_tool_v2.modules.render',
        'complex_unzip_tool_v2.modules.seven_zip_progress',
        'complex_unzip_tool_v2.modules.work_pool',
        'complex_unzip_tool_v2.modules.pool_engine',
        'complex_unzip_tool_v2.modules.const',
        'complex_unzip_tool_v2.modules.utils',
        'complex_unzip_tool_v2.modules.regex',
        'complex_unzip_tool_v2.modules.archive_extension_utils',
        'complex_unzip_tool_v2.modules.cloaked_file_detector',
        'complex_unzip_tool_v2.classes.ArchiveGroup',
        'complex_unzip_tool_v2.classes.PasswordBook',
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [('X utf8', None, 'OPTION')],  # Preserve Chinese output in redirected CI logs.
    name='complex-unzip-tool-v2',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon={icon_line},
)
"""
    return spec_content


def main() -> int:
    # Get project root directory (parent of scripts directory)
    project_root = Path(__file__).parent.parent.absolute()
    scripts_dir = Path(__file__).parent.absolute()

    # Validate native assets before removing any previous build output.
    try:
        spec_content = generate_spec_content(project_root, scripts_dir)
    except SevenZipNotFoundError as exc:
        print(f"❌ Error: {exc}")
        return 1

    # Clean previous builds
    build_dir = project_root / "build"
    dist_dir = project_root / "dist"

    print("🧹 Cleaning previous builds...")
    if build_dir.exists():
        shutil.rmtree(build_dir)
    if dist_dir.exists():
        shutil.rmtree(dist_dir)

    # Generate spec file dynamically
    print("📝 Generating PyInstaller spec file...")
    spec_file = scripts_dir / "build_standalone_generated.spec"

    with open(spec_file, "w", encoding="utf-8") as f:
        f.write(spec_content)

    print(f"✅ Spec file generated: {spec_file}")

    # Run PyInstaller
    print("🔨 Building standalone executable...")
    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "PyInstaller",
                "--clean",
                "--noconfirm",
                str(spec_file),
            ],
            cwd=project_root,
            check=True,
        )

        print("✅ Build completed successfully!")

        # Check if executable was created
        suffix = ".exe" if platform.system() == "Windows" else ""
        exe_path = dist_dir / f"complex-unzip-tool-v2{suffix}"
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"📦 Executable created: {exe_path}")
            print(f"📏 Size: {size_mb:.1f} MB")
            print("🎯 You can now distribute this single file!")
        else:
            print("❌ Error: Executable not found in dist folder")
            return 1

    except subprocess.CalledProcessError as e:
        print(f"❌ Build failed with error code {e.returncode}")
        return 1

    finally:
        # Clean up generated spec file
        if spec_file.exists():
            print("🧹 Cleaning up generated spec file...")
            spec_file.unlink()

    return 0


if __name__ == "__main__":
    sys.exit(main())
