# Validation

## End-to-end run on the reproduction set (task 6.5)

The run used a copy of the reproduction set, with the real bundled 7-Zip 26.03 on Windows x64 and stdin closed (no prompts possible).

- **Input**: four password-protected containers, two `.7z` and two `.rar`, plus a password book. They hold two 7z volume sets. Each set's `.7z.001` is cloaked (`….7z.001删掉`) inside one `.rar`, and its `.7z.002` sits inside one `.7z`.
- **Before** (1.3.2): the run reported "4/4 successful" and recycled all four sources. Both `.002` volumes were lost with the temp folders, and only the two cloaked `.001` files reached the output.
- **After** (stage 2 on `release/v2.0.0`):
  - Round 1 opened the four containers (`password #1`). Round 2 assembled both sets across containers, after uncloaking the derived primaries.
  - Three files (about 3.5 GB) reached `unzipped/`, and every volume was consumed.
  - All four sources went to the Recycle Bin.
  - No `temp.deepunzip-*` work directory and no rename-history file were left behind.
  - The exit code was 0.
  - The log identifies passwords only by their index in the password book.
- **Follow-up fixed during validation**: the summary counted each set's volumes as separate archives (8). It now counts a set once (6).
