"""Small repository hygiene checks for public-facing text."""

import subprocess
from pathlib import Path


def test_tracked_project_text_has_no_em_dash() -> None:
    root = Path(__file__).parents[2]
    names = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).split(b"\0")
    files = [root / name.decode() for name in names if name]
    offenders = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if chr(0x2014) in text:
            offenders.append(str(path.relative_to(root)))
    assert offenders == []
