"""Unit tests for file_utils module."""

import os
import tempfile
import shutil
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

import complex_unzip_tool_v2.modules.file_utils as fu
from complex_unzip_tool_v2.classes.ArchiveGroup import ArchiveGroup


class TestGetArchiveBaseName:
    """Tests for get_archive_base_name function."""

    def test_regular_archive_files(self):
        """Test with regular archive files."""
        assert fu.get_archive_base_name("test.zip") == ("test", "zip")
        assert fu.get_archive_base_name("archive.7z") == ("archive", "7z")
        assert fu.get_archive_base_name("file.tar.gz") == ("file.tar", "gz")

    def test_multipart_archive_files(self):
        """Test with multipart archive files."""
        assert fu.get_archive_base_name("archive.7z.001") == ("archive", "7z")
        assert fu.get_archive_base_name("test.rar.part1") == ("test", "rar")
        assert fu.get_archive_base_name("data.zip.001") == ("data", "zip")

    def test_path_with_directories(self):
        """Test with file paths containing directories."""
        assert fu.get_archive_base_name("/path/to/test.zip") == ("test", "zip")
        assert fu.get_archive_base_name(os.path.join("folder", "archive.7z.001")) == (
            "archive",
            "7z",
        )

    def test_files_without_extension(self):
        """Test with files without extensions."""
        assert fu.get_archive_base_name("filename") == ("filename", "")

    def test_hidden_files(self):
        """Test with hidden files."""
        assert fu.get_archive_base_name(".hidden.zip") == (".hidden", "zip")

    def test_spanned_zip_continuation_returns_zip_family(self):
        """Spanned ZIP continuation parts must share the .zip family extension."""
        assert fu.get_archive_base_name("set.zip") == ("set", "zip")
        assert fu.get_archive_base_name("set.z01") == ("set", "zip")
        assert fu.get_archive_base_name("set.z02") == ("set", "zip")
        assert fu.get_archive_base_name("set.z99") == ("set", "zip")

    def test_volume_rar_continuation_returns_rar_family(self):
        """Volume RAR continuation parts must share the .rar family extension."""
        assert fu.get_archive_base_name("arc.rar") == ("arc", "rar")
        assert fu.get_archive_base_name("arc.r00") == ("arc", "rar")
        assert fu.get_archive_base_name("arc.r01") == ("arc", "rar")

    def test_partN_rar_returns_rar_family(self):
        """Standard .partN.rar volumes must share the .rar family extension."""
        assert fu.get_archive_base_name("data.part1.rar") == ("data", "rar")
        assert fu.get_archive_base_name("data.part2.rar") == ("data", "rar")
        assert fu.get_archive_base_name("data.part10.rar") == ("data", "rar")

    def test_generic_numbered_split_returns_token_family(self):
        """7-Zip generic numbered splits keep the token before the number as the
        family ext, so all parts of one set share (base, ext)."""
        assert fu.get_archive_base_name("a.rar.001") == ("a", "rar")
        assert fu.get_archive_base_name("a.rar.002") == ("a", "rar")
        assert fu.get_archive_base_name("a.iso.001") == ("a", "iso")
        assert fu.get_archive_base_name("a.bin.002") == ("a", "bin")
        assert fu.get_archive_base_name("a.tar.001") == ("a", "tar")

    def test_generic_numbered_split_does_not_change_specific_formats(self):
        """The generic rule must run AFTER the specific ones: 7z/zip/tar split
        parsing stays exactly as before."""
        assert fu.get_archive_base_name("a.7z.001") == ("a", "7z")
        assert fu.get_archive_base_name("a.zip.001") == ("a", "zip")
        assert fu.get_archive_base_name("a.tar.gz.001") == ("a", "tar")

    def test_zipx_split_returns_zipx_family(self):
        """WinZip ZIPX split parts share the .zipx family extension."""
        assert fu.get_archive_base_name("a.zipx") == ("a", "zipx")
        assert fu.get_archive_base_name("a.zx01") == ("a", "zipx")
        assert fu.get_archive_base_name("a.zx02") == ("a", "zipx")

    def test_arj_multivolume_returns_arj_family(self):
        """ARJ multi-volume parts share the .arj family extension."""
        assert fu.get_archive_base_name("a.arj") == ("a", "arj")
        assert fu.get_archive_base_name("a.a01") == ("a", "arj")
        assert fu.get_archive_base_name("a.a02") == ("a", "arj")

    def test_ace_multivolume_returns_ace_family(self):
        """ACE multi-volume parts share the .ace family extension."""
        assert fu.get_archive_base_name("a.ace") == ("a", "ace")
        assert fu.get_archive_base_name("a.c00") == ("a", "ace")
        assert fu.get_archive_base_name("a.c01") == ("a", "ace")


