"""The five READMEs stay in step, and the old project name stays retired."""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
READMES = {
    "README.md": "简体中文",
    "README.en.md": "English",
    "README.zh-TW.md": "繁體中文",
    "README.ja.md": "日本語",
    "README.ko.md": "한국어",
}
OLD_NAME = re.compile(r"complex[-_ ]unzip[-_ ]tool[-_ ]v2|复杂解压工具|複雜解壓工具", re.IGNORECASE)
# History may keep the old name: release notes before 2.0.0 (and the rename
# notice of 2.0.0), and the OpenSpec changes that describe the rename. This
# file names it in OLD_NAME.
ALLOWED = re.compile(
    r"^(docs/releaseNotes/v1\.|docs/releaseNotes/v2\.0\.0\.md$|openspec/changes/"
    r"|tests/test_docs\.py$)"
)


def _text(name):
    return (ROOT / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("name", READMES)
def test_readme_has_the_switcher_with_its_language_marked(name):
    switcher = " | ".join(
        f"**{label}**" if other == name else f"[{label}]({other})"
        for other, label in READMES.items()
    )
    assert switcher in _text(name).splitlines()


@pytest.mark.parametrize("name", READMES)
def test_readme_sections_match_the_chinese_master(name):
    def sections(text):
        return len(re.findall(r"^## ", text, re.MULTILINE))

    assert sections(_text(name)) == sections(_text("README.md")) == 10


@pytest.mark.parametrize("name", READMES)
def test_readme_images_exist(name):
    text = _text(name)
    images = re.findall(r"!\[[^\]]*\]\(([^)\s]+)\)", text)
    images += re.findall(r'<img src="([^"]+)"', text)
    local = [image for image in images if not image.startswith("http")]
    assert "icons/app_icon.svg" in local, name
    assert all((ROOT / image).is_file() for image in local), local


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
def test_old_project_name_is_only_in_history():
    listed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    offenders = []
    for name in listed:
        path = ROOT / name
        if ALLOWED.match(name) or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binaries
        if OLD_NAME.search(text):
            offenders.append(name)
    assert offenders == []
