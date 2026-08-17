from copy import deepcopy
from datetime import UTC, datetime

from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from graphabi.comparison import (
    ContractCoverage,
    compare_schemas,
    compare_semantics,
    findings_fingerprint,
)
from graphabi.contracts.evaluators.builtin import AuthorityEvaluator, UnitConsistencyEvaluator
from graphabi.contracts.models import Condition, Contract, Invariant
from graphabi.impact import analyze_impact
from graphabi.models.traces import (
    EdgeObservation,
    GraphRun,
    NodeExecution,
    RedactedValue,
    TraceBundle,
)

NOW = datetime(2026, 7, 31, tzinfo=UTC)


@st.composite
def coverage_partitions(
    draw: st.DrawFn,
) -> tuple[tuple[str, ...], set[str], set[str]]:
    edge_count = draw(st.integers(min_value=1, max_value=20))
    graph_edges = tuple(f"e{index}" for index in range(edge_count))
    contracted = draw(st.sets(st.sampled_from(graph_edges)))
    observed = draw(st.sets(st.sampled_from(graph_edges)))
    return graph_edges, contracted, observed


def bundle(run_id: str, opened: int) -> TraceBundle:
    observation = EdgeObservation(
        run_id=run_id,
        graph_id="g",
        graph_version="1",
        edge_id="a_to_b",
        producer="a",
        consumer="b",
        input={},
        output={"verified": True},
        metadata={"opened": opened},
        observed_at=NOW,
    )
    run = GraphRun(
        run_id=run_id,
        graph_id="g",
        graph_version="1",
        started_at=NOW,
        ended_at=NOW,
        status="success",
        input={},
        output={},
        executions=(),
    )
    return TraceBundle(runs=(run,), edge_observations=(observation,))


def implication_contract() -> Contract:
    return Contract.model_validate(
        {
            "version": "0.1",
            "graph": "g",
            "nodes": [{"id": "a"}, {"id": "b", "terminal": True}],
            "edges": [
                {
                    "id": "a_to_b",
                    "producer": "a",
                    "consumer": "b",
                    "invariants": [
                        {
                            "id": "verified_opened",
                            "evaluator": "implication",
                            "description": "verified requires opened",
                            "when": {"path": "output.verified", "equals": True},
                            "require": {"path": "metadata.opened", "greater_than": 0},
                        }
                    ],
                }
            ],
        }
    )


def fanout_bundle(run_id: str, branch_order: tuple[str, ...]) -> TraceBundle:
    root = NodeExecution(
        schema_version="0.2",
        run_id=run_id,
        graph_id="fanout",
        graph_version="1",
        node_id="root",
        occurrence_id=f"{run_id}:root",
        causal_sequence=0,
        branch_id="main",
        attempt=1,
        input={},
        output={"value": "root"},
        started_at=NOW,
        ended_at=NOW,
        duration_ms=0,
        status="success",
        framework="test",
        framework_version="1",
    )
    workers = tuple(
        NodeExecution(
            schema_version="0.2",
            run_id=run_id,
            graph_id="fanout",
            graph_version="1",
            node_id="worker",
            occurrence_id=f"{run_id}:{branch}",
            parent_occurrence_id=root.occurrence_id,
            causal_parent_occurrence_ids=(f"{run_id}:root",),
            incoming_edge_id="fan_out",
            causal_sequence=index,
            branch_id=branch,
            attempt=1,
            input={},
            output={"value": branch},
            started_at=NOW,
            ended_at=NOW,
            duration_ms=0,
            status="success",
            framework="test",
            framework_version="1",
        )
        for index, branch in enumerate(branch_order, start=1)
    )
    run = GraphRun(
        schema_version="0.2",
        run_id=run_id,
        graph_id="fanout",
        graph_version="1",
        started_at=NOW,
        ended_at=NOW,
        status="success",
        input={},
        output={},
        executions=(root, *workers),
    )
    observations = tuple(
        EdgeObservation(
            schema_version="0.2",
            run_id=run_id,
            graph_id="fanout",
            graph_version="1",
            edge_id="fan_out",
            producer="root",
            consumer="worker",
            occurrence_id=f"{run_id}:edge:{index}",
            producer_occurrence_id=root.occurrence_id,
            consumer_occurrence_id=worker.occurrence_id,
            causal_sequence=index,
            branch_id=worker.branch_id,
            attempt=1,
            input={},
            output={"value": "present"},
            observed_at=NOW,
        )
        for index, worker in enumerate(workers)
    )
    return TraceBundle(
        schema_version="0.2",
        exported_at=NOW,
        runs=(run,),
        edge_observations=observations,
    )


def fanout_contract() -> Contract:
    return Contract.model_validate(
        {
            "version": "0.2",
            "graph": "fanout",
            "nodes": [{"id": "root"}, {"id": "worker"}],
            "graph_edges": [{"id": "fan_out", "producer": "root", "consumer": "worker"}],
            "edges": [
                {
                    "id": "fan_out",
                    "producer": "root",
                    "consumer": "worker",
                    "invariants": [
                        {
                            "id": "value_present",
                            "evaluator": "completeness",
                            "description": "value is present",
                            "destination_path": "output.value",
                        }
                    ],
                }
            ],
        }
    )


@given(st.integers(min_value=1, max_value=100))
def test_identical_payload_shapes_can_break_semantics(opened: int) -> None:
    baseline = bundle("baseline", opened)
    candidate = bundle("candidate", 0)
    output_schema = {
        "type": "object",
        "properties": {"verified": {"type": "boolean"}},
        "required": ["verified"],
    }
    assert compare_schemas(output_schema, output_schema).status == "PASS"
    assert compare_semantics(implication_contract(), baseline, candidate).status == "FAIL"