class TestArchiveGroupMainSelection:
    """Regression tests verifying ArchiveGroup picks the correct main archive
    regardless of file insertion order (Bug B fix)."""

    def test_spanned_zip_keeps_zip_as_main(self):
        from complex_unzip_tool_v2.classes.ArchiveGroup import ArchiveGroup

        for order in (
            ["set.zip", "set.z01", "set.z02"],
            ["set.z01", "set.z02", "set.zip"],
            ["set.z02", "set.zip", "set.z01"],
        ):
            g = ArchiveGroup("dir-set")
            for f in order:
                g.add_file(f)
            assert (
                g.mainArchiveFile == "set.zip"
            ), f"order {order} produced main {g.mainArchiveFile!r}"
            assert g.isMultiPart is True

    def test_volume_rar_keeps_rar_as_main(self):
        from complex_unzip_tool_v2.classes.ArchiveGroup import ArchiveGroup

        for order in (
            ["arc.rar", "arc.r00", "arc.r01"],
            ["arc.r00", "arc.r01", "arc.rar"],
            ["arc.r01", "arc.rar", "arc.r00"],
        ):
            g = ArchiveGroup("dir-arc")
            for f in order:
                g.add_file(f)
            assert (
                g.mainArchiveFile == "arc.rar"
            ), f"order {order} produced main {g.mainArchiveFile!r}"
            assert g.isMultiPart is True

    def test_part1_rar_wins_over_partN(self):
        from complex_unzip_tool_v2.classes.ArchiveGroup import ArchiveGroup

        g = ArchiveGroup("dir-data")
        g.add_file("data.part2.rar")
        g.add_file("data.part1.rar")
        assert g.mainArchiveFile == "data.part1.rar"

    def test_7z_first_volume_wins(self):
        from complex_unzip_tool_v2.classes.ArchiveGroup import ArchiveGroup

        g = ArchiveGroup("dir-x")
        g.add_file("x.7z.002")
        g.add_file("x.7z.001")
        assert g.mainArchiveFile == "x.7z.001"

    def test_generic_numbered_first_volume_wins(self):
        """For a 7-Zip generic split of any extension, the `.001` is the entry
        point regardless of insertion order."""
        from complex_unzip_tool_v2.classes.ArchiveGroup import ArchiveGroup

        for base, ext in (("x", "rar"), ("y", "iso"), ("z", "bin")):
            g = ArchiveGroup(f"dir-{base}")
            g.add_file(f"{base}.{ext}.002")
            g.add_file(f"{base}.{ext}.001")
            assert g.mainArchiveFile == f"{base}.{ext}.001"
            assert g.isMultiPart is True

    def test_zipx_primary_wins_over_continuations(self):
        from complex_unzip_tool_v2.classes.ArchiveGroup import ArchiveGroup

        for order in (
            ["a.zipx", "a.zx01", "a.zx02"],
            ["a.zx01", "a.zx02", "a.zipx"],
            ["a.zx02", "a.zipx", "a.zx01"],
        ):
            g = ArchiveGroup("dir-a")
            for f in order:
                g.add_file(f)
            assert g.mainArchiveFile == "a.zipx", order
            assert g.isMultiPart is True

    def test_arj_primary_wins_over_continuations(self):
        from complex_unzip_tool_v2.classes.ArchiveGroup import ArchiveGroup

        for order in (
            ["a.arj", "a.a01", "a.a02"],
            ["a.a01", "a.a02", "a.arj"],
            ["a.a02", "a.arj", "a.a01"],
        ):
            g = ArchiveGroup("dir-a")
            for f in order:
                g.add_file(f)
            assert g.mainArchiveFile == "a.arj", order
            assert g.isMultiPart is True

    def test_ace_primary_wins_over_continuations(self):
        from complex_unzip_tool_v2.classes.ArchiveGroup import ArchiveGroup

        for order in (
            ["a.ace", "a.c00", "a.c01"],
            ["a.c00", "a.c01", "a.ace"],
            ["a.c01", "a.ace", "a.c00"],
        ):
            g = ArchiveGroup("dir-a")
            for f in order:
                g.add_file(f)
            assert g.mainArchiveFile == "a.ace", order
            assert g.isMultiPart is True


