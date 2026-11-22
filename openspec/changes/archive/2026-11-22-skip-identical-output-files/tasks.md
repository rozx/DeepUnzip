## 1. Tests
- [x] An identical file already in the output is skipped, and the source is still deleted.
- [x] Two archives with the same identical file write it once.
- [x] A different file with the same name (including same size) is still renamed.
- [x] An identical copy under a numbered name (`a_1.txt`) is found.
- [x] An identical numbered copy past a gap (`a_2.txt` with `a_1.txt` deleted) is found.
- [x] A folder with the same name is not a duplicate.
- [x] A password-failed archive whose identical copy is in the output stays unresolved.
- [x] The summary reports the skipped count, in human output and JSON.

## 2. Implementation
- [x] Compare size, then MD5, before choosing a numbered name in `WorkPool._move_to_output`.
- [x] Add `WorkItem.duplicate_in_output`, `PoolResult.duplicates_skipped`, and count each output file once.
- [x] Add `summary.duplicates_skipped` in all five languages and `duplicates_skipped` in the JSON summary.

## 3. Validation
- [x] `poetry run pytest -q`, `flake8`, `mypy`, `black`, `--help`.
