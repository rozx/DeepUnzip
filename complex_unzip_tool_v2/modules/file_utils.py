import os
import re
import shutil
from send2trash import send2trash

from complex_unzip_tool_v2.modules.const import (
    MULTI_PART_PATTERNS,
    IGNORED_FILES,
    OUTPUT_FOLDER,
    WORK_DIR_PREFIX,
)
from complex_unzip_tool_v2.classes.ArchiveGroup import ArchiveGroup
from complex_unzip_tool_v2.modules.utils import get_string_similarity
from complex_unzip_tool_v2.modules.cloaked_file_detector import CloakedFileDetector
from complex_unzip_tool_v2.modules.regex import multipart_regex


_MEANINGLESS_OUTPUT_FOLDER_ALLOWED_CHARS_RE = re.compile(
    r"^[0-9\+\-_\.,\(\)\[\]\{\}!@#\$%\^&=]+$"
)
_DATE_LIKE_FOLDER_RE = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}$")


def _is_meaningless_output_folder_name(folder_name: str) -> bool:
    """Return True if folder name is considered meaningless for output layout.

    Intended for flattening leading folders under the output root.
    """

    name = (folder_name or "").strip()
    if not name:
        return False

    # Do not treat dates as meaningless (e.g., 2024-01-01)
    if _DATE_LIKE_FOLDER_RE.match(name):
        return False

    # Must contain at least one digit
    if not any(ch.isdigit() for ch in name):
        return False

    # Must not contain letters or CJK characters
    if re.search(r"[A-Za-z]", name):
        return False
    if re.search(r"[\u4e00-\u9fff]", name):
        return False

    # Only allow digits plus specific symbols
    return bool(_MEANINGLESS_OUTPUT_FOLDER_ALLOWED_CHARS_RE.match(name))


def normalize_output_relative_path(relative_path: str) -> str:
    """Normalize a relative path by stripping meaningless *leading* folders.

    Example:
    - "1/aaa.jpg" -> "aaa.jpg"
    - "1/5555+/222.jpg" -> "222.jpg"

    Only leading directories are stripped; once a meaningful directory is reached,
    the remaining structure is preserved.
    """

    if relative_path in ("", "."):
        return relative_path

    norm = os.path.normpath(relative_path)
    parts = [p for p in norm.split(os.path.sep) if p not in ("", ".")]
    if not parts:
        return relative_path

    filename = parts[-1]
    dir_parts = parts[:-1]

    while dir_parts and _is_meaningless_output_folder_name(dir_parts[0]):
        dir_parts.pop(0)

    if dir_parts:
        return os.path.join(*dir_parts, filename)
    return filename


