import subprocess
import os
import shutil
import tempfile
from typing import List, Dict, Optional, Tuple
import re
from complex_unzip_tool_v2.modules.rich_utils import (
    print_warning,
    print_info,
    print_success,
)

# Re-exported: SevenZipEngine.classify calls archive_utils.detect_archive_extension,
# so tests can replace every 7-Zip-facing helper on this one module.
from complex_unzip_tool_v2.modules.archive_extension_utils import (  # noqa: F401
    detect_archive_extension,
)
from complex_unzip_tool_v2.modules.utils import sanitize_path, sanitize_filename
from complex_unzip_tool_v2.modules.const import PATH_ERROR_KEYWORDS
from complex_unzip_tool_v2.modules.seven_zip_runtime import (
    bundled_engine_path,
    resolve_seven_zip_path,
)

from complex_unzip_tool_v2.classes.ArchiveTypes import (
    ArchiveError,
    ArchiveNotFoundError,
    SevenZipNotFoundError,
    ArchivePasswordError,
    ArchiveCorruptedError,
    ArchiveMissingVolumeError,
    ArchiveUnsupportedError,
    ArchiveParsingError,
    ArchiveFileInfo,
)

# ------------------------------
# 7-Zip helpers
# ------------------------------


def _resolve_seven_zip_path(seven_zip_path: Optional[str]) -> str:
    """Return a validated native 7-Zip executable path."""
    return resolve_seven_zip_path(seven_zip_path)


def _ensure_archive_exists(archive_path: str) -> None:
    """Raise if the given archive path does not exist."""
    if not os.path.exists(archive_path):
        raise ArchiveNotFoundError(f"Archive not found: {archive_path}")


def _build_password_arg(password: Optional[str]) -> str:
    """Always return a valid -p argument; empty string means no password."""
    return f"-p{password or ''}"


def _build_7z_extract_cmd(
    seven_zip_path: str,
    password: Optional[str],
    output_path: str,
    archive_path: str,
    overwrite: bool = True,
    specific_files: Optional[List[str]] = None,
) -> List[str]:
    """Build a standardized 7z extract command with consistent argument order."""
    cmd = [seven_zip_path, "x", _build_password_arg(password), f"-o{output_path}"]

    if overwrite:
        cmd.append("-y")
    else:
        cmd.append("-aos")

    cmd.append(archive_path)

    if specific_files:
        cmd.extend(specific_files)

    return cmd


def _run_7z_cmd(cmd: List[str]) -> Tuple[str, str, int]:
    """Run a 7z command returning decoded stdout, stderr and return code."""
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=False,
        check=False,
    )
    stdout, stderr = _decode_subprocess_output(result.stdout, result.stderr)
    return stdout, stderr, result.returncode


def _raise_for_7z_error(
    returncode: int, stderr: str, archive_path: str, stdout: str = ""
) -> None:
    """Map 7z return/err output to specific exceptions or no-op if success.

    Note: 7-Zip sometimes prints important diagnostics (including password failures)
    to stdout instead of stderr. We therefore consider both streams.
    """
    if returncode == 0:
        return
    combined = f"{stderr or ''}\n{stdout or ''}".lower()
    # A missing volume also triggers "cannot open" and "CRC failed" lines, so it
    # is checked first; the set may still be completed by volumes found later.
    if "missing volume" in combined or "unexpected end of archive" in combined:
        raise ArchiveMissingVolumeError(f"Archive is missing a volume: {archive_path}")
    # Treat "not an archive" style errors as unsupported/non-archive, not corruption
    if (
        "can not open file as archive" in combined
        or "cannot open file as archive" in combined
        or "is not archive" in combined
    ):
        raise ArchiveUnsupportedError(
            f"Not a supported archive type (likely not an archive): {archive_path}"
        )
    if (
        "wrong password" in combined
        or "cannot open encrypted archive" in combined
        or "password is incorrect" in combined
    ):
        raise ArchivePasswordError(
            f"Incorrect password or password required for: {archive_path}"
        )
    if "data error" in combined or "crc failed" in combined:
        raise ArchiveCorruptedError(f"Archive appears to be corrupted: {archive_path}")
    if "unsupported method" in combined or "unknown method" in combined:
        raise ArchiveUnsupportedError(f"Archive format not supported: {archive_path}")
    if "cannot open file" in combined:
        raise ArchiveNotFoundError(f"Cannot open archive file: {archive_path}")
    if "disk full" in combined or "not enough space" in combined:
        raise ArchiveError(f"Insufficient disk space for extraction: {archive_path}")
    # Generic fallback
    raise ArchiveError(
        f"7z command failed ({returncode}): {(stderr or '').strip() or (stdout or '').strip()}"
    )


