from examples.research_graph.graph import run_graph


def test_real_graph_records_schema_pass_semantic_fail() -> None:
    baseline_bundle, baseline_result = run_graph("baseline", "baseline-test")
    candidate_bundle, candidate_result = run_graph("candidate", "candidate-test")

    assert baseline_result.__class__ is candidate_result.__class__
    assert baseline_result.model_json_schema() == candidate_result.model_json_schema()
    assert len(baseline_bundle.runs[0].executions) == 4
    observation = candidate_bundle.edge_observations[0]
    assert observation.edge_id == "researcher_to_verifier"
    assert observation.output["verified"] is True
    assert observation.metadata["opened_sources_count"] == 0
    assert observation.source_access[0].opened is False