def get_archive_base_name(file_path: str) -> tuple[str, str]:
    """
    Get the base name and archive extension from a file path,
    handling multi-part archives like .7z.001, .rar.part1, etc.
    获取文件路径的基本名称和档案扩展名，处理多部分档案如.7z.001, .rar.part1等
    Returns (base_name, archive_extension)

    For multi-part formats whose parts use distinct per-part suffixes
    (e.g. .z01/.z02 for spanned ZIP, .r00/.r01 for legacy RAR, .partN.rar for
    standard RAR), the returned extension is the *family* extension (zip/rar)
    so that all parts of the same set share the same (base, ext) tuple. This
    is what enables grouping logic to recognize them as related.
    """
    base_name = os.path.basename(file_path)

    # Family-mapped continuation suffixes: all parts must share the family ext
    # so grouping/comparison treats them as the same multi-part set.
    # Note: .zx must be checked before .z so `.zx01` maps to zipx, not zip.
    family_pattern_map = [
        (r"\.zx\d{2}$", "zipx"),  # .zx01, .zx02 → zipx family
        (r"\.z\d{2}$", "zip"),  # .z01, .z02 → zip family
        (r"\.r\d{2}$", "rar"),  # .r00, .r01 → rar family
        (r"\.a\d{2}$", "arj"),  # .a01, .a02 → arj family
        (r"\.c\d{2}$", "ace"),  # .c00, .c01 → ace family
        (r"\.part\d+\.rar$", "rar"),  # .part1.rar, .part2.rar → rar family
    ]
    for pattern, family_ext in family_pattern_map:
        match = re.search(pattern, base_name, re.IGNORECASE)
        if match:
            return base_name[: match.start()], family_ext

    # Use the multi-part archive patterns from constants
    for pattern in MULTI_PART_PATTERNS:
        match = re.search(pattern, base_name, re.IGNORECASE)
        if match:
            # Remove the part number/suffix to get the base name
            name_without_part = base_name[: match.start()]
            archive_ext = base_name[match.start() + 1 :].split(".")[
                0
            ]  # Get the archive extension
            return name_without_part, archive_ext

    # 7-Zip generic numbered volume split for ANY base extension: `name.<ext>.NNN`
    # (zero-padded, 3+ digits). Checked AFTER the specific patterns above so 7z/zip/
    # tar split parsing is preserved; covers .rar.001, .iso.001, plain .tar.001, etc.
    # The token immediately before the numeric run is the shared family extension.
    generic_match = re.search(r"\.([A-Za-z0-9]+)\.\d{3,}$", base_name)
    if generic_match:
        return base_name[: generic_match.start()], generic_match.group(1)

    # Fallback to regular splitext if no multi-part pattern found
    name, ext = os.path.splitext(base_name)
    return name, ext.lstrip(".")


def _multipart_input_key(filename: str) -> tuple[str, str] | None:
    """Identify an exact volume set without merging different split conventions."""
    if re.search(multipart_regex, filename, re.IGNORECASE):
        numbered = re.match(r"^(.*)\.\d+$", filename)
        if numbered:
            return "numbered", os.path.normcase(numbered.group(1))
    rar_part = re.match(r"^(.*)\.part\d+\.rar$", filename, re.IGNORECASE)
    if rar_part:
        return "rar-part", os.path.normcase(rar_part.group(1))
    # Ambiguous primary names (.zip/.rar/...) only match their own continuations.
    for family, suffix in (
        ("rar", r"rar|r\d{2}"),
        ("zip", r"zip|z\d{2}"),
        ("zipx", r"zipx|zx\d{2}"),
        ("arj", r"arj|a\d{2}"),
        ("ace", r"ace|c\d{2}"),
    ):
        match = re.match(rf"^(.*)\.(?:{suffix})$", filename, re.IGNORECASE)
        if match:
            return family, os.path.normcase(match.group(1))
    return None


def read_dir(file_paths: list[str]) -> list[str]:
    """Read directory contents 读取目录内容"""
    result = []
    detector: CloakedFileDetector | None = None

    def multipart_key(path: str) -> tuple[str, str] | None:
        nonlocal detector
        key = _multipart_input_key(os.path.basename(path))
        if key is not None:
            return key
        if detector is None:
            rules = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "config",
                "cloaked_file_rules.json",
            )
            detector = CloakedFileDetector(rules)
        # Preview only. Step 4 owns actual renames and their recovery history.
        normalized = detector.detect_cloaked_file(path)
        return (
            _multipart_input_key(os.path.basename(normalized)) if normalized else None
        )

    # Use ignored files from constants
    for path in file_paths:
        if os.path.isdir(path):
            # Read files from directory
            for root, dirs, files in os.walk(path):
                # Skip the output folder and run work directories (with contents)
                dirs[:] = [
                    d
                    for d in dirs
                    if d != OUTPUT_FOLDER and not d.startswith(WORK_DIR_PREFIX)
                ]

                for filename in files:
                    if filename not in IGNORED_FILES:
                        result.append(os.path.join(root, filename))
        else:
            # Check if the file is ignored
            basename = os.path.basename(path)
            if basename not in IGNORED_FILES:
                result.append(path)
                key = multipart_key(path) if os.path.isfile(path) else None
                if key is not None and os.path.isfile(path):
                    directory = os.path.dirname(path)
                    try:
                        with os.scandir(directory or ".") as siblings:
                            for sibling in siblings:
                                sibling_path = os.path.join(directory, sibling.name)
                                if (
                                    sibling.name not in IGNORED_FILES
                                    and sibling.is_file()
                                    and multipart_key(sibling_path) == key
                                ):
                                    result.append(sibling_path)
                    except OSError:
                        # Discovery is best-effort; keep the explicitly selected file.
                        pass

    # make sure the result is unique
    return list(set(result))


