from copy import deepcopy
from datetime import UTC, datetime

from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from graphabi.comparison import compare_schemas, compare_semantics, findings_fingerprint
from graphabi.contracts.evaluators.builtin import AuthorityEvaluator, UnitConsistencyEvaluator
from graphabi.contracts.models import Condition, Contract, Invariant
from graphabi.impact import analyze_impact
from graphabi.models.traces import EdgeObservation, GraphRun, RedactedValue, TraceBundle

NOW = datetime(2026, 7, 31, tzinfo=UTC)


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
