from examples.research_graph.graph import run_graph

from graphabi.adapters import FrameworkAdapter
from graphabi.adapters.langgraph import LangGraphRecorder


def test_real_graph_records_schema_pass_semantic_fail() -> None:
    baseline_bundle, baseline_result = run_graph("baseline", "baseline-test")
    candidate_bundle, candidate_result = run_graph("candidate", "candidate-test")

    assert baseline_result.__class__ is candidate_result.__class__
    assert baseline_result.model_json_schema() == candidate_result.model_json_schema()
    assert len(baseline_bundle.runs[0].executions) == 4
    assert baseline_bundle.schema_version == "0.2"
    assert baseline_bundle.runs[0].executions[0].occurrence_id == "researcher:0000"
    observation = candidate_bundle.edge_observations[0]
    assert observation.edge_id == "researcher_to_verifier"
    assert observation.output["verified"] is True
    assert observation.metadata["opened_sources_count"] == 0
    assert observation.source_access[0].opened is False
    assert observation.producer_occurrence_id == "researcher:0000"
    assert observation.consumer_occurrence_id == "verifier:0000"


def test_langgraph_recorder_implements_public_adapter_protocol() -> None:
    recorder = LangGraphRecorder(
        run_id="protocol",
        graph_id="protocol",
        graph_version="1",
        variant="other",
        edges=(),
    )
    assert isinstance(recorder, FrameworkAdapter)