def rename_file(old_path: str, new_path: str, error_callback=None) -> bool:
    """
    Rename a file or directory 重命名文件或目录
    For example, "old_name.txt" to "new_name.txt"
    例如："old_name.txt" 到 "new_name.txt"

    Args:
        old_path: Original path
        new_path: New path
        error_callback: Optional callback function to handle errors

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        os.rename(old_path, new_path)
        return True
    except (OSError, IOError, PermissionError) as e:
        error_msg = f"Error renaming file 重命名文件错误 {old_path} to {new_path}: {e}"
        if error_callback:
            error_callback(error_msg)
        return False


def safe_remove(
    file_path: str, use_recycle_bin: bool = True, error_callback=None
) -> bool:
    """
    Safely remove a file, optionally moving it to recycle bin instead of permanent deletion.
    安全删除文件，可选择移动到回收站而不是永久删除。

    Args:
        file_path (str): Path to the file to remove
        use_recycle_bin (bool): If True, move to recycle bin; if False, permanently delete
        error_callback: Optional callback function to handle errors

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        if os.path.exists(file_path):
            if use_recycle_bin:
                send2trash(file_path)
                return True
            else:
                os.remove(file_path)
                return True
        return False
    except (OSError, IOError, PermissionError, FileNotFoundError) as e:
        error_msg = f"Error removing file 删除文件错误 {file_path}: {e}"
        if error_callback:
            error_callback(error_msg)
        return False


def _should_group_files(
    group_name1: str, group_name2: str, file_path1: str, file_path2: str
) -> bool:
    """
    Improved logic to determine if two files should be grouped together.
    This addresses the issue of unrelated files being grouped due to high similarity scores.
    改进的逻辑来确定两个文件是否应该分组在一起。
    这解决了不相关文件因高相似度分数而被分组的问题。
    """
    if not file_path2:  # Empty comparison file
        return False

    # Extract file information
    base1, ext1 = get_archive_base_name(file_path1)
    base2, ext2 = get_archive_base_name(file_path2)

    # First check: Are they multipart archives of the same base file?
    if _are_multipart_related(file_path1, file_path2):
        return True

    # Second check: Exact base name match (for files like 1.rar, 1.r00, 1.r01)
    # But only if they're in the same directory (to avoid grouping identical files from different folders)
    if base1 == base2 and ext1 == ext2:
        # Check if they're in the same directory
        dir1 = os.path.dirname(file_path1)
        dir2 = os.path.dirname(file_path2)
        if dir1 == dir2:
            return True

    # Third check: Only allow grouping if similarity is very high AND they share
    # exact base name AND same directory AND the same archive family/extension.
    # The extension guard is essential: without it, unrelated archive types that
    # merely share a base name (e.g. foo.7z and foo.zip) would be merged into one
    # group. That corrupts handling — e.g. a standalone .7z swept into a spanned
    # .zip set gets deleted with the set instead of being extracted on its own.
    similarity = get_string_similarity(group_name1, group_name2)
    if similarity >= 0.95:
        # Extract directory and filename parts
        dir1 = group_name1.split("-")[0] if "-" in group_name1 else ""
        dir2 = group_name2.split("-")[0] if "-" in group_name2 else ""
        name1_only = group_name1.split("-")[-1] if "-" in group_name1 else group_name1
        name2_only = group_name2.split("-")[-1] if "-" in group_name2 else group_name2

        # Only group if the file base names are identical AND they're in the same
        # directory AND they belong to the same archive family/extension.
        return name1_only == name2_only and dir1 == dir2 and ext1 == ext2

    # For all other cases, don't group
    return False


