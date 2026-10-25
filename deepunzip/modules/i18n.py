"""
User-facing text in five languages.
面向用户的五种语言文案。

Every user-facing string lives in CATALOG with an entry for each language in
LANGUAGES (English, Simplified Chinese, Traditional Chinese, Japanese,
Korean); code calls `t(key, **params)`. An entry may add "en_one", used when
the `count` parameter is 1 ("1 file" rather than "1 files").

The language is chosen once per run: DEEPUNZIP_LANG if it names a supported
language, otherwise the system UI language, otherwise English.
tests/test_i18n.py fails if a key lacks a language or a placeholder differs.
"""

import os
import sys
from typing import Callable, Mapping, Optional

LANGUAGES = ("en", "zh", "zh-TW", "ja", "ko")

CATALOG: dict[str, dict[str, str]] = {
    # ---------- product and CLI ----------
    "product": {
        "en": "DeepUnzip",
        "zh": "深度解压",
        "zh-TW": "深度解壓",
        "ja": "DeepUnzip",
        "ko": "DeepUnzip",
    },
    "version": {
        "en": "{product} {version}",
        "zh": "{product} {version}",
        "zh-TW": "{product} {version}",
        "ja": "{product} {version}",
        "ko": "{product} {version}",
    },
    "cli.help": {
        "en": "Extract nested, password-protected, multipart and disguised archives.",
        "zh": "解开嵌套、加密、分卷和伪装的压缩包。",
        "zh-TW": "解開巢狀、加密、分卷和偽裝的壓縮檔。",
        "ja": "入れ子、パスワード付き、分割、偽装されたアーカイブを展開します。",
        "ko": "중첩, 암호, 분할, 위장된 압축 파일을 풉니다.",
    },
    "cli.paths": {
        "en": "Archives or folders to extract",
        "zh": "要解压的压缩包或文件夹",
        "zh-TW": "要解壓縮的壓縮檔或資料夾",
        "ja": "展開するアーカイブまたはフォルダー",
        "ko": "압축을 풀 파일 또는 폴더",
    },
    "cli.version": {
        "en": "Show the version and exit",
        "zh": "显示版本后退出",
        "zh-TW": "顯示版本後結束",
        "ja": "バージョンを表示して終了",
        "ko": "버전을 표시하고 종료",
    },
    "cli.permanent_delete": {
        "en": "Delete extracted sources permanently instead of moving them "
        "to the recycle bin",
        "zh": "永久删除已解压的原文件，而不是移到回收站",
        "zh-TW": "永久刪除已解壓縮的原始檔，而不是移到資源回收筒",
        "ja": "展開済みの元ファイルをごみ箱に移さず完全に削除",
        "ko": "압축을 푼 원본 파일을 휴지통으로 옮기지 않고 영구 삭제",
    },
    "cli.json": {
        "en": "Write JSON lines for programs instead of the terminal view; "
        "never prompts",
        "zh": "输出供程序读取的 JSON 行而不是终端界面；不会询问",
        "zh-TW": "輸出供程式讀取的 JSON 行，而不是終端機畫面；不會詢問",
        "ja": "端末表示の代わりにプログラム向けの JSON 行を出力（入力を求めない）",
        "ko": "터미널 화면 대신 프로그램용 JSON 줄을 출력 (질문하지 않음)",
    },
    "cli.version_command": {
        "en": "Show the version",
        "zh": "显示版本",
        "zh-TW": "顯示版本",
        "ja": "バージョンを表示",
        "ko": "버전 표시",
    },
    "cli.unknown_option": {
        "en": "Ignoring unknown option: {token}",
        "zh": "忽略未知选项：{token}",
        "zh-TW": "忽略未知選項：{token}",
        "ja": "不明なオプションを無視します: {token}",
        "ko": "알 수 없는 옵션을 무시합니다: {token}",
    },
    "cli.pause": {
        "en": "Press Enter to exit...",
        "zh": "按回车键退出...",
        "zh-TW": "按 Enter 鍵結束...",
        "ja": "Enter キーを押すと終了します...",
        "ko": "Enter 키를 누르면 종료합니다...",
    },
    "cli.deprecated_alias": {
        "en": "`{alias}` is deprecated and will be removed in 3.0.0; "
        "use `deepunzip` (or `dz`).",
        "zh": "`{alias}` 已弃用，将在 3.0.0 移除；请使用 `deepunzip`（或 `dz`）。",
        "zh-TW": "`{alias}` 已棄用，將在 3.0.0 移除；請改用 `deepunzip`（或 `dz`）。",
        "ja": "`{alias}` は非推奨で、3.0.0 で削除されます。" "`deepunzip`（または `dz`）を使ってください。",
        "ko": "`{alias}` 명령은 더 이상 권장되지 않으며 3.0.0에서 제거됩니다. "
        "`deepunzip` 또는 `dz`를 사용하세요.",
    },
    # ---------- errors ----------
    "error.no_input": {
        "en": "None of the given paths exists: {paths}",
        "zh": "给出的路径都不存在：{paths}",
        "zh-TW": "給出的路徑都不存在：{paths}",
        "ja": "指定されたパスがどれも存在しません: {paths}",
        "ko": "지정한 경로가 모두 존재하지 않습니다: {paths}",
    },
    "error.engine": {
        "en": "{detail}",
        "zh": "{detail}",
        "zh-TW": "{detail}",
        "ja": "{detail}",
        "ko": "{detail}",
    },
    "error.unexpected": {
        "en": "Unexpected error: {detail}",
        "zh": "意外错误：{detail}",
        "zh-TW": "意外錯誤：{detail}",
        "ja": "予期しないエラー: {detail}",
        "ko": "예기치 않은 오류: {detail}",
    },
    "error.cancelled": {
        "en": "Cancelled.",
        "zh": "已取消。",
        "zh-TW": "已取消。",
        "ja": "キャンセルしました。",
        "ko": "취소했습니다.",
    },
    # ---------- counted nouns ----------
    "count.files": {
        "en": "{count} files",
        "en_one": "1 file",
        "zh": "{count} 个文件",
        "zh-TW": "{count} 個檔案",
        "ja": "ファイル {count} 個",
        "ko": "파일 {count}개",
    },
    "count.sources": {
        "en": "{count} sources",
        "en_one": "1 source",
        "zh": "{count} 个原文件",
        "zh-TW": "{count} 個原始檔",
        "ja": "元ファイル {count} 個",
        "ko": "원본 {count}개",
    },
    # ---------- item lines ----------
    "line.opened": {
        "en": "{name}  opened → {files}{password}",
        "zh": "{name}  已打开 → {files}{password}",
        "zh-TW": "{name}  已開啟 → {files}{password}",
        "ja": "{name}  展開 → {files}{password}",
        "ko": "{name}  압축 해제 → {files}{password}",
    },
    "line.assembled": {
        "en": "{name}  {volumes} volumes assembled → {files}{password}",
        "zh": "{name}  已拼合 {volumes} 卷 → {files}{password}",
        "zh-TW": "{name}  已合併 {volumes} 卷 → {files}{password}",
        "ja": "{name}  分割 {volumes} 個を結合 → {files}{password}",
        "ko": "{name}  분할 {volumes}개 결합 → {files}{password}",
    },
    "line.kept": {
        "en": "{name}  kept (not an archive)",
        "zh": "{name}  已保留（不是压缩包）",
        "zh-TW": "{name}  已保留（不是壓縮檔）",
        "ja": "{name}  保持（アーカイブではない）",
        "ko": "{name}  유지 (압축 파일 아님)",
    },
    "line.unresolved": {
        "en": "{name}  unresolved: {reason}",
        "zh": "{name}  未解决：{reason}",
        "zh-TW": "{name}  未解決：{reason}",
        "ja": "{name}  未解決: {reason}",
        "ko": "{name}  미해결: {reason}",
    },
    "line.more": {
        "en": "… and {count} more",
        "zh": "…… 另有 {count} 项",
        "zh-TW": "…… 另有 {count} 項",
        "ja": "… ほか {count} 件",
        "ko": "… 외 {count}건",
    },
    "password.index": {
        "en": " · password #{index}",
        "zh": " · 密码 #{index}",
        "zh-TW": " · 密碼 #{index}",
        "ja": " · パスワード #{index}",
        "ko": " · 비밀번호 #{index}",
    },
    "password.entered": {
        "en": " · entered password",
        "zh": " · 手动输入的密码",
        "zh-TW": " · 手動輸入的密碼",
        "ja": " · 入力したパスワード",
        "ko": " · 입력한 비밀번호",
    },
    # ---------- live progress ----------
    "live.overall": {
        "en": "Overall",
        "zh": "总体",
        "zh-TW": "整體",
        "ja": "全体",
        "ko": "전체",
    },
    "live.archives": {
        "en": "{done}/{total} archives",
        "zh": "{done}/{total} 个压缩包",
        "zh-TW": "{done}/{total} 個壓縮檔",
        "ja": "アーカイブ {done}/{total}",
        "ko": "압축 파일 {done}/{total}",
    },
    "live.round": {
        "en": "round {number}",
        "zh": "第 {number} 轮",
        "zh-TW": "第 {number} 輪",
        "ja": "ラウンド {number}",
        "ko": "{number}회차",
    },
    "live.current": {
        "en": "Current",
        "zh": "当前",
        "zh-TW": "目前",
        "ja": "処理中",
        "ko": "현재",
    },
    # ---------- final tree and summary ----------
    "tree.root": {
        "en": "{root}  {sources} → {files}  {elapsed}",
        "zh": "{root}  {sources} → {files}  {elapsed}",
        "zh-TW": "{root}  {sources} → {files}  {elapsed}",
        "ja": "{root}  {sources} → {files}  {elapsed}",
        "ko": "{root}  {sources} → {files}  {elapsed}",
    },
    "tree.set": {
        "en": "{name}  {files}",
        "zh": "{name}  {files}",
        "zh-TW": "{name}  {files}",
        "ja": "{name}  {files}",
        "ko": "{name}  {files}",
    },
    "tree.volume": {
        "en": "{volume} ← {source}",
        "zh": "{volume} ← {source}",
        "zh-TW": "{volume} ← {source}",
        "ja": "{volume} ← {source}",
        "ko": "{volume} ← {source}",
    },
    "tree.input": {
        "en": "input folder",
        "zh": "输入目录",
        "zh-TW": "輸入資料夾",
        "ja": "入力フォルダー",
        "ko": "입력 폴더",
    },
    "tree.uncloaked": {
        "en": "uncloaked from {original}",
        "zh": "原名 {original}",
        "zh-TW": "原名 {original}",
        "ja": "元の名前 {original}",
        "ko": "원래 이름 {original}",
    },
    "tree.unresolved": {
        "en": "{name}: {reason} → {location}",
        "zh": "{name}：{reason} → {location}",
        "zh-TW": "{name}：{reason} → {location}",
        "ja": "{name}: {reason} → {location}",
        "ko": "{name}: {reason} → {location}",
    },
    "tree.in_place": {
        "en": "kept in place",
        "zh": "保留在原处",
        "zh-TW": "保留在原處",
        "ja": "元の場所に保持",
        "ko": "원래 위치에 유지",
    },
    "summary.output": {
        "en": "output: {files} → {folder}",
        "zh": "输出：{files} → {folder}",
        "zh-TW": "輸出：{files} → {folder}",
        "ja": "出力: {files} → {folder}",
        "ko": "출력: {files} → {folder}",
    },
    "summary.recycled": {
        "en": "sources: {count} moved to the recycle bin",
        "zh": "原文件：{count} 个已移到回收站",
        "zh-TW": "原始檔：{count} 個已移到資源回收筒",
        "ja": "元ファイル: {count} 個をごみ箱に移動",
        "ko": "원본: {count}개를 휴지통으로 이동",
    },
    "summary.deleted": {
        "en": "sources: {count} deleted",
        "zh": "原文件：{count} 个已删除",
        "zh-TW": "原始檔：{count} 個已刪除",
        "ja": "元ファイル: {count} 個を削除",
        "ko": "원본: {count}개 삭제",
    },
    "summary.kept": {
        "en": "sources kept: {count}",
        "zh": "保留的原文件：{count} 个",
        "zh-TW": "保留的原始檔：{count} 個",
        "ja": "保持した元ファイル: {count} 個",
        "ko": "유지한 원본: {count}개",
    },
    "summary.work_dir_kept": {
        "en": "work directory kept: {path}",
        "zh": "工作目录已保留：{path}",
        "zh-TW": "工作資料夾已保留：{path}",
        "ja": "作業フォルダーを残しました: {path}",
        "ko": "작업 폴더를 남겨 두었습니다: {path}",
    },
    "summary.done": {
        "en": "Done in {elapsed} · exit code {code}",
        "zh": "完成，用时 {elapsed} · 退出码 {code}",
        "zh-TW": "完成，用時 {elapsed} · 結束代碼 {code}",
        "ja": "完了 {elapsed} · 終了コード {code}",
        "ko": "완료 {elapsed} · 종료 코드 {code}",
    },
    "summary.passwords_saved": {
        "en": "New passwords saved to {path}",
        "zh": "新密码已保存到 {path}",
        "zh-TW": "新密碼已儲存到 {path}",
        "ja": "新しいパスワードを保存しました: {path}",
        "ko": "새 비밀번호를 저장했습니다: {path}",
    },
    "summary.passwords_failed": {
        "en": "Could not save passwords to {path} ({error}). Check write permissions.",
        "zh": "无法保存密码本 {path}（{error}），请检查写入权限。",
        "zh-TW": "無法儲存密碼本 {path}（{error}），請檢查寫入權限。",
        "ja": "パスワードを保存できませんでした: {path}（{error}）。" "書き込み権限を確認してください。",
        "ko": "비밀번호를 저장하지 못했습니다: {path} ({error}). 쓰기 권한을 확인하세요.",
    },
    # ---------- unresolved reasons ----------
    "reason.password": {
        "en": "wrong or missing password",
        "zh": "密码错误或缺失",
        "zh-TW": "密碼錯誤或缺少密碼",
        "ja": "パスワードが違うか不明",
        "ko": "비밀번호가 틀리거나 없음",
    },
    "reason.missing volume": {
        "en": "missing volume",
        "zh": "缺少分卷",
        "zh-TW": "缺少分卷",
        "ja": "分割ボリュームが不足",
        "ko": "분할 볼륨 누락",
    },
    "reason.unmatched volume": {
        "en": "volume without its set",
        "zh": "找不到所属的分卷组",
        "zh-TW": "找不到所屬的分卷組",
        "ja": "対応する分割セットがない",
        "ko": "속한 분할 세트를 찾지 못함",
    },
    "reason.assembly failed": {
        "en": "volumes do not form a set",
        "zh": "分卷无法组成完整的压缩包",
        "zh-TW": "分卷無法組成完整的壓縮檔",
        "ja": "分割ボリュームを結合できない",
        "ko": "분할 볼륨을 하나로 결합하지 못함",
    },
    "reason.too many combinations": {
        "en": "too many volume combinations",
        "zh": "分卷组合过多",
        "zh-TW": "分卷組合過多",
        "ja": "ボリュームの組み合わせが多すぎる",
        "ko": "볼륨 조합이 너무 많음",
    },
    "reason.unsupported": {
        "en": "not a supported archive",
        "zh": "不支持的压缩格式",
        "zh-TW": "不支援的壓縮格式",
        "ja": "対応していない形式",
        "ko": "지원하지 않는 형식",
    },
    "reason.not a valid archive": {
        "en": "not a valid archive",
        "zh": "不是有效的压缩包",
        "zh-TW": "不是有效的壓縮檔",
        "ja": "有効なアーカイブではない",
        "ko": "올바른 압축 파일이 아님",
    },
    "reason.empty": {
        "en": "empty archive",
        "zh": "空压缩包",
        "zh-TW": "空的壓縮檔",
        "ja": "空のアーカイブ",
        "ko": "빈 압축 파일",
    },
    "reason.max depth": {
        "en": "nested too deep",
        "zh": "嵌套层数过多",
        "zh-TW": "巢狀層數過多",
        "ja": "入れ子が深すぎる",
        "ko": "중첩이 너무 깊음",
    },
    "reason.move failed": {
        "en": "could not move to output",
        "zh": "无法移到输出目录",
        "zh-TW": "無法移到輸出資料夾",
        "ja": "出力先に移動できない",
        "ko": "출력 폴더로 옮기지 못함",
    },
    "reason.error": {
        "en": "extraction error",
        "zh": "解压出错",
        "zh-TW": "解壓縮出錯",
        "ja": "展開エラー",
        "ko": "압축 해제 오류",
    },
    # ---------- password prompt ----------
    "prompt.title": {
        "en": "No known password opens {name}.",
        "zh": "已知密码都无法打开 {name}。",
        "zh-TW": "已知密碼都無法開啟 {name}。",
        "ja": "既知のパスワードでは {name} を開けません。",
        "ko": "{name}: 알려진 비밀번호로는 열 수 없습니다.",
    },
    "prompt.choices": {
        "en": "1) enter a password   2) skip this archive   "
        "3) skip all password prompts",
        "zh": "1) 输入密码   2) 跳过此压缩包   3) 跳过所有密码提示",
        "zh-TW": "1) 輸入密碼   2) 略過此壓縮檔   3) 略過所有密碼詢問",
        "ja": "1) パスワードを入力   2) このアーカイブをスキップ   " "3) 以降のパスワード入力をすべてスキップ",
        "ko": "1) 비밀번호 입력   2) 이 파일 건너뛰기   3) 이후 비밀번호 질문 모두 건너뛰기",
    },
    "prompt.choose": {
        "en": "Choose 1/2/3 [2]: ",
        "zh": "请选择 1/2/3 [2]：",
        "zh-TW": "請選擇 1/2/3 [2]：",
        "ja": "1/2/3 を選択 [2]: ",
        "ko": "1/2/3 중 선택 [2]: ",
    },
    "prompt.password": {
        "en": "Password: ",
        "zh": "密码：",
        "zh-TW": "密碼：",
        "ja": "パスワード: ",
        "ko": "비밀번호: ",
    },
    "prompt.invalid": {
        "en": "Enter 1, 2 or 3.",
        "zh": "请输入 1、2 或 3。",
        "zh-TW": "請輸入 1、2 或 3。",
        "ja": "1、2、3 のいずれかを入力してください。",
        "ko": "1, 2, 3 중 하나를 입력하세요.",
    },
    # ---------- recovery at startup ----------
    "recovery.work_dir": {
        "en": "Work directory left by an interrupted run: {path}",
        "zh": "发现中断运行遗留的工作目录：{path}",
        "zh-TW": "發現中斷執行遺留的工作資料夾：{path}",
        "ja": "中断された実行の作業フォルダーが残っています: {path}",
        "ko": "중단된 실행이 남긴 작업 폴더가 있습니다: {path}",
    },
    "recovery.restored": {
        "en": "Restored {count} source volume(s) moved by an interrupted run",
        "zh": "已还原中断运行移动的 {count} 个原始分卷",
        "zh-TW": "已還原中斷執行時移動的 {count} 個原始分卷",
        "ja": "中断された実行で移動した元の分割ボリューム {count} 個を戻しました",
        "ko": "중단된 실행에서 옮긴 원본 분할 볼륨 {count}개를 되돌렸습니다",
    },
    "recovery.pending": {
        "en": "A previous run left {count} rename(s):",
        "zh": "上次运行遗留了 {count} 条改名记录：",
        "zh-TW": "上次執行遺留了 {count} 筆改名紀錄：",
        "ja": "前回の実行で名前変更が {count} 件残っています:",
        "ko": "이전 실행에서 남은 이름 변경 {count}건:",
    },
    "recovery.other_root": {
        "en": "These were recorded for another input folder: {root}",
        "zh": "这些记录来自另一个输入目录：{root}",
        "zh-TW": "這些紀錄來自另一個輸入資料夾：{root}",
        "ja": "これらは別の入力フォルダーの記録です: {root}",
        "ko": "다른 입력 폴더의 기록입니다: {root}",
    },
    "recovery.entry": {
        "en": "{renamed} → {original}",
        "zh": "{renamed} → {original}",
        "zh-TW": "{renamed} → {original}",
        "ja": "{renamed} → {original}",
        "ko": "{renamed} → {original}",
    },
    "recovery.more": {
        "en": "… and {count} more",
        "zh": "…… 另有 {count} 条",
        "zh-TW": "…… 另有 {count} 筆",
        "ja": "… ほか {count} 件",
        "ko": "… 외 {count}건",
    },
    "recovery.ask": {
        "en": "Revert these renames before starting? (y/N): ",
        "zh": "开始前回滚这些改名吗？(y/N)：",
        "zh-TW": "開始前還原這些改名嗎？(y/N)：",
        "ja": "開始前にこれらの名前変更を元に戻しますか? (y/N): ",
        "ko": "시작하기 전에 이 이름 변경을 되돌릴까요? (y/N): ",
    },
    "recovery.skipped": {
        "en": "Renames kept; this run overwrites the history file.",
        "zh": "保留改名；本次运行会覆盖历史记录。",
        "zh-TW": "保留改名；這次執行會覆寫紀錄檔。",
        "ja": "名前はそのままにします。今回の実行で履歴ファイルを上書きします。",
        "ko": "이름을 그대로 둡니다. 이번 실행에서 기록 파일을 덮어씁니다.",
    },
    "recovery.reverted": {
        "en": "Reverted {count} rename(s).",
        "zh": "已回滚 {count} 个改名。",
        "zh-TW": "已還原 {count} 個改名。",
        "ja": "名前変更を {count} 件元に戻しました。",
        "ko": "이름 변경 {count}건을 되돌렸습니다.",
    },
    "history.reverted": {
        "en": "Reverted {count} rename(s) of kept files",
        "zh": "已回滚 {count} 个保留文件的改名",
        "zh-TW": "已還原 {count} 個保留檔案的改名",
        "ja": "保持したファイルの名前変更を {count} 件元に戻しました",
        "ko": "유지한 파일의 이름 변경 {count}건을 되돌렸습니다",
    },
    # ---------- notices from library code ----------
    "notice.rename_duplicate": {
        "en": "{name} duplicates {existing}; renamed to {target}",
        "zh": "{name} 与 {existing} 重复，已改名为 {target}",
        "zh-TW": "{name} 與 {existing} 重複，已改名為 {target}",
        "ja": "{name} は {existing} と重複するため、{target} に名前を変更しました",
        "ko": "{name}: {existing} 파일과 중복되어 이름 변경 → {target}",
    },
    "notice.rename_failed": {
        "en": "Could not rename {name}: {error}",
        "zh": "无法重命名 {name}：{error}",
        "zh-TW": "無法重新命名 {name}：{error}",
        "ja": "{name} の名前を変更できません: {error}",
        "ko": "{name}: 이름을 바꾸지 못했습니다 ({error})",
    },
    "notice.path_fallback": {
        "en": "Path problem while extracting {name}; retrying with safe file names",
        "zh": "解压 {name} 时遇到路径问题，改用安全的文件名重试",
        "zh-TW": "解壓縮 {name} 時遇到路徑問題，改用安全的檔名重試",
        "ja": "{name} の展開中にパスの問題が起きたため、安全なファイル名で再試行します",
        "ko": "{name} 압축 해제 중 경로 문제가 생겨 안전한 파일 이름으로 다시 시도합니다",
    },
    "notice.remove_failed": {
        "en": "{detail}",
        "zh": "{detail}",
        "zh-TW": "{detail}",
        "ja": "{detail}",
        "ko": "{detail}",
    },
    "notice.missing_path": {
        "en": "Path not found, skipped: {path}",
        "zh": "路径不存在，已跳过：{path}",
        "zh-TW": "路徑不存在，已略過：{path}",
        "ja": "パスが見つからないためスキップしました: {path}",
        "ko": "경로가 없어 건너뜁니다: {path}",
    },
    "notice.rules_failed": {
        "en": "Could not load the uncloaking rules from {path}: {error}",
        "zh": "无法加载伪装文件规则 {path}：{error}",
        "zh-TW": "無法載入偽裝檔名規則 {path}：{error}",
        "ja": "偽装ファイル名のルールを読み込めません: {path}: {error}",
        "ko": "위장 파일 이름 규칙을 불러오지 못했습니다: {path}: {error}",
    },
    "notice.signature_failed": {
        "en": "Could not check the file signature of {name}: {error}",
        "zh": "无法检查 {name} 的文件签名：{error}",
        "zh-TW": "無法檢查 {name} 的檔案簽章：{error}",
        "ja": "{name} のファイルシグネチャを確認できません: {error}",
        "ko": "{name}: 파일 시그니처를 확인하지 못했습니다 ({error})",
    },
    "notice.move_failed": {
        "en": "Could not move {name}: {error}",
        "zh": "无法移动 {name}：{error}",
        "zh-TW": "無法移動 {name}：{error}",
        "ja": "{name} を移動できません: {error}",
        "ko": "{name}: 옮기지 못했습니다 ({error})",
    },
    # ---------- file helper messages (passed to callbacks) ----------
    "file.rename_error": {
        "en": "Error renaming file {old} to {new}: {error}",
        "zh": "重命名文件出错 {old} → {new}：{error}",
        "zh-TW": "重新命名檔案出錯 {old} → {new}：{error}",
        "ja": "ファイル名の変更に失敗しました {old} → {new}: {error}",
        "ko": "파일 이름 변경 오류 {old} → {new}: {error}",
    },
    "file.remove_error": {
        "en": "Error removing file {path}: {error}",
        "zh": "删除文件出错 {path}：{error}",
        "zh-TW": "刪除檔案出錯 {path}：{error}",
        "ja": "ファイルの削除に失敗しました {path}: {error}",
        "ko": "파일 삭제 오류 {path}: {error}",
    },
    "file.group_rename_missing": {
        "en": "Could not rename {old} to {new}: the file does not exist. "
        "The group is not updated.",
        "zh": "无法将 {old} 改名为 {new}：文件不存在，分组未更新。",
        "zh-TW": "無法將 {old} 改名為 {new}：檔案不存在，分組未更新。",
        "ja": "{old} を {new} に変更できません: ファイルが存在しません。" "グループは更新されません。",
        "ko": "{old} → {new} 이름 변경 실패: 파일이 없습니다. 그룹을 갱신하지 않습니다.",
    },
    "file.moved": {
        "en": "Moved: {path}",
        "zh": "已移动：{path}",
        "zh-TW": "已移動：{path}",
        "ja": "移動しました: {path}",
        "ko": "이동함: {path}",
    },
    "file.move_error": {
        "en": "Error moving {path}: {error}",
        "zh": "移动出错 {path}：{error}",
        "zh-TW": "移動出錯 {path}：{error}",
        "ja": "移動に失敗しました {path}: {error}",
        "ko": "이동 오류 {path}: {error}",
    },
}