# 7-Zip format names (as printed by `7z i`) that are real containers worth
# extracting. 7-Zip can also open many non-archives (PE, ELF, MachO, Compound,
# FLV, Hash, Nsis, …); exploding those destroys the file (issue #21).
_CONTAINER_ARCHIVE_TYPES = frozenset(
    {
        "7z",
        "rar",
        "rar5",
        "zip",
        "gzip",
        "bzip2",
        "xz",
        "zstd",
        "lzma",
        "lzma86",
        "z",
        "tar",
        "cab",
        "arj",
        "lzh",
        "cpio",
        "wim",
        "iso",
        "udf",
        "split",
    }
)

# Document and package formats that are zip files underneath. 7-Zip reports
# them as ``Type = zip``; extracting them would explode e.g. a .docx into its
# XML parts, so such a file is kept. The name alone is not trusted: each format
# must also contain its required root entry, so a plain zip renamed to .docx or
# .apk (a cloaked archive) is still extracted. Markers are lowercase root
# names; ``*suffix`` matches a root name ending in that suffix and ``**suffix``
# matches any entry, at any depth, ending in that suffix.
# Comic archives (.cbz) are intentionally absent: users want their images.
_OPC = ("[content_types].xml",)  # Office Open XML, XPS, 3MF, APPX/MSIX, NuGet
_ODF = ("mimetype",)
_ZIP_DOCUMENT_MARKERS: Dict[str, Tuple[str, ...]] = {
    **dict.fromkeys(
        (
            ".docx",
            ".docm",
            ".dotx",
            ".dotm",
            ".xlsx",
            ".xlsm",
            ".xlsb",
            ".xltx",
            ".xltm",
            ".xlam",
            ".pptx",
            ".pptm",
            ".potx",
            ".potm",
            ".ppsx",
            ".ppsm",
            ".ppam",
            ".sldx",
            ".sldm",
            ".vsdx",
            ".vsdm",
            ".vssx",
            ".vssm",
            ".vstx",
            ".vstm",
            ".thmx",
            ".xps",
            ".oxps",
            ".3mf",
            ".appx",
            ".appxbundle",
            ".msix",
            ".msixbundle",
            ".vsix",
            ".nupkg",
        ),
        _OPC,
    ),
    **dict.fromkeys(
        (
            ".odt",
            ".ods",
            ".odp",
            ".odg",
            ".odf",
            ".odb",
            ".odm",
            ".ott",
            ".ots",
            ".otp",
            ".otg",
        ),
        _ODF,
    ),
    ".epub": ("mimetype", "meta-inf"),
    # Apple iWork (Pages, Numbers, Keynote); index.xml is the pre-2013 layout
    **dict.fromkeys(
        (".pages", ".numbers", ".key"), ("index", "index.zip", "index.xml")
    ),
    ".kmz": ("*.kml",),
    # `jar --no-manifest` JARs have no META-INF, only compiled classes
    **dict.fromkeys((".jar", ".war", ".ear"), ("meta-inf", "web-inf", "**.class")),
    **dict.fromkeys((".apk", ".aar"), ("androidmanifest.xml",)),
    ".aab": ("bundleconfig.pb",),
    ".xapk": ("manifest.json",),
    ".apks": ("toc.pb",),
    ".ipa": ("payload",),
    **dict.fromkeys((".xpi", ".crx"), ("manifest.json", "install.rdf")),
    ".oxt": ("meta-inf",),  # LibreOffice extension
    ".whl": ("*.dist-info",),
}
_ZIP_DOCUMENT_EXTENSIONS = frozenset(_ZIP_DOCUMENT_MARKERS)