def _are_multipart_related(file_path1: str, file_path2: str) -> bool:
    """Check if two files are related multipart archives."""
    if not file_path2:  # Empty comparison file
        return False

    # Extract base names without part numbers
    base1, ext1 = get_archive_base_name(file_path1)
    base2, ext2 = get_archive_base_name(file_path2)

    # Check if both are multipart archives with identical base names
    file1_is_multipart = re.search(multipart_regex, file_path1)
    file2_is_multipart = re.search(multipart_regex, file_path2)

    if file1_is_multipart and file2_is_multipart:
        # Base names must be exactly the same for multipart grouping
        return base1 == base2 and ext1 == ext2

    return False


def _have_matching_multipart_pattern(file_path1: str, file_path2: str) -> bool:
    """Check if two files follow the same multipart pattern (for short names)."""
    if not file_path2:  # Empty comparison file
        return False

    # Check if both are multipart and have the same base pattern

    # Extract base names and extensions
    base1, ext1 = get_archive_base_name(file_path1)
    base2, ext2 = get_archive_base_name(file_path2)

    # For short names, require exact base name match and same extension type
    if len(base1) <= 3 and len(base2) <= 3:
        return base1 == base2 and ext1 == ext2

    return False


def create_groups_by_name(file_paths: list[str]) -> list[ArchiveGroup]:
    """Create Archive Groups by name 按名称创建档案组"""
    groups: list[ArchiveGroup] = []

    for path in file_paths:
        # get base name and directory name using the new function
        base_name, _ = get_archive_base_name(path)
        dir_name = os.path.dirname(path).split(os.path.sep)[-1]
        group_name = f"{dir_name}-{base_name}"

        # Check if file belongs to an existing group using improved logic
        found_group = False
        for group in groups:
            if _should_group_files(
                group_name, group.name, path, group.files[0] if group.files else ""
            ):
                group.add_file(path)
                found_group = True
                break

        if not found_group:
            new_group = ArchiveGroup(group_name)
            new_group.add_file(path)
            groups.append(new_group)

    # and finally sort it by name
    for group in groups:
        group.files.sort()

    return groups


def uncloak_file_extension_for_groups(
    groups: list[ArchiveGroup],
    rules_file_path: str = None,
    warning_callback=None,
    history=None,
) -> None:
    """
    Uncloak file extensions for groups using rule-based detection.
    使用基于规则的检测为组揭示文件扩展名。

    Args:
        groups: List of ArchiveGroup objects to process
        rules_file_path: Path to JSON rules file (optional, uses default if not provided)
        warning_callback: Optional callback function to handle warnings
    """
    # Use default rules file if not provided
    if rules_file_path is None:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_dir = os.path.join(os.path.dirname(current_dir), "config")
        rules_file_path = os.path.join(config_dir, "cloaked_file_rules.json")

    # Initialize the detector
    detector = CloakedFileDetector(rules_file_path)

    for group in groups:
        for i, file in enumerate(group.files):
            original_file = file
            new_path = detector.uncloak_file(file, history=history)

            if new_path != original_file:
                if os.path.exists(new_path):
                    group.files[i] = new_path
                    if group.mainArchiveFile == original_file:
                        group.mainArchiveFile = new_path
                else:
                    warning_msg = (
                        f"⚠ Failed to rename file '{original_file}' to '{new_path}'. "
                        "File does not exist. Group not updated."
                    )
                    if warning_callback:
                        warning_callback(warning_msg)


def create_cloaked_detector(rules_file_path: str | None = None) -> CloakedFileDetector:
    """Create a cloaked-file detector with the default (or given) rules file."""
    if rules_file_path is None:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_dir = os.path.join(os.path.dirname(current_dir), "config")
        rules_file_path = os.path.join(config_dir, "cloaked_file_rules.json")
    return CloakedFileDetector(rules_file_path)


