import re
import os


def detect_archive_extension(filepath: str) -> str | None:
    """
    Detect and uncloak the true archive extension including multipart suffixes.
    Handles cloaked filenames and returns clean extension like '7z.001', 'rar.002', 'zip', etc.

    Examples:
        '11111.7z删除.001' -> '7z.001'
        '11111.7z.00删1' -> '7z.001'
        'archive.zip.z0隐藏1' -> 'zip.z01'
        'file.rar.r00删除' -> 'rar.r00'
        'normal.7z' -> '7z'
    """
    # First try to detect with the original filename
    info = detect_archive_info(filepath)
    if info:
        archive_type = info["type"]
        if info["is_multipart"]:
            if archive_type in ["7z", "rar", "zip"]:
                return f"{archive_type}.{info['part_number']:03d}"
            else:
                return f"{archive_type}.part{info['part_number']}"
        return archive_type

    # If detection failed, try uncloaking the filename first
    uncloaked_path = _uncloakFilename(filepath)
    if uncloaked_path != filepath:
        # Try detection again with uncloaked filename
        info = detect_archive_info(uncloaked_path)
        if info:
            archive_type = info["type"]
            if info["is_multipart"]:
                if archive_type in ["7z", "rar", "zip"]:
                    return f"{archive_type}.{info['part_number']:03d}"
                else:
                    return f"{archive_type}.part{info['part_number']}"
            return archive_type

    return None


def uncloak_archive_filename(filepath: str) -> str | None:
    """
    Reconstruct the clean basename when cloaking characters are embedded
    *inside* a recognizable archive extension or its part number -- cases the
    flat rename rules cannot express because they only strip trailing garbage.

    Name-based only (does not read file contents). Returns the de-cloaked
    basename, or None when no archive extension is found in the name.

    Examples:
        '12.7z.0删02'   -> '12.7z.002'
        '6.7z.0删01'    -> '6.7z.001'
        '1.part2.r删ar' -> '1.part2.rar'
        'ordinary.txt'  -> None
    """
    clean_path = _uncloakFilename(filepath)
    if clean_path == filepath:
        return None
    return os.path.basename(clean_path)


def _uncloakFilename(filepath: str) -> str:
    """
    Internal function to remove cloaking patterns from filename.
    Returns the uncloaked filepath.
    """
    filename = os.path.basename(filepath)
    directory = os.path.dirname(filepath)

    # Archive extensions and their common multipart patterns
    archive_patterns = {
        "7z": [r"\.00[1-9]", r"\.0[1-9][0-9]", r"\.part[0-9]+"],
        "rar": [r"\.r[0-9]{2}", r"\.part[0-9]+", r"\.00[1-9]"],
        "zip": [r"\.z[0-9]{2}", r"\.00[1-9]", r"\.part[0-9]+"],
        "tar": [r"\.part[0-9]+"],
        "gz": [r"\.part[0-9]+"],
        "bz2": [r"\.part[0-9]+"],
        "xz": [r"\.part[0-9]+"],
        "arj": [r"\.a[0-9]{2}", r"\.part[0-9]+"],
        "cab": [r"\.part[0-9]+"],
        "lzh": [r"\.part[0-9]+"],
        "ace": [r"\.c[0-9]{2}", r"\.part[0-9]+"],
        "iso": [r"\.part[0-9]+"],
    }

    # Try to find archive extension in the filename
    for archive_ext, part_patterns in archive_patterns.items():
        # Look for the archive extension anywhere in the filename
        archive_matches = list(
            re.finditer(re.escape(archive_ext), filename, re.IGNORECASE)
        )

        if archive_matches:
            match = archive_matches[0]
            start_pos = match.start()
            end_pos = match.end()

            # Get the part before the archive extension
            prefix = filename[:start_pos]

            # Get the part after the archive extension
            suffix = filename[end_pos:]

            # Try to find multipart patterns in the suffix
            part_extension = _extractPartExtension(suffix, part_patterns)

            if part_extension:
                clean_filename = f"{prefix}{archive_ext}{part_extension}"
                return os.path.join(directory, clean_filename)
            else:
                # No part extension found, just use the archive extension
                clean_filename = f"{prefix}{archive_ext}"
                return os.path.join(directory, clean_filename)

    # If no exact match, try flexible matching for heavily cloaked files
    for archive_ext, part_patterns in archive_patterns.items():
        clean_filename = _flexibleArchiveMatch(filename, archive_ext, part_patterns)
        if clean_filename and clean_filename != filename:
            return os.path.join(directory, clean_filename)

    # If no archive pattern found, return original filepath
    return filepath