def _has_zip_document_extension(file_path: str) -> bool:
    """Return True if the name ends with a zip-based document/package extension."""
    return os.path.splitext(file_path)[1].lower() in _ZIP_DOCUMENT_EXTENSIONS


def _is_zip_document(file_path: str, content: List[ArchiveFileInfo]) -> bool:
    """Return True if a zip named like a document/package has that format's
    required root entry (e.g. ``[Content_Types].xml`` for .docx)."""
    markers = _ZIP_DOCUMENT_MARKERS.get(os.path.splitext(file_path)[1].lower())
    if not markers:
        return False
    names = [
        entry.get("name", "").replace("\\", "/").lstrip("/").lower()
        for entry in content
    ]
    roots = {name.split("/", 1)[0] for name in names}
    for marker in markers:
        if marker.startswith("**"):
            if any(name.endswith(marker[2:]) for name in names):
                return True
        elif marker.startswith("*"):
            if any(root.endswith(marker[1:]) for root in roots):
                return True
        elif marker in roots:
            return True
    return False


def _is_intact_zip_document(
    file_path: str,
    password: Optional[str] = "",
    seven_zip_path: Optional[str] = None,
) -> bool:
    """Return True only if 7-Zip lists the file as a zip carrying its format's
    required entry; a damaged or disguised file named like a document is not."""
    try:
        archive_type, content, _volumes = _list_archive_with7z(
            archive_path=file_path,
            password=password,
            seven_zip_path=seven_zip_path,
        )
    except Exception:
        return False
    return (
        archive_type is not None
        and archive_type.lower() == "zip"
        and _is_zip_document(file_path, content)
    )


def is_valid_archive(
    file_path: str,
    password: Optional[str] = "",
    seven_zip_path: Optional[str] = None,
) -> bool:
    """Check quickly if a file is a container archive that 7z can extract.

    Returns True for valid (including password-protected) archives whose
    archive-level 7-Zip type is a real container (self-extracting archives
    report their embedded container type, e.g. ``7z``).
    Returns False for non-archive/unreadable files and for formats 7-Zip can
    merely open, such as plain executables (``Type = PE``), and for zip-based
    documents/packages (``Type = zip`` named e.g. ``.docx`` or ``.jar`` that
    also contain that format's required entry).
    """
    try:
        archive_type, content, split_volumes = _list_archive_with7z(
            archive_path=file_path,
            password=password,
            seven_zip_path=seven_zip_path,
        )
        if archive_type is not None and (
            archive_type.lower() not in _CONTAINER_ARCHIVE_TYPES
        ):
            return False
        # A bare Split with one volume is a lone numbered file (report.001)
        # with nothing to join; real splits of raw files have 2+ volumes.
        if archive_type is not None and archive_type.lower() == "split":
            if split_volumes is not None and split_volumes < 2:
                return False
        if (
            archive_type is not None
            and archive_type.lower() == "zip"
            and _is_zip_document(file_path, content)
        ):
            return False
        return bool(content)
    except ArchivePasswordError:
        return True
    except (
        ArchiveError,
        ArchiveCorruptedError,
        ArchiveUnsupportedError,
        ArchiveParsingError,
    ):
        return False
    except Exception:
        return False


def _get_default_7z_path() -> str:
    """Return the native engine path for source and standalone execution."""
    return str(bundled_engine_path())