def uncloak_file_extensions(
    file_paths: list[str], rules_file_path: str = None, history=None
) -> list[str]:
    """
    Uncloak file extensions for a list of file paths using rule-based detection.
    使用基于规则的检测为文件路径列表解除文件扩展名隐藏。

    Args:
        file_paths: List of file paths to process
        rules_file_path: Path to JSON rules file (optional, uses default if not provided)
        history: Optional RenameHistory to record successful renames

    Returns:
        The updated file paths list with proper extensions.
    """
    detector = create_cloaked_detector(rules_file_path)

    # Process all files
    updated_paths = detector.uncloak_files(file_paths, history=history)

    return updated_paths


def add_file_to_groups(file: str, groups: list[ArchiveGroup]) -> ArchiveGroup | None:
    """
    Check if a file belongs to a specific multi-part archive group, then add it to the group.
    检查文件是否属于特定的多部分档案组，然后将其添加到组中
    """

    file_basename = os.path.basename(file)

    for group in groups:
        if group.isMultiPart:
            main_archive_path = group.mainArchiveFile
            main_archive_basename = os.path.basename(main_archive_path)

            # Only allow exact multipart base-name matching to avoid cross-group misclassification
            file_base_name, _ = get_archive_base_name(file_basename)
            main_base_name, _ = get_archive_base_name(main_archive_basename)

            # Additional constraint: file must be under the same directory tree as the group's main archive
            try:
                same_tree = os.path.commonpath(
                    [
                        os.path.abspath(file),
                        os.path.abspath(os.path.dirname(main_archive_path)),
                    ]
                ) == os.path.abspath(os.path.dirname(main_archive_path))
            except ValueError:
                # If drives differ on Windows, they are not in the same tree
                same_tree = False

            # Check if both files have the same base name (for multipart archives) and are in same tree
            if file_base_name == main_base_name and same_tree:
                # move file to group's main archive's location
                new_path = os.path.join(
                    os.path.dirname(main_archive_path), file_basename
                )
                shutil.move(file, new_path)
                group.add_file(new_path)
                return group

    return None


def relocate_multipart_parts_from_directory(
    source_root: str, groups: list[ArchiveGroup]
) -> int:
    """
    Scan a directory (recursively) for multipart archive parts and relocate them
    next to their corresponding multipart group's main archive file.

    This is used after extracting single archives into an output/temp directory
    to ensure any parts contained inside those archives are moved beside the
    existing multipart set before attempting extraction.

    Args:
        source_root: The root directory to scan (e.g., output folder)
        groups: The current archive groups

    Returns:
        The number of files relocated.
    """
    relocated = 0

    # Build quick lookup for multipart groups by base name and archive ext
    multipart_groups: list[tuple[str, str, ArchiveGroup]] = []
    for group in groups:
        if group.isMultiPart and group.mainArchiveFile:
            main_basename = os.path.basename(group.mainArchiveFile)
            main_base, main_ext = get_archive_base_name(main_basename)
            multipart_groups.append((main_base, main_ext, group))

    if not multipart_groups:
        return 0

    for root, _dirs, files in os.walk(source_root):
        for filename in files:
            # Only consider multipart-looking filenames
            if not re.search(multipart_regex, filename):
                continue

            file_path = os.path.join(root, filename)

            # Derive base and ext for matching
            file_base, _file_ext = get_archive_base_name(filename)

            for main_base, _main_ext, group in multipart_groups:
                if file_base == main_base:
                    # Move this part next to the group's main archive
                    dest_dir = os.path.dirname(group.mainArchiveFile)
                    dest_path = os.path.join(dest_dir, filename)

                    # If the file is already in the correct destination, do nothing.
                    # This avoids renaming the group's own main archive due to self-collision.
                    try:
                        if os.path.abspath(file_path) == os.path.abspath(dest_path):
                            break
                    except Exception:
                        pass

                    # Handle potential name collisions in destination
                    final_dest = dest_path
                    counter = 1
                    while os.path.exists(final_dest):
                        name, ext = os.path.splitext(dest_path)
                        final_dest = f"{name}_{counter}{ext}"
                        counter += 1

                    try:
                        os.makedirs(dest_dir, exist_ok=True)
                        shutil.move(file_path, final_dest)
                        group.add_file(final_dest)
                        relocated += 1
                        break  # Do not match same file to another group
                    except (OSError, IOError, PermissionError):
                        # If we fail to move, just skip; extraction step will handle
                        pass

    return relocated