def _extractPartExtension(suffix: str, part_patterns: list[str]) -> str:
    """Extract and clean part extension from suffix."""

    # First, try direct pattern matching
    for pattern in part_patterns:
        match = re.search(pattern, suffix, re.IGNORECASE)
        if match:
            return match.group()

    # If no direct match, try to extract and reconstruct common patterns
    digits = re.findall(r"\d", suffix)

    # Extract digits for .001/.002 format
    if len(digits) >= 3:
        part_num = int(f"{digits[0]}{digits[1]}{digits[2]}")
        if 1 <= part_num <= 999:
            return f".{part_num:03d}"

    # Extract for .z01/.z02 format (zip multipart)
    z_match = re.search(r"z.*?(\d).*?(\d)", suffix, re.IGNORECASE)
    if z_match and len(digits) >= 2:
        part_num = int(f"{digits[0]}{digits[1]}")
        if 0 <= part_num <= 99:
            return f".z{part_num:02d}"

    # Extract for .r00/.r01 format (rar multipart)
    r_match = re.search(r"r.*?(\d).*?(\d)", suffix, re.IGNORECASE)
    if r_match and len(digits) >= 2:
        part_num = int(f"{digits[0]}{digits[1]}")
        if 0 <= part_num <= 99:
            return f".r{part_num:02d}"

    # Extract for .a00/.a01 format (arj multipart)
    a_match = re.search(r"a.*?(\d).*?(\d)", suffix, re.IGNORECASE)
    if a_match and len(digits) >= 2:
        part_num = int(f"{digits[0]}{digits[1]}")
        if 0 <= part_num <= 99:
            return f".a{part_num:02d}"

    # Extract for .c00/.c01 format (ace multipart)
    c_match = re.search(r"c.*?(\d).*?(\d)", suffix, re.IGNORECASE)
    if c_match and len(digits) >= 2:
        part_num = int(f"{digits[0]}{digits[1]}")
        if 0 <= part_num <= 99:
            return f".c{part_num:02d}"

    # Extract for .part1/.part2 format
    if len(digits) >= 1:
        part_num = int(digits[0])
        if 1 <= part_num <= 99:
            return f".part{part_num}"

    return ""


def _flexibleArchiveMatch(
    filename: str, archive_ext: str, part_patterns: list[str]
) -> str:
    """Try flexible matching for heavily cloaked archive extensions."""

    # Create a regex that allows for insertions between characters
    pattern_chars = list(archive_ext.lower())
    flexible_pattern = pattern_chars[0]
    for char in pattern_chars[1:]:
        flexible_pattern += r"[^\.]*?" + char  # Allow any non-dot characters between

    # Look for this flexible pattern
    match = re.search(flexible_pattern, filename.lower())
    if match:
        # Found a potential match
        prefix = filename[: match.start()]
        remaining = filename[match.end() :]

        # Try to extract part extension
        part_extension = _extractPartExtension(remaining, part_patterns)

        if part_extension:
            return f"{prefix}{archive_ext}{part_extension}"
        else:
            return f"{prefix}{archive_ext}"

    return filename