def _decode_subprocess_output(
    stdout_bytes: bytes, stderr_bytes: bytes
) -> Tuple[str, str]:
    """
    Safely decode subprocess output with multiple encoding fallbacks.

    Args:
        stdout_bytes (bytes): Raw stdout bytes from subprocess
        stderr_bytes (bytes): Raw stderr bytes from subprocess

    Returns:
        tuple[str, str]: Decoded stdout and stderr strings
    """
    stdout = ""
    stderr = ""

    # Try UTF-8 first
    try:
        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")
        return stdout, stderr
    except (UnicodeDecodeError, AttributeError):
        pass

    # Fallback to gbk
    try:
        stdout = stdout_bytes.decode("gbk", errors="replace")
        stderr = stderr_bytes.decode("gbk", errors="replace")
        return stdout, stderr
    except Exception:
        pass

    # Fallback to gb2312
    try:
        stdout = stdout_bytes.decode("gb2312", errors="replace")
        stderr = stderr_bytes.decode("gb2312", errors="replace")
        return stdout, stderr
    except Exception:
        pass

    # Fallback to cp1252 (Windows-1252)
    try:
        stdout = stdout_bytes.decode("cp1252", errors="replace")
        stderr = stderr_bytes.decode("cp1252", errors="replace")
        return stdout, stderr
    except Exception:
        pass

    # Final fallback - convert bytes to string representation
    try:
        stdout = str(stdout_bytes, errors="replace")
        stderr = str(stderr_bytes, errors="replace")
    except Exception:
        stdout = str(stdout_bytes)
        stderr = str(stderr_bytes)

    return stdout, stderr


def readArchiveContentWith7z(
    archive_path: str,
    password: Optional[str] = "",
    seven_zip_path: Optional[str] = None,
) -> List[ArchiveFileInfo]:
    """
    Read archive content using 7z.exe with optional password support.

    Args:
        archive_path (str): Path to the archive file
        password (str, optional): Password for encrypted archives
        seven_zip_path (str): Path to 7z.exe executable (default: auto-detect from program path)

    Returns:
        List[Dict]: List of file information dictionaries containing:
            - name: file/folder name
            - size: uncompressed size in bytes
            - packed_size: compressed size in bytes
            - type: file type (File/Folder)
            - modified: modification date

    Raises:
        ArchiveNotFoundError: If archive file not found
        SevenZipNotFoundError: If 7z executable not found
        ArchivePasswordError: If password is incorrect or required
        ArchiveCorruptedError: If archive is corrupted
        ArchiveUnsupportedError: If archive format is not supported
        ArchiveParsingError: If unable to parse 7z output
    """
    _archive_type, files_info, _volumes = _list_archive_with7z(
        archive_path, password=password, seven_zip_path=seven_zip_path
    )
    return files_info


def _list_archive_with7z(
    archive_path: str,
    password: Optional[str] = "",
    seven_zip_path: Optional[str] = None,
) -> Tuple[Optional[str], List[ArchiveFileInfo], Optional[int]]:
    """Run `7z l -slt` once and return (archive-level type, file entries,
    split volume count from the header, if any).

    Raises the same exceptions as :func:`readArchiveContentWith7z`.
    """

    # Resolve paths and validate inputs
    seven_zip_path = _resolve_seven_zip_path(seven_zip_path)
    _ensure_archive_exists(archive_path)

    # Build command
    cmd = [seven_zip_path, "l", "-slt", _build_password_arg(password), archive_path]

    try:
        stdout, stderr, code = _run_7z_cmd(cmd)
        _raise_for_7z_error(code, stderr, archive_path, stdout=stdout)

        try:
            return (
                _parse7zArchiveType(stdout),
                _parse7zListOutput(stdout),
                _parse7zSplitVolumes(stdout),
            )
        except Exception as e:
            raise ArchiveParsingError(f"Failed to parse 7z output: {str(e)}") from e
    except FileNotFoundError as exc:
        # In case running the binary failed despite path existence checks
        raise SevenZipNotFoundError(
            f"7z executable not found at: {seven_zip_path}"
        ) from exc


def _parse7zArchiveType(output: str) -> Optional[str]:
    """Return the archive-level ``Type`` from `7z l -slt` output, if any.

    Only the header block before the first ``----------`` line is considered;
    entry-level ``Type`` lines after it (e.g. a 7z embedded in PE resources)
    are ignored. When 7-Zip opens nested layers in the header (``Split`` →
    ``7z``), the innermost type is returned.
    """
    archive_type: Optional[str] = None
    for raw_line in output.split("\n"):
        line = raw_line.strip()
        if line.startswith("----------"):
            break
        if line.startswith("Type = "):
            archive_type = line.split(" = ", 1)[1].strip()
    return archive_type


