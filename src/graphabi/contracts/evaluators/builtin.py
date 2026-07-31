"""Built-in deterministic evaluator families."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from graphabi.contracts.evaluators.base import EvaluationResult, failure_status
from graphabi.contracts.evaluators.paths import (
    MISSING,
    evaluate_condition,
    observation_context,
    resolve_path,
)
from graphabi.contracts.models import Invariant
from graphabi.models.traces import EdgeObservation


def _failure(
    invariant: Invariant, reason: str, expectation: str, observed: Any, *paths: str
) -> EvaluationResult:
    return EvaluationResult(
        status=failure_status(invariant),
        reason=invariant.failure_message or reason,
        expectation=expectation,
        observed=observed,
        relevant_paths=paths,
    )


class ImplicationEvaluator:
    name = "implication"

    def evaluate(
        self,
        invariant: Invariant,
        candidate: EdgeObservation,
        baseline: EdgeObservation | None = None,
    ) -> EvaluationResult:
        del baseline
        assert invariant.when is not None and invariant.require is not None
        context = observation_context(candidate)
        triggered, _ = evaluate_condition(invariant.when, context)
        if triggered is None:
            return EvaluationResult(
                status="INSUFFICIENT_EVIDENCE",
                reason=f"could not evaluate implication condition at {invariant.when.path}",
                expectation=invariant.description,
                relevant_paths=(invariant.when.path,),
            )
        if not triggered:
            return EvaluationResult(
                status="PASS",
                reason="implication antecedent was not true",
                expectation=invariant.description,
            )
        satisfied, observed = evaluate_condition(invariant.require, context)
        if satisfied is None:
            return EvaluationResult(
                status="INSUFFICIENT_EVIDENCE",
                reason=f"required evidence is missing or incomparable at {invariant.require.path}",
                expectation=invariant.description,
                relevant_paths=(invariant.when.path, invariant.require.path),
            )
        if satisfied:
            return EvaluationResult(
                status="PASS",
                reason="triggered implication requirement was satisfied",
                expectation=invariant.description,
                observed=observed,
                relevant_paths=(invariant.when.path, invariant.require.path),
            )
        operation, expected = invariant.require.operation
        return _failure(
            invariant,
            f"{invariant.require.path} was {observed!r}; expected {operation} {expected!r}",
            invariant.description,
            observed,
            invariant.when.path,
            invariant.require.path,
        )


class ProvenanceEvaluator:
    name = "provenance"

    def evaluate(
        self,
        invariant: Invariant,
        candidate: EdgeObservation,
        baseline: EdgeObservation | None = None,
    ) -> EvaluationResult:
        del baseline
        verified = candidate.output.get("verified")
        if verified is not True:
            return EvaluationResult(
                status="PASS",
                reason="output was not marked verified",
                expectation=invariant.description,
            )
        opened = [access for access in candidate.source_access if access.opened]
        supporting = [access for access in opened if access.supports_claim is True]
        cited = candidate.output.get("sources", [])
        accessed_ids = {access.source_id for access in opened}
        if (invariant.rule == "opened_source" and opened) or (
            invariant.rule == "claim_support" and supporting
        ):
            passed = True
        elif invariant.rule == "accessed_citations" and isinstance(cited, list):
            passed = bool(cited) and {str(item) for item in cited}.issubset(accessed_ids)
        elif invariant.rule == "opened_supporting_source":
            passed = bool(supporting)
        else:
            passed = False
        if passed:
            return EvaluationResult(
                status="PASS",
                reason="recorded source-access events satisfy the provenance rule",
                expectation=invariant.description,
                observed={"opened": len(opened), "supporting": len(supporting)},
                relevant_paths=("output.verified", "source_access"),
            )
        return _failure(
            invariant,
            "verified=true had no successfully opened source recorded as supporting the claim",
            invariant.description,
            {"cited": cited, "opened": len(opened), "supporting": len(supporting)},
            "output.verified",
            "output.sources",
            "source_access",
        )


class SetPreservationEvaluator:
    name = "set_preservation"

    def evaluate(
        self,
        invariant: Invariant,
        candidate: EdgeObservation,
        baseline: EdgeObservation | None = None,
    ) -> EvaluationResult:
        del baseline
        assert invariant.source_path and invariant.destination_path
        context = observation_context(candidate)
        source = resolve_path(context, invariant.source_path)
        destination = resolve_path(context, invariant.destination_path)
        if source is MISSING or destination is MISSING:
            return EvaluationResult(
                status="INSUFFICIENT_EVIDENCE",
                reason="a preservation path was not observed",
                expectation=invariant.description,
                relevant_paths=(invariant.source_path, invariant.destination_path),
            )
        if not isinstance(source, (list, tuple, set)) or not isinstance(
            destination, (list, tuple, set)
        ):
            return EvaluationResult(
                status="UNKNOWN",
                reason="preservation values are not collections",
                expectation=invariant.description,
            )
        missing = sorted(set(source) - set(destination), key=str)
        if not missing:
            return EvaluationResult(
                status="PASS",
                reason="all required values were preserved",
                expectation=invariant.description,
                observed=[],
            )
        return _failure(
            invariant,
            f"required values disappeared across the edge: {missing}",
            invariant.description,
            missing,
            invariant.source_path,
            invariant.destination_path,
        )


class CompletenessEvaluator:
    name = "completeness"

    def evaluate(
        self,
        invariant: Invariant,
        candidate: EdgeObservation,
        baseline: EdgeObservation | None = None,
    ) -> EvaluationResult:
        del baseline
        assert invariant.destination_path
        value = resolve_path(observation_context(candidate), invariant.destination_path)
        if value is MISSING:
            return EvaluationResult(
                status="INSUFFICIENT_EVIDENCE",
                reason="required field was not observed",
                expectation=invariant.description,
            )
        if value:
            return EvaluationResult(
                status="PASS",
                reason="consumer-required value is non-empty",
                expectation=invariant.description,
                observed=value,
            )
        return _failure(
            invariant,
            "consumer-required value became empty",
            invariant.description,
            value,
            invariant.destination_path,
        )


class UnitConsistencyEvaluator:
    name = "unit_consistency"

    def evaluate(
        self,
        invariant: Invariant,
        candidate: EdgeObservation,
        baseline: EdgeObservation | None = None,
    ) -> EvaluationResult:
        del baseline
        assert invariant.value_path and invariant.unit_path and invariant.expected_unit
        context = observation_context(candidate)
        value = resolve_path(context, invariant.value_path)
        unit = resolve_path(context, invariant.unit_path)
        representation = (
            resolve_path(context, invariant.representation_path)
            if invariant.representation_path
            else None
        )
        if value is MISSING or unit is MISSING:
            return EvaluationResult(
                status="INSUFFICIENT_EVIDENCE",
                reason="unit or magnitude metadata is missing",
                expectation=invariant.description,
            )
        unit_ok = unit == invariant.expected_unit
        representation_ok = (
            invariant.expected_representation is None
            or representation == invariant.expected_representation
        )
        if unit_ok and representation_ok:
            return EvaluationResult(
                status="PASS",
                reason="unit and representation match the consumer requirement",
                expectation=invariant.description,
                observed={"value": value, "unit": unit, "representation": representation},
            )
        reason = (
            f"observed unit {unit!r} and representation {representation!r}; "
            f"expected {invariant.expected_unit!r}"
        )
        if invariant.expected_representation:
            reason += f" with {invariant.expected_representation!r} representation"
        if invariant.allow_conversion:
            return EvaluationResult(
                status="UNKNOWN",
                reason=reason + "; conversion correctness was not proven",
                expectation=invariant.description,
            )
        return _failure(
            invariant,
            reason,
            invariant.description,
            {"value": value, "unit": unit, "representation": representation},
            invariant.value_path,
            invariant.unit_path,
        )


AUTHORITY_SCALE = {
    "suggestion": 0,
    "recommendation": 1,
    "draft": 1,
    "decision": 2,
    "authorized": 3,
    "published": 4,
}


class AuthorityEvaluator:
    name = "authority"

    def evaluate(
        self,
        invariant: Invariant,
        candidate: EdgeObservation,
        baseline: EdgeObservation | None = None,
    ) -> EvaluationResult:
        del baseline
        assert invariant.source_path and invariant.maximum_allowed
        value = resolve_path(observation_context(candidate), invariant.source_path)
        if value is MISSING:
            return EvaluationResult(
                status="INSUFFICIENT_EVIDENCE",
                reason="authority level was not observed",
                expectation=invariant.description,
            )
        if value not in AUTHORITY_SCALE or invariant.maximum_allowed not in AUTHORITY_SCALE:
            return EvaluationResult(
                status="UNKNOWN",
                reason=f"unknown authority level: {value!r}",
                expectation=invariant.description,
                observed=value,
            )
        if AUTHORITY_SCALE[str(value)] <= AUTHORITY_SCALE[invariant.maximum_allowed]:
            return EvaluationResult(
                status="PASS",
                reason="authority did not exceed the consumer maximum",
                expectation=invariant.description,
                observed=value,
            )
        return _failure(
            invariant,
            f"authority escalated to {value!r} above {invariant.maximum_allowed!r}",
            invariant.description,
            value,
            invariant.source_path,
        )


class FreshnessEvaluator:
    name = "freshness"

    def evaluate(
        self,
        invariant: Invariant,
        candidate: EdgeObservation,
        baseline: EdgeObservation | None = None,
    ) -> EvaluationResult:
        del baseline
        assert invariant.timestamp_path and invariant.max_age_seconds
        value = resolve_path(observation_context(candidate), invariant.timestamp_path)
        if value is MISSING or value is None:
            return EvaluationResult(
                status="INSUFFICIENT_EVIDENCE",
                reason="required observation timestamp is missing",
                expectation=invariant.description,
            )
        try:
            observed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if observed.tzinfo is None:
                observed = observed.replace(tzinfo=UTC)
        except ValueError:
            return EvaluationResult(
                status="UNKNOWN",
                reason=f"timestamp is not ISO-8601: {value!r}",
                expectation=invariant.description,
                observed=str(value),
            )
        age = max(0.0, (candidate.observed_at - observed).total_seconds())
        if age <= invariant.max_age_seconds:
            return EvaluationResult(
                status="PASS",
                reason="evidence is within the configured maximum age",
                expectation=invariant.description,
                observed=age,
            )
        return _failure(
            invariant,
            f"evidence age {age:.0f}s exceeds {invariant.max_age_seconds:.0f}s",
            invariant.description,
            age,
            invariant.timestamp_path,
        )
