from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from examples.research_graph import baseline as baseline_fixture
from examples.research_graph import graph as research_graph

from graphabi.comparison import compare_semantics
from graphabi.contracts import load_contract
from graphabi.contracts.evaluators import EvaluationResult, default_registry
from graphabi.contracts.models import Contract, Invariant
from graphabi.models import EdgeObservation, GraphRun, TraceBundle

NOW = datetime(2026, 8, 1, tzinfo=UTC)
ROOT = Path(__file__).resolve().parents[2]


def bundle(
    run_id: str,
    *,
    graph: str,
    edge: str,
    producer: str,
    consumer: str,
    output: dict[str, object],
    metadata: dict[str, object],
) -> TraceBundle:
    run = GraphRun(
        run_id=run_id,
        graph_id=graph,
        graph_version="1",
        started_at=NOW,
        ended_at=NOW,
        status="success",
        input={},
        output={},
        executions=(),
    )
    observation = EdgeObservation(
        run_id=run_id,
        graph_id=graph,
        graph_version="1",
        edge_id=edge,
        producer=producer,
        consumer=consumer,
        input={},
        output=output,
        metadata=metadata,
        observed_at=NOW,
    )
    return TraceBundle(runs=(run,), edge_observations=(observation,))


def test_same_model_and_schema_and_removing_regression_naturally_passes(monkeypatch) -> None:
    contract = load_contract(ROOT / "examples/research_graph/contracts.yml")
    baseline, baseline_result = research_graph.run_graph("baseline", "hostile-baseline")
    broken, broken_result = research_graph.run_graph("candidate", "hostile-broken")

    real_source = ROOT / "examples/research_graph/fixtures/helios-study.txt"
    monkeypatch.setattr(
        research_graph.candidate,
        "make_researcher",
        lambda _missing: baseline_fixture.make_researcher(real_source),
    )
    repaired, repaired_result = research_graph.run_graph("candidate", "hostile-repaired")

    assert baseline_result.__class__ is broken_result.__class__ is repaired_result.__class__
    assert baseline_result.model_json_schema() == broken_result.model_json_schema()
    assert baseline_result.model_json_schema() == repaired_result.model_json_schema()
    assert compare_semantics(contract, baseline, broken).status == "FAIL"
    repaired_report = compare_semantics(contract, baseline, repaired)
    assert repaired_report.status == "PASS"
    assert all(
        finding.status == "PASS"
        for finding in repaired_report.findings
        if finding.edge == "researcher_to_verifier" and "provenance" in finding.reason
    )

    unit_regression = repaired.model_copy(
        update={
            "edge_observations": tuple(
                item.model_copy(update={"metadata": {**item.metadata, "evidence_unit": "percent"}})
                if item.edge_id == "researcher_to_verifier"
                else item
                for item in repaired.edge_observations
            )
        }
    )
    unit_report = compare_semantics(contract, baseline, unit_regression)
    assert unit_report.status == "FAIL"
    assert {finding.contract_id.split(":")[-1] for finding in unit_report.breaking_findings} == {
        "confidence_fraction_unit"
    }


def test_independent_unit_regression_uses_no_research_demo_identifier() -> None:
    contract = Contract.model_validate(
        {
            "version": "0.1",
            "graph": "commerce_flow",
            "nodes": [{"id": "pricing"}, {"id": "risk", "terminal": True}],
            "edges": [
                {
                    "id": "price_quote",
                    "producer": "pricing",
                    "consumer": "risk",
                    "invariants": [
                        {
                            "id": "currency_must_remain_usd",
                            "evaluator": "unit_consistency",
                            "description": "The risk consumer interprets amount as USD.",
                            "value_path": "output.amount",
                            "unit_path": "metadata.currency",
                            "expected_unit": "USD",
                        }
                    ],
                }
            ],
        }
    )
    baseline = bundle(
        "money-before",
        graph="commerce_flow",
        edge="price_quote",
        producer="pricing",
        consumer="risk",
        output={"amount": 100.0},
        metadata={"currency": "USD"},
    )
    candidate = bundle(
        "money-after",
        graph="commerce_flow",
        edge="price_quote",
        producer="pricing",
        consumer="risk",
        output={"amount": 100.0},
        metadata={"currency": "INR"},
    )

    report = compare_semantics(contract, baseline, candidate)
    assert report.status == "FAIL"
    assert report.first_breaking_edge == "price_quote"
    assert report.breaking_findings[0].contract_id.endswith("currency_must_remain_usd")
    assert report.breaking_findings[0].run_id == "money-after"


