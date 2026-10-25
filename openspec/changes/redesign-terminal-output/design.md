## Context

Output today goes through ~40 `print_*` helpers in `modules/rich_utils.py`, called directly from `main.py` and `archive_utils.py`. Strings are bilingual inline (`"Wrong password 密码错误"`). The single `Console(width=120, force_terminal=True)` renders spinners and progress bars even into pipes and files.

The work pool (`redesign-work-pool-extraction`) replaces the step pipeline with rounds, so most call sites change anyway.

The user chose:
- style C (a lineage tree at the end) plus progress bars;
- a flag for program-friendly output;
- single-language output that follows the system language.

## Goals / Non-Goals

**Goals:**
- One line per meaningful event; live progress only in a real terminal.
- A final view that explains where every output came from (lineage tree).
- Machine-readable output with a stable schema, no prompts, and meaningful exit codes.
- No password ever appears in any output.
- Extraction logic that does not know how output is rendered, so it is testable without a console.

**Non-Goals:**
- Languages beyond zh/en in the terminal. The catalog is built to allow more later; the README covers five languages separately.
- A TUI with keyboard interaction.
- Log files. `--json` redirected to a file serves that purpose.

## Decisions

### D1. Event bus between the pool and the renderers

The work pool and the extraction helpers emit typed events (dataclasses):

| Event | Emitted when |
| --- | --- |
| `RunStarted` / `RootStarted` | a run or an input root starts |
| `RoundStarted` | a round starts |
| `ItemOpened` | a container is opened |
| `SetAssembled` | a multipart set is extracted |
| `ItemUnresolved` | an item cannot be resolved |
| `Progress` | the current item makes progress |
| `PromptNeeded` | a prompt is needed |
| `RootFinished` | a root is finished, with its lineage snapshot |
| `RunFinished` | the run ends |

They go to exactly one renderer, chosen at startup:

- **`TreeRenderer`**: when stdout is a TTY and `--json` is not set. Uses Rich `Live` for the two progress lines and prints item lines above them.
- **`PlainRenderer`**: when stdout is not a TTY. Same item lines and summary, no `Live`, no spinner, no color unless the terminal supports it and `NO_COLOR` is unset.
- **`JsonRenderer`**: with `--json`.

The `Console` is created with `force_terminal=None` (auto-detect). The Windows UTF-8 reconfiguration in `_configure_redirected_output` is kept.

Tests assert on emitted events, and test renderers separately by feeding recorded event lists.

*Alternative considered:* keep the `print_*` helpers and branch on a mode flag inside each. Rejected, because every helper would grow three branches, and logic and presentation would stay entangled.

### D2. Human layout (style C + progress)

While running:
- A header line: product name, version, input root.
- Then one line per finished item:
  - `✓ <name>  opened → N files`
  - `✓ <set>  K volumes assembled → N files`
  - `⚠ <name>  unresolved: <reason>`
- Two live lines at the bottom:
  - **Overall**: a bar over items resolved / items known (the total grows as containers reveal more), the round number, and elapsed time.
  - **Current**: a spinner, a bar, the percentage, the item name, bytes done/total, and speed.

At the end, the live lines are removed and the **lineage tree** is printed, built from the `RootFinished` lineage snapshot. Per top-level result:

- A multipart set shows one child per volume: `.7z.001 ← <source container>`, plus `uncloaked <original name>` when the volume was renamed.
- A container shows its output count; nested containers appear as children.
- Unresolved items are listed with their reason (password, missing volume, max depth, empty, too many combinations, …) and where they were preserved.

The tree is followed by a summary:
- output file count and output folder;
- sources deleted (and whether to the Recycle Bin) / kept;
- elapsed time;
- exit code.

Rich measures CJK width correctly (`cell_len`), so columns align in real terminals. Long names are truncated in the middle with `…`, keeping the extension.

**Item lines are capped.** With more than 200 finished items in a root, further item lines are summarized ("… and N more"); the tree and summary stay complete. *Rationale:* a folder with thousands of small archives would otherwise scroll for minutes.

### D3. Progress from 7-Zip

Extraction runs `7z x … -bsp1 -bso0 -bse1`: the percentage stream goes to stdout, and normal output is suppressed. The process is read line by line with `Popen` instead of `subprocess.run`. Percent lines (`NN%` plus an optional byte count) become `Progress` events, throttled to one per 200 ms or per 1% change. stderr is still captured for `_raise_for_7z_error`.

