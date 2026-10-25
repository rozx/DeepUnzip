import hashlib
import stat
import tarfile
import zipfile

import pytest

from scripts import release


@pytest.fixture
def project(tmp_path):
    (tmp_path / "deepunzip").mkdir()
    (tmp_path / "deepunzip" / "__init__.py").write_text(
        '__version__ = "1.3.0"\n'
    )
    (tmp_path / "pyproject.toml").write_text('[tool.poetry]\nversion = "1.3.0"\n')
    (tmp_path / ".bumpversion.cfg").write_text(
        "[bumpversion]\ncurrent_version = 1.3.0\n"
    )
    return tmp_path


def test_release_version_matches_all_declarations(project):
    assert release.read_version(project) == "1.3.0"


def test_release_notes_are_read_from_matching_version_file(project):
    notes = "# v1.3.0 发布说明\n\n- Native builds\n"
    directory = project / "docs" / "releaseNotes"
    directory.mkdir(parents=True)
    (directory / "v1.3.0.md").write_text(notes, encoding="utf-8")
    assert release.read_release_notes(project) == notes


@pytest.mark.parametrize("contents", [None, " \n\t"])
def test_missing_or_empty_release_notes_fail_without_fallback(project, contents):
    directory = project / "docs" / "releaseNotes"
    directory.mkdir(parents=True)
    (directory / "v1.2.2.md").write_text("Previous version")
    if contents is not None:
        (directory / "v1.3.0.md").write_text(contents)
    with pytest.raises(ValueError, match=r"v1\.3\.0\.md"):
        release.read_release_notes(project)


@pytest.mark.parametrize(
    "ref", ["release/1.3.0", "release/v1.3.0", "release/rename", "release/v1.3"]
)
def test_release_branch_matching_or_non_version_suffix_passes(project, ref):
    release.verify_branch(ref, project)


@pytest.mark.parametrize("ref", ["release/1.3.1", "release/v2.0.0"])
def test_release_branch_version_must_match_project_version(project, ref):
    with pytest.raises(ValueError, match="1.3.0"):
        release.verify_branch(ref, project)


def test_release_branch_must_start_with_release(project):
    with pytest.raises(ValueError, match="release/"):
        release.verify_branch("feature/1.3.0", project)


@pytest.mark.parametrize("bad_version", ["1.2.2", "1.3.0rc1", "1.3"])
def test_release_version_rejects_inconsistent_or_nonstable_versions(
    project, bad_version
):
    (project / "pyproject.toml").write_text(
        f'[tool.poetry]\nversion = "{bad_version}"\n'
    )
    with pytest.raises(ValueError):
        release.read_version(project)


@pytest.mark.parametrize(
    "target,executable,license_path,suffix",
    [
        (
            "windows-x64",
            "complex-unzip-tool-v2.exe",
            "7z/windows-x64/License.txt",
            ".zip",
        ),
        ("macos-arm64", "complex-unzip-tool-v2", "7z/macos/License.txt", ".tar.gz"),
    ],
)
def test_package_contains_executable_notices_and_checksum(
    project, target, executable, license_path, suffix
):
    (project / "dist").mkdir()
    binary = project / "dist" / executable
    binary.write_bytes(b"standalone program")
    binary.chmod(0o755)
    # Windows chmod cannot set POSIX execute bits; preserve the host's file mode.
    expected_mode = stat.S_IMODE(binary.stat().st_mode)
    notice = project / license_path
    notice.parent.mkdir(parents=True)
    notice.write_text("upstream notice")
    for name in ("LICENSE", "README.md", "README.en.md", "7z/manifest.json"):
        (project / name).write_text("documentation")
    archive = release.package(project, target, project / "artifacts")
    assert archive.name == f"complex-unzip-tool-v2-v1.3.0-{target}{suffix}"
    expected_names = {
        executable,
        "LICENSE",
        "README.md",
        "README.en.md",
        "7-Zip-License.txt",
        "7-Zip-manifest.json",
    }
    if suffix == ".zip":
        with zipfile.ZipFile(archive) as zipped:
            assert set(zipped.namelist()) == expected_names
            assert zipped.read(executable) == binary.read_bytes()
    else:
        with tarfile.open(archive) as tar:
            assert set(tar.getnames()) == expected_names
            assert tar.getmember(executable).mode == expected_mode
            assert tar.extractfile(executable).read() == binary.read_bytes()
    assert archive.with_name(archive.name + ".sha256").read_text() == (
        f"{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}\n"
    )


def release_assets(directory):
    expected = {}
    for target in (
        "windows-x64",
        "macos-x64",
        "macos-arm64",
        "linux-x64",
        "linux-arm64",
    ):
        extension = "zip" if target == "windows-x64" else "tar.gz"
        archive = directory / f"complex-unzip-tool-v2-v1.3.0-{target}.{extension}"
        archive.write_bytes(target.encode())
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        expected[archive.name] = f"{digest}  {archive.name}\n"
        archive.with_name(archive.name + ".sha256").write_text(
            f"{digest}  {archive.name}\n"
        )
    return expected


def test_verify_complete_release_writes_checksum_index(tmp_path):
    expected = release_assets(tmp_path)
    index = release.verify_assets(tmp_path, "1.3.0")
    assert index.name == "SHA256SUMS"
    assert index.read_text() == "".join(expected[name] for name in sorted(expected))


@pytest.mark.parametrize("problem", ["missing", "tampered", "unexpected"])
def test_incomplete_or_tampered_release_is_rejected(tmp_path, problem):
    release_assets(tmp_path)
    archive = tmp_path / "complex-unzip-tool-v2-v1.3.0-linux-x64.tar.gz"
    if problem == "missing":
        archive.unlink()
    elif problem == "tampered":
        archive.write_bytes(b"different build")
    else:
        (tmp_path / "unexpected.zip").touch()
    with pytest.raises(ValueError):
        release.verify_assets(tmp_path, "1.3.0")
    assert not (tmp_path / "SHA256SUMS").exists()
