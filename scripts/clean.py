"""Remove only known GraphABI-generated local state."""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = (
    ROOT / ".graphabi/demo",
    ROOT / ".graphabi/reports",
    ROOT / "benchmarks/latest.json",
    ROOT / "benchmarks/latest.md",
    ROOT / "dist",
    ROOT / "htmlcov",
    ROOT / ".coverage",
)

for target in TARGETS:
    if target.is_dir():
        shutil.rmtree(target)
    elif target.exists():
        target.unlink()
