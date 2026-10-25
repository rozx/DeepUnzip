# Drafts for v2.0.0 / v2.0.0 文稿草稿

Text written by this change for later use: the upgrade notes go into `docs/releaseNotes/v2.0.0.md` (release task 8.3 of `redesign-work-pool-extraction`, written by the `release-ready` skill), and the usage section goes into the READMEs (`rename-to-deepunzip`, README section 5). Both use the new command name `deepunzip`.

本 change 为后续步骤准备的文稿：升级说明写入 `docs/releaseNotes/v2.0.0.md`（`redesign-work-pool-extraction` 的发布任务 8.3，由 `release-ready` skill 生成），用法段落写入各语言 README（`rename-to-deepunzip`，README 第 5 节）。两者都使用新命令名 `deepunzip`。

---

## Draft: upgrade notes / 草稿：升级说明

### New terminal output / 全新的终端输出

In a terminal, DeepUnzip prints one line per finished archive, with a live progress line for the whole run and one for the current archive (percentage, size and speed from 7-Zip). When a folder is done, a lineage tree shows where every output came from: each multipart set lists its volumes, the archive each volume was found in, and the original name of any disguised volume. A summary lists the output files, the sources moved to the Recycle Bin or deleted, and every unresolved item with its reason and location. When the output is redirected to a file or a pipe, the same lines are printed without animation.

在终端中，DeepUnzip 每处理完一个压缩包输出一行，并实时显示整体进度和当前压缩包的进度（百分比、大小和速度来自 7-Zip）。一个文件夹处理完后，会输出一棵来源树，说明每个输出从何而来：每个分卷组列出它的各个分卷、每个分卷来自哪个压缩包，以及被伪装分卷的原始文件名。随后的摘要列出输出文件、移到回收站或已删除的原文件，以及每个未解决的项目及其原因和位置。输出重定向到文件或管道时，打印同样的内容，但没有动画。

### Output follows the system language / 输出语言跟随系统

Output is now in one language per run instead of English and Chinese side by side, and DeepUnzip speaks five languages: English, Simplified Chinese, Traditional Chinese, Japanese and Korean. The system UI language decides; any other system language gets English. Set `DEEPUNZIP_LANG` to `en`, `zh`, `zh-TW`, `ja` or `ko` to choose explicitly.

输出不再中英并列，每次运行只使用一种语言。DeepUnzip 支持五种语言：英文、简体中文、繁体中文、日文和韩文，默认跟随系统界面语言，其他语言的系统使用英文。可以把 `DEEPUNZIP_LANG` 设为 `en`、`zh`、`zh-TW`、`ja` 或 `ko` 来指定语言。

### `--json` for scripts / 供脚本使用的 `--json`

`deepunzip --json <path>` writes newline-delimited JSON events to stdout and nothing else: `start`, `root`, `round`, `item`, `set`, `progress`, `unresolved`, `error`, and always a final `summary`. Every event carries `schema_version: 1`. A `--json` run never prompts and never waits for Enter: an archive whose password is not in the password book becomes unresolved with reason `password`.

`deepunzip --json <路径>` 只向 stdout 输出逐行的 JSON 事件：`start`、`root`、`round`、`item`、`set`、`progress`、`unresolved`、`error`，最后一行总是 `summary`。每个事件都带有 `schema_version: 1`。`--json` 运行从不询问，也不会等待按回车：密码本中没有密码的压缩包会以原因 `password` 标记为未解决。

### Exit codes / 退出码

| Code / 退出码 | Meaning / 含义 |
| --- | --- |
| `0` | Everything was extracted, or there was nothing to do / 全部解压完成，或没有需要处理的内容 |
| `1` | The run finished, but some items are unresolved; their sources are kept / 运行完成，但有未解决的项目，其原文件已保留 |
| `2` | Fatal or usage error: 7-Zip is missing or unusable, no given path exists, or an unexpected error / 致命错误或用法错误：7-Zip 缺失或不可用、给出的路径都不存在，或发生意外错误 |

### Breaking changes / 不兼容变更

