OUTPUT_FOLDER = "unzipped"

# Run work directory created inside each input root by the work pool
# 工作池在每个输入根目录中创建的运行工作目录
WORK_DIR_PREFIX = "temp.deepunzip-"

# Files to ignore when scanning directories
# 扫描目录时忽略的文件
IGNORED_FILES = {".DS_Store", "thumbs.db", "desktop.ini", "passwords.txt"}


# Multi-part archive patterns for detecting split archives
# 多部分档案模式，用于检测分割档案
MULTI_PART_PATTERNS = [
    r"\.7z\.\d+$",  # .7z.001, .7z.002, etc.
    r"\.rar\.part\d+$",  # .rar.part1, .rar.part2, etc.
    r"\.zip\.\d+$",  # .zip.001, .zip.002, etc.
    r"\.tar\.gz\.\d+$",  # .tar.gz.001, etc.
    r"\.tar\.bz2\.\d+$",  # .tar.bz2.001, etc.
    r"\.tar\.xz\.\d+$",  # .tar.xz.001, etc.
    r"\.part\d+\.rar$",  # .part1.rar, .part2.rar (standard RAR multi-volume)
    r"\.r\d{2}$",  # .r00, .r01 (legacy RAR continuation parts)
    r"\.z\d{2}$",  # .z01, .z02 (spanned ZIP continuation parts)
    r"\.\w+\.part\d+$",  # generic .ext.part1 format
]

# Common filesystem/path error keywords from 7z outputs to detect path-related failures
# 7z输出中常见的文件系统/路径错误关键词，用于检测路径相关故障
PATH_ERROR_KEYWORDS = [
    "cannot create folder",
    "cannot open output file",
    "the system cannot find the path specified",
    "path",
    "file name",
    "directory",
    "cannot create",
    "access denied",
    "permission",
    "disk full",
    "not enough space",
]
