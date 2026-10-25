import os
import re

from deepunzip.modules.regex import multipart_regex


def _entry_point_priority(file_path: str) -> int:
    """Score a file's suitability as the multipart extraction entry point.

    7-Zip must be invoked on the *primary* file of a multipart set, not on a
    continuation part. The mapping below reflects which filenames are valid
    entry points and ranks unambiguous primaries above ambiguous ones.

    Returns 0 for files that are NOT valid entry points (e.g., `.z01`, `.r00`,
    `.7z.002`) so they will never beat a real primary already chosen.
    """
    fname = os.path.basename(file_path).lower()

    # Unambiguous first parts
    if re.search(r"\.7z\.0*1$", fname):
        return 100
    if re.search(r"\.tar\.(?:gz|bz2|xz)\.0*1$", fname):
        return 100
    if re.search(r"\.part0*1\.rar$", fname):
        return 100
    # 7-Zip generic numbered split: `name.<ext>.001` is the entry point for ANY
    # base extension (.zip.001, .rar.001, .iso.001, …). 3+ zero-padded digits.
    if re.search(r"\.[a-z0-9]+\.0{2,}1$", fname):
        return 100

    # ZIP/RAR/ZIPX/ARJ/ACE primaries — entry points for their multi-volume sets,
    # and also valid for the standalone archive (lower priority so split-volume
    # primaries above always win when both exist).
    if re.search(r"\.part\d+\.rar$", fname):
        # .partN.rar where N != 1 — continuation, not entry point
        return 0
    if fname.endswith(".rar"):
        return 90
    if fname.endswith(".zip"):
        return 90
    if fname.endswith(".zipx"):
        return 90
    if fname.endswith(".arj"):
        return 90
    if fname.endswith(".ace"):
        return 90

    return 0


class ArchiveGroup:
    def __init__(self, name: str):
        self.name = name
        self.files = []
        self.mainArchiveFile = ""
        self.isMultiPart = False

    def add_file(self, file: str):
        self.files.append(file)
        # if it is a multipart archive
        if re.search(multipart_regex, file):
            self.isMultiPart = True

        # Pick the file with the highest extraction-entry-point priority as the
        # main archive. This guarantees spanned ZIP keeps `.zip` (not `.z01`)
        # and volume RAR keeps `.rar` (not `.r00`) as main, regardless of the
        # order files were added to the group.
        if not self.mainArchiveFile:
            self.set_main_archive(file)
            return

        new_priority = _entry_point_priority(file)
        cur_priority = _entry_point_priority(self.mainArchiveFile)
        if new_priority > cur_priority:
            self.set_main_archive(file)

    def set_main_archive(self, archive: str):
        # Set the archive as main - validation will happen during extraction
        self.mainArchiveFile = archive
        if re.search(multipart_regex, archive):
            self.isMultiPart = True

    def get_alternative_main_archives(self) -> list[str]:
        """
        Get list of alternative files in the group that could be the main archive.
        This is used when the default main archive fails extraction.
        Returns files in priority order (highest entry-point priority first).
        """
        candidates = [fp for fp in self.files if fp != self.mainArchiveFile]
        candidates.sort(key=_entry_point_priority, reverse=True)
        return candidates

    def try_set_alternative_main_archive(self) -> bool:
        """
        Try to set an alternative file as the main archive.
        Only considers files that actually exist.
        Returns True if an alternative was found and set, False otherwise.
        """
        import os

        alternatives = self.get_alternative_main_archives()
        for alternative in alternatives:
            if os.path.exists(alternative):
                # Found an existing alternative, set it as main
                self.set_main_archive(alternative)
                return True

        # No existing alternatives found
        return False