def test_independent_authority_escalation_is_detected() -> None:
    contract = Contract.model_validate(
        {
            "version": "0.1",
            "graph": "approval_flow",
            "nodes": [{"id": "advisor"}, {"id": "executor", "terminal": True}],
            "edges": [
                {
                    "id": "advice",
                    "producer": "advisor",
                    "consumer": "executor",
                    "invariants": [
                        {
                            "id": "recommendation_ceiling",
                            "evaluator": "authority",
                            "description": "Advice cannot authorize execution.",
                            "source_path": "output.authority",
                            "maximum_allowed": "recommendation",
                        }
                    ],
                }
            ],
        }
    )
    baseline = bundle(
        "authority-before",
        graph="approval_flow",
        edge="advice",
        producer="advisor",
        consumer="executor",
        output={"authority": "recommendation"},
        metadata={},
    )
    candidate = bundle(
        "authority-after",
        graph="approval_flow",
        edge="advice",
        producer="advisor",
        consumer="executor",
        output={"authority": "authorized"},
        metadata={},
    )

    finding = compare_semantics(contract, baseline, candidate).breaking_findings[0]
    assert finding.contract_id == "approval_flow:advice:recommendation_ceiling"
    assert "authorized" in finding.reason


def test_external_evaluator_registry_operates_outside_demo() -> None:
    class EvenEvaluator:
        name = "even"

        def evaluate(
            self,
            invariant: Invariant,
            candidate: EdgeObservation,
            baseline: EdgeObservation | None = None,
        ) -> EvaluationResult:
            del baseline
            value = candidate.output.get("number")
            if not isinstance(value, int):
                return EvaluationResult(
                    status="INSUFFICIENT_EVIDENCE",
                    reason="number missing",
                    expectation=invariant.description,
                )
            return EvaluationResult(
                status="PASS" if value % 2 == 0 else "BREAKING",
                reason="number must be even",
                expectation=invariant.description,
                observed=value,
                relevant_paths=("output.number",),
            )

    contract = Contract.model_validate(
        {
            "version": "0.1",
            "graph": "math",
            "nodes": [{"id": "source"}, {"id": "sink"}],
            "edges": [
                {
                    "id": "number_edge",
                    "producer": "source",
                    "consumer": "sink",
                    "invariants": [
                        {"id": "even_number", "evaluator": "even", "description": "even only"}
                    ],
                }
            ],
        }
    )
    baseline = bundle(
        "even-base",
        graph="math",
        edge="number_edge",
        producer="source",
        consumer="sink",
        output={"number": 2},
        metadata={},
    )
    candidate = bundle(
        "odd-candidate",
        graph="math",
        edge="number_edge",
        producer="source",
        consumer="sink",
        output={"number": 3},
        metadata={},
    )
    registry = default_registry()
    registry.register(EvenEvaluator())

    assert compare_semantics(contract, baseline, candidate, registry=registry).status == "FAIL"


def test_mismatched_edge_identity_cannot_pass() -> None:
    contract = Contract.model_validate(
        {
            "version": "0.1",
            "graph": "expected_graph",
            "nodes": [{"id": "producer"}, {"id": "consumer"}],
            "edges": [
                {
                    "id": "edge",
                    "producer": "producer",
                    "consumer": "consumer",
                    "invariants": [
                        {
                            "id": "complete",
                            "evaluator": "completeness",
                            "description": "value required",
                            "destination_path": "output.value",
                        }
                    ],
                }
            ],
        }
    )
    legitimate = bundle(
        "base",
        graph="expected_graph",
        edge="edge",
        producer="producer",
        consumer="consumer",
        output={"value": "present"},
        metadata={},
    )
    impostor = bundle(
        "candidate",
        graph="different_graph",
        edge="edge",
        producer="attacker",
        consumer="somewhere_else",
        output={"value": "present"},
        metadata={},
    )

    report = compare_semantics(contract, legitimate, impostor)
    assert report.status == "INSUFFICIENT_EVIDENCE"
    assert report.findings[0].status == "INSUFFICIENT_EVIDENCE"


def test_matching_unit_label_with_non_numeric_magnitude_is_not_pass() -> None:
    contract = Contract.model_validate(
        {
            "version": "0.1",
            "graph": "units",
            "nodes": [{"id": "p"}, {"id": "c"}],
            "edges": [
                {
                    "id": "e",
                    "producer": "p",
                    "consumer": "c",
                    "invariants": [
                        {
                            "id": "usd",
                            "evaluator": "unit_consistency",
                            "description": "numeric USD",
                            "value_path": "output.amount",
                            "unit_path": "metadata.unit",
                            "expected_unit": "USD",
                        }
                    ],
                }
            ],
        }
    )
    trace = bundle(
        "wrong-type",
        graph="units",
        edge="e",
        producer="p",
        consumer="c",
        output={"amount": "one hundred"},
        metadata={"unit": "USD"},
    )
    assert compare_semantics(contract, trace, trace).status == "UNKNOWN"
