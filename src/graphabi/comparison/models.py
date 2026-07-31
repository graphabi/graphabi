"""Versioned semantic finding and witness models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from graphabi.models.traces import EdgeObservation, JsonValue


class Witness(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    edge: str
    relevant_input: dict[str, Any]
    relevant_output: dict[str, Any]
    relevant_metadata: dict[str, Any]
    contract_expectation: str
    observed_conflict: JsonValue
    schema_blind_spot: str


class Finding(BaseModel):
    """One deterministic evaluation result with complete local evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    finding_id: str
    contract_id: str
    contract_version: str
    graph: str
    edge: str
    producer: str
    consumer: str
    severity: Literal["warning", "breaking"]
    status: Literal["PASS", "WARNING", "BREAKING", "UNKNOWN", "INSUFFICIENT_EVIDENCE"]
    baseline_observation: EdgeObservation | None = None
    candidate_observation: EdgeObservation | None = None
    input: dict[str, JsonValue] = Field(default_factory=dict)
    output: dict[str, JsonValue] = Field(default_factory=dict)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    run_id: str
    reason: str
    witness: Witness
    direct_consumer: str
    affected_downstream_nodes: tuple[str, ...] = ()
    affected_terminal_paths: tuple[tuple[str, ...], ...] = ()
    affected_side_effecting_paths: tuple[tuple[str, ...], ...] = ()
    shortest_affected_path: tuple[str, ...] = ()
    unaffected_branches_exist: bool = False
    nearest_repair_location: str
    impact_explanation: str = ""


class SemanticReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["PASS", "WARNING", "FAIL", "UNKNOWN", "INSUFFICIENT_EVIDENCE"]
    first_breaking_edge: str | None = None
    findings: tuple[Finding, ...]

    @property
    def breaking_findings(self) -> tuple[Finding, ...]:
        return tuple(item for item in self.findings if item.status == "BREAKING")
