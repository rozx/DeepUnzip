# Parity list

Today's tests already pin down behaviors that the work pool must keep (task 1.2).

- **Re-express against the pool**: these tests exercise the old flow (`main.extract_files` or `extract_nested_archives`). Each behavior below is covered again through the pool driver (task 4.11) before task 7.1 removes the old tests.
- **Keep unchanged**: these are unit tests of helpers that the pool reuses. They stay as they are.

| # | Behavior | Existing tests | Action |
| --- | --- | --- | --- |
| P1 | Multipart parts extracted from a container survive a failed extraction and reach the output folder | `test_main.py::test_contained_multipart_parts_preserved_to_output_when_extraction_fails`, `test_archive_utils.py::test_nested_multipart_missing_parts_are_preserved_in_final_files` | Re-express |
| P2 | Password failure never deletes the source; a password-failed nested archive is preserved | `test_main.py::test_should_delete_original_archives_*`, `test_archive_utils.py::test_extract_nested_archives_returns_false_when_passwords_fail`, `::test_extract_nested_archives_preserves_nested_archive_when_password_fails` | Re-express |
| P3 | A spanned ZIP found inside a container is grouped and extracted in the same run | `test_main.py::test_step7_autogroups_contained_zip_spanned_and_step8_processes_it` | Re-express |
| P4 | Nested cleanup follows the user's deletion mode; if the Recycle Bin fails, the nested archive is kept as output | `test_main.py::test_nested_cleanup_follows_user_recycle_bin_choice`, `test_archive_utils.py::test_nested_archive_kept_when_recycle_bin_fails` | Re-express |
| P5 | A top-level non-archive or zip document is kept quietly and is not a failure | `test_main.py::test_top_level_non_archive_is_kept_and_not_counted_as_failure`, `test_archive_utils.py::test_top_level_plain_file_is_skipped_without_error`, `::test_top_level_zip_document_is_skipped_without_error`, `::test_top_level_zip_document_is_not_extracted_or_deleted` | Re-express (source `kept`) |
| P6 | A broken or damaged top-level archive is still reported | `test_archive_utils.py::test_top_level_broken_archive_is_still_reported`, `::test_top_level_damaged_archive_with_unknown_extension_is_reported`, `::test_top_level_damaged_zip_named_like_document_is_reported` | Re-express (source `unresolved`) |
| P7 | Rename history: revert on failure, clear on success, recovery prompt yes/no | `test_main.py::test_rename_history_*` (4 tests), `test_rename_history.py` | Re-express main-level tests; keep module tests |
| P8 | Continuation parts found inside containers join their set (all formats); unmatched ones are preserved | `test_archive_utils.py::test_nested_continuation_parts_are_relocated`, `::test_nested_continuation_parts_skipped_when_not_relocated`, `::test_nested_continuation_parts_relocated_across_all_formats` | Re-express (pool assembly) |
| P9 | Nested classification: non-archives, PE files, zip documents and manifestless JARs are kept; a cloaked zip named like a document is extracted | `test_archive_utils.py::test_extract_nested_archives_treats_non_archive_as_regular_file`, `::test_nested_pe_is_kept_as_regular_file`, `::test_nested_zip_document_is_kept_while_nested_zip_is_extracted`, `::test_nested_cloaked_zip_named_like_document_is_extracted`, `::test_libreoffice_extension_kept_unless_plain_zip`, `::test_manifestless_jar_is_kept` | Re-express |
| P10 | Source multipart volumes are never deleted when extraction fails (7z and RAR) | `test_multipart_retention.py` (2 tests) | Re-express |
| P11 | A file argument collects its own numbered (and cloaked) sibling volumes without renaming others | `test_multipart_file_input.py` (5 tests) | Keep (`read_dir` is reused as the scan) |
| P12 | Primary/continuation naming and entry-point priority per format | `test_file_utils.py` base-name, entry-point and grouping classes | Keep; the consolidated key helper (task 2.3) gets equivalent cases |
| P13 | Output-path normalization and collision handling | `test_file_utils.py` normalize and `move_files_preserving_structure` tests | Keep (finalization reuses them) |
| P14 | Ambiguous primaries (`.zip`/`.rar`/`.zipx`/`.arj`/`.ace`) need a continuation; `.001` may stand alone | `test_file_utils.py::TestEnsureContainedMultipartGroups*` | Re-express as pool grouping, then remove with task 7.1 |
| P15 | Archive validation and type classification (`is_valid_archive`, 7z error mapping, list parsing) | the remaining `test_archive_utils.py` unit tests | Keep |
