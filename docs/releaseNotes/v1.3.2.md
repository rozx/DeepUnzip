# Release Notes v1.3.2 / 发布说明 v1.3.2

Version 1.3.2 fixes repeated password prompts when extracting multiple encrypted archives in one run.

1.3.2 修复了同一次运行中解压多个加密压缩包时，需要重复输入相同密码的问题。

## Bug Fixes / 错误修复

### Entered passwords are reused for later archives / 手动输入的密码会复用于后续压缩包 — [#24](https://github.com/rozx/Complex-unzip-tool-v2/issues/24)

After a manually entered password successfully extracts an archive, later single and multipart archives in the same run automatically try it. This also covers passwords entered while extracting nested archives or retrying with an alternative archive in the group. Previously, a password learned in one group was unavailable to later groups in the same processing stage, so archives sharing a password required repeated input.

New passwords are still saved to the tool-directory `passwords.txt` when the run finishes, for reuse next time. Existing comments, blank lines and password order are preserved. Archives skipped because of a missing or incorrect password are still retained.

手动输入密码并成功解压后，工具会立即将该密码用于本次运行后续的单包和分卷。这也适用于嵌套解压和使用组内备用档案重试时输入的密码。此前，同一处理阶段中的后续档案无法使用刚学到的密码，导致使用相同密码的一批压缩包仍需逐个输入。

新密码仍在运行结束时保存到工具目录的 `passwords.txt`，供下次运行复用。已有注释、空行和密码顺序保持不变；因密码缺失或错误而跳过的压缩包仍会保留。