def _parse7zSplitVolumes(output: str) -> Optional[int]:
    """Return ``Volumes = N`` from the `7z l -slt` header (Split archives)."""
    for raw_line in output.split("\n"):
        line = raw_line.strip()
        if line.startswith("----------"):
            break
        if line.startswith("Volumes = "):
            try:
                return int(line.split(" = ", 1)[1].strip())
            except ValueError:
                return None
    return None


def _parse7zListOutput(output: str) -> List[ArchiveFileInfo]:
    """
    Parse 7z list command output into structured data.

    Args:
        output (str): Raw output from 7z list command

    Returns:
        List[Dict]: Parsed file information
    """
    files = []
    current_file = {}

    lines = output.split("\n")
    in_file_section = False
    dash_count = 0

    for i, line in enumerate(lines):
        line = line.strip()

        # The file listing section in `7z l -slt` often starts after a dashed line
        # Accept the first dashed line to maintain compatibility with tests and varied 7z outputs
        if line.startswith("----------"):
            dash_count += 1
            if dash_count >= 1:
                in_file_section = True
            continue

        # Skip lines before file section
        if not in_file_section:
            continue

        # Skip empty lines
        if not line:
            continue

        # Check if this line starts a new file entry (starts with "Path = ")
        if line.startswith("Path = "):
            # Save previous file if it exists
            if current_file and current_file.get("Path"):
                files.append(_formatFileInfo(current_file))

            # Start new file entry
            current_file = {}
            parts = line.split(" = ", 1)
            if len(parts) == 2:
                current_file["Path"] = parts[1]

        # Parse other key-value pairs
        elif " = " in line and current_file:
            parts = line.split(" = ", 1)
            if len(parts) == 2:
                key = parts[0].strip()
                value = parts[1].strip()
                current_file[key] = value

    # Add final file if exists
    if current_file and current_file.get("Path"):
        files.append(_formatFileInfo(current_file))

    return files


def _formatFileInfo(file_data: Dict[str, str]) -> ArchiveFileInfo:
    """
    Format raw file data into standardized structure.

    Args:
        file_data (Dict): Raw file data from 7z output

    Returns:
        Dict: Formatted file information
    """
    try:
        size = int(file_data.get("Size", "0"))
    except (ValueError, TypeError):
        size = 0

    try:
        packed_size = int(file_data.get("Packed Size", "0"))
    except (ValueError, TypeError):
        packed_size = 0

    return {
        "name": file_data.get("Path", ""),
        "size": size,
        "packed_size": packed_size,
        "type": file_data.get("Folder", "File")
        .replace("-", "File")
        .replace("+", "Folder"),
        "modified": file_data.get("Modified", ""),
        "attributes": file_data.get("Attributes", ""),
        "crc": file_data.get("CRC", ""),
        "method": file_data.get("Method", ""),
    }


