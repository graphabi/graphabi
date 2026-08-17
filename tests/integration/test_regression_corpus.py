from pathlib import Path

from regression_corpus.runner import run_corpus
from scripts.generate_regression_corpus import check

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "regression_corpus"


def test_checked_in_regression_corpus_matches_engine_results() -> None:
    results = run_corpus(CORPUS)

    assert len(results) == 10
    assert {result["category"] for result in results} == {
        "provenance",
        "preservation",
        "units",
        "authority",
        "freshness",
        "loops",
        "fan-out",
        "model-migration",
        "prompt-migration",
        "tool-migration",
    }
    assert all(result["baseline_status"] == "PASS" for result in results)
    assert all(result["matches_expected"] for result in results)


def test_checked_in_regression_corpus_is_reproducible() -> None:
    assert check(CORPUS)