# Chinese regions and scripts written in Traditional characters.
_TRADITIONAL_CHINESE = {"tw", "hk", "mo", "hant"}
# Windows LANGIDs: primary language IDs, and the Chinese sublanguages for
# Taiwan, Hong Kong, Macau and the zh-Hant neutral.
_WINDOWS_PRIMARY = {0x11: "ja", 0x12: "ko"}
_WINDOWS_CHINESE = 0x04
_WINDOWS_TRADITIONAL_SUBLANGUAGES = {0x01, 0x03, 0x05, 0x1F}

_language: Optional[str] = None


def normalize_language(value: str) -> Optional[str]:
    """Map a language name ("zh_TW.UTF-8", "ja-JP", "zh-Hant") to LANGUAGES."""
    name = value.split(".")[0].split("@")[0].strip().lower().replace("_", "-")
    parts = [part for part in name.split("-") if part]
    if not parts:
        return None
    if parts[0] == "zh":
        regions = set(parts[1:])
        if "hans" not in regions and regions & _TRADITIONAL_CHINESE:
            return "zh-TW"
        return "zh"
    return parts[0] if parts[0] in ("en", "ja", "ko") else None


def language_from_langid(langid: int) -> str:
    """Map a Windows LANGID to a catalog language."""
    primary, sublanguage = langid & 0x3FF, langid >> 10
    if primary == _WINDOWS_CHINESE:
        traditional = sublanguage in _WINDOWS_TRADITIONAL_SUBLANGUAGES
        return "zh-TW" if traditional else "zh"
    return _WINDOWS_PRIMARY.get(primary, "en")


