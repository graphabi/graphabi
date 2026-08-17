"""Generate or verify checked-in GraphABI regression corpus fixtures."""

from __future__ import annotations

import argparse
import filecmp
import tempfile
from pathlib import Path

import yaml
from regression_corpus.definitions import OBSERVED_AT, corpus_cases

from graphabi.traces import export_json

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "regression_corpus"


def generate(output: Path) -> None:
    entries: list[dict[str, object]] = []
    for case in corpus_cases():
        directory = output / "cases" / case.case_id
        directory.mkdir(parents=True, exist_ok=True)
        contract_path = directory / "contract.yml"
        baseline_path = directory / "baseline.json"
        candidate_path = directory / "candidate.json"
        contract_path.write_text(
            yaml.safe_dump(case.contract, sort_keys=False, allow_unicode=False), encoding="utf-8"
        )
        export_json(case.baseline.model_copy(update={"exported_at": OBSERVED_AT}), baseline_path)
        export_json(case.candidate.model_copy(update={"exported_at": OBSERVED_AT}), candidate_path)
        entries.append(
            {
                "id": case.case_id,
                "category": case.category,
                "rationale": case.rationale,
                "baseline": f"cases/{case.case_id}/baseline.json",
                "candidate": f"cases/{case.case_id}/candidate.json",
                "contract": f"cases/{case.case_id}/contract.yml",
                "expected": {
                    "status": case.expected_status,
                    "first_breaking_edge": case.expected_first_breaking_edge,
                    "findings": [
                        {
                            "invariant": invariant,
                            "status": status,
                            "occurrence_pairing": pairing,
                        }
                        for invariant, status, pairing in case.expected_findings
                    ],
                },
            }
        )
    (output / "manifest.yml").write_text(
        yaml.safe_dump(
            {"schema_version": "0.1", "name": "GraphABI regression corpus", "cases": entries},
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )


def _generated_files(root: Path) -> tuple[Path, ...]:
    return tuple(
        sorted(
            (path.relative_to(root) for path in root.rglob("*") if path.is_file()),
            key=str,
        )
    )


def check(expected: Path) -> bool:
    with tempfile.TemporaryDirectory(prefix="graphabi-corpus-") as temporary:
        actual = Path(temporary)
        generate(actual)
        actual_files = _generated_files(actual)
        expected_files = tuple(
            path
            for path in _generated_files(expected)
            if path == Path("manifest.yml") or "cases" in path.parts
        )
        return actual_files == expected_files and all(
            filecmp.cmp(actual / path, expected / path, shallow=False) for path in actual_files
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        if not check(args.output):
            print(f"Regression corpus fixtures are stale under {args.output}")
            return 1
        print(f"Regression corpus fixtures verified under {args.output}")
        return 0
    generate(args.output)
    print(f"Generated regression corpus fixtures under {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
