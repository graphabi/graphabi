from copy import deepcopy
from pathlib import Path

from examples.research_graph.graph import run_graph

from graphabi.comparison import compare_semantics, findings_fingerprint
from graphabi.contracts import load_contract
from graphabi.contracts.evaluators import EvaluatorRegistry, default_registry
from graphabi.contracts.evaluators.builtin import ImplicationEvaluator
from graphabi.models.traces import TraceBundle

ROOT = Path(__file__).resolve().parents[2]


def test_semantic_engine_finds_stable_first_break_and_witness() -> None:
    contract = load_contract(ROOT / "examples/research_graph/contracts.yml")
    baseline, _ = run_graph("baseline", "baseline-semantic")
    candidate, _ = run_graph("candidate", "candidate-semantic")
    original = deepcopy(candidate.model_dump())
    report = compare_semantics(contract, baseline, candidate)
    repeated = compare_semantics(contract, baseline, candidate)

    assert report.status == "FAIL"
    assert report.first_breaking_edge == "researcher_to_verifier"
    assert report.breaking_findings[0].run_id == "candidate-semantic"
    assert report.breaking_findings[0].affected_downstream_nodes == (
        "verifier",
        "decision_maker",
        "publisher",
    )
    assert report.breaking_findings[0].affected_terminal_paths == (
        ("verifier", "decision_maker", "publisher"),
    )
    assert report.breaking_findings[0].affected_side_effecting_paths == (
        ("verifier", "decision_maker", "publisher"),
    )
    assert report.breaking_findings[0].shortest_affected_path == (
        "verifier",
        "decision_maker",
        "publisher",
    )
    assert report.breaking_findings[0].direct_consumer == "verifier"
    assert report.breaking_findings[0].witness.relevant_output["verified"] is True
    assert report.findings[0].finding_id == repeated.findings[0].finding_id
    assert findings_fingerprint(report) == findings_fingerprint(repeated)
    assert candidate.model_dump() == original


def test_baseline_passes_and_missing_or_plugin_results_stay_uncertain() -> None:
    contract = load_contract(ROOT / "examples/research_graph/contracts.yml")
    baseline, _ = run_graph("baseline", "base")
    assert compare_semantics(contract, baseline, baseline).status == "PASS"

    empty = TraceBundle(runs=baseline.runs, edge_observations=())
    missing = compare_semantics(contract, baseline, empty)
    assert {item.status for item in missing.findings} == {"INSUFFICIENT_EVIDENCE"}
    assert missing.status == "INSUFFICIENT_EVIDENCE"

    registry = EvaluatorRegistry()
    unknown = compare_semantics(contract, baseline, baseline, registry=registry)
    assert {item.status for item in unknown.findings} == {"UNKNOWN"}
    assert unknown.status == "UNKNOWN"


def test_registry_prevents_accidental_replacement() -> None:
    registry = default_registry()
    assert "implication" in registry.names
    try:
        registry.register(ImplicationEvaluator())
    except ValueError as exc:
        assert "already registered" in str(exc)
    else:
        raise AssertionError("duplicate registration should fail")
    registry.register(ImplicationEvaluator(), replace=True)


def test_first_breaking_edge_uses_graph_order_not_yaml_order() -> None:
    contract = load_contract(ROOT / "examples/research_graph/contracts.yml")
    reversed_contract = contract.model_copy(update={"edges": tuple(reversed(contract.edges))})
    baseline, _ = run_graph("baseline", "ordered-base")
    candidate, _ = run_graph("candidate", "ordered-candidate")
    observations = tuple(
        item.model_copy(update={"output": {**item.output, "authority_level": "authorized"}})
        if item.edge_id == "verifier_to_decision_maker"
        else item
        for item in candidate.edge_observations
    )
    candidate = candidate.model_copy(update={"edge_observations": observations})
    report = compare_semantics(reversed_contract, baseline, candidate)
    assert report.first_breaking_edge == "researcher_to_verifier"