def posix_language(env: Mapping[str, str]) -> Optional[str]:
    """Language from the first set of LC_ALL, LC_MESSAGES and LANG, or None."""
    for name in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = env.get(name)
        if value:
            return normalize_language(value) or "en"
    return None


def system_language() -> Optional[str]:
    """The operating system's UI language, or None when it cannot be read."""
    if sys.platform == "win32":
        try:
            import ctypes

            windll = getattr(ctypes, "windll")
            return language_from_langid(int(windll.kernel32.GetUserDefaultUILanguage()))
        except (AttributeError, OSError):
            return None
    return posix_language(os.environ)


def resolve_language(
    env: Optional[Mapping[str, str]] = None,
    system_language: Callable[[], Optional[str]] = system_language,
) -> str:
    """DEEPUNZIP_LANG first, then the system UI language, then English."""
    env = os.environ if env is None else env
    override = normalize_language(env.get("DEEPUNZIP_LANG", ""))
    if override is not None:
        return override
    return system_language() or "en"


def set_language(language: str) -> None:
    global _language
    _language = normalize_language(language) or "en"


def get_language() -> str:
    if _language is None:
        set_language(resolve_language())
    assert _language is not None
    return _language


def t(key: str, **params: object) -> str:
    """The text of `key` in the run's language (English when missing)."""
    entry = CATALOG.get(key)
    if entry is None:
        return key
    language = get_language()
    if language not in entry:
        language = "en"
    text = entry[language]
    if params.get("count") == 1:
        text = entry.get(f"{language}_one", text)
    return text.format(**params) if params else text
