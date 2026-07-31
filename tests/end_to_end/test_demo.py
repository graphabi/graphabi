from pathlib import Path

from examples.research_graph.models import ResearchResult
from jsonschema import validate

from graphabi.demo import run_demo
from graphabi.storage import SQLiteTraceStore


def test_complete_demo_uses_real_traces_and_generates_reports() -> None:
    result = run_demo()
    report = result.report
    store = SQLiteTraceStore(result.database)
    baseline = store.load_run("baseline-001")
    candidate = store.load_run("candidate-003")
    baseline_output = baseline.edge_observations[0].output
    candidate_output = candidate.edge_observations[0].output
    schema = ResearchResult.model_json_schema()

    assert ResearchResult.model_validate(baseline_output)
    assert ResearchResult.model_validate(candidate_output)
    validate(baseline_output, schema)
    validate(candidate_output, schema)
    assert report.structural.status == "PASS"
    assert report.structural.exact_schema_match
    assert report.semantic.status == "FAIL"
    assert report.semantic.first_breaking_edge == "researcher_to_verifier"
    assert "publisher" in report.semantic.breaking_findings[0].affected_downstream_nodes
    assert report.semantic.breaking_findings[0].run_id == "candidate-003"
    assert result.report_json.is_file()
    assert result.report_html.is_file()
    assert Path(".graphabi/demo/baseline.json").is_file()
    assert Path(".graphabi/demo/traces.jsonl").is_file()
