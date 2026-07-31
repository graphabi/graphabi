"""Deterministic, non-enforcing contract inference from successful traces."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from graphabi.contracts.evaluators.builtin import AUTHORITY_SCALE
from graphabi.models.traces import EdgeObservation, TraceBundle


class ContractSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    label: Literal["SUGGESTED — NOT ENFORCED"] = "SUGGESTED — NOT ENFORCED"
    suggestion_id: str
    edge: str
    evaluator: str
    supporting_observation_count: int = Field(ge=0)
    counterexample_count: int = Field(ge=0)
    confidence: float = Field(ge=0, le=1)
    reason: str
    yaml_snippet: str


def _yaml(value: dict[str, Any]) -> str:
    return yaml.safe_dump(value, sort_keys=False).strip()


def _suggestion(
    *,
    suggestion_id: str,
    edge: str,
    evaluator: str,
    support: int,
    counter: int,
    reason: str,
    invariant: dict[str, Any],
) -> ContractSuggestion:
    total = support + counter
    return ContractSuggestion(
        suggestion_id=suggestion_id,
        edge=edge,
        evaluator=evaluator,
        supporting_observation_count=support,
        counterexample_count=counter,
        confidence=support / total if total else 0.0,
        reason=reason,
        yaml_snippet=_yaml(invariant),
    )


def _group(bundle: TraceBundle) -> dict[str, list[EdgeObservation]]:
    grouped: dict[str, list[EdgeObservation]] = {}
    successful = {run.run_id for run in bundle.runs if run.status == "success"}
    for observation in bundle.edge_observations:
        if observation.run_id in successful:
            grouped.setdefault(observation.edge_id, []).append(observation)
    return grouped


def infer_contracts(bundle: TraceBundle) -> tuple[ContractSuggestion, ...]:
    """Suggest repeated relationships; never edits an enforced contract."""
    suggestions: list[ContractSuggestion] = []
    for edge, observations in sorted(_group(bundle).items()):
        verified = [item for item in observations if item.output.get("verified") is True]
        if verified:
            support = sum(any(access.opened for access in item.source_access) for item in verified)
            counter = len(verified) - support
            suggestions.append(
                _suggestion(
                    suggestion_id=f"{edge}.verified_requires_opened_source",
                    edge=edge,
                    evaluator="provenance",
                    support=support,
                    counter=counter,
                    reason="verified=true co-occurred with recorded source access",
                    invariant={
                        "id": "verified_requires_opened_source",
                        "evaluator": "provenance",
                        "description": "A verified result requires an opened source.",
                        "severity": "breaking",
                        "rule": "opened_source",
                    },
                )
            )
        preservation_pairs = [
            (
                item.metadata.get("required_entities"),
                item.output.get("entities"),
            )
            for item in observations
            if "required_entities" in item.metadata and "entities" in item.output
        ]
        if preservation_pairs:
            support = sum(
                isinstance(source, list)
                and isinstance(destination, list)
                and set(source).issubset(destination)
                for source, destination in preservation_pairs
            )
            counter = len(preservation_pairs) - support
            suggestions.append(
                _suggestion(
                    suggestion_id=f"{edge}.required_entities_preserved",
                    edge=edge,
                    evaluator="set_preservation",
                    support=support,
                    counter=counter,
                    reason="consumer-required entities were repeatedly present in producer output",
                    invariant={
                        "id": "required_entities_preserved",
                        "evaluator": "set_preservation",
                        "description": "Required entities survive the edge.",
                        "severity": "warning",
                        "source_path": "metadata.required_entities",
                        "destination_path": "output.entities",
                    },
                )
            )
        authority = [
            str(item.output["authority_level"])
            for item in observations
            if "authority_level" in item.output
        ]
        known = [item for item in authority if item in AUTHORITY_SCALE]
        if known:
            maximum = max(known, key=lambda item: AUTHORITY_SCALE[item])
            suggestions.append(
                _suggestion(
                    suggestion_id=f"{edge}.authority_ceiling",
                    edge=edge,
                    evaluator="authority",
                    support=len(known),
                    counter=len(authority) - len(known),
                    reason=f"observed authority never exceeded {maximum!r}",
                    invariant={
                        "id": "authority_ceiling",
                        "evaluator": "authority",
                        "description": "Authority must not exceed the observed consumer ceiling.",
                        "severity": "breaking",
                        "source_path": "output.authority_level",
                        "maximum_allowed": maximum,
                    },
                )
            )
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
            unique_units = sorted(set(values))
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
            if values and len(unique_units) == 1 and value_path:
                suggestions.append(
                    _suggestion(
                        suggestion_id=f"{edge}.{unit_key}_stable",
                        edge=edge,
                        evaluator="unit_consistency",
                        support=len(values),
                        counter=len(observations) - len(values),
                        reason=f"explicit unit metadata remained stable at {unique_units[0]!r}",
                        invariant={
                            "id": f"{unit_key}_stable",
                            "evaluator": "unit_consistency",
                            "description": (
                                "The consumer relies on the observed unit remaining stable."
                            ),
                            "severity": "breaking",
                            "value_path": value_path,
                            "unit_path": f"metadata.{unit_key}",
                            "expected_unit": unique_units[0],
                        },
                    )
                )
        timestamped: list[float] = []
        for item in observations:
            value = item.metadata.get("evidence_observed_at")
            if isinstance(value, str):
                try:
                    timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
                    if timestamp.tzinfo is None:
                        timestamp = timestamp.replace(tzinfo=UTC)
                    age = (item.observed_at - timestamp).total_seconds()
                    if age >= 0:
                        timestamped.append(age)
                except ValueError:
                    continue
        if timestamped:
            suggested_age = max(60, int(max(timestamped) * 1.1))
            suggestions.append(
                _suggestion(
                    suggestion_id=f"{edge}.evidence_freshness",
                    edge=edge,
                    evaluator="freshness",
                    support=len(timestamped),
                    counter=len(observations) - len(timestamped),
                    reason="successful traces consistently included parseable evidence timestamps",
                    invariant={
                        "id": "evidence_freshness",
                        "evaluator": "freshness",
                        "description": "Evidence remains within the observed freshness envelope.",
                        "severity": "breaking",
                        "timestamp_path": "metadata.evidence_observed_at",
                        "max_age_seconds": suggested_age,
                    },
                )
            )
    return tuple(suggestions)
