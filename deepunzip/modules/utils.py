import re
import os
import unicodedata
from difflib import SequenceMatcher


def sanitize_filename(filename: str, max_length: int = 100) -> str:
    """
    Sanitize a filename to be safe for Windows file systems.

    Args:
        filename (str): The original filename
        max_length (int): Maximum length for the filename (default: 100)

    Returns:
        str: Sanitized filename safe for Windows
    """
    if not filename:
        return "unnamed"

    # Normalize unicode characters
    filename = unicodedata.normalize("NFKD", filename)

    # Remove or replace invalid Windows filename characters
    # < > : " | ? * and control characters (0-31)
    invalid_chars = r'[<>:"|?*\x00-\x1f]'
    filename = re.sub(invalid_chars, "_", filename)

    # Replace additional problematic characters
    filename = filename.replace("/", "_").replace("\\", "_")

    # Remove leading/trailing spaces and dots (Windows doesn't like these)
    filename = filename.strip(" .")

    # Handle reserved Windows names
    reserved_names = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "COM6",
        "COM7",
        "COM8",
        "COM9",
        "LPT1",
        "LPT2",
        "LPT3",
        "LPT4",
        "LPT5",
        "LPT6",
        "LPT7",
        "LPT8",
        "LPT9",
    }

    name_without_ext = os.path.splitext(filename)[0].upper()
    if name_without_ext in reserved_names:
        filename = f"_{filename}"

    # Truncate if too long, keeping extension if present
    if len(filename) > max_length:
        name, ext = os.path.splitext(filename)
        if ext:
            max_name_length = max_length - len(ext)
            filename = name[:max_name_length] + ext
        else:
            filename = filename[:max_length]

    # Ensure we don't end up with an empty string
    if not filename or filename == ".":
        filename = "unnamed"

    return filename


def sanitize_path(path: str, max_path_length: int = 200) -> str:
    """
    Sanitize a full path to be safe for Windows file systems.

    Args:
        path (str): The original path
        max_path_length (int): Maximum total path length (default: 200)

    Returns:
        str: Sanitized path safe for Windows
    """
    if not path:
        return ""

    # Split path into components
    drive, path_without_drive = os.path.splitdrive(path)
    path_parts = path_without_drive.split(os.sep)

    # Sanitize each path component
    sanitized_parts = []
    for part in path_parts:
        if part:  # Skip empty parts
            sanitized_part = sanitize_filename(
                part, max_length=80
            )  # Shorter for path components
            sanitized_parts.append(sanitized_part)

    # Reconstruct path
    sanitized_path = os.path.join(drive, *sanitized_parts) if sanitized_parts else drive

    # If path is still too long, truncate path components from the middle
    if len(sanitized_path) > max_path_length and len(sanitized_parts) > 1:
        # Calculate how much we need to reduce
        excess_length = len(sanitized_path) - max_path_length

        # Reduce each component proportionally, but keep at least 10 chars each
        for i in range(len(sanitized_parts)):
            if excess_length <= 0:
                break

            current_len = len(sanitized_parts[i])
            if current_len > 15:  # Only reduce if component is reasonably long
                reduction = min(excess_length, current_len - 10)
                name, ext = os.path.splitext(sanitized_parts[i])
                if ext:
                    new_name_len = len(name) - reduction
                    if new_name_len > 5:
                        sanitized_parts[i] = name[:new_name_len] + ext
                        excess_length -= reduction
                else:
                    new_len = current_len - reduction
                    if new_len > 5:
                        sanitized_parts[i] = sanitized_parts[i][:new_len]
                        excess_length -= reduction

        sanitized_path = os.path.join(drive, *sanitized_parts)

    return sanitized_path


def get_string_similarity(str1, str2):
    """
    Calculate similarity between two strings using SequenceMatcher.

    Args:
        str1 (str): First string to compare
        str2 (str): Second string to compare

    Returns:
        float: Similarity ratio between 0.0 (no similarity) and 1.0 (identical)
    """
    if not str1 and not str2:
        return 1.0
    if not str1 or not str2:
        return 0.0

    return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()
