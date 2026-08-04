"""Versioned semantic finding and witness models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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


class ContractCoverage(BaseModel):
    """Observed edge coverage without claiming behavior beyond the compared traces."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contracted_edges: tuple[str, ...] = ()
    uncontracted_edges: tuple[str, ...] = ()
    observed_branches: tuple[str, ...] = ()
    unobserved_branches: tuple[str, ...] = ()
    insufficient_evidence_contracts: tuple[str, ...] = ()

    @model_validator(mode="after")
    def branch_sets_match_contracts(self) -> ContractCoverage:
        contracted = set(self.contracted_edges)
        observed = set(self.observed_branches)
        unobserved = set(self.unobserved_branches)
        if observed & unobserved:
            raise ValueError("observed and unobserved branches must be disjoint")
        if not (observed | unobserved) <= contracted:
            raise ValueError("observed and unobserved branches must be contracted edges")
        return self


class SemanticReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["PASS", "WARNING", "FAIL", "UNKNOWN", "INSUFFICIENT_EVIDENCE"]
    first_breaking_edge: str | None = None
    findings: tuple[Finding, ...]
    coverage: ContractCoverage = ContractCoverage()

    @model_validator(mode="after")
    def summary_matches_findings(self) -> SemanticReport:
        statuses = {finding.status for finding in self.findings}
        if "BREAKING" in statuses:
            expected = "FAIL"
        elif "UNKNOWN" in statuses:
            expected = "UNKNOWN"
        elif "INSUFFICIENT_EVIDENCE" in statuses:
            expected = "INSUFFICIENT_EVIDENCE"
        elif "WARNING" in statuses:
            expected = "WARNING"
        else:
            expected = "PASS"
        if self.status != expected:
            raise ValueError(
                f"{self.status} report cannot contain finding statuses that require {expected}"
            )
        breaking_edges = {finding.edge for finding in self.findings if finding.status == "BREAKING"}
        if expected == "FAIL" and self.first_breaking_edge not in breaking_edges:
            raise ValueError("FAIL report must identify an edge with a BREAKING finding")
        if expected != "FAIL" and self.first_breaking_edge is not None:
            raise ValueError("non-failing report cannot identify a first breaking edge")
        return self

    @property
    def breaking_findings(self) -> tuple[Finding, ...]:
        return tuple(item for item in self.findings if item.status == "BREAKING")
