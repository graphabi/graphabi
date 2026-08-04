"""Verify public proof metrics against the current source tree and test run."""

from __future__ import annotations

import io
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

from coverage import Coverage

from graphabi.contracts.evaluators import default_registry

ROOT = Path(__file__).resolve().parents[1]
PROOF = ROOT / "docs/public-proof.json"


def _test_count() -> int:
    output = subprocess.check_output(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=ROOT,
        text=True,
    )
    match = re.search(r"(\d+) tests collected", output)
    if match is None:
        raise RuntimeError("pytest collection output did not contain a test count")
    return int(match.group(1))


def _coverage_percent() -> float:
    data_file = ROOT / ".coverage"
    if not data_file.is_file():
        raise RuntimeError(".coverage is missing; run `make test` before `make proof`")
    coverage = Coverage(data_file=str(data_file))
    coverage.load()
    return round(coverage.report(file=io.StringIO()), 2)


def _python_versions() -> list[str]:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    prefix = "Programming Language :: Python :: "
    return sorted(
        classifier.removeprefix(prefix)
        for classifier in project["classifiers"]
        if classifier.startswith(prefix)
    )


def _maintained_adapters() -> list[str]:
    root = ROOT / "src/graphabi/adapters"
    return sorted(
        path.name for path in root.iterdir() if path.is_dir() and not path.name.startswith("_")
    )


def main() -> int:
    expected = json.loads(PROOF.read_text(encoding="utf-8"))
    actual = {
        "tests": _test_count(),
        "coverage_percent": _coverage_percent(),
        "python_versions": _python_versions(),
        "evaluator_names": list(default_registry().names),
        "maintained_adapters": _maintained_adapters(),
    }
    if actual != expected:
        print("Public proof metrics are stale.")
        print(json.dumps({"expected": expected, "actual": actual}, indent=2))
        return 1
    print(
        f"Public proof verified: {actual['tests']} tests, "
        f"{actual['coverage_percent']:.2f}% coverage, "
        f"{len(actual['evaluator_names'])} evaluators."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