def extractArchiveWith7z(
    archive_path: str,
    output_path: str,
    password: Optional[str] = "",
    seven_zip_path: Optional[str] = None,
    overwrite: bool = True,
    specific_files: Optional[List[str]] = None,
) -> bool:
    """
    Extract archive using 7z.exe with optional password support.

    Args:
        archive_path (str): Path to the archive file
        output_path (str): Directory where files will be extracted
        password (str, optional): Password for encrypted archives
        seven_zip_path (str): Path to 7z.exe executable (default: auto-detect)
        overwrite (bool): Whether to overwrite existing files (default: True)
        specific_files (List[str], optional): List of specific files to extract

    Returns:
        bool: True if extraction successful

    Raises:
        ArchiveNotFoundError: If archive file not found
        SevenZipNotFoundError: If 7z executable not found
        ArchivePasswordError: If password is incorrect or required
        ArchiveCorruptedError: If archive is corrupted
        ArchiveUnsupportedError: If archive format is not supported
        ArchiveError: For other extraction errors
    """

    # Resolve paths and validate inputs
    seven_zip_path = _resolve_seven_zip_path(seven_zip_path)
    _ensure_archive_exists(archive_path)

    # Create output directory if it doesn't exist
    try:
        os.makedirs(output_path, exist_ok=True)
    except OSError as e:
        raise ArchiveError(f"Failed to create output directory: {e}") from e

    # Build command using centralized helper
    cmd = _build_7z_extract_cmd(
        seven_zip_path=seven_zip_path,
        password=password,
        output_path=output_path,
        archive_path=archive_path,
        overwrite=overwrite,
        specific_files=specific_files,
    )

    try:
        stdout, stderr, code = _run_7z_cmd(cmd)
        try:
            _raise_for_7z_error(code, stderr, archive_path, stdout=stdout)
        except ArchivePasswordError:
            # Re-raise password errors immediately without path checking
            raise
        except ArchiveError as e:
            # Detect path-related issues and fallback to sanitized path extraction
            msg = str(e).lower()
            if any(k in msg for k in PATH_ERROR_KEYWORDS):
                print_warning(
                    "Path-related extraction error detected, trying alternative extraction method...",
                    2,
                )
                return _extractWithSanitizedPaths(
                    archive_path,
                    output_path,
                    password,
                    seven_zip_path,
                    overwrite,
                    specific_files,
                )
            raise
        return True
    except FileNotFoundError:
        raise SevenZipNotFoundError(f"7z executable not found at: {seven_zip_path}")


def _extractWithSanitizedPaths(
    archive_path: str,
    output_path: str,
    password: Optional[str] = "",
    seven_zip_path: Optional[str] = None,
    overwrite: bool = True,
    specific_files: Optional[List[str]] = None,
) -> bool:
    """
    Extract archive using a temporary directory with sanitized paths.

    This is a fallback method when the direct extraction fails due to invalid
    Windows filenames or path length issues.
    """
    temp_dir = None

    try:
        # Create a temporary directory for extraction
        temp_dir = tempfile.mkdtemp(prefix="complex_unzip_temp_")
        print_info(f"Using temporary extraction directory: {temp_dir}", 3)

        # Try extracting to temp directory first
        temp_cmd = _build_7z_extract_cmd(
            seven_zip_path=seven_zip_path,
            password=password,
            output_path=temp_dir,
            archive_path=archive_path,
            overwrite=overwrite,
            specific_files=specific_files,
        )

        # Execute extraction to temp directory
        stdout, stderr, code = _run_7z_cmd(temp_cmd)
        if code != 0:
            _raise_for_7z_error(code, stderr, archive_path, stdout=stdout)

        # Now move files from temp directory to final destination with sanitized names
        try:
            _moveAndSanitizeFiles(temp_dir, output_path)
            print_success("Successfully extracted with sanitized file paths", 2)
            return True
        except Exception as e:
            raise ArchiveError(f"Failed to move extracted files: {e}")

    except Exception as e:
        # Re-raise specific archive exceptions, wrap others
        if isinstance(
            e,
            (
                ArchivePasswordError,
                ArchiveCorruptedError,
                ArchiveUnsupportedError,
                ArchiveNotFoundError,
                ArchiveError,
            ),
        ):
            raise
        else:
            raise ArchiveError(f"Extraction failed: {e}")

    finally:
        # Clean up temporary directory
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except OSError:
                pass  # Ignore cleanup errors


