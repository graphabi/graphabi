"""Versioned semantic finding and witness models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from graphabi.models.traces import EdgeObservation, JsonValue


class Witness(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    edge: str
    baseline_occurrence_id: str | None = None
    candidate_occurrence_id: str | None = None
    occurrence_pairing: Literal[
        "LOGICAL_SINGLETON",
        "CAUSAL_MATCH",
        "BASELINE_ONLY",
        "CANDIDATE_ONLY",
        "AMBIGUOUS",
        "UNOBSERVED",
    ] = "LOGICAL_SINGLETON"
    causal_pairing_key: str | None = None
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
    baseline_occurrence_id: str | None = None
    candidate_occurrence_id: str | None = None
    occurrence_pairing: Literal[
        "LOGICAL_SINGLETON",
        "CAUSAL_MATCH",
        "BASELINE_ONLY",
        "CANDIDATE_ONLY",
        "AMBIGUOUS",
        "UNOBSERVED",
    ] = "LOGICAL_SINGLETON"
    causal_pairing_key: str | None = None
    reason: str
    witness: Witness
    direct_consumer: str
    affected_downstream_nodes: tuple[str, ...] = ()
    affected_downstream_occurrences: tuple[str, ...] = ()
    affected_terminal_paths: tuple[tuple[str, ...], ...] = ()
    affected_side_effecting_paths: tuple[tuple[str, ...], ...] = ()
    shortest_affected_path: tuple[str, ...] = ()
    shortest_affected_occurrence_path: tuple[str, ...] = ()
    unaffected_branches_exist: bool = False
    nearest_repair_location: str
    impact_explanation: str = ""


class ContractCoverageSummary(BaseModel):
    """Counted coverage metrics for machine and human report consumers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    total_graph_nodes: int = Field(ge=0)
    total_graph_edges: int = Field(ge=0)
    contracted_edges: int = Field(ge=0)
    uncontracted_edges: int = Field(ge=0)
    observed_edges: int = Field(ge=0)
    unobserved_edges: int = Field(ge=0)
    contracted_and_observed: int = Field(ge=0)
    contracted_but_unobserved: int = Field(ge=0)
    observed_but_uncontracted: int = Field(ge=0)
    branches_with_insufficient_evidence: int = Field(ge=0)
    observed_contract_coverage_percent: float = Field(ge=0, le=100)
    coverage_is_correctness: Literal[False] = False
    explanation: str = (
        "Coverage measures declared graph edges that are both contracted and observed in the "
        "selected candidate run. It does not establish semantic correctness."
    )