class TestCreateGroupsByNameMultipart:
    """End-to-end grouping tests for spanned ZIP / volume RAR (Bugs A+B)."""

    def setup_method(self):
        self.test_dir = tempfile.mkdtemp()

    def teardown_method(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create(self, name: str) -> str:
        p = os.path.join(self.test_dir, name)
        with open(p, "wb") as f:
            f.write(b"x")
        return p

    def test_spanned_zip_files_grouped_with_zip_as_main(self):
        files = [
            self._create("set.zip"),
            self._create("set.z01"),
            self._create("set.z02"),
        ]
        groups = fu.create_groups_by_name(files)
        assert len(groups) == 1
        g = groups[0]
        assert g.isMultiPart is True
        assert os.path.basename(g.mainArchiveFile) == "set.zip"
        assert len(g.files) == 3

    def test_volume_rar_files_grouped_with_rar_as_main(self):
        files = [
            self._create("arc.rar"),
            self._create("arc.r00"),
            self._create("arc.r01"),
        ]
        groups = fu.create_groups_by_name(files)
        assert len(groups) == 1
        g = groups[0]
        assert g.isMultiPart is True
        assert os.path.basename(g.mainArchiveFile) == "arc.rar"
        assert len(g.files) == 3

    def test_zip_continuations_only_still_group(self):
        """If user gives only .z01/.z02 (no .zip), they should still group together."""
        files = [
            self._create("set.z01"),
            self._create("set.z02"),
        ]
        groups = fu.create_groups_by_name(files)
        assert len(groups) == 1
        assert groups[0].isMultiPart is True

    def _assert_single_multipart(self, names, expected_main):
        files = [self._create(n) for n in names]
        groups = fu.create_groups_by_name(files)
        assert len(groups) == 1, [g.name for g in groups]
        g = groups[0]
        assert g.isMultiPart is True
        assert os.path.basename(g.mainArchiveFile) == expected_main
        assert len(g.files) == len(names)

    def test_generic_split_zip_grouped_with_001_as_main(self):
        self._assert_single_multipart(["a.zip.001", "a.zip.002"], "a.zip.001")

    def test_generic_split_rar_grouped_with_001_as_main(self):
        self._assert_single_multipart(["a.rar.001", "a.rar.002"], "a.rar.001")

    def test_generic_split_iso_grouped_with_001_as_main(self):
        self._assert_single_multipart(["a.iso.001", "a.iso.002"], "a.iso.001")

    def test_zipx_split_grouped_with_zipx_as_main(self):
        self._assert_single_multipart(["a.zipx", "a.zx01", "a.zx02"], "a.zipx")

    def test_arj_multivolume_grouped_with_arj_as_main(self):
        self._assert_single_multipart(["a.arj", "a.a01", "a.a02"], "a.arj")

    def test_ace_multivolume_grouped_with_ace_as_main(self):
        self._assert_single_multipart(["a.ace", "a.c00", "a.c01"], "a.ace")

    def test_generic_split_main_independent_of_insertion_order(self):
        # `.002` created/scanned before `.001` must still pick `.001`.
        self._assert_single_multipart(["a.iso.002", "a.iso.001"], "a.iso.001")


class TestReadDir:
    """Tests for read_dir function."""

    def setup_method(self):
        """Set up test directory structure."""
        self.test_dir = tempfile.mkdtemp()
        self.sub_dir = os.path.join(self.test_dir, "subdir")
        os.makedirs(self.sub_dir)

        # Create test files
        self.test_files = [
            os.path.join(self.test_dir, "file1.txt"),
            os.path.join(self.test_dir, "file2.zip"),
            os.path.join(self.sub_dir, "nested.7z"),
        ]
        for file_path in self.test_files:
            with open(file_path, "w") as f:
                f.write("test content")

    def teardown_method(self):
        """Clean up test directory."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_read_directory(self):
        """Test reading files from a directory."""
        result = fu.read_dir([self.test_dir])
        assert len(result) >= 3  # Should include all test files
        assert any("file1.txt" in path for path in result)
        assert any("file2.zip" in path for path in result)
        assert any("nested.7z" in path for path in result)

    def test_read_directory_skips_output_and_work_directories(self):
        """Leftover work directories and the output folder are never inputs."""
        for folder in ("temp.deepunzip-abc123", "unzipped"):
            os.makedirs(os.path.join(self.test_dir, folder, "deep"))
            with open(os.path.join(self.test_dir, folder, "deep", "x.7z"), "w") as f:
                f.write("x")
        result = fu.read_dir([self.test_dir])
        assert not any("temp.deepunzip-" in path for path in result)
        assert not any(os.sep + "unzipped" + os.sep in path for path in result)
        assert any("nested.7z" in path for path in result)

    def test_read_individual_files(self):
        """Test reading individual file paths."""
        result = fu.read_dir(self.test_files)
        assert len(result) == 3
        for file_path in self.test_files:
            assert file_path in result

    def test_mixed_files_and_directories(self):
        """Test reading mix of files and directories."""
        paths = [self.test_dir, self.test_files[0]]
        result = fu.read_dir(paths)
        assert self.test_files[0] in result
        # Directory contents should also be included
        assert any("file2.zip" in path for path in result)

    def test_nonexistent_paths(self):
        """Test handling of nonexistent paths."""
        # read_dir includes non-directory paths in result regardless of existence
        result = fu.read_dir(["/nonexistent/path"])
        assert result == [
            "/nonexistent/path"
        ]  # Function adds non-directory paths as-is

    def test_empty_input(self):
        """Test with empty input list."""
        result = fu.read_dir([])
        assert result == []


class TestRenameFile:
    """Tests for rename_file function."""

    def setup_method(self):
        """Set up test files."""
        self.test_dir = tempfile.mkdtemp()
        self.source_file = os.path.join(self.test_dir, "source.txt")
        self.target_file = os.path.join(self.test_dir, "target.txt")

        with open(self.source_file, "w") as f:
            f.write("test content")

    def teardown_method(self):
        """Clean up test files."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_successful_rename(self):
        """Test successful file rename."""
        result = fu.rename_file(self.source_file, self.target_file)
        assert result is True
        assert os.path.exists(self.target_file)
        assert not os.path.exists(self.source_file)

    def test_rename_nonexistent_file(self):
        """Test renaming a nonexistent file."""
        callback_mock = Mock()
        result = fu.rename_file("/nonexistent/file", self.target_file, callback_mock)
        assert result is False
        callback_mock.assert_called_once()
        assert "Error renaming file" in callback_mock.call_args[0][0]

    def test_rename_with_error_callback(self):
        """Test rename with error callback."""
        # Make target directory read-only to cause permission error
        callback_mock = Mock()
        readonly_dir = os.path.join(self.test_dir, "readonly")
        os.makedirs(readonly_dir)

        with patch("os.rename", side_effect=PermissionError("Permission denied")):
            result = fu.rename_file(
                self.source_file, os.path.join(readonly_dir, "test.txt"), callback_mock
            )
            assert result is False
            callback_mock.assert_called_once()
            assert "Permission denied" in callback_mock.call_args[0][0]


class TestSafeRemove:
    """Tests for safe_remove function."""

    def setup_method(self):
        """Set up test files."""
        self.test_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.test_dir, "test.txt")

        with open(self.test_file, "w") as f:
            f.write("test content")

    def teardown_method(self):
        """Clean up test files."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch("complex_unzip_tool_v2.modules.file_utils.send2trash")
    def test_remove_to_recycle_bin(self, mock_send2trash):
        """Test removing file to recycle bin."""
        result = fu.safe_remove(self.test_file, use_recycle_bin=True)
        assert result is True
        mock_send2trash.assert_called_once_with(self.test_file)

    def test_permanent_remove(self):
        """Test permanent file removal."""
        result = fu.safe_remove(self.test_file, use_recycle_bin=False)
        assert result is True
        assert not os.path.exists(self.test_file)

    def test_remove_nonexistent_file(self):
        """Test removing nonexistent file."""
        result = fu.safe_remove("/nonexistent/file")
        assert result is False

    def test_remove_with_error_callback(self):
        """Test remove with error callback."""
        callback_mock = Mock()

        with patch("os.remove", side_effect=PermissionError("Permission denied")):
            result = fu.safe_remove(
                self.test_file, use_recycle_bin=False, error_callback=callback_mock
            )
            assert result is False
            callback_mock.assert_called_once()
            assert "Permission denied" in callback_mock.call_args[0][0]


class TestShouldGroupFiles:
    """Tests for _should_group_files function."""

    def test_exact_name_match(self):
        """Test grouping with exact name match."""
        assert (
            fu._should_group_files("test", "test", "/path/file1.zip", "/path/file2.zip")
            is True
        )

    def test_multipart_related_files(self):
        """Test grouping multipart related files."""
        with patch.object(fu, "_are_multipart_related", return_value=True):
            assert (
                fu._should_group_files(
                    "archive", "archive", "/path/archive.7z.001", "/path/archive.7z.002"
                )
                is True
            )

    def test_similar_names(self):
        """Test grouping files with similar names."""
        # The function requires 0.95+ similarity AND exact base name match
        with patch.object(fu, "get_string_similarity", return_value=0.95):
            # Should work when group names have same base after splitting on '-'
            assert (
                fu._should_group_files(
                    "dir-test", "dir-test", "/path/test.zip", "/path/test.zip"
                )
                is True
            )

        with patch.object(fu, "get_string_similarity", return_value=0.85):
            # Should fail with lower similarity
            assert (
                fu._should_group_files(
                    "test", "test123", "/path/test.zip", "/path/test123.zip"
                )
                is False
            )

    def test_different_names_no_grouping(self):
        """Test that different names don't get grouped."""
        assert (
            fu._should_group_files(
                "archive1", "archive2", "/path/archive1.zip", "/path/archive2.zip"
            )
            is False
        )

    def test_short_names_no_grouping(self):
        """Test that short names with low similarity don't get grouped."""
        with patch.object(fu, "get_string_similarity", return_value=0.5):
            assert (
                fu._should_group_files("a", "b", "/path/a.zip", "/path/b.zip") is False
            )

    def test_same_base_different_archive_type_not_grouped(self):
        """Files sharing a base name but with different archive families must
        NOT be grouped together (e.g. foo.zip vs foo.7z).

        Regression: the similarity (third) check ignored the extension, so a
        standalone .7z was merged into a spanned .zip group, corrupting both.
        """
        assert (
            fu._should_group_files(
                "in-foo", "in-foo", r"C:\in\foo.7z", r"C:\in\foo.zip"
            )
            is False
        )


