"""Deterministic, non-enforcing contract inference from successful traces."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from math import isfinite
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from graphabi.contracts.evaluators.builtin import AUTHORITY_SCALE
from graphabi.models.traces import EdgeObservation, TraceBundle

EvidenceOutcome = Literal["SUPPORTING", "COUNTEREXAMPLE", "INSUFFICIENT_EVIDENCE"]


class SuggestionEvidence(BaseModel):
    """A trace identity and bounded explanation supporting one empirical count."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    edge: str
    occurrence_id: str
    outcome: EvidenceOutcome
    reason: str


class ContractSuggestion(BaseModel):
    """An observed candidate invariant that has no enforcement authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    label: Literal["SUGGESTED: NOT ENFORCED"] = "SUGGESTED: NOT ENFORCED"
    status: Literal["SUGGESTED"] = "SUGGESTED"
    enforcement: Literal["NOT ENFORCED"] = "NOT ENFORCED"
    suggestion_id: str
    edge: str
    evaluator: str
    observation_count: int = Field(ge=0)
    supporting_observation_count: int = Field(ge=0)
    counterexample_count: int = Field(ge=0)
    insufficient_evidence_count: int = Field(ge=0)
    empirical_support_ratio: float = Field(ge=0, le=1)
    # Retained for compatibility with the alpha.1 suggestion shape. It is an empirical ratio,
    # not statistical confidence or a semantic-safety probability.
    confidence: float = Field(ge=0, le=1)
    reason: str
    evidence: tuple[SuggestionEvidence, ...]
    yaml_snippet: str

    @model_validator(mode="after")
    def counts_and_ratio_are_consistent(self) -> ContractSuggestion:
        counted = (
            self.supporting_observation_count
            + self.counterexample_count
            + self.insufficient_evidence_count
        )
        if counted != self.observation_count or len(self.evidence) != self.observation_count:
            raise ValueError("suggestion evidence counts must partition observation_count")
        evidence_counts = Counter(item.outcome for item in self.evidence)
        if (
            evidence_counts["SUPPORTING"] != self.supporting_observation_count
            or evidence_counts["COUNTEREXAMPLE"] != self.counterexample_count
            or evidence_counts["INSUFFICIENT_EVIDENCE"] != self.insufficient_evidence_count
        ):
            raise ValueError("suggestion counts must match evidence outcomes")
        eligible = self.supporting_observation_count + self.counterexample_count
        expected = self.supporting_observation_count / eligible if eligible else 0.0
        if self.empirical_support_ratio != expected or self.confidence != expected:
            raise ValueError(
                "suggestion support ratios must match supporting and counterexample counts"
            )
        return self


def _yaml(value: dict[str, Any]) -> str:
    return yaml.safe_dump(value, sort_keys=False).strip()


def _observation_key(observation: EdgeObservation) -> tuple[str, int, str]:
    return (
        observation.run_id,
        observation.causal_sequence if observation.causal_sequence is not None else -1,
        observation.occurrence_id or f"legacy:{observation.edge_id}",
    )


def _evidence(
    observation: EdgeObservation,
    outcome: EvidenceOutcome,
    reason: str,
) -> SuggestionEvidence:
    return SuggestionEvidence(
        run_id=observation.run_id,
        edge=observation.edge_id,
        occurrence_id=observation.occurrence_id or f"legacy:{observation.edge_id}",
        outcome=outcome,
        reason=reason,
    )


def _suggestion(
    *,
    suggestion_id: str,
    edge: str,
    evaluator: str,
    reason: str,
    evidence: list[SuggestionEvidence],
    invariant: dict[str, Any],
) -> ContractSuggestion:
    support = sum(item.outcome == "SUPPORTING" for item in evidence)
    counter = sum(item.outcome == "COUNTEREXAMPLE" for item in evidence)
    insufficient = sum(item.outcome == "INSUFFICIENT_EVIDENCE" for item in evidence)
    eligible = support + counter
    ratio = support / eligible if eligible else 0.0
    return ContractSuggestion(
        suggestion_id=suggestion_id,
        edge=edge,
        evaluator=evaluator,
        observation_count=len(evidence),
        supporting_observation_count=support,
        counterexample_count=counter,
        insufficient_evidence_count=insufficient,
        empirical_support_ratio=ratio,
        confidence=ratio,
        reason=reason,
        evidence=tuple(evidence),
        yaml_snippet=_yaml(invariant),
    )


def _group(bundle: TraceBundle) -> dict[str, list[EdgeObservation]]:
    identities = {(run.graph_id, run.graph_version, run.schema_version) for run in bundle.runs}
    if len(identities) > 1:
        rendered = ", ".join("/".join(identity) for identity in sorted(identities))
        raise ValueError(
            "contract inference requires one graph identity and trace schema; "
            f"selected runs contain {rendered}"
        )
    grouped: dict[str, list[EdgeObservation]] = {}
    successful = {run.run_id for run in bundle.runs if run.status == "success"}
    for observation in bundle.edge_observations:
        if observation.run_id in successful:
            grouped.setdefault(observation.edge_id, []).append(observation)
    for observations in grouped.values():
        observations.sort(key=_observation_key)
    return grouped


def _provenance_suggestion(
    edge: str, observations: list[EdgeObservation]
) -> ContractSuggestion | None:
    verified = [item for item in observations if item.output.get("verified") is True]
    if not verified:
        return None
    evidence = []
    for item in verified:
        supporting = any(
            access.opened and access.supports_claim is True for access in item.source_access
        )
        evidence.append(
            _evidence(
                item,
                "SUPPORTING" if supporting else "COUNTEREXAMPLE",
                (
                    "verified=true had an opened source recorded as supporting the claim"
                    if supporting
                    else "verified=true had no opened source recorded as supporting the claim"
                ),
            )
        )
    return _suggestion(
        suggestion_id=f"{edge}.verified_requires_opened_supporting_source",
        edge=edge,
        evaluator="provenance",
        reason="verified=true was evaluated against recorded opened supporting source access",
        evidence=evidence,
        invariant={
            "id": "verified_requires_opened_supporting_source",
            "evaluator": "provenance",
            "description": "A verified result requires an opened source supporting the claim.",
            "severity": "breaking",
            "rule": "opened_supporting_source",
        },
    )


def _preservation_suggestion(
    edge: str, observations: list[EdgeObservation]
) -> ContractSuggestion | None:
    evidence: list[SuggestionEvidence] = []
    eligible = False
    for item in observations:
        source = item.metadata.get("required_entities")
        destination = item.output.get("entities")
        if not isinstance(source, list) or not isinstance(destination, list):
            evidence.append(
                _evidence(
                    item,
                    "INSUFFICIENT_EVIDENCE",
                    "required_entities and output.entities were not both observed as lists",
                )
            )
            continue
        try:
            preserved = set(source).issubset(destination)
        except TypeError:
            evidence.append(
                _evidence(
                    item,
                    "INSUFFICIENT_EVIDENCE",
                    "entity collections could not be compared as sets",
                )
            )
            continue
        eligible = True
        evidence.append(
            _evidence(
                item,
                "SUPPORTING" if preserved else "COUNTEREXAMPLE",
                (
                    "all required entities were preserved"
                    if preserved
                    else "one or more required entities were absent from output.entities"
                ),
            )
        )
    if not eligible:
        return None
    return _suggestion(
        suggestion_id=f"{edge}.required_entities_preserved",
        edge=edge,
        evaluator="set_preservation",
        reason="consumer-required entities were evaluated for preservation in producer output",
        evidence=evidence,
        invariant={
            "id": "required_entities_preserved",
            "evaluator": "set_preservation",
            "description": "Required entities survive the edge.",
            "severity": "warning",
            "source_path": "metadata.required_entities",
            "destination_path": "output.entities",
        },
    )


def _authority_suggestion(
    edge: str, observations: list[EdgeObservation]
) -> ContractSuggestion | None:
    known = [
        str(item.output["authority_level"])
        for item in observations
        if isinstance(item.output.get("authority_level"), str)
        and item.output["authority_level"] in AUTHORITY_SCALE
    ]
    if not known:
        return None
    maximum = max(known, key=lambda item: (AUTHORITY_SCALE[item], item))
    evidence = []
    for item in observations:
        value = item.output.get("authority_level")
        if not isinstance(value, str) or value not in AUTHORITY_SCALE:
            evidence.append(
                _evidence(
                    item,
                    "INSUFFICIENT_EVIDENCE",
                    "authority_level was missing or outside the maintained authority vocabulary",
                )
            )
        elif AUTHORITY_SCALE[value] <= AUTHORITY_SCALE[maximum]:
            evidence.append(
                _evidence(item, "SUPPORTING", "authority did not exceed the observed ceiling")
            )
        else:
            evidence.append(
                _evidence(item, "COUNTEREXAMPLE", "authority exceeded the observed ceiling")
            )
    return _suggestion(
        suggestion_id=f"{edge}.authority_ceiling",
        edge=edge,
        evaluator="authority",
        reason=f"known authority observations did not exceed {maximum!r}",
        evidence=evidence,
        invariant={
            "id": "authority_ceiling",
            "evaluator": "authority",
            "description": "Authority must not exceed the observed consumer ceiling.",
            "severity": "breaking",
            "source_path": "output.authority_level",
            "maximum_allowed": maximum,
        },
    )


def _unit_suggestions(edge: str, observations: list[EdgeObservation]) -> list[ContractSuggestion]:
    suggestions: list[ContractSuggestion] = []
    unit_keys = sorted(
        {
            key
            for item in observations
            for key, value in item.metadata.items()
            if key.endswith("_unit") and isinstance(value, str)
        }
    )
    for unit_key in unit_keys:
        values = [
            str(item.metadata[unit_key])
            for item in observations
            if isinstance(item.metadata.get(unit_key), str)
        ]
        if not values:
            continue
        counts = Counter(values)
        expected_unit = min(counts, key=lambda value: (-counts[value], value))
        base_name = unit_key.removesuffix("_unit")
        candidate_paths = (
            f"output.{base_name}",
            "output.confidence" if unit_key == "evidence_unit" else "output.value",
        )
        value_path = next(
            (
                path
                for path in candidate_paths
                if any(path.split(".", 1)[1] in item.output for item in observations)
            ),
            None,
        )
        if value_path is None:
            continue
        value_key = value_path.split(".", 1)[1]
        evidence = []
        eligible = False
        for item in observations:
            unit = item.metadata.get(unit_key)
            value = item.output.get(value_key)
            if (
                not isinstance(unit, str)
                or isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(value)
            ):
                evidence.append(
                    _evidence(
                        item,
                        "INSUFFICIENT_EVIDENCE",
                        "unit metadata and a finite numeric magnitude were not both observed",
                    )
                )
                continue
            eligible = True
            evidence.append(
                _evidence(
                    item,
                    "SUPPORTING" if unit == expected_unit else "COUNTEREXAMPLE",
                    (
                        "unit matched the most frequently observed value"
                        if unit == expected_unit
                        else "unit differed from the most frequently observed value"
                    ),
                )
            )
        if not eligible:
            continue
        suggestions.append(
            _suggestion(
                suggestion_id=f"{edge}.{unit_key}_stable",
                edge=edge,
                evaluator="unit_consistency",
                reason=f"the most frequently observed explicit unit was {expected_unit!r}",
                evidence=evidence,
                invariant={
                    "id": f"{unit_key}_stable",
                    "evaluator": "unit_consistency",
                    "description": "The consumer relies on the observed unit remaining stable.",
                    "severity": "breaking",
                    "value_path": value_path,
                    "unit_path": f"metadata.{unit_key}",
                    "expected_unit": expected_unit,
                },
            )
        )
    return suggestions


def _freshness_suggestion(
    edge: str, observations: list[EdgeObservation]
) -> ContractSuggestion | None:
    parsed: list[tuple[EdgeObservation, float]] = []
    for item in observations:
        value = item.metadata.get("evidence_observed_at")
        if not isinstance(value, str):
            continue
        try:
            timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=UTC)
        except ValueError:
            continue
        age = (item.observed_at - timestamp).total_seconds()
        if age < 0:
            continue
        parsed.append((item, age))
    if not parsed:
        return None
    suggested_age = max(60, int(max(age for _, age in parsed) * 1.1))
    parsed_ids = {_observation_key(item) for item, _ in parsed}
    evidence = [
        _evidence(
            item,
            "SUPPORTING" if _observation_key(item) in parsed_ids else "INSUFFICIENT_EVIDENCE",
            (
                "evidence timestamp was within the observed freshness envelope"
                if _observation_key(item) in parsed_ids
                else "evidence timestamp was missing, invalid, or in the future"
            ),
        )
        for item in observations
    ]
    return _suggestion(
        suggestion_id=f"{edge}.evidence_freshness",
        edge=edge,
        evaluator="freshness",
        reason="parseable non-future evidence timestamps defined an observed freshness envelope",
        evidence=evidence,
        invariant={
            "id": "evidence_freshness",
            "evaluator": "freshness",
            "description": "Evidence remains within the observed freshness envelope.",
            "severity": "breaking",
            "timestamp_path": "metadata.evidence_observed_at",
            "max_age_seconds": suggested_age,
        },
    )


def infer_contracts(bundle: TraceBundle) -> tuple[ContractSuggestion, ...]:
    """Suggest empirical candidate invariants; never edits or enforces a contract."""
    suggestions: list[ContractSuggestion] = []
    for edge, observations in sorted(_group(bundle).items()):
        for candidate in (
            _provenance_suggestion(edge, observations),
            _preservation_suggestion(edge, observations),
            _authority_suggestion(edge, observations),
        ):
            if candidate is not None:
                suggestions.append(candidate)
        suggestions.extend(_unit_suggestions(edge, observations))
        freshness = _freshness_suggestion(edge, observations)
        if freshness is not None:
            suggestions.append(freshness)
    return tuple(suggestions)