Listing and probing (`7z l`) stay with `subprocess.run`.

### D4. Localization

`modules/i18n.py` holds a catalog `{key: {"en": str, "zh": str}}` with `str.format` placeholders and a `t(key, **kw)` accessor. The language is resolved once, at startup:

1. `DEEPUNZIP_LANG` = `zh` or `en`, if set.
2. The system UI language:
   - Windows: `GetUserDefaultUILanguage` via `ctypes`;
   - POSIX: `LC_ALL` → `LC_MESSAGES` → `LANG`.

   Any `zh*` value means Chinese.
3. English otherwise.

A missing zh entry falls back to en at runtime. A unit test fails if any key lacks either language. Help text for Typer options is localized the same way.

JSON output never contains catalog text. It carries only codes and data, so it is language-independent.

### D5. `--json` event stream

Each line is one JSON object with `event` and `schema_version` (starting at `1`). Paths are relative to their input root, plus the absolute root in `start` / `root`.

| Event | Fields |
| --- | --- |
| `start` | version, roots |
| `root` | index, path |
| `round` | root, number |
| `item` | root, path, action (`opened`, `kept`), files, password_index |
| `set` | root, key, volumes[{index, path, source, uncloaked_from}], status, files |
| `progress` | root, path, percent, bytes_done, bytes_total (throttled as in D3) |
| `unresolved` | root, path, reason, preserved_to |
| `error` | code, detail; fatal only |
| `summary` | status (`ok`, `partial`, `error`), files, output_dirs, sources{deleted, kept}, unresolved[], exit |

- The `summary` line is always last, even after a fatal error. Consumers can read just the last line.
- `password_index` is the 1-based position in the merged password book; `0` means empty password; `null` means not encrypted. User-entered passwords appear as `"entered"`.
- Nothing else is written to stdout. Python warnings and unexpected tracebacks go to stderr.

### D6. Non-interactive behavior

A run is non-interactive when `--json` is set or stdin is not a TTY. In non-interactive runs:

- **Password prompts** are skipped, as option 2 ("skip this archive"). The item becomes unresolved with reason `password`.
- **The leftover rename-history prompt** takes its default ("no"). Relocation entries are still auto-restored, as specified in the work-pool change.
- **The Windows "Press Enter to exit" pause** is skipped.

`EOFError` from `input()` is caught in every prompt and treated as the default, so a closed stdin can never crash the run.

### D7. Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Every item resolved (extracted, final or kept), or there was nothing to do |
| `1` | The run completed but at least one item is unresolved |
| `2` | Fatal or usage error: engine missing or unusable, no valid input path, unexpected exception |

`--help` and `--version` exit 0. The codes are the same in all three renderers. `_ask_for_user_input_and_exit` keeps its pause rule but receives the computed code.

## Risks / Trade-offs

- [Scripts that relied on exit 0 / 1] → Documented as **BREAKING** in the v2.0.0 upgrade notes, which explain the mapping. Code 2 for a missing engine makes it distinguishable from a partial run.
- [Single-language output surprises users who liked bilingual output] → `DEEPUNZIP_LANG` forces either language, and the README documents it.
- [Reading 7-Zip progress line by line on Windows] → `-bsp1` writes `\b`-separated updates without newlines. The reader therefore splits on `\b`, `\r` and `\n`. It is covered by a unit test with a recorded byte stream.
- [Lineage tree too large for big runs] → Containers with no notable children (single level, everything extracted) collapse to one line, and each tree level shows the first 50 children plus "… and N more".
- [Catalog drift] → The completeness test runs in CI. `CLAUDE.md` forbids inline user-facing strings.

## Migration Plan

This change ships in **v2.0.0** with `redesign-work-pool-extraction`. It is committed directly on `release/v2.0.0` after that change's stage 2, and released through the single release PR. The commit stages are:

1. Event types, `i18n.py` with the catalog and its tests, and the three renderers with recorded-event tests.
2. Wire the renderers into the pool driver and `main.py`. Add `--json`, exit codes, prompt gating, and `-bsp1` progress. Remove `rich_utils.py`.
3. Docs: the `CLAUDE.md` / `AGENTS.md` conventions, the README `--json` and exit-code section, and the upgrade notes in `docs/releaseNotes/v2.0.0.md`.

## Open Questions

None.