class TestAreMultipartRelated:
    """Tests for _are_multipart_related function."""

    @patch("complex_unzip_tool_v2.modules.file_utils.re.search")
    def test_multipart_archives_same_base(self, mock_search):
        """Test multipart archives with same base name."""
        mock_search.return_value = True

        with patch.object(fu, "get_archive_base_name") as mock_get_base:
            mock_get_base.side_effect = [("archive", "7z"), ("archive", "7z")]
            result = fu._are_multipart_related(
                "/path/archive.7z.001", "/path/archive.7z.002"
            )
            assert result is True

    @patch("complex_unzip_tool_v2.modules.file_utils.re.search")
    def test_multipart_archives_different_base(self, mock_search):
        """Test multipart archives with different base names."""
        mock_search.return_value = True

        with patch.object(fu, "get_archive_base_name") as mock_get_base:
            mock_get_base.side_effect = [("archive1", "7z"), ("archive2", "7z")]
            result = fu._are_multipart_related(
                "/path/archive1.7z.001", "/path/archive2.7z.001"
            )
            assert result is False

    def test_empty_comparison_file(self):
        """Test with empty comparison file."""
        result = fu._are_multipart_related("/path/archive.7z.001", "")
        assert result is False

    @patch("complex_unzip_tool_v2.modules.file_utils.re.search")
    def test_non_multipart_archives(self, mock_search):
        """Test non-multipart archives."""
        mock_search.return_value = False
        result = fu._are_multipart_related("/path/archive1.zip", "/path/archive2.zip")
        assert result is False


