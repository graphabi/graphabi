from datetime import timedelta
from pathlib import Path

from examples.research_graph.graph import run_graph
from fastapi.testclient import TestClient

from graphabi.comparison import compare_schemas, compare_semantics
from graphabi.contracts import load_contract
from graphabi.inference import infer_contracts
from graphabi.reporting import CompatibilityReport, write_report
from graphabi.reporting.server import create_report_app

ROOT = Path(__file__).resolve().parents[2]


def test_inference_is_labeled_and_does_not_edit_contract() -> None:
    contract_path = ROOT / "examples/research_graph/contracts.yml"
    before = contract_path.read_bytes()
    baseline, _ = run_graph("baseline", "inference")
    suggestions = infer_contracts(baseline)
    assert suggestions
    assert all(item.label == "SUGGESTED: NOT ENFORCED" for item in suggestions)
    assert any(item.evaluator == "provenance" and item.confidence == 1 for item in suggestions)
    assert any(item.evaluator == "unit_consistency" for item in suggestions)
    assert any("evaluator: freshness" in item.yaml_snippet for item in suggestions)
    assert contract_path.read_bytes() == before


def test_inference_does_not_treat_future_evidence_as_fresh_support() -> None:
    baseline, _ = run_graph("baseline", "future-inference")
    observations = tuple(
        item.model_copy(
            update={
                "metadata": {
                    **item.metadata,
                    "evidence_observed_at": (item.observed_at + timedelta(hours=1)).isoformat(),
                }
            }
        )
        if "evidence_observed_at" in item.metadata
        else item
        for item in baseline.edge_observations
    )
    future = baseline.model_copy(update={"edge_observations": observations})
    suggestions = infer_contracts(future)
    assert not any(item.evaluator == "freshness" for item in suggestions)


def test_report_is_offline_versioned_and_served(tmp_path: Path) -> None:
    contract = load_contract(ROOT / "examples/research_graph/contracts.yml")
    baseline, baseline_result = run_graph("baseline", "baseline-report")
    candidate, candidate_result = run_graph("candidate", "candidate-report")
    schema = baseline_result.model_json_schema()
    structural = compare_schemas(
        schema,
        candidate_result.model_json_schema(),
        same_pydantic_model=True,
    )
    semantic = compare_semantics(contract, baseline, candidate)
    report = CompatibilityReport(
        graph="research_demo",
        baseline_run_id="baseline-report",
        candidate_run_id="candidate-report",
        structural=structural,
        semantic=semantic,
        limitations=("Explicit contracts only.",),
        reproduction_command="graphabi demo --allow-breaking",
    )
    json_path, html_path = write_report(report, contract, tmp_path)
    html = html_path.read_text(encoding="utf-8")
    assert 'schema_version": "0.1"' in json_path.read_text(encoding="utf-8")
    assert "Structural compatibility" in html
    assert "researcher_to_verifier" in html
    assert "candidate-report" in html
    assert "<svg" in html
    assert "cdn" not in html.lower()
    assert 'id="replay"' in html
    assert "prefers-reduced-motion:reduce" in html
    assert 'class="semantic-pulse"' in html
    assert "Trace-backed witness" in html
    assert "Contract coverage" in html
    assert "Uncontracted observed edges" in html
    assert "#0B0F14" in html
    assert "#A78BFA" in html
    assert "#EF4444" in html
    assert "<script src=" not in html
    assert html.startswith("<!DOCTYPE html>")
    assert 'class="skip-link"' in html
    assert 'aria-label="Semantic edge statuses; scroll horizontally if needed"' in html
    assert not any(line.endswith(" ") for line in html.splitlines())
    client = TestClient(create_report_app(html_path))
    assert client.get("/").status_code == 200
    assert client.get("/report.json").json()["schema_version"] == "0.1"