def detect_archive_info(filepath: str) -> dict | None:
    """
    Detect archive type and multipart information from filepath.
    Returns dict with 'type', 'is_multipart', 'part_number' or None if not an archive.
    """
    filename = os.path.basename(filepath).lower()

    # Check for various archive formats and their multipart patterns
    archive_patterns = {
        "7z": {
            "extensions": [".7z"],
            "multipart_patterns": [
                (r"\.7z\.(\d{3})$", lambda m: int(m.group(1))),  # .7z.001
                (r"\.7z\.part(\d+)$", lambda m: int(m.group(1))),  # .7z.part1
            ],
        },
        "rar": {
            "extensions": [".rar"],
            "multipart_patterns": [
                (r"\.rar\.(\d{3})$", lambda m: int(m.group(1))),  # .rar.001
                (r"\.r(\d{2})$", lambda m: int(m.group(1))),  # .r00, .r01
                (r"\.rar\.part(\d+)$", lambda m: int(m.group(1))),  # .rar.part1
            ],
        },
        "zip": {
            "extensions": [".zip"],
            "multipart_patterns": [
                (r"\.zip\.(\d{3})$", lambda m: int(m.group(1))),  # .zip.001
                (r"\.z(\d{2})$", lambda m: int(m.group(1))),  # .z01, .z02
                (r"\.zip\.part(\d+)$", lambda m: int(m.group(1))),  # .zip.part1
            ],
        },
        "tar": {
            "extensions": [
                ".tar",
                ".tar.gz",
                ".tgz",
                ".tar.bz2",
                ".tbz2",
                ".tar.xz",
                ".txz",
            ],
            "multipart_patterns": [
                (r"\.tar\.part(\d+)$", lambda m: int(m.group(1))),
                (r"\.tar\.gz\.part(\d+)$", lambda m: int(m.group(1))),
                (r"\.tgz\.part(\d+)$", lambda m: int(m.group(1))),
            ],
        },
        "gz": {
            "extensions": [".gz"],
            "multipart_patterns": [(r"\.gz\.part(\d+)$", lambda m: int(m.group(1)))],
        },
        "bz2": {
            "extensions": [".bz2"],
            "multipart_patterns": [(r"\.bz2\.part(\d+)$", lambda m: int(m.group(1)))],
        },
        "xz": {
            "extensions": [".xz"],
            "multipart_patterns": [(r"\.xz\.part(\d+)$", lambda m: int(m.group(1)))],
        },
        "arj": {
            "extensions": [".arj"],
            "multipart_patterns": [
                (r"\.arj\.(\d{3})$", lambda m: int(m.group(1))),
                (r"\.a(\d{2})$", lambda m: int(m.group(1))),
                (r"\.arj\.part(\d+)$", lambda m: int(m.group(1))),
            ],
        },
        "cab": {
            "extensions": [".cab"],
            "multipart_patterns": [(r"\.cab\.part(\d+)$", lambda m: int(m.group(1)))],
        },
        "lzh": {
            "extensions": [".lzh", ".lha"],
            "multipart_patterns": [
                (r"\.lzh\.part(\d+)$", lambda m: int(m.group(1))),
                (r"\.lha\.part(\d+)$", lambda m: int(m.group(1))),
            ],
        },
        "ace": {
            "extensions": [".ace"],
            "multipart_patterns": [
                (r"\.ace\.(\d{3})$", lambda m: int(m.group(1))),
                (r"\.c(\d{2})$", lambda m: int(m.group(1))),
                (r"\.ace\.part(\d+)$", lambda m: int(m.group(1))),
            ],
        },
        "iso": {
            "extensions": [".iso", ".img", ".bin"],
            "multipart_patterns": [
                (r"\.iso\.part(\d+)$", lambda m: int(m.group(1))),
                (r"\.img\.part(\d+)$", lambda m: int(m.group(1))),
                (r"\.bin\.part(\d+)$", lambda m: int(m.group(1))),
            ],
        },
    }

    # Check each archive type
    for archive_type, patterns in archive_patterns.items():
        # First check for multipart patterns
        for pattern, extract_func in patterns["multipart_patterns"]:
            match = re.search(pattern, filename)
            if match:
                part_number = extract_func(match)
                return {
                    "type": archive_type,
                    "is_multipart": True,
                    "part_number": part_number,
                }

        # Then check for single archive files
        for ext in patterns["extensions"]:
            if filename.endswith(ext):
                return {"type": archive_type, "is_multipart": False, "part_number": 1}

    # If no pattern matched, try to detect by file signature (magic bytes)
    if os.path.exists(filepath):
        archive_type = _detectBySignature(filepath)
        if archive_type:
            return {"type": archive_type, "is_multipart": False, "part_number": 1}

    return None


