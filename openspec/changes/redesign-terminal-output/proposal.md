## Why

The console output is hard to read, and unusable from scripts:

- **Too long.** Every line is printed in both English and Chinese. One run over four archives produced about 200 lines, mostly spinner frames and repeated headers.
- **Animation in logs.** `rich_utils.console` is created with `force_terminal=True`, so a redirected run fills the log with repeated progress-bar frames.
- **Passwords in plain text.** `print_password_success` and `print_password_failed` print the password itself on every attempt.
- **No usable exit status.** Almost every path exits 0, including runs where archives could not be extracted. Only a missing engine exits 1.
- **Prompts that break automation.** Prompts read stdin unconditionally. A non-interactive stdin can block the run or crash it: the password prompt's choice loop does not catch `EOFError`.

The work-pool redesign (`redesign-work-pool-extraction`) replaces the step-by-step flow with rounds, sets and lineage. The output has to be rebuilt around those anyway, so this is the moment to fix it.

## What Changes

- **New human output: progress plus a lineage tree.**
  - A header line, then one line per finished item (container opened, set assembled, item unresolved).
  - In an interactive terminal, two live progress lines: overall progress (items resolved / items known) and the current item. The current item's percentage, size and speed come from 7-Zip's `-bsp2` progress stream.
  - At the end, the live lines are replaced by a **lineage tree**: each multipart set lists its volumes and the source container each came from, including the original cloaked name. It is followed by a summary of output files, deleted or kept sources, and unresolved items with reasons.
- **Plain output when not a terminal.** Live rendering is used only when stdout is a TTY. Otherwise the same item lines and summary are printed without animation or progress frames. `NO_COLOR` is honored.
- **Single-language output that follows the system language.**
  - The language comes from the `DEEPUNZIP_LANG` environment variable (`zh` / `en`) if set; otherwise from the system UI language (`zh-*` → Chinese, anything else → English).
  - All user-facing strings move into a message catalog with Chinese and English entries.
  - **BREAKING (convention):** this replaces the "every string bilingual inline" rule in `CLAUDE.md` / `AGENTS.md`.
- **Passwords are never printed.** A working password is shown by its position in the password book (`password #4`), and user-entered passwords as `password (entered)`.
- **New `--json` flag for program-friendly output:**
  - stdout carries newline-delimited JSON events (`start`, `item`, `set`, `progress`, `unresolved`, `error`, `summary`), one object per line, with a `schema_version`; the last line is always the `summary`;
  - no human text, colors or animation;
  - no prompts at all: password prompts are skipped (the item becomes unresolved), recovery prompts take their default, and there is no exit pause.
- **Meaningful exit codes in every mode:**
  - `0`: everything resolved;
  - `1`: the run finished but some items are unresolved (sources kept);
  - `2`: fatal or usage error (engine missing, no valid input path).
  - **BREAKING:** a missing engine moves from 1 to 2, and a run with unresolved items moves from 0 to 1.
- **Non-interactive stdin is detected even without `--json`.** When stdin is not a TTY, every prompt takes its default ("skip") instead of blocking or crashing.

## Capabilities

### New Capabilities
- `terminal-output`: human output: item lines, live progress (TTY only), the final lineage tree and summary, plain non-TTY rendering, `NO_COLOR`, and password masking.
- `output-localization`: language selection (`DEEPUNZIP_LANG`, system UI language, English fallback), a single language per run, and a message catalog with complete zh/en coverage.
- `machine-readable-output`: the `--json` event stream and its schema, non-interactive behavior, exit codes, and automatic non-interactive mode when stdin is not a TTY.

### Modified Capabilities
- `cross-platform-runtime`: "Terminal-compatible exit" also covers `--json` (never pauses) and the new exit codes. "Engine errors precede CLI file mutations" exits with code 2.

## Impact

- **Code**:
  - `modules/rich_utils.py` is replaced by renderers (tree/live, plain, JSON) that consume typed events emitted by the work pool. Today's ~40 `print_*` helpers go away.
  - New `modules/i18n.py`: a catalog plus language detection.
  - `archive_utils`: run 7-Zip with `-bsp2` and stream its progress.
  - `main.py`: the `--json` flag, exit codes, and prompt gating.
- **Depends on** `redesign-work-pool-extraction`, whose rounds, sets and lineage these events describe. Ships with it in **v2.0.0**.
- **Tests**: a catalog completeness test (every key has zh and en); renderer tests that feed recorded event sequences; JSON schema tests; exit-code tests; non-TTY tests (no ANSI or progress frames). 7-Zip stays mocked.
- **Docs**: `CLAUDE.md` / `AGENTS.md` conventions (catalog instead of inline bilingual strings), README usage for `--json` and exit codes, and v2.0.0 upgrade notes about exit codes and single-language output.