def _moveAndSanitizeFiles(source_dir: str, target_dir: str) -> None:
    """
    Move files from source to target directory, sanitizing names as needed.
    """
    if not os.path.exists(source_dir):
        return

    allowed_chars_re = re.compile(r"^[0-9\+\-_\.,\(\)\[\]\{\}!@#\$%\^&=]+$")
    date_like_re = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}$")

    def _is_meaningless_dir(name: str) -> bool:
        n = (name or "").strip()
        if not n:
            return False
        if date_like_re.match(n):
            return False
        if not any(ch.isdigit() for ch in n):
            return False
        if re.search(r"[A-Za-z]", n):
            return False
        if re.search(r"[\u4e00-\u9fff]", n):
            return False
        return bool(allowed_chars_re.match(n))

    def _normalize_rel_dir(rel_dir: str) -> str:
        if rel_dir in ("", "."):
            return "."
        norm = os.path.normpath(rel_dir)
        parts = [p for p in norm.split(os.path.sep) if p not in ("", ".")]
        while parts and _is_meaningless_dir(parts[0]):
            parts.pop(0)
        if not parts:
            return "."
        return os.path.join(*parts)

    # Ensure target directory exists
    os.makedirs(target_dir, exist_ok=True)

    # Process all files and directories
    for root, dirs, files in os.walk(source_dir):
        rel_path = os.path.relpath(root, source_dir)

        if rel_path != ".":
            rel_path = _normalize_rel_dir(rel_path)

        # Determine target subdirectory
        if rel_path != ".":
            sanitized_rel_path = sanitize_path(rel_path)
            target_subdir = os.path.join(target_dir, sanitized_rel_path)
        else:
            target_subdir = target_dir

        # Handle directory conflicts by adding counter if needed
        if target_subdir != target_dir and os.path.exists(target_subdir):
            counter = 1
            base_target_subdir = target_subdir
            while os.path.exists(target_subdir):
                parent_dir = os.path.dirname(base_target_subdir)
                dir_name = os.path.basename(base_target_subdir)
                target_subdir = os.path.join(parent_dir, f"{dir_name}_{counter}")
                counter += 1

            if counter > 1:
                print_info(
                    f"Directory conflict resolved: {os.path.basename(base_target_subdir)} → {os.path.basename(target_subdir)}",
                    3,
                )

        # Create target directory
        os.makedirs(target_subdir, exist_ok=True)

        # Move files with sanitized names
        for file in files:
            source_file = os.path.join(root, file)
            sanitized_filename = sanitize_filename(file)
            target_file = os.path.join(target_subdir, sanitized_filename)

            # Handle file name conflicts by adding counter
            counter = 1
            base_target = target_file
            while os.path.exists(target_file):
                name, ext = os.path.splitext(base_target)
                target_file = f"{name}_{counter}{ext}"
                counter += 1

            try:
                # Use copy2 + remove instead of move to avoid cross-device issues
                shutil.copy2(source_file, target_file)
                os.remove(source_file)

                if sanitized_filename != file or counter > 1:
                    print_info(
                        f"Moved file: {file} → {os.path.basename(target_file)}", 3
                    )

            except OSError:
                # If copy fails, try a more robust approach
                try:
                    with open(source_file, "rb") as src, open(target_file, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    os.remove(source_file)
                    print_info(
                        f"Moved file (fallback): {file} → {os.path.basename(target_file)}",
                        3,
                    )
                except OSError as e2:
                    print_warning(f"Failed to move file {file}: {e2}", 2)
                    # Don't raise exception, just continue with other files


def extractSpecificFilesWith7z(
    archive_path: str,
    output_path: str,
    file_list: List[str],
    password: Optional[str] = "",
    seven_zip_path: Optional[str] = None,
    overwrite: bool = True,
) -> Dict[str, bool]:
    """
    Extract specific files from archive using 7z.exe.

    Args:
        archive_path (str): Path to the archive file
        output_path (str): Directory where files will be extracted
        file_list (List[str]): List of file paths to extract
        password (str, optional): Password for encrypted archives
        seven_zip_path (str): Path to 7z.exe executable (default: auto-detect)
        overwrite (bool): Whether to overwrite existing files

    Returns:
        Dict[str, bool]: Dictionary mapping file paths to extraction success status

    Raises:
        Same exceptions as extract_archive_with_7z
    """

    results = {}

    # Extract all specified files in one operation for efficiency
    try:
        extractArchiveWith7z(
            archive_path=archive_path,
            output_path=output_path,
            password=password,
            seven_zip_path=seven_zip_path,
            overwrite=overwrite,
            specific_files=file_list,
        )

        # If extraction succeeded, check which files were actually extracted
        for file_path in file_list:
            extracted_path = os.path.join(output_path, file_path)
            results[file_path] = os.path.exists(extracted_path)

    except Exception as e:
        # If extraction failed, mark all files as failed
        for file_path in file_list:
            results[file_path] = False
        raise e

    return results
