from datetime import UTC, datetime, timedelta

import pytest

from graphabi.contracts.evaluators.builtin import (
    AuthorityEvaluator,
    CompletenessEvaluator,
    FreshnessEvaluator,
    ImplicationEvaluator,
    ProvenanceEvaluator,
    SetPreservationEvaluator,
    UnitConsistencyEvaluator,
)
from graphabi.contracts.evaluators.paths import (
    MISSING,
    evaluate_condition,
    observation_context,
    resolve_path,
)
from graphabi.contracts.models import Condition, Invariant
from graphabi.models.traces import EdgeObservation, SourceAccess

NOW = datetime(2026, 7, 31, tzinfo=UTC)


def observation(
    *,
    output: dict[str, object] | None = None,
    metadata: dict[str, object] | None = None,
    sources: tuple[SourceAccess, ...] = (),
) -> EdgeObservation:
    return EdgeObservation(
        run_id="candidate",
        graph_id="g",
        graph_version="2",
        edge_id="a_to_b",
        producer="a",
        consumer="b",
        input={"required": ["x", "y"]},
        output=output or {},
        metadata=metadata or {},
        source_access=sources,
        observed_at=NOW,
    )


@pytest.mark.parametrize(
    ("raw", "value", "expected"),
    [
        ({"path": "output.x", "equals": 3}, 3, True),
        ({"path": "output.x", "not_equals": 4}, 3, True),
        ({"path": "output.x", "greater_than": 2}, 3, True),
        ({"path": "output.x", "greater_than_or_equal": 3}, 3, True),
        ({"path": "output.x", "less_than": 4}, 3, True),
        ({"path": "output.x", "non_empty": True}, [1], True),
        ({"path": "output.x", "contains": "a"}, ["a"], True),
        ({"path": "output.x", "exists": True}, 3, True),
    ],
)
def test_conditions_support_all_comparisons(
    raw: dict[str, object], value: object, expected: bool
) -> None:
    condition = Condition.model_validate(raw)
    assert evaluate_condition(condition, {"output": {"x": value}})[0] is expected


def test_nested_paths_and_incomparable_conditions() -> None:
    assert resolve_path({"a": [{"b": 2}]}, "a.0.b") == 2
    assert resolve_path({"a": []}, "a.1") is MISSING
    condition = Condition(path="output.value", greater_than=2)
    assert evaluate_condition(condition, {"output": {"value": "no"}})[0] is None
    exists = Condition(path="output.missing", exists=False)
    assert evaluate_condition(exists, {"output": {}})[0] is True
    numeric = Condition(path="output.value", greater_than=0)
    assert evaluate_condition(numeric, {"output": {"value": True}})[0] is None
    boolean = Condition(path="output.value", equals=True)
    assert evaluate_condition(boolean, {"output": {"value": 1}})[0] is False


def test_implication_pass_fail_and_insufficient() -> None:
    invariant = Invariant(
        id="i",
        evaluator="implication",
        description="verified needs count",
        when=Condition(path="output.verified", equals=True),
        require=Condition(path="metadata.count", greater_than=0),
    )
    evaluator = ImplicationEvaluator()
    assert evaluator.evaluate(invariant, observation(output={"verified": False})).status == "PASS"
    assert (
        evaluator.evaluate(
            invariant, observation(output={"verified": True}, metadata={"count": 1})
        ).status
        == "PASS"
    )
    assert (
        evaluator.evaluate(
            invariant, observation(output={"verified": True}, metadata={"count": 0})
        ).status
        == "BREAKING"
    )
    assert evaluator.evaluate(invariant, observation()).status == "INSUFFICIENT_EVIDENCE"
    assert (
        evaluator.evaluate(invariant, observation(output={"verified": True})).status
        == "INSUFFICIENT_EVIDENCE"
    )


def test_provenance_uses_access_events_not_citations() -> None:
    opened = SourceAccess(
        source_id="s1",
        uri="file:///s1",
        attempted_at=NOW,
        opened=True,
        supports_claim=True,
    )
    evaluator = ProvenanceEvaluator()
    for rule in (
        "opened_source",
        "claim_support",
        "accessed_citations",
        "opened_supporting_source",
    ):
        invariant = Invariant(id=rule, evaluator="provenance", description=rule, rule=rule)
        result = evaluator.evaluate(
            invariant,
            observation(output={"verified": True, "sources": ["s1"]}, sources=(opened,)),
        )
        assert result.status == "PASS"
    broken = Invariant(id="p", evaluator="provenance", description="p", rule="opened_source")
    assert (
        evaluator.evaluate(broken, observation(output={"verified": True, "sources": ["s1"]})).status
        == "BREAKING"
    )
    assert evaluator.evaluate(broken, observation(output={"verified": False})).status == "PASS"
    assert evaluator.evaluate(broken, observation()).status == "INSUFFICIENT_EVIDENCE"
    assert evaluator.evaluate(broken, observation(output={"verified": "yes"})).status == "UNKNOWN"


