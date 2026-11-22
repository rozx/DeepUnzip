# Change: Recover better from interrupted runs

## Why
An interrupted run (Ctrl+C, a closed window, a crash) loses nothing: sources are deleted only at the end, and moved volumes are restored by the next run. But two things were left for the user to deal with:

- A password typed at a prompt was saved to `passwords.txt` only when the whole run finished, so an interruption lost it and the user had to type it again.
- The run's `temp.deepunzip-<run-id>` work directory stayed behind. The next run reported it and ignored it, so these folders (often holding large partial extractions) piled up until the user deleted them by hand.

## What Changes
- A typed password is saved as soon as it opens an archive or a set.
- After a root's run, the work directories that interrupted runs left in that root are removed: to the recycle bin, or permanently with `--permanent-delete`. A leftover is kept while a rename-history entry still points into it (a source volume that could not be moved home), or while the run that owns it is still going: each run writes an `.owner` marker (process ID and computer name) into its work directory, and an owner on another computer counts as running. All are kept when the new run had to keep its own work directory. A notice names each removed directory.
- Resuming an interrupted run is out of scope: the next run extracts again, and identical files already in the output are skipped (see `2026-11-22-skip-identical-output-files`).

## Impact
- Affected specs: `work-pool-extraction`
- Affected code: `deepunzip/main.py`, `deepunzip/modules/pool_engine.py`, `deepunzip/modules/file_utils.py` (`safe_remove` removes folders), `deepunzip/modules/i18n.py`, READMEs, and tests