def ensure_contained_multipart_groups(
    file_paths: list[str], groups: list[ArchiveGroup]
) -> int:
    """Create multipart groups for newly discovered multipart primaries.

    This is used when nested extraction preserves contained multipart sets into the
    output folder during Step 7. The groups list was created earlier (Step 5), so
    without this, Step 8 would not attempt extraction for newly discovered sets.

    Safety: only auto-creates groups for unambiguous multipart primaries:
    - `.7z.001`
    - `.tar.(gz|bz2|xz).001`
    - `.part1.rar`
    - `.<ext>.001` (7-Zip generic numbered split of any extension)
    And conservative formats only when a continuation part exists in the same bucket:
    - `.zip` when any `.zNN` exists
    - `.rar` when any `.rNN` exists
    - `.zipx` when any `.zxNN` exists
    - `.arj` when any `.aNN` exists
    - `.ace` when any `.cNN` exists

    Returns the number of groups created.
    """

    created = 0

    def _base_for_part_notation(filename: str) -> str | None:
        m = re.match(r"^(.*)\.part(\d+)\.rar$", filename, re.IGNORECASE)
        if not m:
            return None
        return m.group(1)

    # Build an index of existing groups by (dir, base) to avoid duplicates
    existing: set[tuple[str, str]] = set()
    for g in groups:
        if not g.mainArchiveFile:
            continue
        d = os.path.abspath(os.path.dirname(g.mainArchiveFile))
        b = os.path.basename(g.mainArchiveFile)
        base_name, _ext = get_archive_base_name(b)
        # Special-case partN.rar notation
        base_part = _base_for_part_notation(b)
        if base_part is not None:
            base_name = base_part
        existing.add((d, base_name))

    # Bucket multipart-looking files by (dir, base)
    buckets: dict[tuple[str, str], list[str]] = {}
    for p in file_paths:
        if not os.path.exists(p):
            continue
        filename = os.path.basename(p)

        base_part = _base_for_part_notation(filename)
        if base_part is not None:
            base_name = base_part
        else:
            base_name, _ext = get_archive_base_name(filename)

        key = (os.path.abspath(os.path.dirname(p)), base_name)
        buckets.setdefault(key, []).append(p)

    for (dir_path, base_name), files in buckets.items():
        # Identify an unambiguous multipart primary within this bucket
        primary: str | None = None
        force_main: str | None = None

        for p in files:
            fname = os.path.basename(p).lower()
            # 7z primary
            if re.search(r"\.7z\.(0*1)$", fname):
                primary = p
                break
            # tar.* primary
            if re.search(r"\.tar\.(gz|bz2|xz)\.(0*1)$", fname):
                primary = p
                break
            # rar part notation primary
            if re.search(r"\.part1\.rar$", fname):
                primary = p
                break
            # 7-Zip generic numbered split primary (any extension): name.<ext>.001
            # The .001 suffix is unambiguous, so the .001 alone is enough.
            if re.search(r"\.[a-z0-9]+\.0{2,}1$", fname):
                primary = p
                break

        # Spanned ZIP / volume RAR / ZIPX / ARJ / ACE primaries are ambiguous
        # (they can be standalone archives); only group if a continuation exists.
        if primary is None:
            has_zip = None
            has_z_cont = False
            has_rar = None
            has_r_cont = False
            has_zipx = None
            has_zx_cont = False
            has_arj = None
            has_a_cont = False
            has_ace = None
            has_c_cont = False

            for p in files:
                fname = os.path.basename(p).lower()
                if fname.endswith(".zipx"):
                    has_zipx = p
                elif re.search(r"\.zx\d{2}$", fname):
                    has_zx_cont = True
                elif fname.endswith(".zip"):
                    has_zip = p
                elif re.search(r"\.z\d{2}$", fname):
                    has_z_cont = True

                if fname.endswith(".rar"):
                    has_rar = p
                elif re.search(r"\.r\d{2}$", fname):
                    has_r_cont = True

                if fname.endswith(".arj"):
                    has_arj = p
                elif re.search(r"\.a\d{2}$", fname):
                    has_a_cont = True

                if fname.endswith(".ace"):
                    has_ace = p
                elif re.search(r"\.c\d{2}$", fname):
                    has_c_cont = True

            if has_zip is not None and has_z_cont:
                primary = has_zip
                force_main = has_zip
            elif has_rar is not None and has_r_cont:
                primary = has_rar
                force_main = has_rar
            elif has_zipx is not None and has_zx_cont:
                primary = has_zipx
                force_main = has_zipx
            elif has_arj is not None and has_a_cont:
                primary = has_arj
                force_main = has_arj
            elif has_ace is not None and has_c_cont:
                primary = has_ace
                force_main = has_ace

        if primary is None:
            continue

        if (dir_path, base_name) in existing:
            continue

        # Create a new group named like the existing grouping logic: <dir>-<base>
        dir_name = os.path.basename(dir_path)
        group_name = f"{dir_name}-{base_name}"
        new_group = ArchiveGroup(group_name)

        # Add primary first for stable main selection
        new_group.add_file(primary)
        for p in sorted(files):
            if p == primary:
                continue
            if p not in new_group.files:
                new_group.add_file(p)

        if new_group.isMultiPart:
            # If we grouped a spanned ZIP/RAR set, make sure the main archive stays
            # on the `.zip`/`.rar` primary, not the `.z01`/`.r00` continuation.
            if force_main is not None:
                new_group.set_main_archive(force_main)
            groups.append(new_group)
            existing.add((dir_path, base_name))
            created += 1

    return created