class TestCreateGroupsByName:
    """Tests for create_groups_by_name function."""

    def setup_method(self):
        """Set up test files."""
        self.test_dir = tempfile.mkdtemp()
        self.test_files = [
            os.path.join(self.test_dir, "archive1.zip"),
            os.path.join(self.test_dir, "archive2.7z"),
            os.path.join(self.test_dir, "data.rar"),
        ]

        # Create the test files
        for file_path in self.test_files:
            with open(file_path, "wb") as f:
                # Write some binary content that looks like a valid archive
                f.write(b"PK\x03\x04")  # ZIP file signature

    def teardown_method(self):
        """Clean up test files."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_create_groups_basic(self):
        """Test basic group creation."""
        with patch.object(ArchiveGroup, "add_file"):
            groups = fu.create_groups_by_name(self.test_files)
            assert len(groups) == 3  # Each file should create its own group

    def test_all_files_processed(self):
        """Test that all files are processed as potential archives."""
        groups = fu.create_groups_by_name(self.test_files)
        assert len(groups) == 3  # All files should be processed

    @patch.object(fu, "_should_group_files", return_value=True)
    def test_group_related_files(self, mock_should_group):
        """Test grouping related files."""
        with patch.object(ArchiveGroup, "add_file"):
            groups = fu.create_groups_by_name(self.test_files)
            # Files should be grouped together due to mocked _should_group_files returning True
            assert len(groups) <= len(self.test_files)

    def test_no_validation_errors(self):
        """Test that no files are skipped due to validation (since validation is removed)."""
        # All files should be processed without any validation errors
        groups = fu.create_groups_by_name(self.test_files)
        assert len(groups) > 0  # All files should result in groups

    def test_7z_not_merged_into_spanned_zip_group(self, tmp_path):
        """A standalone .7z sharing a base name with a spanned .zip set must
        stay in its own group, not get merged into the multipart zip group.

        Regression for the reported bug where a .7z grouped with a .zip/.z01
        set caused the .7z to be deleted (and the zip mishandled).
        """
        files = [str(tmp_path / f"foo.{ext}") for ext in ("7z", "zip", "z01", "z02")]
        groups = fu.create_groups_by_name(files)

        # Exactly two groups: the standalone 7z, and the spanned zip set.
        assert len(groups) == 2

        by_main = {os.path.basename(g.mainArchiveFile): g for g in groups}

        # The 7z is its own single (non-multipart) group containing only itself.
        assert "foo.7z" in by_main
        sevenz_group = by_main["foo.7z"]
        assert sevenz_group.isMultiPart is False
        assert sevenz_group.files == [files[0]]

        # The spanned zip set is multipart with .zip as the main entry point.
        assert "foo.zip" in by_main
        zip_group = by_main["foo.zip"]
        assert zip_group.isMultiPart is True
        assert set(zip_group.files) == set(files[1:])


class TestMoveFilesPreservingStructure:
    """Tests for move_files_preserving_structure function."""

    def setup_method(self):
        """Set up test directory structure."""
        self.source_dir = tempfile.mkdtemp()
        self.dest_dir = tempfile.mkdtemp()

        # Create nested directory structure
        self.subdir = os.path.join(self.source_dir, "subdir")
        os.makedirs(self.subdir)

        # Create test files
        self.test_files = [
            os.path.join(self.source_dir, "file1.txt"),
            os.path.join(self.subdir, "file2.txt"),
        ]

        for file_path in self.test_files:
            with open(file_path, "w") as f:
                f.write("test content")

    def teardown_method(self):
        """Clean up test directories."""
        shutil.rmtree(self.source_dir, ignore_errors=True)
        shutil.rmtree(self.dest_dir, ignore_errors=True)

    def test_move_files_basic(self):
        """Test basic file moving with structure preservation."""
        result = fu.move_files_preserving_structure(
            self.test_files, self.source_dir, self.dest_dir
        )

        assert len(result) == 2
        assert "file1.txt" in result
        assert (
            os.path.join("subdir", "file2.txt") in result
            or "subdir/file2.txt" in result
        )

        # Check that files were actually moved
        assert os.path.exists(os.path.join(self.dest_dir, "file1.txt"))
        assert os.path.exists(os.path.join(self.dest_dir, "subdir", "file2.txt"))

        # Source files should be gone
        assert not os.path.exists(self.test_files[0])
        assert not os.path.exists(self.test_files[1])

    def test_move_with_callbacks(self):
        """Test moving with progress and success callbacks."""
        progress_callback = Mock()
        success_callback = Mock()

        result = fu.move_files_preserving_structure(
            self.test_files,
            self.source_dir,
            self.dest_dir,
            verbose=True,
            progress_callback=progress_callback,
            success_callback=success_callback,
        )

        assert len(result) == 2
        assert progress_callback.call_count == 2  # Called for each file
        assert success_callback.call_count == 2  # Called for each successful move

    def test_move_with_duplicate_handling(self):
        """Test handling of duplicate filenames."""
        # Create a file in destination that would conflict
        dest_file = os.path.join(self.dest_dir, "file1.txt")
        with open(dest_file, "w") as f:
            f.write("existing content")

        result = fu.move_files_preserving_structure(
            [self.test_files[0]], self.source_dir, self.dest_dir  # Just move one file
        )

        assert len(result) == 1
        # Should have created file1_1.txt or similar
        assert any(
            os.path.exists(os.path.join(self.dest_dir, f"file1_{i}.txt"))
            for i in range(1, 5)
        )

    def test_move_nonexistent_files(self):
        """Test moving nonexistent files."""
        error_callback = Mock()

        result = fu.move_files_preserving_structure(
            ["/nonexistent/file.txt"],
            self.source_dir,
            self.dest_dir,
            error_callback=error_callback,
        )

        assert len(result) == 0
        # Error callback should not be called for nonexistent files (they're just skipped)

    def test_move_with_permission_error(self):
        """Test handling permission errors during move."""
        error_callback = Mock()

        with patch("shutil.move", side_effect=PermissionError("Permission denied")):
            result = fu.move_files_preserving_structure(
                self.test_files,
                self.source_dir,
                self.dest_dir,
                error_callback=error_callback,
            )

            assert len(result) == 0  # No files successfully moved
            assert error_callback.call_count == 2  # Error called for each file


class TestAddFileToGroupsStrictMatching:
    """Regression tests for add_file_to_groups strict matching behavior."""

    def setup_method(self):
        self.base_dir = tempfile.mkdtemp()
        # Create two separate multipart groups with similar names but different bases
        self.group1_dir = os.path.join(self.base_dir, "A100")
        self.group2_dir = os.path.join(self.base_dir, "A101")
        os.makedirs(self.group1_dir)
        os.makedirs(self.group2_dir)

        # Group1: base B100
        self.g1_p1 = os.path.join(self.group1_dir, "B100.7z.001")
        self.g1_p2 = os.path.join(self.group1_dir, "B100.7z.002")
        # Group2: base B101
        self.g2_p1 = os.path.join(self.group2_dir, "B101.7z.001")
        self.g2_p2 = os.path.join(self.group2_dir, "B101.7z.002")

        for p in [self.g1_p1, self.g1_p2, self.g2_p1, self.g2_p2]:
            with open(p, "w") as f:
                f.write("dummy")

        # Build groups
        self.groups = []
        g1 = ArchiveGroup("A100-B100")
        g1.add_file(self.g1_p1)
        self.groups.append(g1)

        g2 = ArchiveGroup("A101-B101")
        g2.add_file(self.g2_p1)
        self.groups.append(g2)

    def teardown_method(self):
        shutil.rmtree(self.base_dir, ignore_errors=True)

    def test_exact_base_name_is_required(self):
        """B100.7z.002 should join only B100 group, not B101 based on similarity."""
        added = fu.add_file_to_groups(self.g1_p2, self.groups)
        assert added is self.groups[0]
        assert self.groups[0].files and any(
            fp.endswith("B100.7z.002") for fp in self.groups[0].files
        )
        # Ensure it did not end up in the other group
        assert not any(fp.endswith("B100.7z.002") for fp in self.groups[1].files)

    def test_no_group_on_different_base(self):
        """B101.7z.002 must not be added to B100 group despite similar naming."""
        # Intentionally pass B101 part 2 when only B100 group exists in same dir list first
        groups_local = [self.groups[0]]  # only B100 group
        # Create a loose file resembling different base
        loose = os.path.join(self.group1_dir, "B101.7z.002")
        with open(loose, "w") as f:
            f.write("dummy")

        added = fu.add_file_to_groups(loose, groups_local)
        assert added is None
        # File should remain at original location
        assert os.path.exists(loose)


class TestAddFileToGroupsDirectoryAwareness:
    """Tests ensuring grouping only occurs within the same directory tree."""

    def setup_method(self):
        self.base_dir = tempfile.mkdtemp()
        # Create two separate sibling dirs
        self.dir_a = os.path.join(self.base_dir, "FolderA")
        self.dir_b = os.path.join(self.base_dir, "FolderB")
        os.makedirs(self.dir_a)
        os.makedirs(self.dir_b)

        # Same basename across folders
        self.a_p1 = os.path.join(self.dir_a, "Same.7z.001")
        self.a_p2 = os.path.join(self.dir_a, "Same.7z.002")
        self.b_p2 = os.path.join(self.dir_b, "Same.7z.002")

        for p in [self.a_p1, self.a_p2, self.b_p2]:
            with open(p, "w") as f:
                f.write("dummy")

        # Group uses FolderA main archive
        self.group = ArchiveGroup("FolderA-Same")
        self.group.add_file(self.a_p1)

    def teardown_method(self):
        shutil.rmtree(self.base_dir, ignore_errors=True)

    def test_group_same_folder(self):
        groups = [self.group]
        added = fu.add_file_to_groups(self.a_p2, groups)
        assert added is self.group
        assert any(fp.endswith("Same.7z.002") for fp in self.group.files)

    def test_do_not_group_different_folder(self):
        groups = [self.group]
        added = fu.add_file_to_groups(self.b_p2, groups)
        assert added is None
        # File should remain where it is
        assert os.path.exists(self.b_p2)


class TestEnsureContainedMultipartGroups:
    def test_creates_group_for_7z_set(self, tmp_path):
        out_dir = tmp_path / "unzipped"
        out_dir.mkdir(parents=True, exist_ok=True)

        p1 = out_dir / "MySet.7z.001"
        p2 = out_dir / "MySet.7z.002"
        p1.write_bytes(b"1")
        p2.write_bytes(b"2")

        groups: list[ArchiveGroup] = []
        created = fu.ensure_contained_multipart_groups([str(p1), str(p2)], groups)

        assert created == 1
        assert len(groups) == 1
        g = groups[0]
        assert g.isMultiPart is True
        assert os.path.basename(g.mainArchiveFile).lower().endswith(".7z.001")
        assert any(f.lower().endswith(".7z.002") for f in g.files)

    def test_creates_group_for_spanned_zip_and_keeps_zip_as_main(self, tmp_path):
        out_dir = tmp_path / "unzipped"
        out_dir.mkdir(parents=True, exist_ok=True)

        p_zip = out_dir / "Set.zip"
        p_z01 = out_dir / "Set.z01"
        p_zip.write_bytes(b"zip")
        p_z01.write_bytes(b"z01")

        groups: list[ArchiveGroup] = []
        created = fu.ensure_contained_multipart_groups([str(p_zip), str(p_z01)], groups)

        assert created == 1
        assert len(groups) == 1
        g = groups[0]
        assert g.isMultiPart is True
        assert os.path.basename(g.mainArchiveFile).lower().endswith(".zip")
        assert any(f.lower().endswith(".z01") for f in g.files)

    def test_does_not_create_group_for_standalone_zip(self, tmp_path):
        out_dir = tmp_path / "unzipped"
        out_dir.mkdir(parents=True, exist_ok=True)

        p_zip = out_dir / "Standalone.zip"
        p_zip.write_bytes(b"zip")

        groups: list[ArchiveGroup] = []
        created = fu.ensure_contained_multipart_groups([str(p_zip)], groups)

        assert created == 0
        assert groups == []

    def test_creates_group_for_rar_volume_and_keeps_rar_as_main(self, tmp_path):
        out_dir = tmp_path / "unzipped"
        out_dir.mkdir(parents=True, exist_ok=True)

        p_rar = out_dir / "Arc.rar"
        p_r00 = out_dir / "Arc.r00"
        p_rar.write_bytes(b"rar")
        p_r00.write_bytes(b"r00")

        groups: list[ArchiveGroup] = []
        created = fu.ensure_contained_multipart_groups([str(p_rar), str(p_r00)], groups)

        assert created == 1
        assert len(groups) == 1
        g = groups[0]
        assert g.isMultiPart is True
        assert os.path.basename(g.mainArchiveFile).lower().endswith(".rar")
        assert any(f.lower().endswith(".r00") for f in g.files)

    def test_does_not_create_group_for_standalone_rar(self, tmp_path):
        out_dir = tmp_path / "unzipped"
        out_dir.mkdir(parents=True, exist_ok=True)

        p_rar = out_dir / "Standalone.rar"
        p_rar.write_bytes(b"rar")

        groups: list[ArchiveGroup] = []
        created = fu.ensure_contained_multipart_groups([str(p_rar)], groups)

        assert created == 0
        assert groups == []

    def test_creates_group_for_generic_numbered_split(self, tmp_path):
        out_dir = tmp_path / "unzipped"
        out_dir.mkdir(parents=True, exist_ok=True)

        p1 = out_dir / "Set.iso.001"
        p2 = out_dir / "Set.iso.002"
        p1.write_bytes(b"1")
        p2.write_bytes(b"2")

        groups: list[ArchiveGroup] = []
        created = fu.ensure_contained_multipart_groups([str(p1), str(p2)], groups)

        assert created == 1
        g = groups[0]
        assert g.isMultiPart is True
        assert os.path.basename(g.mainArchiveFile).lower().endswith(".iso.001")
        assert any(f.lower().endswith(".iso.002") for f in g.files)

    def test_creates_group_for_generic_numbered_split_from_001_alone(self, tmp_path):
        # `.001` is unambiguous, so a group is created even without a sibling.
        out_dir = tmp_path / "unzipped"
        out_dir.mkdir(parents=True, exist_ok=True)

        p1 = out_dir / "Lonely.rar.001"
        p1.write_bytes(b"1")

        groups: list[ArchiveGroup] = []
        created = fu.ensure_contained_multipart_groups([str(p1)], groups)

        assert created == 1
        assert os.path.basename(groups[0].mainArchiveFile).lower().endswith(".rar.001")

    def test_creates_group_for_zipx_set(self, tmp_path):
        out_dir = tmp_path / "unzipped"
        out_dir.mkdir(parents=True, exist_ok=True)

        p_zipx = out_dir / "Z.zipx"
        p_zx01 = out_dir / "Z.zx01"
        p_zipx.write_bytes(b"zipx")
        p_zx01.write_bytes(b"zx01")

        groups: list[ArchiveGroup] = []
        created = fu.ensure_contained_multipart_groups(
            [str(p_zipx), str(p_zx01)], groups
        )

        assert created == 1
        g = groups[0]
        assert g.isMultiPart is True
        assert os.path.basename(g.mainArchiveFile).lower().endswith(".zipx")

    def test_creates_group_for_arj_set(self, tmp_path):
        out_dir = tmp_path / "unzipped"
        out_dir.mkdir(parents=True, exist_ok=True)

        p_arj = out_dir / "A.arj"
        p_a01 = out_dir / "A.a01"
        p_arj.write_bytes(b"arj")
        p_a01.write_bytes(b"a01")

        groups: list[ArchiveGroup] = []
        created = fu.ensure_contained_multipart_groups([str(p_arj), str(p_a01)], groups)

        assert created == 1
        assert os.path.basename(groups[0].mainArchiveFile).lower().endswith(".arj")

    def test_creates_group_for_ace_set(self, tmp_path):
        out_dir = tmp_path / "unzipped"
        out_dir.mkdir(parents=True, exist_ok=True)

        p_ace = out_dir / "C.ace"
        p_c00 = out_dir / "C.c00"
        p_ace.write_bytes(b"ace")
        p_c00.write_bytes(b"c00")

        groups: list[ArchiveGroup] = []
        created = fu.ensure_contained_multipart_groups([str(p_ace), str(p_c00)], groups)

        assert created == 1
        assert os.path.basename(groups[0].mainArchiveFile).lower().endswith(".ace")

    def test_does_not_create_group_for_standalone_arj_or_ace(self, tmp_path):
        out_dir = tmp_path / "unzipped"
        out_dir.mkdir(parents=True, exist_ok=True)

        p_arj = out_dir / "Solo.arj"
        p_ace = out_dir / "Solo2.ace"
        p_arj.write_bytes(b"arj")
        p_ace.write_bytes(b"ace")

        groups: list[ArchiveGroup] = []
        created = fu.ensure_contained_multipart_groups([str(p_arj), str(p_ace)], groups)

        assert created == 0
        assert groups == []


class TestOutputPathNormalization:
    def test_normalize_numeric_only_folder(self):
        assert (
            fu.normalize_output_relative_path(os.path.join("1", "aaa.jpg")) == "aaa.jpg"
        )

    def test_normalize_numeric_symbol_folder_chain(self):
        assert (
            fu.normalize_output_relative_path(os.path.join("1", "5555+", "222.jpg"))
            == "222.jpg"
        )

    def test_date_folder_is_not_flattened(self):
        assert fu.normalize_output_relative_path(
            os.path.join("2024-01-01", "aaa.jpg")
        ) == os.path.join("2024-01-01", "aaa.jpg")

    def test_meaningful_prefix_stops_flattening(self):
        assert fu.normalize_output_relative_path(
            os.path.join("photos", "1", "aaa.jpg")
        ) == os.path.join("photos", "1", "aaa.jpg")

    def test_only_leading_meaningless_folders_are_flattened(self):
        assert fu.normalize_output_relative_path(
            os.path.join("1", "photos", "1", "aaa.jpg")
        ) == os.path.join("photos", "1", "aaa.jpg")

    def test_move_files_preserving_structure_flattens_meaningless_prefix(
        self, tmp_path
    ):
        src_root = tmp_path / "src"
        dest_root = tmp_path / "unzipped"
        (src_root / "1").mkdir(parents=True, exist_ok=True)
        dest_root.mkdir(parents=True, exist_ok=True)

        src_file = src_root / "1" / "aaa.jpg"
        src_file.write_bytes(b"aaa")

        moved = fu.move_files_preserving_structure(
            [str(src_file)],
            source_root=str(src_root),
            destination_root=str(dest_root),
        )

        assert moved == [os.path.join("aaa.jpg")]
        assert (dest_root / "aaa.jpg").exists()

    def test_move_files_preserving_structure_only_flattens_leading_meaningless(
        self, tmp_path
    ):
        src_root = tmp_path / "src"
        dest_root = tmp_path / "unzipped"
        (src_root / "1" / "photos" / "1").mkdir(parents=True, exist_ok=True)
        dest_root.mkdir(parents=True, exist_ok=True)

        src_file = src_root / "1" / "photos" / "1" / "aaa.jpg"
        src_file.write_bytes(b"aaa")

        moved = fu.move_files_preserving_structure(
            [str(src_file)],
            source_root=str(src_root),
            destination_root=str(dest_root),
        )

        assert moved == [os.path.join("photos", "1", "aaa.jpg")]
        assert (dest_root / "photos" / "1" / "aaa.jpg").exists()

    def test_move_files_preserving_structure_keeps_date_folder(self, tmp_path):
        src_root = tmp_path / "src"
        dest_root = tmp_path / "unzipped"
        (src_root / "2024-01-01").mkdir(parents=True, exist_ok=True)
        dest_root.mkdir(parents=True, exist_ok=True)

        src_file = src_root / "2024-01-01" / "aaa.jpg"
        src_file.write_bytes(b"aaa")

        fu.move_files_preserving_structure(
            [str(src_file)],
            source_root=str(src_root),
            destination_root=str(dest_root),
        )

        assert (dest_root / "2024-01-01" / "aaa.jpg").exists()

    def test_collisions_are_handled_after_flattening(self, tmp_path):
        src_root = tmp_path / "src"
        dest_root = tmp_path / "unzipped"
        (src_root / "1").mkdir(parents=True, exist_ok=True)
        (src_root / "2").mkdir(parents=True, exist_ok=True)
        dest_root.mkdir(parents=True, exist_ok=True)

        f1 = src_root / "1" / "aaa.jpg"
        f2 = src_root / "2" / "aaa.jpg"
        f1.write_bytes(b"one")
        f2.write_bytes(b"two")

        fu.move_files_preserving_structure(
            [str(f1), str(f2)],
            source_root=str(src_root),
            destination_root=str(dest_root),
        )

        files = sorted(p.name for p in dest_root.iterdir() if p.is_file())
        assert "aaa.jpg" in files
        assert any(name.startswith("aaa_") and name.endswith(".jpg") for name in files)
        assert len(files) == 2


if __name__ == "__main__":
    pytest.main([__file__])
