The tasks follow TDD with mocked 7-Zip. They are committed directly on `release/v2.0.0` (single release PR), after stage 2 of `redesign-work-pool-extraction` and before `rename-to-deepunzip`.

## 1. Events and localization

- [x] 1.1 Finalize the typed event dataclasses that the work pool emits (`RunStarted`, `RootStarted`, `RoundStarted`, `ItemOpened`, `SetAssembled`, `ItemUnresolved`, `Progress`, `PromptNeeded`, `RootFinished` with lineage snapshot, `RunFinished`). Record event sequences from the work-pool regression tests as fixtures.
- [x] 1.2 `modules/i18n.py`:
  - a catalog `{key: {"en", "zh"}}` with a `t(key, **kw)` accessor;
  - language resolution in this order: `DEEPUNZIP_LANG`, then the Windows `GetUserDefaultUILanguage` (via `ctypes`), then POSIX `LC_ALL` / `LC_MESSAGES` / `LANG`, then English;
  - unsupported override values are ignored;
  - tests with a monkeypatched environment and `ctypes`.
- [x] 1.3 Catalog completeness test: fail when any key lacks `en` or `zh`. At runtime, a missing `zh` falls back to `en`.
- [x] 1.4 Move every user-facing string into the catalog, including Typer help and option text. That covers `main.py`, `archive_utils.py`, `file_utils.py`, `cloaked_file_detector.py`, `rename_history.py` and `password_util.py`. No inline bilingual strings remain.

## 2. Renderers

- [x] 2.1 Renderer selection at startup:
  - `--json` → `JsonRenderer`;
  - stdout is a TTY → `TreeRenderer`;
  - otherwise → `PlainRenderer`.

  Create the `Console` with `force_terminal=None`, keep the Windows UTF-8 reconfiguration, and honor `NO_COLOR`.
- [x] 2.2 `PlainRenderer`:
  - item lines, capped at 200 per root with a "… and N more" line;
  - the lineage tree and summary;
  - test that redirected output has no cursor-movement sequences and no repeated lines.
- [x] 2.3 `TreeRenderer`: Rich `Live`, with the overall and current-item lines below the item lines. The final lineage tree shows:
  - for each set, its volumes with their source containers and uncloaked original names;
  - unresolved items with reason and location;
  - collapsed single-level containers, at most 50 children per level, and middle truncation of long names.
- [x] 2.4 `JsonRenderer`:
  - one object per line, each with `event` and `schema_version: 1`;
  - event types `start` / `root` / `round` / `item` / `set` / `progress` / `unresolved` / `error` / `summary`;
  - `summary` is always last;
  - `progress` is throttled to one per 200 ms or per 1% change;
  - nothing else is written to stdout;
  - the event stream is identical under `zh` and `en`.
- [x] 2.5 Password masking test: feed events from a run with a known password book through all three renderers. Assert that no password text appears, and that `password #N` / `password_index` is used instead.

## 3. 7-Zip progress

- [x] 3.1 Run extraction as `7z x … -bsp2` through `Popen`: progress and `ERROR:` lines arrive on stderr, stdout keeps the normal output, and both still reach `_raise_for_7z_error`.
- [x] 3.2 Progress stream parser: split on `\b`, `\r` and `\n`, and extract the percentage (7-Zip prints no byte counts). Test it with a recorded Windows byte stream.
- [x] 3.3 Turn the parsed values into `Progress` events (percent, bytes done and total; the terminal view derives the speed), emitted when the percentage changes and throttled as in 2.4.

## 4. CLI wiring

- [x] 4.1 Add the `--json` option. The run is non-interactive when `--json` is set or stdin is not a TTY. In that case:
  - password prompts are skipped (the item becomes unresolved with reason `password`);
  - the recovery prompt takes its default;
  - there is no exit pause.
- [x] 4.2 Every `input()` prompt treats `EOFError` as its default. Test with a closed stdin and an unknown password: the run completes without an exception.
- [x] 4.3 Exit codes:
  - `0` when everything is resolved;
  - `1` when anything is unresolved;
  - `2` when the engine is missing or unusable, no valid input path is given, or an unexpected exception occurs;
  - `0` for `--help` and `--version`.

  The Windows pause rule is unchanged but never applies with `--json`. Add tests for each code.
- [x] 4.4 Connect the renderers to the pool driver. Remove the temporary `rich_utils` adapter and `modules/rich_utils.py`.
- [x] 4.5 Quality gates: `pytest -q`, `flake8`, `mypy`, `black`, plus `--help` in both languages.

## 5. Docs

- [ ] 5.1 In `CLAUDE.md` / `AGENTS.md`, replace the "all user-facing strings bilingual inline" rule with the catalog rule (add keys in both languages, and never use inline user-facing strings).
- [ ] 5.2 Draft the upgrade-notes text for `docs/releaseNotes/v2.0.0.md` (exit codes, single-language output, `DEEPUNZIP_LANG`, `--json`) and the README usage section text, for use in `rename-to-deepunzip` and in release task 8.3.
