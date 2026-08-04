from copy import deepcopy
from pathlib import Path

import pytest
from examples.research_graph.graph import run_graph
from pydantic import ValidationError

from graphabi.comparison import ContractCoverage, compare_semantics, findings_fingerprint
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
    assert report.coverage.contracted_edges == (
        "researcher_to_verifier",
        "verifier_to_decision_maker",
        "decision_maker_to_publisher",
    )
    assert report.coverage.observed_branches == report.coverage.contracted_edges
    assert report.coverage.unobserved_branches == ()
    assert report.coverage.uncontracted_edges == ()
    assert report.coverage.insufficient_evidence_contracts == ()


def test_baseline_passes_and_missing_or_plugin_results_stay_uncertain() -> None:
    contract = load_contract(ROOT / "examples/research_graph/contracts.yml")
    baseline, _ = run_graph("baseline", "base")
    assert compare_semantics(contract, baseline, baseline).status == "PASS"

    empty = TraceBundle(runs=baseline.runs, edge_observations=())
    missing = compare_semantics(contract, baseline, empty)
    assert {item.status for item in missing.findings} == {"INSUFFICIENT_EVIDENCE"}
    assert missing.status == "INSUFFICIENT_EVIDENCE"
    assert missing.coverage.observed_branches == ()
    assert missing.coverage.unobserved_branches == missing.coverage.contracted_edges
    assert len(missing.coverage.insufficient_evidence_contracts) == len(missing.findings)

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


def test_coverage_reports_only_observed_uncontracted_edges() -> None:
    contract = load_contract(ROOT / "examples/research_graph/contracts.yml")
    baseline, _ = run_graph("baseline", "coverage-base")
    extra = baseline.edge_observations[0].model_copy(
        update={"edge_id": "observed_without_contract"}
    )
    candidate = baseline.model_copy(
        update={"edge_observations": (*baseline.edge_observations, extra)}
    )

    coverage = compare_semantics(contract, baseline, candidate).coverage

    assert coverage.uncontracted_edges == ("observed_without_contract",)
    assert coverage.observed_branches == coverage.contracted_edges


@pytest.mark.parametrize(
    "coverage",
    (
        {
            "contracted_edges": ("a", "b"),
            "observed_branches": ("a",),
            "unobserved_branches": (),
        },
        {
            "contracted_edges": ("a",),
            "uncontracted_edges": ("a",),
            "observed_branches": ("a",),
        },
        {
            "contracted_edges": ("a", "a"),
            "observed_branches": ("a",),
        },
    ),
)
def test_coverage_rejects_incomplete_overlapping_or_duplicate_sets(
    coverage: dict[str, tuple[str, ...]],
) -> None:
    with pytest.raises(ValidationError):
        ContractCoverage.model_validate(coverage)


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
