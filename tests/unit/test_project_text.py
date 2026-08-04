"""Small repository hygiene checks for public-facing text."""

import re
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).parents[2]


def _tracked_files() -> list[Path]:
    names = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).split(b"\0")
    return [ROOT / name.decode() for name in names if name]


def test_tracked_project_text_has_no_em_dash() -> None:
    offenders = []
    for path in _tracked_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if chr(0x2014) in text:
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_tracked_text_has_no_private_absolute_paths() -> None:
    offenders = []
    mac_user_prefix = "/" + "Users" + "/"
    windows_user_prefix = "C:" + "\\" + "Users" + "\\"
    for path in _tracked_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if mac_user_prefix in text or windows_user_prefix in text:
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_local_markdown_links_resolve() -> None:
    sources = [ROOT / "README.md", ROOT / "CONTRIBUTING.md", ROOT / "SECURITY.md"]
    sources.extend(sorted((ROOT / "docs").rglob("*.md")))
    sources.extend(sorted((ROOT / "examples").rglob("README.md")))
    missing: list[str] = []
    pattern = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
    for source in sources:
        text = source.read_text(encoding="utf-8")
        for raw_reference in pattern.findall(text):
            reference = raw_reference.strip().strip("<>").split(" ", 1)[0]
            parsed = urlsplit(reference)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            target = (source.parent / unquote(parsed.path)).resolve()
            if not target.exists():
                missing.append(f"{source.relative_to(ROOT)} -> {reference}")
    assert missing == []