class ContractCoverage(BaseModel):
    """Graph, contract, and observation sets without a semantic-safety claim."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    graph_nodes: tuple[str, ...] = ()
    graph_edges: tuple[str, ...] = ()
    contracted_edges: tuple[str, ...] = ()
    uncontracted_edges: tuple[str, ...] = ()
    observed_edges: tuple[str, ...] = ()
    unobserved_edges: tuple[str, ...] = ()
    contracted_and_observed: tuple[str, ...] = ()
    contracted_but_unobserved: tuple[str, ...] = ()
    observed_but_uncontracted: tuple[str, ...] = ()
    insufficient_evidence_branches: tuple[str, ...] = ()
    unexpected_observed_edges: tuple[str, ...] = ()
    graph_inventory_complete: bool = False
    # Retained in report 0.2 so report 0.1 consumers can migrate without guessing.
    observed_branches: tuple[str, ...] = ()
    unobserved_branches: tuple[str, ...] = ()
    insufficient_evidence_contracts: tuple[str, ...] = ()

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_coverage(cls, value: Any) -> Any:
        """Populate the complete inventory when loading a report 0.1 payload."""
        if not isinstance(value, dict):
            return value
        migrated = dict(value)
        # ``summary`` is derived from the identity sets. Recalculate it on load
        # so a serialized or hand-edited count cannot contradict the evidence.
        migrated.pop("summary", None)
        if "graph_edges" in migrated:
            return migrated
        contracted = tuple(migrated.get("contracted_edges", ()))
        uncontracted = tuple(migrated.get("uncontracted_edges", ()))
        observed = tuple(migrated.get("observed_branches", ())) + uncontracted
        unobserved = tuple(migrated.get("unobserved_branches", ()))
        graph_edges = tuple(dict.fromkeys((*contracted, *uncontracted)))
        migrated.update(
            graph_nodes=(),
            graph_edges=graph_edges,
            observed_edges=observed,
            unobserved_edges=unobserved,
            contracted_and_observed=tuple(migrated.get("observed_branches", ())),
            contracted_but_unobserved=unobserved,
            observed_but_uncontracted=uncontracted,
            insufficient_evidence_branches=unobserved,
            unexpected_observed_edges=uncontracted,
            graph_inventory_complete=False,
        )
        return migrated

    @model_validator(mode="after")
    def coverage_sets_are_consistent(self) -> ContractCoverage:
        graph = set(self.graph_edges)
        contracted = set(self.contracted_edges)
        uncontracted = set(self.uncontracted_edges)
        observed = set(self.observed_edges)
        unobserved = set(self.unobserved_edges)
        collections = {
            "graph_nodes": self.graph_nodes,
            "graph_edges": self.graph_edges,
            "contracted_edges": self.contracted_edges,
            "uncontracted_edges": self.uncontracted_edges,
            "observed_edges": self.observed_edges,
            "unobserved_edges": self.unobserved_edges,
            "contracted_and_observed": self.contracted_and_observed,
            "contracted_but_unobserved": self.contracted_but_unobserved,
            "observed_but_uncontracted": self.observed_but_uncontracted,
            "insufficient_evidence_branches": self.insufficient_evidence_branches,
            "unexpected_observed_edges": self.unexpected_observed_edges,
            "observed_branches": self.observed_branches,
            "unobserved_branches": self.unobserved_branches,
            "insufficient_evidence_contracts": self.insufficient_evidence_contracts,
        }
        duplicates = [
            name for name, values in collections.items() if len(values) != len(set(values))
        ]
        if duplicates:
            raise ValueError(f"coverage collections must not contain duplicates: {duplicates}")
        expected_sets = {
            "contracted and uncontracted edges": (contracted | uncontracted, graph),
            "observed and unobserved edges": (observed | unobserved, graph),
            "contracted_and_observed": (set(self.contracted_and_observed), contracted & observed),
            "contracted_but_unobserved": (
                set(self.contracted_but_unobserved),
                contracted - observed,
            ),
            "observed_but_uncontracted": (
                set(self.observed_but_uncontracted),
                observed - contracted,
            ),
            "observed_branches": (set(self.observed_branches), contracted & observed),
            "unobserved_branches": (set(self.unobserved_branches), contracted - observed),
        }
        if contracted & uncontracted:
            raise ValueError("contracted and uncontracted edges must be disjoint")
        if observed & unobserved:
            raise ValueError("observed and unobserved edges must be disjoint")
        for name, (actual, expected) in expected_sets.items():
            if actual != expected:
                raise ValueError(f"coverage set {name} is inconsistent with graph inventory")
        if not set(self.insufficient_evidence_branches) <= contracted:
            raise ValueError("insufficient-evidence branches must be contracted edges")
        if not set(self.unexpected_observed_edges) <= graph:
            raise ValueError("unexpected observed edges must be present in the graph inventory")
        return self

    @computed_field
    @property
    def summary(self) -> ContractCoverageSummary:
        denominator = len(self.graph_edges)
        covered = len(self.contracted_and_observed)
        percentage = round(100 * covered / denominator, 1) if denominator else 0.0
        return ContractCoverageSummary(
            total_graph_nodes=len(self.graph_nodes),
            total_graph_edges=denominator,
            contracted_edges=len(self.contracted_edges),
            uncontracted_edges=len(self.uncontracted_edges),
            observed_edges=len(self.observed_edges),
            unobserved_edges=len(self.unobserved_edges),
            contracted_and_observed=covered,
            contracted_but_unobserved=len(self.contracted_but_unobserved),
            observed_but_uncontracted=len(self.observed_but_uncontracted),
            branches_with_insufficient_evidence=len(self.insufficient_evidence_branches),
            observed_contract_coverage_percent=percentage,
        )


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
