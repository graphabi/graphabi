"""Run the checked-in GraphABI semantic regression corpus."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from regression_corpus.runner import run_corpus

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT / "regression_corpus")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args()
    results = run_corpus(args.root)
    if args.json_output:
        print(json.dumps({"cases": results}, indent=2))
    else:
        for result in results:
            match = "MATCH" if result["matches_expected"] else "MISMATCH"
            print(
                f"{result['id']}: {result['actual_status']} "
                f"(baseline {result['baseline_status']}, {match})"
            )
        print(f"Corpus cases: {len(results)}")
    return 0 if all(result["matches_expected"] for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