def _detectBySignature(filepath: str) -> str | None:
    """Detect archive type by reading file signature (magic bytes)."""
    try:
        with open(filepath, "rb") as f:
            # Read first 16 bytes for signature detection
            header = f.read(16)

            if len(header) < 4:
                return None

            # Check for standard archive signatures first
            # 7z signature
            if header.startswith(b"7z\xbc\xaf\x27\x1c"):
                return "7z"

            # RAR signatures
            if header.startswith(b"Rar!\x1a\x07\x00") or header.startswith(
                b"Rar!\x1a\x07\x01\x00"
            ):
                return "rar"

            # ZIP signature
            if (
                header.startswith(b"PK\x03\x04")
                or header.startswith(b"PK\x05\x06")
                or header.startswith(b"PK\x07\x08")
            ):
                return "zip"

            # GZIP signature
            if header.startswith(b"\x1f\x8b"):
                return "gz"

            # BZIP2 signature
            if header.startswith(b"BZ"):
                return "bz2"

            # XZ signature
            if header.startswith(b"\xfd7zXZ\x00"):
                return "xz"

            # ARJ signature
            if header.startswith(b"\x60\xea"):
                return "arj"

            # CAB signature
            if header.startswith(b"MSCF"):
                return "cab"

            # LZH signatures
            if b"-lh" in header[:10] or b"-lz" in header[:10]:
                return "lzh"

            # ACE signature
            if header.startswith(b"**ACE**"):
                return "ace"

            # ISO signature (CD001 at offset 32769, but we'll check a simpler pattern)
            if b"CD001" in header:
                return "iso"

            # Check for self-extracting archives (SFX)
            # If it's an executable file, search for embedded archive signatures
            if header.startswith(b"MZ"):  # PE executable signature
                f.seek(0)
                # Read more data to search for embedded archive signatures
                # SFX archives typically have the archive data after the executable stub
                chunk_size = 8192
                search_limit = min(
                    1024 * 1024, f.seek(0, 2)
                )  # Search first 1MB or file size
                f.seek(0)

                # Skip the PE header and DOS stub to avoid false positives
                # Most SFX archives have the embedded data after the executable section
                pe_header_size = 1024  # Skip first 1KB which contains PE headers
                f.seek(pe_header_size)

                archive_signatures_found = []
                pos = pe_header_size

                while pos < search_limit:
                    chunk = f.read(chunk_size)
                    if len(chunk) == 0:
                        break

                    # Search for archive signatures in the chunk
                    # 7z signature
                    if b"7z\xbc\xaf\x27\x1c" in chunk:
                        archive_signatures_found.append("7z")

                    # RAR signatures
                    if b"Rar!\x1a\x07\x00" in chunk or b"Rar!\x1a\x07\x01\x00" in chunk:
                        archive_signatures_found.append("rar")

                    # ZIP signature (look for central directory signature too for better confidence)
                    if b"PK\x03\x04" in chunk:
                        # Also check for central directory signature for higher confidence
                        if b"PK\x01\x02" in chunk or b"PK\x05\x06" in chunk:
                            archive_signatures_found.append("zip")
                        else:
                            # Just local file header, could be a false positive
                            # Check if we have more ZIP-like structure
                            zip_count = chunk.count(b"PK\x03\x04")
                            if zip_count >= 2:  # Multiple entries suggest real ZIP
                                archive_signatures_found.append("zip")

                    # CAB signature (common in SFX)
                    if b"MSCF" in chunk:
                        archive_signatures_found.append("cab")

                    pos += chunk_size - 32  # Larger overlap to catch split signatures
                    f.seek(pos)

                # Only return archive type if we found strong evidence
                if archive_signatures_found:
                    # Return the most common signature found, or the first one
                    from collections import Counter

                    signature_counts = Counter(archive_signatures_found)
                    return signature_counts.most_common(1)[0][0]

    except (IOError, OSError):
        pass

    return None
