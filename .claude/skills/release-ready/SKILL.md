---
name: release-ready
description: 准备一次发布：核对 release/x.y.z 分支与项目版本（不一致则升级版本号），在 docs/releaseNotes 写中英双语发布说明，按本次改动更新 README 与文档，运行检查，最后推送分支并创建带 release 标签的 PR。用户说“release ready”“准备发布”“发版”或输入 /release-ready 时使用。
---

# release ready

把 `release/<版本>` 分支上的改动整理成一个可合并的发布 PR。合并后，`.github/workflows/release.yml` 在五个平台上构建并冒烟测试，然后以本技能写的发布说明创建 GitHub Release。

一次发布的所有提交都放在 `release/<版本>` 分支上，最后只开**一个** PR 合并到 `main`；不要为发布内容另开功能分支或多个 PR。

按顺序执行下面的步骤，中途不要停下来询问，除非遇到“停止条件”。

## 1. 确定版本与分支

1. 确认工作区干净（`git status --porcelain` 为空），否则停止，请用户先提交或丢弃改动。
2. 读取当前版本：`poetry run python -m scripts.release version`。它同时核对 `pyproject.toml`、`deepunzip/__init__.py` 的 `__version__` 与 `.bumpversion.cfg`，三者不一致时报错。
3. 找到上一次发布：先 `git fetch --tags origin`，再 `git tag --list 'v*' --sort=-v:refname | head -1`。没有标签时视为首次发布。
4. 读取当前分支名 `git branch --show-current`：
   - **在 `release/<版本>` 分支上**（允许 `release/v<版本>`）：分支中的版本即目标版本。
   - **在其他分支上（通常是 `main`）**：按上次发布以来的改动推算目标版本（语义化版本：有 `BREAKING CHANGE` 或 `!` 升主版本号，有 `feat` 升次版本号，否则升修订号）。如果项目版本已经高于上一个标签，直接用它。然后 `git switch -c release/v<目标版本>`。
5. 核对目标版本：
   - 必须是 `x.y.z` 格式，且高于上一个发布标签。
   - `git ls-remote --tags origin "refs/tags/v<目标版本>"` 必须为空。
6. 目标版本与项目版本不一致时，用项目的升级命令一次改齐三处声明，并单独提交 `chore: bump version to <目标版本>`：
   - 正好是下一个主、次或修订版本：`poetry run bump-major`、`poetry run bump-minor` 或 `poetry run bump-patch`。
   - 其他版本：`poetry run bump2version --allow-dirty --new-version <目标版本> patch`。
   - 提交前再运行一次 `poetry run python -m scripts.release version`，确认输出目标版本。`.bumpversion.cfg` 中 `commit = False`、`tag = False` 保持不变。

**停止条件**：工作区不干净、分支名不是 `release/<x.y.z>` 或 `release/v<x.y.z>` 格式、分支中的版本低于项目版本或不高于上一个标签、标签已经存在。说明原因并请用户决定。

## 2. 收集本次改动

以上一个标签为起点（首次发布则从仓库第一个提交开始）：

- `git log <上一个标签>..HEAD --no-merges --format='%h %s'`：提交标题。
- `git diff --stat <上一个标签>..HEAD`：改动范围。
- `openspec/changes/archive/` 中在此期间新增的变更：读它们的 `proposal.md`（为什么、改了什么）和 `tasks.md`（未勾选的项目就是待验收或已知问题）。
- `openspec list` 中仍未归档的变更：说明哪些工作尚未完成。

需要时读具体提交的 diff，弄清对用户可见的行为变化。

## 3. 写发布说明

文件：`docs/releaseNotes/v<目标版本>.md`。发布工作流按这个路径取文件原文作为 GitHub Release 的正文，文件缺失或为空时发布失败。

中英双语：每个小节先写中文，再写英文，与 `docs/releaseNotes/` 中已有说明的双语格式一致。产品名是 DeepUnzip / 深度解压（与 `README.md` 标题一致），发布包名是 `deepunzip`。

