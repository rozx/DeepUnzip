## 1. Tests
- [x] A typed password is in `passwords.txt` after the run is interrupted by a later archive.
- [x] `SevenZipEngine.remember` reports the password once it is in the book.
- [x] A leftover work directory is removed after the run, to the recycle bin by default, permanently with `--permanent-delete`.
- [x] A leftover is kept when this run keeps its own work directory.
- [x] A leftover holding a source volume that could not be moved home is kept.
- [x] A leftover whose owner process is still running is kept and reported as in use (real child process; owner on another computer counts as running; no or unreadable marker is a leftover).
- [x] `safe_remove` removes a folder permanently.

## 2. Implementation
- [x] `SevenZipEngine(on_learn=...)`; `extract_files` saves the book from it.
- [x] `main._remove_leftover_work_dirs` after `_reconcile_history`; `safe_remove` handles folders.
- [x] Notices `recovery.work_dir_recycled` / `recovery.work_dir_deleted` in all five languages.
- [x] READMEs (five languages), CLAUDE.md and AGENTS.md.

## 3. Validation
- [x] `poetry run pytest -q`, `flake8`, `mypy`, `black`, `--help`.
- [x] Real engine: a hard-killed run and a Ctrl+C run, then a normal run, which extracted everything and removed both leftovers.
- [x] Real engine: a second run that finished while the first was still extracting left the first run's work directory alone.