def move_files_preserving_structure(
    file_paths: list[str],
    source_root: str,
    destination_root: str,
    verbose: bool = False,
    progress_callback: callable = None,
    success_callback: callable = None,
    error_callback: callable = None,
) -> list[str]:
    """
    Move files from source to destination while preserving directory structure.
    在保持目录结构的同时将文件从源移动到目标

    Args:
        file_paths: List of file paths to move 要移动的文件路径列表
        source_root: Root directory to calculate relative paths from 计算相对路径的根目录
        destination_root: Root directory to move files to 移动文件到的根目录
        verbose: Print verbose output 打印详细输出
        progress_callback: Optional callback function for progress updates 可选的进度更新回调函数
        success_callback: Optional callback function for success messages 可选的成功消息回调函数
        error_callback: Optional callback function for error messages 可选的错误消息回调函数

    Returns:
        List of relative paths that were successfully moved 成功移动的相对路径列表
    """
    moved_files = []

    for file_path in file_paths:
        if os.path.exists(file_path):
            try:
                # Calculate relative path from source root to preserve structure
                relative_path = os.path.relpath(file_path, source_root)
                relative_path = normalize_output_relative_path(relative_path)
                destination = os.path.join(destination_root, relative_path)

                # Create destination directory if it doesn't exist
                destination_dir = os.path.dirname(destination)
                os.makedirs(destination_dir, exist_ok=True)

                # Handle duplicate filenames while preserving directory structure
                counter = 1
                original_destination = destination
                while os.path.exists(destination):
                    name, ext = os.path.splitext(original_destination)
                    destination = f"{name}_{counter}{ext}"
                    counter += 1

                shutil.move(file_path, destination)
                moved_files.append(relative_path)

                # Call progress callback if provided
                if progress_callback:
                    progress_callback()
                if verbose and success_callback:
                    success_callback(f"📁 Moved 已移动: {relative_path}")

            except (OSError, IOError, PermissionError) as e:
                error_msg = f"Error moving 移动错误 {file_path}: {e}"
                if error_callback:
                    error_callback(error_msg)

    return moved_files
