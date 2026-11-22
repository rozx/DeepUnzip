# Change: Skip identical files already in the output

## Why
When a file's output path in `unzipped/` is already taken, the work pool always moved the new file in under a numbered name (`a_1.txt`, `a_2.txt`, ...). Re-running on the same archives, or two archives that ship the same file, filled the output with byte-identical copies.

## What Changes
- Before giving a file a numbered name, compare it with the file already at the destination, and with each numbered alternative in turn: first by size, then by MD5 hash.
- If one of them has the same content, do not write a second copy. The item's output path is that existing file, and its copy in the work directory is removed.
- A file with the same name but different content is still kept under a numbered name, as before. A folder with the same name is never a duplicate.
- An unresolved item (for example a password-failed archive) whose identical copy is already in the output stays unresolved; only the second copy is skipped.
- Report the number of skipped files: a summary line in human output, and `duplicates_skipped` in the JSON `summary` event. `files` counts each output file once.

## Impact
- Affected specs: `output-path-normalization` (collision handling)
- Affected code: `deepunzip/modules/work_pool.py` (`_move_to_output`, `PoolResult`), `deepunzip/modules/render.py`, `deepunzip/modules/i18n.py`, and tests
