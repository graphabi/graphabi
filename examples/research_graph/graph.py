"""Build and invoke the local deterministic LangGraph demonstration."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, cast

from langgraph.graph import END, START, StateGraph

from examples.research_graph import baseline, candidate
from examples.research_graph.models import (
    DecisionResult,
    PublicationResult,
    ResearchResult,
    ResearchState,
    VerifierResult,
)
from graphabi.adapters.langgraph import EdgeSpec, LangGraphRecorder
from graphabi.models.traces import TraceBundle

Variant = Literal["baseline", "candidate"]
ROOT = Path(__file__).resolve().parents[2]


def verifier(state: ResearchState) -> dict[str, object]:
    """Consume a research result under the baseline semantic assumptions."""
    research = ResearchResult.model_validate(state["research_result"])
    required = set(state["required_entities"])
    preserved = required.issubset(research.entities)
    accepted = research.verified and preserved
    result = VerifierResult(
        accepted=accepted,
        checked_entities=research.entities,
        reason="verified evidence and entities accepted"
        if accepted
        else "required evidence missing",
    )
    return {"verifier_result": result.model_dump(mode="json")}


def decision_maker(state: ResearchState) -> dict[str, object]:
    checked = VerifierResult.model_validate(state["verifier_result"])
    result = DecisionResult(
        action="publish" if checked.accepted else "hold",
        rationale="verifier accepted" if checked.accepted else "verifier rejected",
    )
    return {"decision_result": result.model_dump(mode="json")}


def publisher(state: ResearchState) -> dict[str, object]:
    decision = DecisionResult.model_validate(state["decision_result"])
    result = PublicationResult(
        status="published" if decision.action == "publish" else "withheld",
        message="Deterministic local demo publication result",
        authority_level="published" if decision.action == "publish" else "draft",
    )
    return {"publication_result": result.model_dump(mode="json")}


def run_graph(variant: Variant, run_id: str) -> tuple[TraceBundle, ResearchResult]:
    """Execute one graph version and return its real trace plus producer result."""
    edges = (
        EdgeSpec("researcher_to_verifier", "researcher", "verifier", "research_result"),
        EdgeSpec("verifier_to_decision_maker", "verifier", "decision_maker", "verifier_result"),
        EdgeSpec("decision_maker_to_publisher", "decision_maker", "publisher", "decision_result"),
    )
    recorder = LangGraphRecorder(
        run_id=run_id,
        graph_id="research_demo",
        graph_version="baseline-v1" if variant == "baseline" else "candidate-v2",
        variant=variant,
        edges=edges,
    )
    source_path = ROOT / "examples/research_graph/fixtures/helios-study.txt"
    if variant == "candidate":
        source_path = ROOT / "examples/research_graph/fixtures/missing-study.txt"
    researcher = (
        baseline.make_researcher(source_path)
        if variant == "baseline"
        else candidate.make_researcher(source_path)
    )
    builder = StateGraph(ResearchState)
    builder.add_node("researcher", recorder.instrument("researcher", researcher))
    builder.add_node(
        "verifier",
        recorder.instrument(
            "verifier", verifier, parent_node="researcher", incoming_edge="researcher_to_verifier"
        ),
    )
    builder.add_node(
        "decision_maker",
        recorder.instrument(
            "decision_maker",
            decision_maker,
            parent_node="verifier",
            incoming_edge="verifier_to_decision_maker",
        ),
    )
    builder.add_node(
        "publisher",
        recorder.instrument(
            "publisher",
            publisher,
            parent_node="decision_maker",
            incoming_edge="decision_maker_to_publisher",
        ),
    )
    builder.add_edge(START, "researcher")
    builder.add_edge("researcher", "verifier")
    builder.add_edge("verifier", "decision_maker")
    builder.add_edge("decision_maker", "publisher")
    builder.add_edge("publisher", END)
    compiled = builder.compile(name=f"research-demo-{variant}")
    graph_input: ResearchState = {
        "topic": "Helios battery capacity",
        "required_entities": ["Helios battery", "1,000 charge cycles"],
    }
    bundle = recorder.invoke(compiled, cast(dict[str, object], graph_input))
    graph_output = cast(ResearchState, bundle.runs[0].output)
    result = ResearchResult.model_validate(graph_output["research_result"])
    return bundle, result


if __name__ == "__main__":
    baseline_bundle, baseline_result = run_graph("baseline", "baseline-001")
    candidate_bundle, candidate_result = run_graph("candidate", "candidate-003")
    assert baseline_result.model_json_schema() == candidate_result.model_json_schema()
    observation = candidate_bundle.edge_observations[0]
    semantic_pass = not (
        observation.output["verified"] is True and observation.metadata["opened_sources_count"] == 0
    )
    print(f"baseline executions: {len(baseline_bundle.runs[0].executions)}")
    print(f"candidate executions: {len(candidate_bundle.runs[0].executions)}")
    print("structural compatibility: PASS")
    print(f"researcher -> verifier semantic compatibility: {'PASS' if semantic_pass else 'FAIL'}")
