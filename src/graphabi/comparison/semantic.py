"""Deterministic consumer-driven semantic comparison engine."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import networkx as nx

from graphabi.comparison.models import Finding, SemanticReport, Witness
from graphabi.contracts.evaluators import EvaluatorRegistry, default_registry
from graphabi.contracts.evaluators.base import EvaluationResult
from graphabi.contracts.models import Contract, ContractEdge, Invariant
from graphabi.impact import analyze_impact
from graphabi.models.traces import EdgeObservation, RedactedValue, TraceBundle


def _stable_id(contract: Contract, edge: ContractEdge, invariant: Invariant) -> str:
    identity = f"{contract.version}|{contract.graph}|{edge.id}|{invariant.id}"
    return "gabi-" + hashlib.sha256(identity.encode()).hexdigest()[:16]


def _select(mapping: dict[str, Any], paths: tuple[str, ...], prefix: str) -> dict[str, Any]:
    selected: dict[str, Any] = {}
    for path in paths:
        parts = path.split(".")
        if parts[0] == prefix and len(parts) > 1 and parts[1] in mapping:
            selected[parts[1]] = mapping[parts[1]]
    if len(selected) < len(mapping):
        selected["_unrelated"] = RedactedValue().model_dump(mode="json")
    return selected


def _witness(
    observation: EdgeObservation | None,
    edge: ContractEdge,
    result: EvaluationResult,
) -> Witness:
    if observation is None:
        return Witness(
            run_id="<missing>",
            edge=edge.id,
            relevant_input={},
            relevant_output={},
            relevant_metadata={},
            contract_expectation=result.expectation,
            observed_conflict=result.observed,
            schema_blind_spot=(
                "No candidate edge observation was available for structural validation."
            ),
        )
    return Witness(
        run_id=observation.run_id,
        edge=edge.id,
        relevant_input=_select(observation.input, result.relevant_paths, "input"),
        relevant_output=_select(observation.output, result.relevant_paths, "output"),
        relevant_metadata=_select(observation.metadata, result.relevant_paths, "metadata"),
        contract_expectation=result.expectation,
        observed_conflict=result.observed,
        schema_blind_spot=(
            "The payload validates because its schema constrains structure and primitive values, "
            "not this cross-field or trace-evidence relationship."
        ),
    )


def _missing_result(edge_id: str) -> EvaluationResult:
    return EvaluationResult(
        status="INSUFFICIENT_EVIDENCE",
        reason=f"candidate has no recorded observation for edge {edge_id}",
        expectation="a candidate observation is required before compatibility can be established",
    )


def _ordered_edges(contract: Contract) -> tuple[ContractEdge, ...]:
    graph = nx.DiGraph()
    graph.add_nodes_from(node.id for node in contract.nodes)
    graph.add_edges_from((edge.producer, edge.consumer) for edge in contract.edges)
    try:
        node_order = {node: index for index, node in enumerate(nx.topological_sort(graph))}
    except nx.NetworkXUnfeasible:
        return contract.edges
    original_order = {edge.id: index for index, edge in enumerate(contract.edges)}
    return tuple(
        sorted(
            contract.edges,
            key=lambda edge: (
                node_order[edge.producer],
                node_order[edge.consumer],
                original_order[edge.id],
            ),
        )
    )


def compare_semantics(
    contract: Contract,
    baseline: TraceBundle,
    candidate: TraceBundle,
    *,
    registry: EvaluatorRegistry | None = None,
) -> SemanticReport:
    """Evaluate every edge invariant against actual candidate observations."""
    active_registry = registry or default_registry()
    baseline_by_edge = {item.edge_id: item for item in baseline.edge_observations}
    candidate_by_edge = {item.edge_id: item for item in candidate.edge_observations}
    findings: list[Finding] = []
    first_breaking_edge: str | None = None
    for edge in _ordered_edges(contract):
        baseline_observation = baseline_by_edge.get(edge.id)
        candidate_observation = candidate_by_edge.get(edge.id)
        for invariant in edge.invariants:
            evaluator = active_registry.get(invariant.evaluator)
            if candidate_observation is None:
                result = _missing_result(edge.id)
            elif evaluator is None:
                result = EvaluationResult(
                    status="UNKNOWN",
                    reason=f"evaluator {invariant.evaluator!r} is not registered",
                    expectation=invariant.description,
                )
            else:
                result = evaluator.evaluate(invariant, candidate_observation, baseline_observation)
            impact = analyze_impact(contract, edge.id) if result.status == "BREAKING" else None
            if first_breaking_edge is None and result.status == "BREAKING":
                first_breaking_edge = edge.id
            finding = Finding(
                finding_id=_stable_id(contract, edge, invariant),
                contract_id=f"{contract.graph}:{edge.id}:{invariant.id}",
                contract_version=contract.version,
                graph=contract.graph,
                edge=edge.id,
                producer=edge.producer,
                consumer=edge.consumer,
                severity=invariant.severity,
                status=result.status,
                baseline_observation=baseline_observation,
                candidate_observation=candidate_observation,
                input=candidate_observation.input if candidate_observation else {},
                output=candidate_observation.output if candidate_observation else {},
                metadata=candidate_observation.metadata if candidate_observation else {},
                run_id=candidate_observation.run_id if candidate_observation else "<missing>",
                reason=result.reason,
                witness=_witness(candidate_observation, edge, result),
                direct_consumer=impact.direct_consumer if impact else edge.consumer,
                affected_downstream_nodes=impact.downstream_nodes if impact else (),
                affected_terminal_paths=impact.terminal_paths if impact else (),
                affected_side_effecting_paths=impact.side_effecting_paths if impact else (),
                shortest_affected_path=impact.shortest_affected_path if impact else (),
                unaffected_branches_exist=impact.unaffected_branches_exist if impact else False,
                nearest_repair_location=(
                    impact.nearest_repair_location
                    if impact
                    else f"at contract {invariant.id} on {edge.producer} -> {edge.consumer}"
                ),
                impact_explanation=impact.explanation if impact else "",
            )
            findings.append(finding)
    statuses = {item.status for item in findings}
    if first_breaking_edge:
        overall_status = "FAIL"
    elif "UNKNOWN" in statuses:
        overall_status = "UNKNOWN"
    elif "INSUFFICIENT_EVIDENCE" in statuses:
        overall_status = "INSUFFICIENT_EVIDENCE"
    elif "WARNING" in statuses:
        overall_status = "WARNING"
    else:
        overall_status = "PASS"
    return SemanticReport(
        status=overall_status,
        first_breaking_edge=first_breaking_edge,
        findings=tuple(findings),
    )


def findings_fingerprint(report: SemanticReport) -> str:
    """Return a deterministic digest useful when comparing repeated evaluations."""
    payload = [
        {"finding_id": item.finding_id, "status": item.status, "reason": item.reason}
        for item in report.findings
    ]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