```markdown
# <产品名> v<版本>

发布日期 / Release date：<YYYY-MM-DD>

<一两句话概括这次发布。>

<One or two sentences summarizing the release.>

## 新功能 / New features

- <面向用户描述：能做什么、怎么使用。>
- <The same, in English.>

## 改进 / Improvements

## 修复 / Bug fixes

## 下载 / Downloads

| 平台 / Platform | 文件 / File |
| --- | --- |
| Windows x64 | `deepunzip-v<版本>-windows-x64.zip` |
| macOS Intel | `deepunzip-v<版本>-macos-x64.tar.gz` |
| macOS Apple Silicon | `deepunzip-v<版本>-macos-arm64.tar.gz` |
| Linux x64 | `deepunzip-v<版本>-linux-x64.tar.gz` |
| Linux ARM64 | `deepunzip-v<版本>-linux-arm64.tar.gz` |

`SHA256SUMS` 列出各文件的校验和。 / `SHA256SUMS` lists the checksum of every file.

## 升级说明 / Upgrade notes

<文件名、行为或默认值的变化，以及需要用户注意的地方。没有就写“直接替换程序即可。” / “Replace the program; nothing else changes.”>

## 已知问题与待验收 / Known issues and pending verification

<未勾选的 OpenSpec 任务、尚未在实机验证的平台等。>
```

写作要求：

- 面向使用者描述行为变化，不罗列提交哈希，不写内部重构；没有内容的小节删除。
- 下载表与 `scripts/release.py` 的 `TARGETS` 和发布包命名（`package()`）保持一致；目标或包名有变化时同步修改。
- 密码、令牌、分享链接与提取码、用户的真实文件名或路径不得出现在发布说明里；举例时用虚构的名字。
- 遵循项目文风：简洁、陈述句、中文全角标点，代码与路径用反引号。

## 4. 更新 README 与文档

逐一检查每个语言的 README（`README.md`、`README.en.md` 及其他 `README.*.md`）、`AGENTS.md`、`CLAUDE.md` 和 `docs/*.md`（不含 `docs/releaseNotes/`），把与本次改动不符的内容改正：

- 版本摘要、发布包表格、示例包名、发布说明链接。
- 功能、命令与选项、退出码、环境变量、支持的平台与产物名。
- “开发中”“待验收”之类的状态描述：以第 2 步的事实为准，不夸大也不遗漏；验收与已知问题只写在发布说明里，不另建验收文档。
- 各语言 README 的章节结构保持一致。

不要修改 `openspec/specs/`、`openspec/changes/archive/` 和旧版本的发布说明：它们分别由 OpenSpec 流程和历史记录维护。

## 5. 检查与提交

1. 运行下列检查，全部通过才继续；失败时修复或停止，不要带着失败发布：

   ```sh
   poetry run pytest -q
   poetry run python -m scripts.smoke_test
   poetry run python -m scripts.release version
   poetry run python -m scripts.release verify-notes
   poetry run python -m scripts.release verify-engines
   poetry run python -m scripts.release verify-branch "$(git branch --show-current)"
   poetry run main --help
   openspec validate --specs --strict
   git diff --check
   ```

2. 提交（标题用 conventional commits，正文末尾带会话要求的署名行）：
   - 发布说明：`docs: add release notes for v<版本>`
   - 文档更新：`docs: update docs for v<版本>`（没有改动就跳过）

## 6. 推送并创建 PR

1. 确认 `origin` 是本项目的仓库（`git remote get-url origin`）。
2. 确保仓库有 `release` 标签：`gh label list --search release`；没有时创建：
   `gh label create release --color 0E8A16 --description "合并后构建并发布 / Build and publish on merge"`
3. `git push -u origin release/<版本>`
4. 如果该分支已有未合并的 PR，更新它的标题、正文和标签，不要重复创建；否则创建 PR，正文用发布说明，末尾加会话要求的 PR 署名：

   ```sh
   gh pr create --base main --head release/<版本> --title "release: v<版本>" --label release --body-file <正文文件>
   ```

   正文文件写在临时目录（发布说明加署名），不要提交到仓库。
5. 把 PR 链接告诉用户，并说明：合并后工作流会核对版本、分支与标签，在 Windows、macOS、Linux 共五个目标上测试、构建并冒烟测试，然后为合并提交创建 `v<版本>` 标签和 Release，正文取自 `docs/releaseNotes/v<版本>.md`，并上传五个发布包和 `SHA256SUMS`。不要自己合并 PR、创建标签或 Release。

## 发布工作流的约束（供核对）

- PR 必须合并到 `main`，合并时带 `release` 标签，来源分支以 `release/` 开头且位于本仓库。
- 分支名后缀形如版本号时（`release/2.0.0` 或 `release/v2.0.0`），必须与项目版本一致；三处版本声明必须一致。
- `v<版本>` 的标签不能已指向其他提交；已公开的 Release 不会被覆盖（同一合并提交的草稿可以续传）。
- `docs/releaseNotes/v<版本>.md` 必须存在且非空。
- 普通推送与 PR 只在 Ubuntu 和 Windows 上运行快速检查；五个平台的构建与冒烟测试只在发布时进行，也可在 Actions 中手动运行 CI 并勾选 `full_build`。
