"""
Rule-based cloaked file detection and renaming system.
基于规则的隐藏文件检测和重命名系统。
"""

import json
import os
import re
import uuid
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from complex_unzip_tool_v2.modules.events import notice
from complex_unzip_tool_v2.modules.archive_extension_utils import (
    detect_archive_extension,
    uncloak_archive_filename,
)
from complex_unzip_tool_v2.modules.regex import multipart_regex

# An explicit archive-type token (.7z/.rar/.zip) embedded in a filename means the
# user deliberately named the file as that archive type; the surrounding garbage
# is just cloaking. Such renames are trustworthy even for continuation parts that
# carry no signature. When NO token is present, the archive type is only a guess
# from a trailing numeric suffix and must be confirmed by the file's signature.
# 文件名中显式带有归档标记(.7z/.rar/.zip)说明用户有意将其命名为该归档类型，
# 周围的内容只是伪装；此类改名即使对无签名的续卷也是可信的。若没有该标记，
# 归档类型只是根据尾部数字猜测得到，必须由文件签名确认。
ARCHIVE_TOKEN_RE = re.compile(
    r"\.(?:7z|rar|zip)(?:\.|$|[^0-9A-Za-z])",
    re.IGNORECASE,
)


@dataclass
class CloakedFileRule:
    """
    Data class representing a cloaked file detection rule.
    表示隐藏文件检测规则的数据类。
    """

    name: str
    filename_pattern: str
    ext_pattern: str
    priority: int
    matching_type: str  # "both", "filename", "ext"
    type: str  # "7z", "rar", "zip", etc.
    enabled: bool

    def __post_init__(self):
        """Validate the rule after initialization."""
        if self.matching_type not in ["both", "filename", "ext"]:
            raise ValueError(f"Invalid matching_type: {self.matching_type}")

        if self.matching_type == "both" and (
            not self.filename_pattern or self.ext_pattern is None
        ):
            raise ValueError(
                "filename_pattern and ext_pattern (can be empty string) required for matching_type 'both'"
            )

        if self.matching_type == "filename" and not self.filename_pattern:
            raise ValueError("filename_pattern required for matching_type 'filename'")

        if self.matching_type == "ext" and not self.ext_pattern:
            raise ValueError("ext_pattern required for matching_type 'ext'")


