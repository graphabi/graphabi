import pytest
from tests.unit.test_evaluators import observation

from graphabi.contracts.evaluators.builtin import AuthorityEvaluator, SetPreservationEvaluator
from graphabi.contracts.models import Invariant


def test_identity_continuity_rejects_unrelated_non_empty_identifier() -> None:
    invariant = Invariant(
        id="identity",
        evaluator="set_preservation",
        description="required identifiers continue across the edge",
        source_path="metadata.required_ids",
        destination_path="output.ids",
        set_relation="contains_all_required",
    )
    evaluator = SetPreservationEvaluator()
    result = evaluator.evaluate(
        invariant,
        observation(
            metadata={"required_ids": ["invoice-83"]},
            output={"ids": ["invoice-99"]},
        ),
    )
    assert result.status == "BREAKING"


def test_identity_continuity_allows_reorder_and_superset() -> None:
    invariant = Invariant(
        id="identity",
        evaluator="set_preservation",
        description="required identifiers continue across the edge",
        source_path="metadata.required_ids",
        destination_path="output.ids",
        set_relation="contains_all_required",
    )
    result = SetPreservationEvaluator().evaluate(
        invariant,
        observation(
            metadata={"required_ids": ["customer-17", "invoice-83"]},
            output={"ids": ["invoice-83", "customer-17", "unrelated-4"]},
        ),
    )
    assert result.status == "PASS"


def test_authority_requires_declared_order() -> None:
    invariant = Invariant(
        id="authority",
        evaluator="authority",
        description="authority is bounded",
        source_path="output.level",
        maximum_allowed="recommendation",
    )
    result = AuthorityEvaluator().evaluate(invariant, observation(output={"level": "suggestion"}))
    assert result.status == "UNKNOWN"


def test_authority_uses_contract_local_order() -> None:
    invariant = Invariant(
        id="authority",
        evaluator="authority",
        description="authority is bounded",
        source_path="output.level",
        maximum_allowed="recommender",
        authority_order=("viewer", "recommender", "approver"),
    )
    evaluator = AuthorityEvaluator()
    assert evaluator.evaluate(invariant, observation(output={"level": "viewer"})).status == "PASS"
    assert (
        evaluator.evaluate(invariant, observation(output={"level": "approver"})).status
        == "BREAKING"
    )
    assert (
        evaluator.evaluate(invariant, observation(output={"level": "supervisor"})).status
        == "UNKNOWN"
    )


def _identity(relation: str = "contains_all_required") -> Invariant:
    return Invariant(
        id="identity",
        evaluator="set_preservation",
        description="identity relation",
        source_path="metadata.required_ids",
        destination_path="output.ids",
        set_relation=relation,
    )


@pytest.mark.parametrize(
    ("source", "destination", "expected"),
    [
        (["a", "b"], ["a", "b"], "PASS"),
        (["a", "b"], ["b", "a"], "PASS"),
        (["a"], ["a", "extra"], "PASS"),
        (["a", "b"], ["a"], "BREAKING"),
        (["invoice-83"], ["invoice-99"], "BREAKING"),
        (["a"], ["a", "a"], "PASS"),
        ([None], [None], "PASS"),
        (["a"], [], "BREAKING"),
        ([], ["extra"], "PASS"),
        ([1], ["1"], "BREAKING"),
    ],
)
def test_identity_relations_cover_common_safe_and_breaking_shapes(
    source: list[object], destination: list[object], expected: str
) -> None:
    result = SetPreservationEvaluator().evaluate(
        _identity(), observation(metadata={"required_ids": source}, output={"ids": destination})
    )
    assert result.status == expected


def test_identity_rejects_non_collections_and_unhashable_values() -> None:
    evaluator = SetPreservationEvaluator()
    assert (
        evaluator.evaluate(
            _identity(), observation(metadata={"required_ids": "a"}, output={"ids": ["a"]})
        ).status
        == "UNKNOWN"
    )
    assert (
        evaluator.evaluate(
            _identity(),
            observation(metadata={"required_ids": [{"id": "a"}]}, output={"ids": [{"id": "a"}]}),
        ).status
        == "UNKNOWN"
    )


def test_identity_equal_relation_rejects_superset() -> None:
    result = SetPreservationEvaluator().evaluate(
        _identity("equal"),
        observation(metadata={"required_ids": ["a"]}, output={"ids": ["a", "extra"]}),
    )
    assert result.status == "BREAKING"


AUTHORITY_ORDER = ("viewer", "recommender", "approver")


def _authority(
    maximum: str = "recommender", order: tuple[str, ...] | None = AUTHORITY_ORDER
) -> Invariant:
    return Invariant(
        id="authority",
        evaluator="authority",
        description="authority relation",
        source_path="output.level",
        maximum_allowed=maximum,
        authority_order=order,
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("viewer", "PASS"),
        ("recommender", "PASS"),
        ("approver", "BREAKING"),
        ("supervisor", "UNKNOWN"),
        (None, "UNKNOWN"),
        (3, "UNKNOWN"),
    ],
)
def test_authority_declared_order_is_deterministic(value: object, expected: str) -> None:
    assert (
        AuthorityEvaluator().evaluate(_authority(), observation(output={"level": value})).status
        == expected
    )


def test_authority_missing_evidence_is_insufficient() -> None:
    assert (
        AuthorityEvaluator().evaluate(_authority(), observation()).status == "INSUFFICIENT_EVIDENCE"
    )


def test_authority_unknown_order_is_unknown() -> None:
    assert (
        AuthorityEvaluator()
        .evaluate(
            _authority(maximum="recommendation", order=None),
            observation(output={"level": "viewer"}),
        )
        .status
        == "UNKNOWN"
    )


def test_authority_contract_rejects_duplicate_order_and_missing_maximum() -> None:
    with pytest.raises(ValueError, match="unique"):
        _authority(order=("viewer", "viewer"))
    with pytest.raises(ValueError, match="appear"):
        _authority(maximum="missing", order=AUTHORITY_ORDER)