- A run that leaves items unresolved now exits with `1` (it exited with `0`). A missing or unusable 7-Zip now exits with `2` (it exited with `1`).
- Output is in a single language and its wording and layout changed. Scripts that parsed the old text should use `--json` instead.
- When stdin is not a console (for example `deepunzip <path> < NUL` or a scheduled task), DeepUnzip no longer prompts: unknown passwords are skipped and leftover renames from an interrupted run are kept.

- 有未解决项目的运行现在以 `1` 退出（原来是 `0`）；7-Zip 缺失或不可用时现在以 `2` 退出（原来是 `1`）。
- 输出改为单一语言，措辞和排版都有变化。解析旧输出文本的脚本请改用 `--json`。
- stdin 不是控制台时（例如 `deepunzip <路径> < NUL` 或计划任务），DeepUnzip 不再询问：未知密码的压缩包会被跳过，中断运行遗留的改名会保留。

Passwords are still never printed: output only names a password by its position in the password book (`password #2`), or as an entered password.

密码依然不会出现在任何输出中：输出只以密码在密码本中的位置（`密码 #2`）或"手动输入的密码"来指代它。

---

## Draft: README usage section / 草稿：README 用法段落

### English

```bash
deepunzip <archive-or-folder>...           # extract; sources go to the Recycle Bin
deepunzip --permanent-delete <path>...     # delete extracted sources permanently
deepunzip --json <path>...                 # JSON lines for scripts; never prompts
deepunzip --version
```

Output goes to an `unzipped` folder inside each input folder (for a file, inside the folder that holds it). Sources are removed only after everything extracted from them is resolved; anything that cannot be extracted is kept and listed with its reason.

- **Language**: output follows the system language (English, Simplified Chinese, Traditional Chinese, Japanese or Korean; English otherwise). Override with `DEEPUNZIP_LANG` set to `en`, `zh`, `zh-TW`, `ja` or `ko`.
- **Passwords**: put one password per line in `passwords.txt` next to the program, or next to the archives. Passwords you type during a run are tried on later archives and saved to the program's `passwords.txt`. Output refers to passwords only as `password #N`.
- **Exit codes**: `0` everything extracted, `1` some items unresolved (their sources kept), `2` fatal or usage error.
- **`--json`**: one JSON object per line (`start`, `root`, `round`, `item`, `set`, `progress`, `unresolved`, `error`, `summary`), each with `schema_version`. The last line is always `summary`:

  ```json
  {"event": "summary", "schema_version": 1, "status": "partial", "files": 12, "output_dirs": ["D:\\Downloads\\unzipped"], "sources": {"deleted": 3, "kept": 1}, "unresolved": [{"root": 1, "path": "locked.7z", "reason": "password"}], "exit": 1}
  ```

### 中文

```bash
deepunzip <压缩包或文件夹>...              # 解压；原文件移到回收站
deepunzip --permanent-delete <路径>...     # 永久删除已解压的原文件
deepunzip --json <路径>...                 # 供脚本读取的 JSON 行；不会询问
deepunzip --version
```

输出位于每个输入文件夹内的 `unzipped` 文件夹（输入是文件时，位于该文件所在的文件夹内）。只有当从原文件解出的所有内容都已解决时，原文件才会被移除；无法解压的内容会被保留，并列出原因。

- **语言**：输出跟随系统语言（英文、简体中文、繁体中文、日文或韩文，其他系统使用英文），可把 `DEEPUNZIP_LANG` 设为 `en`、`zh`、`zh-TW`、`ja` 或 `ko` 指定。
- **密码**：在程序旁边或压缩包旁边的 `passwords.txt` 中每行写一个密码。运行中手动输入的密码会用于后续压缩包，并保存到程序目录的 `passwords.txt`。输出中只以 `密码 #N` 指代密码。
- **退出码**：`0` 全部解压完成，`1` 有未解决的项目（其原文件已保留），`2` 致命错误或用法错误。
- **`--json`**：每行一个 JSON 对象（`start`、`root`、`round`、`item`、`set`、`progress`、`unresolved`、`error`、`summary`），都带有 `schema_version`，最后一行总是 `summary`（示例见上方英文部分）。
