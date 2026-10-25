"""Rename history with revert-on-failure for cloaked-file uncloaking.

Tracks every successful in-place rename performed by the cloaked-file detector
so that, if a downstream extraction step fails for the corresponding archive
group, the renamed source files can be put back to their original names. This
preserves the user's ability to handle failed groups manually.

Persistence is eager — every record/revert/clear writes the JSON file
atomically (temp + os.replace) so a crash mid-run still leaves a recoverable
record. The file lives at `<input_root>/.unzip-rename-history.tmp.json` and
is removed on clean completion.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime
from typing import Optional


HISTORY_FILENAME = ".unzip-rename-history.tmp.json"
SCHEMA_VERSION = 1
KIND_UNCLOAK = "uncloak"
KIND_RELOCATION = "relocation"


class RenameHistory:
    """In-memory + on-disk record of uncloak renames bound to archive groups."""

    def __init__(self, input_root: str, started_at: Optional[str] = None):
        self.input_root = os.path.abspath(input_root)
        self.started_at = started_at or datetime.now().isoformat(timespec="seconds")
        self.entries: list[dict] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(self, original: str, renamed: str, kind: str = KIND_UNCLOAK) -> None:
        """Record a successful rename of a source file. Entry starts unbound.

        `kind` is "uncloak" for cloaked-name normalization, or "relocation"
        for a source volume temporarily moved for multipart assembly.
        """
        self.entries.append(
            {
                "original": os.path.abspath(original),
                "renamed": os.path.abspath(renamed),
                "group": None,
                "kind": kind,
            }
        )
        self._persist()

    def clear_relocation(self, renamed: str) -> None:
        """Drop the relocation entry of a volume that was moved back."""
        target = os.path.abspath(renamed)
        before = len(self.entries)
        self.entries = [
            e
            for e in self.entries
            if not (e.get("kind") == KIND_RELOCATION and e["renamed"] == target)
        ]
        if len(self.entries) != before:
            self._persist()

    def restore_relocations(self) -> int:
        """Move every relocated source volume back; return how many moved.

        Used at startup after an interrupted run, without asking: these are
        tool moves that would otherwise strand a source in a work directory.
        """
        restored = 0
        for entry in [e for e in self.entries if e.get("kind") == KIND_RELOCATION]:
            renamed, original = entry["renamed"], entry["original"]
            if os.path.exists(renamed):
                target = original
                if os.path.exists(target):
                    target = self._collision_safe_path(original)
                try:
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    os.replace(renamed, target)
                except OSError:
                    continue
                restored += 1
            self.entries.remove(entry)
            self._persist()
        return restored

    def uncloak_entries(self) -> list[dict]:
        return [e for e in self.entries if e.get("kind") == KIND_UNCLOAK]

    def clear_for(self, renamed_path: str) -> int:
        """Drop the uncloak entries of a deleted source. Returns count."""
        target = os.path.abspath(renamed_path)
        before = len(self.entries)
        self.entries = [
            e
            for e in self.entries
            if not (e.get("kind") == KIND_UNCLOAK and e["renamed"] == target)
        ]
        cleared = before - len(self.entries)
        if cleared:
            self._persist()
        return cleared

    def bind(self, renamed_path: str, group_key: str) -> bool:
        """Bind the entry whose `renamed` matches the given path to a group key.

        Returns True if an entry was bound, False if no matching entry exists.
        """
        target = os.path.abspath(renamed_path)
        for entry in self.entries:
            if entry["renamed"] == target and entry["group"] is None:
                entry["group"] = group_key
                self._persist()
                return True
        return False

    def revert_group(self, group_key: str) -> tuple[int, list[tuple[str, str]]]:
        """Rename every file bound to `group_key` back to its original path.

        Returns (count_reverted, sample) where sample is up to 5 tuples of
        (renamed_basename, original_basename) for UI display.
        """
        sample: list[tuple[str, str]] = []
        reverted = 0

        # Iterate over a snapshot since we mutate during the loop
        for entry in [e for e in self.entries if e.get("group") == group_key]:
            renamed = entry["renamed"]
            original = entry["original"]

            if not os.path.exists(renamed):
                # Nothing to revert; drop the entry quietly
                self.entries.remove(entry)
                self._persist()
                continue

            target = original
            if os.path.exists(target):
                target = self._collision_safe_path(original)

            try:
                os.rename(renamed, target)
            except OSError:
                # Best-effort; leave the entry so a later run can retry
                continue

            reverted += 1
            if len(sample) < 5:
                sample.append((os.path.basename(renamed), os.path.basename(target)))
            self.entries.remove(entry)
            self._persist()

        return reverted, sample

    def clear_group(self, group_key: str) -> int:
        """Drop every entry bound to `group_key` without reverting. Returns count."""
        before = len(self.entries)
        self.entries = [e for e in self.entries if e.get("group") != group_key]
        cleared = before - len(self.entries)
        if cleared:
            self._persist()
        return cleared

    def revert_unbound(self) -> tuple[int, list[tuple[str, str]]]:
        """Revert every entry that was never bound to a group.

        These are renames whose `renamed` file disappeared from any group
        before binding ran (e.g., it was extracted away or moved). Treated
        as "lost track" → revert defensively.
        """
        sample: list[tuple[str, str]] = []
        reverted = 0

        for entry in [e for e in self.entries if e.get("group") is None]:
            renamed = entry["renamed"]
            original = entry["original"]

            if not os.path.exists(renamed):
                self.entries.remove(entry)
                self._persist()
                continue

            target = original
            if os.path.exists(target):
                target = self._collision_safe_path(original)

            try:
                os.rename(renamed, target)
            except OSError:
                continue

            reverted += 1
            if len(sample) < 5:
                sample.append((os.path.basename(renamed), os.path.basename(target)))
            self.entries.remove(entry)
            self._persist()

        return reverted, sample

    def finalize(self) -> None:
        """Delete the on-disk file when no entries remain; leave it otherwise."""
        if self.entries:
            return
        path = self._history_path()
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Recovery
    # ------------------------------------------------------------------

    @classmethod
    def load_pending(cls, input_root: str) -> Optional["RenameHistory"]:
        """Return a populated history if a leftover file exists with entries.

        Returns None if no leftover file, the file is empty/invalid, or the
        file contains zero entries.
        """
        root = os.path.abspath(input_root)
        path = os.path.join(root, HISTORY_FILENAME)
        if not os.path.exists(path):
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return None

        entries = data.get("entries", [])
        if not entries:
            return None

        history = cls(
            input_root=data.get("input_root", root),
            started_at=data.get("started_at"),
        )
        # Files written by 1.3.x have no kind; all of their entries are uncloaks.
        for entry in entries:
            entry.setdefault("kind", KIND_UNCLOAK)
        history.entries = entries
        return history

    def root_matches(self, input_root: str) -> bool:
        """Whether this history was created against the given input root."""
        return os.path.abspath(input_root) == self.input_root

    def has_entries(self) -> bool:
        return bool(self.entries)

    def bound_group_keys(self) -> list[str]:
        seen: list[str] = []
        for entry in self.entries:
            key = entry.get("group")
            if key and key not in seen:
                seen.append(key)
        return seen

    def delete_file(self) -> None:
        """Force-delete the on-disk history file, regardless of entries."""
        path = self._history_path()
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _history_path(self) -> str:
        return os.path.join(self.input_root, HISTORY_FILENAME)

    def _persist(self) -> None:
        path = self._history_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
        except OSError:
            pass

        payload = {
            "version": SCHEMA_VERSION,
            "input_root": self.input_root,
            "started_at": self.started_at,
            "entries": self.entries,
        }

        tmp_path = path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
            os.replace(tmp_path, path)
        except OSError:
            # If we cannot persist, fall back to leaving prior state in place.
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass

    @staticmethod
    def _collision_safe_path(original: str) -> str:
        """Pick a unique fallback path when reverting would clobber an existing file.

        Mirrors the `_build_collision_path` naming convention from
        cloaked_file_detector so the user sees consistent suffixes.
        """
        base_dir = os.path.dirname(original)
        file_name = os.path.basename(original)

        suffix = ""
        base_name = file_name
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
            stem, ext = os.path.splitext(file_name)
            base_name = stem
            suffix = ext

        token = uuid.uuid5(uuid.NAMESPACE_URL, f"{base_dir}|{base_name}").hex[:8]
        counter = 0
        while True:
            counter_suffix = f"_{counter}" if counter else ""
            candidate = os.path.join(
                base_dir,
                f"{base_name}__reverted_{token}{counter_suffix}{suffix}",
            )
            if not os.path.exists(candidate):
                return candidate
            counter += 1


class RelocationLog:
    """Work-pool relocation log persisted as `relocation` history entries."""

    def __init__(self, history: RenameHistory) -> None:
        self.history = history

    def record(self, original: str, renamed: str) -> None:
        self.history.record(original, renamed, kind=KIND_RELOCATION)

    def clear(self, renamed: str) -> None:
        self.history.clear_relocation(renamed)