@given(st.integers(min_value=0, max_value=20))
def test_evaluation_is_stable_and_does_not_mutate_traces(opened: int) -> None:
    baseline = bundle("baseline", max(opened, 1))
    candidate = bundle("candidate", opened)
    original = deepcopy(candidate.model_dump())
    first = compare_semantics(implication_contract(), baseline, candidate)
    second = compare_semantics(implication_contract(), baseline, candidate)
    assert findings_fingerprint(first) == findings_fingerprint(second)
    assert candidate.model_dump() == original


@given(st.integers(min_value=2, max_value=12))
def test_reachability_is_deterministic(node_count: int) -> None:
    nodes = [{"id": f"n{i}", "terminal": i == node_count - 1} for i in range(node_count)]
    edges = [
        {
            "id": f"e{i}",
            "producer": f"n{i}",
            "consumer": f"n{i + 1}",
            "invariants": [{"id": "i", "evaluator": "custom", "description": "d"}],
        }
        for i in range(node_count - 1)
    ]
    contract = Contract.model_validate(
        {"version": "0.1", "graph": "chain", "nodes": nodes, "edges": edges}
    )
    first = analyze_impact(contract, "e0")
    second = analyze_impact(contract, "e0")
    assert first == second
    assert len(first.downstream_nodes) == node_count - 1


@given(st.integers(), st.integers())
def test_multiple_condition_operators_never_validate(left: int, right: int) -> None:
    try:
        Condition(path="x", equals=left, not_equals=right)
    except ValidationError:
        pass
    else:
        raise AssertionError("ambiguous conditions must fail")


@given(
    st.sampled_from(["suggestion", "recommendation"]),
    st.sampled_from(["decision", "authorized", "published"]),
)
def test_authority_escalation_never_passes(maximum: str, observed: str) -> None:
    invariant = Invariant(
        id="authority",
        evaluator="authority",
        description="no escalation",
        source_path="output.level",
        maximum_allowed=maximum,
        authority_order=("suggestion", "recommendation", "decision", "authorized", "published"),
    )
    result = AuthorityEvaluator().evaluate(
        invariant,
        bundle("c", 0).edge_observations[0].model_copy(update={"output": {"level": observed}}),
    )
    assert result.status == "BREAKING"


@given(st.floats(allow_nan=False, allow_infinity=False, min_value=-1e9, max_value=1e9))
def test_unit_mismatch_never_silently_alters_magnitude(value: float) -> None:
    invariant = Invariant(
        id="unit",
        evaluator="unit_consistency",
        description="milliseconds",
        value_path="output.value",
        unit_path="metadata.unit",
        expected_unit="milliseconds",
    )
    candidate = (
        bundle("c", 0)
        .edge_observations[0]
        .model_copy(update={"output": {"value": value}, "metadata": {"unit": "seconds"}})
    )
    result = UnitConsistencyEvaluator().evaluate(invariant, candidate)
    assert result.status == "BREAKING"
    assert result.observed["value"] == value


@given(st.uuids().map(str))
def test_redaction_serialization_does_not_leak_original(original: str) -> None:
    marker = RedactedValue(reason="sensitive")
    assert original not in marker.model_dump_json()


@given(coverage_partitions())
def test_contract_coverage_partitions_and_percentage_are_exact(
    case: tuple[tuple[str, ...], set[str], set[str]],
) -> None:
    graph_edges, contracted, observed = case

    def ordered(values: set[str]) -> tuple[str, ...]:
        return tuple(edge for edge in graph_edges if edge in values)

    coverage = ContractCoverage(
        graph_nodes=tuple(f"n{index}" for index in range(len(graph_edges) + 1)),
        graph_edges=graph_edges,
        contracted_edges=ordered(contracted),
        uncontracted_edges=ordered(set(graph_edges) - contracted),
        observed_edges=ordered(observed),
        unobserved_edges=ordered(set(graph_edges) - observed),
        contracted_and_observed=ordered(contracted & observed),
        contracted_but_unobserved=ordered(contracted - observed),
        observed_but_uncontracted=ordered(observed - contracted),
        insufficient_evidence_branches=ordered(contracted - observed),
        observed_branches=ordered(contracted & observed),
        unobserved_branches=ordered(contracted - observed),
        graph_inventory_complete=True,
    )

    assert coverage.summary.contracted_edges + coverage.summary.uncontracted_edges == len(
        graph_edges
    )
    assert coverage.summary.observed_edges + coverage.summary.unobserved_edges == len(graph_edges)
    assert coverage.summary.observed_contract_coverage_percent == round(
        100 * len(contracted & observed) / len(graph_edges), 1
    )
    assert coverage.summary.coverage_is_correctness is False


@given(st.permutations(("left", "middle", "right")))
def test_causal_pairing_is_invariant_to_fanout_schedule(
    branch_order: list[str],
) -> None:
    baseline = fanout_bundle("baseline", ("left", "middle", "right"))
    candidate = fanout_bundle("candidate", tuple(branch_order))
    reference = compare_semantics(
        fanout_contract(),
        baseline,
        fanout_bundle("candidate-reference", ("left", "middle", "right")),
    )
    reordered = compare_semantics(fanout_contract(), baseline, candidate)

    assert reordered.status == "PASS"
    assert len(reordered.findings) == 3
    assert findings_fingerprint(reordered) == findings_fingerprint(reference)