class CloakedFileDetector:
    """
    Rule-based cloaked file detector and renamer.
    基于规则的隐藏文件检测器和重命名器。
    """

    def __init__(self, rules_file_path: str):
        """
        Initialize the detector with rules from a JSON file.
        使用JSON文件中的规则初始化检测器。

        Args:
            rules_file_path: Path to the JSON file containing rules
        """
        self.rules: List[CloakedFileRule] = []
        self.load_rules(rules_file_path)

    def load_rules(self, rules_file_path: str) -> None:
        """
        Load rules from a JSON configuration file.
        从JSON配置文件加载规则。

        Args:
            rules_file_path: Path to the JSON rules file
        """
        try:
            with open(rules_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.rules = []
            for rule_data in data.get("rules", []):
                rule = CloakedFileRule(
                    name=rule_data["name"],
                    filename_pattern=rule_data["filename_pattern"],
                    ext_pattern=rule_data["ext_pattern"],
                    priority=rule_data["priority"],
                    matching_type=rule_data["matching_type"],
                    type=rule_data["type"],
                    enabled=rule_data.get("enabled", True),
                )
                self.rules.append(rule)

            # Sort rules by priority (higher priority first)
            self.rules.sort(key=lambda r: r.priority, reverse=True)

        except Exception as e:
            notice("warning", "notice.rules_failed", path=rules_file_path, error=e)
            self.rules = []

    def _match_rule(
        self, filename: str, rule: CloakedFileRule
    ) -> Optional[Tuple[str, str, str]]:
        """
        Check if a filename matches a specific rule.
        检查文件名是否匹配特定规则。

        Args:
            filename: The filename to check
            rule: The rule to match against

        Returns:
            Tuple of (base_name, original_ext, part_number) if matched, None otherwise
        """
        if not rule.enabled:
            return None

        # Split filename into name and extension
        if "." in filename:
            name_part, ext_part = filename.rsplit(".", 1)
        else:
            name_part, ext_part = filename, ""

        base_name = ""
        part_number = ""
        original_ext = ""

        if rule.matching_type == "both":
            # For 'both' type, we need to be careful about what we match against
            # If the rule expects no extension (empty ext_pattern), match against full filename
            # Otherwise, match filename_pattern against name_part only
            if rule.ext_pattern == "":
                # Rule expects no extension, so match pattern against full filename
                filename_match = re.match(rule.filename_pattern, filename)
                ext_match = not ext_part  # True if no extension
            else:
                # Rule expects an extension, so match filename pattern against name part
                filename_match = re.match(rule.filename_pattern, name_part)
                ext_match = re.match(rule.ext_pattern, ext_part) if ext_part else False

            if filename_match and ext_match:
                groups = filename_match.groups()
                if len(groups) >= 1:
                    base_name = groups[0]

                # For empty ext_pattern, the part number should come from filename groups
                if rule.ext_pattern == "":
                    if len(groups) >= 2:
                        part_number = groups[1]  # Part number from filename pattern
                    # original_ext stays empty for extensionless files
                else:
                    if len(groups) >= 2:
                        original_ext = groups[1]

                    # Handle part number from extension if ext_pattern is not empty
                    if isinstance(ext_match, re.Match) and len(ext_match.groups()) >= 1:
                        part_number = ext_match.group(1)

                return (base_name, original_ext, part_number)

        elif rule.matching_type == "filename":
            # Match filename pattern only - use full filename for cloaked detection
            filename_match = re.match(rule.filename_pattern, filename)

            if filename_match:
                groups = filename_match.groups()
                if len(groups) >= 1:
                    base_name = groups[0]

                # Handle different pattern structures with validation
                if rule.type == "auto" and len(groups) >= 3:
                    # Pattern has (base_name, archive_type, part_number)
                    potential_ext = groups[1].strip() if groups[1] else ""
                    potential_part = groups[2].strip() if groups[2] else ""

                    # Validate archive type (should be alphanumeric, 2-4 chars typically)
                    if potential_ext and re.match(r"^[a-zA-Z0-9]{2,4}$", potential_ext):
                        original_ext = potential_ext
                    else:
                        original_ext = rule.type

                    # Validate part number (should be numeric)
                    if potential_part and (
                        potential_part.isdigit() or re.match(r"^\d+$", potential_part)
                    ):
                        part_number = potential_part
                    else:
                        part_number = ""

                elif len(groups) >= 2:
                    # Pattern has (base_name, part_number)
                    potential_part = groups[1].strip() if groups[1] else ""
                    original_ext = rule.type  # Use rule type

                    # Validate part number (should be numeric)
                    if potential_part and (
                        potential_part.isdigit() or re.match(r"^\d+$", potential_part)
                    ):
                        part_number = potential_part
                    else:
                        part_number = ""
                else:
                    # Single group - just base name
                    original_ext = rule.type
                    part_number = ""

                return (base_name, original_ext, part_number)

        elif rule.matching_type == "ext":
            # Match extension pattern only
            ext_match = re.match(rule.ext_pattern, ext_part) if ext_part else None

            if ext_match:
                base_name = name_part
                if len(ext_match.groups()) >= 1:
                    part_number = ext_match.group(1)
                return (base_name, original_ext, part_number)

        return None

    def detect_cloaked_file(self, file_path: str) -> Optional[str]:
        """
        Detect if a file is cloaked and return the proper filename.
        检测文件是否被隐藏并返回正确的文件名。

        Args:
            file_path: Full path to the file

        Returns:
            New filename with proper extension, or None if no changes needed
        """
        filename = os.path.basename(file_path)
        dirname = os.path.dirname(file_path)

        # Fast-path: skip already proper archive names to avoid unnecessary renames
        # 1) Proper multipart formats like: .7z.001, .rar.r00, .zip.z01, .tar.gz.001, .part1.rar
        if re.search(multipart_regex, filename, re.IGNORECASE):
            return None

        # 2) Proper single archive extensions (no cloaking suffixes)
        proper_single_exts = [
            ".7z",
            ".rar",
            ".zip",
            ".tar",
            ".tar.gz",
            ".tgz",
            ".tar.bz2",
            ".tbz2",
            ".tar.xz",
            ".txz",
            ".gz",
            ".bz2",
            ".xz",
            ".arj",
            ".cab",
            ".lzh",
            ".lha",
            ".ace",
            ".iso",
            ".img",
            ".bin",
        ]
        lower_name = filename.lower()
        if any(lower_name.endswith(ext) for ext in proper_single_exts):
            return None

        for rule in self.rules:
            match_result = self._match_rule(filename, rule)

            if match_result:
                base_name, original_ext, part_number = match_result

                # Skip if the file already has the target format
                if self._is_already_proper_format(filename, rule.type):
                    continue

                # Generate new filename based on rule
                new_filename = self._generate_new_filename(
                    base_name, original_ext, part_number, rule, file_path
                )

                if new_filename and new_filename != filename:
                    new_path = os.path.join(dirname, new_filename)

                    # Verify the detection with file signature if available
                    if self._verify_with_signature(file_path, rule.type, part_number):
                        return new_path

                    # If signature verification fails, continue to next rule
                    continue

        # Fallback: cloaking characters embedded *inside* the extension or the
        # part-number digits (e.g. "12.7z.0删02", "1.part2.r删ar") cannot be
        # expressed by the flat rules above, which only strip trailing garbage.
        # Reconstruct via the flexible archive-name uncloaker and accept it only
        # when the result is an unambiguous multipart/volume form, so ordinary
        # files are never renamed into bogus parts.
        embedded = uncloak_archive_filename(file_path)
        if (
            embedded
            and embedded != filename
            and re.search(multipart_regex, embedded, re.IGNORECASE)
        ):
            return os.path.join(dirname, embedded)

        return None

    def _is_already_proper_format(self, filename: str, archive_type: str) -> bool:
        """
        Check if file already has proper multi-part archive format.
        检查文件是否已经具有正确的多部分档案格式。

        Args:
            filename: The filename to check
            archive_type: Expected archive type

        Returns:
            True if file already has proper format, False otherwise
        """
        # Check if filename matches expected format like "file.7z.001"
        pattern = rf"^.+\.{re.escape(archive_type)}\.\d+$"
        return bool(re.match(pattern, filename, re.IGNORECASE))

    def _generate_new_filename(
        self,
        base_name: str,
        original_ext: str,
        part_number: str,
        rule: CloakedFileRule,
        file_path: str = None,
    ) -> Optional[str]:
        """
        Generate new filename based on matched rule.
        基于匹配的规则生成新文件名。

        Args:
            base_name: Base name without extension
            original_ext: Original extension (if any)
            part_number: Part number (if any)
            rule: The matched rule

        Returns:
            New filename or None if cannot generate
        """
        if not base_name:
            return None

        # Format part number consistently (pad with zeros if needed)
        if part_number:
            if part_number.isdigit():
                formatted_part = part_number.zfill(3)  # Pad to 3 digits
            else:
                formatted_part = part_number
        else:
            return f"{base_name}.{rule.type}"  # Single file, not multipart

        # Generate the new filename
        archive_type = original_ext if original_ext else rule.type

        # If archive_type is "auto", try to detect the actual type from file signature
        if archive_type == "auto":
            # Try to detect actual archive type from file signature
            try:
                if file_path and os.path.exists(file_path):
                    detected_type = detect_archive_extension(file_path)
                    if detected_type:
                        archive_type = detected_type
                    else:
                        archive_type = "7z"  # Default fallback if detection fails
                else:
                    archive_type = "7z"  # Default fallback if no file path
            except Exception:
                archive_type = "7z"  # Default fallback on error

        new_filename = f"{base_name}.{archive_type}.{formatted_part}"

        return new_filename

    def _verify_with_signature(
        self, file_path: str, expected_type: str, part_number: str = None
    ) -> bool:
        """
        Verify the detected archive type with file signature.
        使用文件签名验证检测到的档案类型。

        Args:
            file_path: Path to the file
            expected_type: Expected archive type
            part_number: Part number if this is a multipart archive (e.g., "001", "002")

        Returns:
            True if there is real evidence the file is an archive, False otherwise.
        """
        try:
            filename = os.path.basename(file_path)

            # The user explicitly named the file as a .7z/.rar/.zip archive; the
            # rest is just cloaking. Trust it even when this is a continuation
            # part that legitimately carries no signature (e.g. ".7z.002删除").
            if ARCHIVE_TOKEN_RE.search(filename):
                return True

            # No archive token in the name: the type was only guessed from a
            # trailing numeric suffix (e.g. "2382" -> "2.7z.382"). Require a real
            # archive signature so ordinary files are never mistaken for parts.
            detected_type = detect_archive_extension(file_path)
            if not detected_type:
                return False

            # A lone file that carries an archive signature can only be a whole
            # archive or the FIRST volume of a multipart set; the first
            # 7z/zip/rar volume is always ".001". If the type was guessed from
            # trailing digits that resolve to any other part number, those digits
            # are not a part index -- they are just part of the name (e.g. the
            # "705" of an "..._192705" timestamp). Refuse such renames so real
            # archives keep their name instead of becoming a bogus "part 705".
            if part_number:
                stripped = part_number.lstrip("0") or "0"
                if not (stripped.isdigit() and int(stripped) == 1):
                    return False

            return True

        except Exception as e:
            notice(
                "warning",
                "notice.signature_failed",
                name=os.path.basename(file_path),
                error=e,
            )
            return False  # Be conservative: do not rename on verification failure

    def _build_collision_path(self, file_path: str, normalized_path: str | None) -> str:
        """
        Build a unique collision path by appending a duplicate suffix.
        使用重复后缀生成唯一的冲突路径。
        """
        target_path = normalized_path or file_path
        base_dir = os.path.dirname(target_path)
        file_name = os.path.basename(target_path)
        base_name = file_name
        suffix = ""

        multipart_patterns = [
            r"^(?P<base>.+)\.(?P<archive>7z|zip|rar)\.(?P<part>\d{1,3})$",
            r"^(?P<base>.+)\.(?P<archive>zip|rar)\.(?P<part>[rz]\d{2})$",
            r"^(?P<base>.+)\.(?P<archive>tar\.(?:gz|bz2|xz))\.(?P<part>\d{1,3})$",
            r"^(?P<base>.+)\.part(?P<part>\d+)\.rar$",
        ]

        for pattern in multipart_patterns:
            match = re.match(pattern, file_name, re.IGNORECASE)
            if match:
                base_name = match.group("base")
                if "archive" in match.groupdict():
                    suffix = f".{match.group('archive')}.{match.group('part')}"
                else:
                    suffix = f".part{match.group('part')}.rar"
                break

        if not suffix:
            suffix_match = re.search(r"(\.\d{1,3})$", file_name)
            if suffix_match:
                base_name = file_name[: suffix_match.start()]
                suffix = suffix_match.group(1)

        token = self._build_collision_token(base_dir, base_name)
        counter = 0
        while True:
            counter_suffix = f"_{counter}" if counter else ""
            candidate_name = f"{base_name}__duplicate_{token}{counter_suffix}{suffix}"
            candidate = os.path.join(base_dir, candidate_name)
            if not os.path.exists(candidate):
                return candidate
            counter += 1

    def _build_collision_token(self, base_dir: str, base_name: str) -> str:
        """
        Build a deterministic token so multipart siblings share the same duplicate stem.
        生成确定性令牌，确保多分卷重复文件共享相同名称前缀。
        """
        seed = f"{base_dir}|{base_name}"
        return uuid.uuid5(uuid.NAMESPACE_URL, seed).hex[:8]

    def uncloak_file(self, file_path: str, history=None) -> str:
        """
        Uncloak a single file and rename it if needed.
        解除单个文件的隐藏并在需要时重命名。

        Args:
            file_path: Full path to the file to uncloak
            history: Optional RenameHistory to record successful renames

        Returns:
            New file path with proper extension, or original path if no changes needed
        """
        if not os.path.exists(file_path):
            return file_path

        new_path = self.detect_cloaked_file(file_path)

        if new_path and new_path != file_path:
            if os.path.exists(new_path):
                duplicate_path = self._build_collision_path(file_path, new_path)
                try:
                    os.rename(file_path, duplicate_path)
                    if history is not None:
                        history.record(file_path, duplicate_path)
                    notice(
                        "warning",
                        "notice.rename_duplicate",
                        name=os.path.basename(file_path),
                        existing=os.path.basename(new_path),
                        target=os.path.basename(duplicate_path),
                    )
                    return duplicate_path
                except Exception as e:
                    notice(
                        "warning",
                        "notice.rename_failed",
                        name=os.path.basename(file_path),
                        error=e,
                    )
                    return new_path
            try:
                # Rename the actual file
                os.rename(file_path, new_path)
                if history is not None:
                    history.record(file_path, new_path)
                return new_path
            except Exception as e:
                notice(
                    "warning",
                    "notice.rename_failed",
                    name=os.path.basename(file_path),
                    error=e,
                )
                return file_path

        return file_path

    def uncloak_files(self, file_paths: List[str], history=None) -> List[str]:
        """
        Uncloak multiple files and return updated paths.
        解除多个文件的隐藏并返回更新的路径。

        Args:
            file_paths: List of file paths to uncloak
            history: Optional RenameHistory to record successful renames

        Returns:
            List of updated file paths with proper extensions
        """
        updated_paths = []

        for file_path in file_paths:
            updated_path = self.uncloak_file(file_path, history=history)
            updated_paths.append(updated_path)

        return updated_paths

    def get_rule_info(self) -> Dict:
        """
        Get information about loaded rules.
        获取已加载规则的信息。

        Returns:
            Dictionary containing rule statistics and details
        """
        enabled_rules = [r for r in self.rules if r.enabled]
        disabled_rules = [r for r in self.rules if not r.enabled]

        return {
            "total_rules": len(self.rules),
            "enabled_rules": len(enabled_rules),
            "disabled_rules": len(disabled_rules),
            "rules_by_type": {
                rule_type: len([r for r in enabled_rules if r.type == rule_type])
                for rule_type in set(r.type for r in enabled_rules)
            },
            "highest_priority": (
                max(r.priority for r in self.rules) if self.rules else 0
            ),
            "lowest_priority": min(r.priority for r in self.rules) if self.rules else 0,
        }
