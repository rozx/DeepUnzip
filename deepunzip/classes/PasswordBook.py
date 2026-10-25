import re
import sys
from pathlib import Path
from typing import Optional

_BOM = chr(0xFEFF)
# A password that really starts with # is written with a leading backslash
# (\#abc), like .gitignore; one backslash is added on save, removed on load.
_ESCAPED_HASH_RE = re.compile(r"^\\+#")
_NEEDS_ESCAPE_RE = re.compile(r"^\\*#")


class PasswordBook:
    def __init__(self) -> None:
        self.local_entries: list[str] = []
        self.dest_entries: list[str] = []
        self._has_changes: bool = False  # Track if there are unsaved changes

        # Portable builds use the real executable directory, never _MEIPASS or CWD.
        tool_root = (
            Path(sys.executable).absolute().parent
            if getattr(sys, "frozen", False)
            else Path(__file__).resolve().parents[2]
        )
        self.password_file = tool_root / "passwords.txt"
        self.load_passwords(str(self.password_file), True)

    @staticmethod
    def _password_token(line: str) -> Optional[str]:
        """Return the password on a line, or None for blank/# comment lines."""
        token = line.strip().strip(_BOM)  # remove BOM if any and trim
        if not token or token.startswith("#"):
            return None
        if _ESCAPED_HASH_RE.match(token):
            return token[1:]
        return token

    @staticmethod
    def _password_line(password: str) -> str:
        """Return the file line for a password, escaping a leading #."""
        if _NEEDS_ESCAPE_RE.match(password):
            return "\\" + password
        return password

    @staticmethod
    def _read_lines(path: str) -> list[str]:
        """Read a password book's lines, detecting its text encoding."""
        # Try multiple encodings to handle files containing Chinese characters or BOM
        encodings = [
            "utf-8-sig",  # handles BOM if present
            "utf-8",
            "gbk",
            "gb2312",
            "big5",
            "utf-16",
            "utf-16-le",
            "utf-16-be",
        ]
        content_lines: list[str] = []
        for enc in encodings:
            try:
                with open(path, "r", encoding=enc, errors="strict") as f:
                    content_lines = f.readlines()
                break
            except (OSError, UnicodeError):
                # Try next encoding
                content_lines = []
                continue

        if not content_lines:
            # Best-effort fallback that ignores decode errors
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content_lines = f.readlines()
            except OSError:
                # File not found or unreadable; nothing to load
                content_lines = []

        return content_lines

    def load_passwords(self, path: str, is_local: bool = False) -> None:
        """Load passwords from a file 从文件加载密码"""
        cleaned: list[str] = []
        for line in self._read_lines(path):
            token = self._password_token(line)  # skips empty and # comment lines
            if token is not None:
                cleaned.append(token)

        if cleaned:
            if is_local:
                self.local_entries.extend(cleaned)
            else:
                self.dest_entries.extend(cleaned)

        # make sure passwords are unique
        self.local_entries = list(dict.fromkeys(self.local_entries))
        self.dest_entries = list(dict.fromkeys(self.dest_entries))

    def save_passwords(self, force: bool = False) -> None:
        """Save passwords to local 将密码保存到本地"""
        if not self._has_changes and not force:
            return  # No changes to save

        # Update the existing book in place so the user's comments, blank lines
        # and ordering survive; removed passwords are dropped, new ones appended.
        current = set(self.local_entries)
        lines: list[str] = []
        written: set[str] = set()
        for line in self._read_lines(str(self.password_file)):
            token = self._password_token(line)
            if token is not None:
                if token not in current:
                    continue
                written.add(token)
            lines.append(line.rstrip("\r\n").lstrip(_BOM))
        lines.extend(
            self._password_line(entry)
            for entry in self.local_entries
            if entry not in written
        )

        with open(self.password_file, "w", encoding="utf-8") as f:
            for line in lines:
                f.write(f"{line}\n")

        self._has_changes = False  # Reset change tracking after save

    def get_passwords(self) -> list[str]:
        """Get all passwords 获取所有密码"""
        return list(dict.fromkeys(self.local_entries + self.dest_entries))

    def add_password(self, password: str) -> None:
        """Add a single password 添加单个密码"""
        if password:
            original_length = len(self.local_entries)
            self.local_entries.append(password)
            self.local_entries = list(dict.fromkeys(self.local_entries))

            # Mark as changed only if a new password was actually added
            if len(self.local_entries) > original_length:
                self._has_changes = True

    def add_passwords(self, passwords: list[str]) -> None:
        """Add multiple passwords 添加多个密码"""
        if passwords:
            original_length = len(self.local_entries)
            self.local_entries.extend(passwords)
            self.local_entries = list(dict.fromkeys(self.local_entries))

            # Mark as changed only if new passwords were actually added
            if len(self.local_entries) > original_length:
                self._has_changes = True

    def remove_password(self, password: str) -> None:
        """Remove a password 删除密码"""
        if password in self.local_entries:
            self.local_entries.remove(password)
            self._has_changes = True
        else:
            raise ValueError(f"Password '{password}' not found in local entries.")

    def has_unsaved_changes(self) -> bool:
        """Check if there are unsaved changes 检查是否有未保存的更改"""
        return self._has_changes
