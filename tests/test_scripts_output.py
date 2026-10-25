"""Developer scripts print emoji; redirected Windows output must not crash."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
# Select the Windows behavior on any host, as tests/test_platform_cli.py does.
WINDOWS = "import platform; platform.system = lambda: 'Windows'; "


def _run_with_gbk_pipe(script):
    return subprocess.run(
        [sys.executable, "-c", WINDOWS + script],
        cwd=ROOT,
        env={**os.environ, "PYTHONUTF8": "0", "PYTHONIOENCODING": "gbk"},
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=60,
    )


@pytest.mark.parametrize(
    "script, expected",
    [
        (
            "import scripts.version as v; v.subprocess.run = lambda *a, **k: None; "
            "v.run_bump2version('patch')",
            "✓ Successfully bumped patch version",
        ),
        (
            "import scripts.build as b; "
            "from deepunzip.modules.seven_zip_runtime import SevenZipNotFoundError; "
            "b.generate_spec_content = lambda *a: "
            "(_ for _ in ()).throw(SevenZipNotFoundError('missing engine')); "
            "raise SystemExit(b.main())",
            "❌ Error: missing engine",
        ),
    ],
    ids=["bump", "build"],
)
def test_scripts_print_emoji_to_a_legacy_code_page_pipe(script, expected):
    result = _run_with_gbk_pipe(script)
    assert expected in result.stdout.decode("utf-8"), result.stderr.decode("utf-8")
