"""
Regex patterns for multi-part archive detection and file naming.
用于多部分档案检测和文件命名的正则表达式模式。

Note: These patterns handle the base case only - files that are already properly
formatted after cloaked file detection and renaming. For cloaked file detection,
see the rule-based system in cloaked_file_detector.py.
注意：这些模式仅处理基本情况 - 在隐藏文件检测和重命名后已经正确格式化的文件。
对于隐藏文件检测，请参见 cloaked_file_detector.py 中基于规则的系统。
"""

# Part number patterns for extensionless files that might be archive parts
# 用于可能是档案部分的无扩展名文件的部分编号模式
PART_NUMBER_PATTERNS = [
    (r"(\d{3})$", 3),  # 3 digits like 001, 002, 003
    (r"(\d{2})$", 2),  # 2 digits like 01, 02, 03
    (r"(\d{1})$", 1),  # 1 digit like 1, 2, 3
]

# Multi-part archive format patterns (files that already have proper extensions)
# 多部分档案格式模式（已经有正确扩展名的文件）
MULTIPART_EXTENSION_PATTERNS = [
    r"\.(\d{3})$",  # .001, .002, .003, etc.
    r"\.(\d{2})$",  # .01, .02, .03, etc.
    r"\.(\d{1})$",  # .1, .2, .3, etc.
]

# Check for multipart archives (base case only - after cloaked files have been renamed)
# These patterns match different multipart archive conventions:
# - .7z.001, .7z.002, etc. (7z multipart with .00X)
# - .tar.gz.001, .tar.bz2.001, etc. (TAR multipart)
# - .<ext>.001, .<ext>.002, etc. (7-Zip generic volume split of ANY file, 3+ digits;
#   covers .zip.001, .rar.001, .iso.001, .bin.001, plain .tar.001, …)
# - .r00, .r01, etc. (RAR continuation parts)
# - .z01, .z02, etc. (ZIP continuation parts)
# - .zx01, .zx02, etc. (ZIPX continuation parts)
# - .a01, .a02, etc. (ARJ continuation parts)
# - .c00, .c01, etc. (ACE continuation parts)
# - .part1.rar, .part2.rar, etc. (RAR part notation)
# Note: .rar / .zip / .zipx / .arj / .ace primaries are ambiguous (could be single
# files or first parts) and are intentionally NOT matched here.
multipart_regex = (
    r"\.(?:"
    r"7z\.\d{1,3}"
    r"|tar\.(?:gz|bz2|xz)\.\d{1,3}"
    r"|[A-Za-z0-9]+\.\d{3,}"
    r"|r\d{2}|z\d{2}|zx\d{2}|a\d{2}|c\d{2}"
    r"|part\d+\.rar"
    r")$"
)

# Check if it's an unambiguous extraction entry point of a multipart archive.
# These patterns match the file 7-Zip needs to be invoked on to extract the set:
# - .7z.001, .tar.gz.001, etc. (first split-volume of .7z/.tar.*)
# - .part1.rar (first volume of standard RAR multi-volume)
# Note: .rar and .zip are NOT included here because they are ambiguous (could
# be standalone or the entry point of a spanned set). They are still treated
# as the highest-priority main archive for spanned ZIP / volume RAR sets via
# explicit handling in ArchiveGroup.add_file (which knows the full file list).
# - .<ext>.001 (first volume of a 7-Zip generic numbered split, 3+ digits)
# IMPORTANT: .r00 and .z01 are intentionally excluded — they are continuation
# parts, not extraction entry points; 7-Zip must be invoked on .rar / .zip.
first_part_regex = (
    r"\.(?:7z\.0*1|tar\.(?:gz|bz2|xz)\.0*1|[A-Za-z0-9]+\.0{2,}1|part0*1\.rar)$"
)
