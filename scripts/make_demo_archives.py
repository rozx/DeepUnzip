"""Build the demo archive set used for the README screenshots.

Everything is generated: placeholder files with seeded random bytes, demo
passwords, and archives made with the bundled 7-Zip. The set mirrors the
cases DeepUnzip is built for:

- `Holiday Photos.7z`: encrypted with demo password #1;
- `docs.zip` → `manual.7z` → `manual.pdf`: nested archives;
- `Concert.7z.001删除`: a disguised first volume in the folder, whose
  `.002` sits in the encrypted `part2.7z` and `.003` in `part3.zip`;
- `readme.txt`: a regular file that is kept;
- `passwords.txt`: the demo password book.

Usage: poetry run python -m scripts.make_demo_archives <empty-or-new-folder>
"""

import argparse
import random
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from deepunzip.modules.seven_zip_runtime import resolve_seven_zip_path

DEMO_PASSWORDS = ("demo-pass-1", "demo-pass-2")
CONCERT_SIZE = 3_000_000


def _placeholder(path: Path, size: int, seed: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(random.Random(seed).randbytes(size))


def _seven_zip(engine: str, cwd: Path, *args: str) -> None:
    subprocess.run(
        [engine, "a", "-bso0", "-bsp0", *args],
        cwd=cwd,
        check=True,
        stdin=subprocess.DEVNULL,
    )


def build(target: Path) -> list[Path]:
    """Write the demo set into `target`; return the files created there."""
    if target.exists() and any(target.iterdir()):
        raise FileExistsError(f"{target} is not empty")
    target.mkdir(parents=True, exist_ok=True)
    engine = resolve_seven_zip_path()
    first, second = DEMO_PASSWORDS

    with tempfile.TemporaryDirectory(prefix="deepunzip-demo-") as temporary:
        work = Path(temporary)

        photos = work / "photos"
        for number in range(1, 4):
            _placeholder(photos / f"IMG_000{number}.jpg", 40_000, seed=number)
        _seven_zip(
            engine, work, f"-p{first}", str(target / "Holiday Photos.7z"), "photos"
        )

        _placeholder(work / "manual.pdf", 60_000, seed=10)
        _seven_zip(engine, work, "manual.7z", "manual.pdf")
        with zipfile.ZipFile(target / "docs.zip", "w") as archive:
            archive.write(work / "manual.7z", "manual.7z")

        _placeholder(work / "Concert.mkv", CONCERT_SIZE, seed=20)
        _seven_zip(
            engine,
            work,
            "-mx0",
            f"-v{CONCERT_SIZE // 3 + 4096}b",  # three volumes
            f"-p{second}",
            "Concert.7z",
            "Concert.mkv",
        )
        shutil.copy(work / "Concert.7z.001", target / "Concert.7z.001删除")
        _seven_zip(
            engine, work, f"-p{first}", str(target / "part2.7z"), "Concert.7z.002"
        )
        with zipfile.ZipFile(target / "part3.zip", "w") as archive:
            archive.write(work / "Concert.7z.003", "Concert.7z.003")

    (target / "readme.txt").write_text(
        "DeepUnzip demo files. Everything here is generated.\n", encoding="utf-8"
    )
    (target / "passwords.txt").write_text(
        "# Demo passwords\n" + "\n".join(DEMO_PASSWORDS) + "\n", encoding="utf-8"
    )
    return sorted(target.iterdir())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("target", type=Path, help="an empty or new folder")
    for path in build(parser.parse_args().target):
        print(path.name)


if __name__ == "__main__":
    main()