def test_preservation_and_completeness_statuses() -> None:
    preserve = Invariant(
        id="p",
        evaluator="set_preservation",
        description="preserve",
        severity="warning",
        source_path="metadata.required",
        destination_path="output.entities",
    )
    evaluator = SetPreservationEvaluator()
    assert (
        evaluator.evaluate(
            preserve,
            observation(output={"entities": ["x", "y"]}, metadata={"required": ["x"]}),
        ).status
        == "PASS"
    )
    assert (
        evaluator.evaluate(
            preserve, observation(output={"entities": []}, metadata={"required": ["x"]})
        ).status
        == "WARNING"
    )
    assert evaluator.evaluate(preserve, observation()).status == "INSUFFICIENT_EVIDENCE"
    assert (
        evaluator.evaluate(
            preserve, observation(output={"entities": "x"}, metadata={"required": "x"})
        ).status
        == "UNKNOWN"
    )
    assert (
        evaluator.evaluate(
            preserve,
            observation(
                output={"entities": [{"id": "x"}]},
                metadata={"required": [{"id": "x"}]},
            ),
        ).status
        == "UNKNOWN"
    )
    complete = Invariant(
        id="c", evaluator="completeness", description="complete", destination_path="output.ids"
    )
    completeness = CompletenessEvaluator()
    assert completeness.evaluate(complete, observation(output={"ids": [1]})).status == "PASS"
    assert completeness.evaluate(complete, observation(output={"ids": 0})).status == "PASS"
    assert completeness.evaluate(complete, observation(output={"ids": False})).status == "PASS"
    assert completeness.evaluate(complete, observation(output={"ids": []})).status == "BREAKING"
    assert completeness.evaluate(complete, observation()).status == "INSUFFICIENT_EVIDENCE"


def test_unit_authority_and_freshness_are_conservative() -> None:
    unit = Invariant(
        id="u",
        evaluator="unit_consistency",
        description="unit",
        value_path="output.value",
        unit_path="metadata.unit",
        expected_unit="USD",
    )
    units = UnitConsistencyEvaluator()
    assert (
        units.evaluate(unit, observation(output={"value": 5}, metadata={"unit": "USD"})).status
        == "PASS"
    )
    assert (
        units.evaluate(unit, observation(output={"value": 5}, metadata={"unit": "INR"})).status
        == "BREAKING"
    )
    assert units.evaluate(unit, observation(output={"value": 5})).status == "INSUFFICIENT_EVIDENCE"
    assert (
        units.evaluate(
            unit,
            observation(output={"value": "five"}, metadata={"unit": "USD"}),
        ).status
        == "UNKNOWN"
    )
    convertible = unit.model_copy(update={"allow_conversion": True})
    assert (
        units.evaluate(
            convertible, observation(output={"value": 5}, metadata={"unit": "INR"})
        ).status
        == "UNKNOWN"
    )
    fraction = unit.model_copy(
        update={
            "representation_path": "metadata.representation",
            "expected_representation": "fraction",
        }
    )
    assert (
        units.evaluate(
            fraction,
            observation(
                output={"value": 50},
                metadata={"unit": "USD", "representation": "fraction"},
            ),
        ).status
        == "BREAKING"
    )
    assert (
        units.evaluate(
            fraction, observation(output={"value": 0.5}, metadata={"unit": "USD"})
        ).status
        == "INSUFFICIENT_EVIDENCE"
    )

    authority = Invariant(
        id="a",
        evaluator="authority",
        description="authority",
        source_path="output.level",
        maximum_allowed="recommendation",
        authority_order=("suggestion", "recommendation", "decision", "authorized", "published"),
    )
    authorities = AuthorityEvaluator()
    assert (
        authorities.evaluate(authority, observation(output={"level": "suggestion"})).status
        == "PASS"
    )
    assert (
        authorities.evaluate(authority, observation(output={"level": "authorized"})).status
        == "BREAKING"
    )
    assert (
        authorities.evaluate(authority, observation(output={"level": "mystery"})).status
        == "UNKNOWN"
    )
    assert authorities.evaluate(authority, observation(output={"level": []})).status == "UNKNOWN"
    assert authorities.evaluate(authority, observation()).status == "INSUFFICIENT_EVIDENCE"

    freshness = Invariant(
        id="f",
        evaluator="freshness",
        description="fresh",
        timestamp_path="metadata.observed",
        max_age_seconds=60,
    )
    evaluator = FreshnessEvaluator()
    fresh = (NOW - timedelta(seconds=30)).isoformat()
    stale = (NOW - timedelta(seconds=90)).isoformat()
    assert evaluator.evaluate(freshness, observation(metadata={"observed": fresh})).status == "PASS"
    assert (
        evaluator.evaluate(freshness, observation(metadata={"observed": stale})).status
        == "BREAKING"
    )
    assert evaluator.evaluate(freshness, observation()).status == "INSUFFICIENT_EVIDENCE"
    assert (
        evaluator.evaluate(freshness, observation(metadata={"observed": "today"})).status
        == "UNKNOWN"
    )
    future = (NOW + timedelta(seconds=30)).isoformat()
    assert (
        evaluator.evaluate(freshness, observation(metadata={"observed": future})).status
        == "UNKNOWN"
    )


def test_observation_context_serializes_activity() -> None:
    context = observation_context(observation(output={"value": 1}))
    assert context["output"] == {"value": 1}
    assert context["observed_at"] == NOW
