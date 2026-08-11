"""Downstream reachability and repair analysis for a breaking edge."""

from __future__ import annotations

import networkx as nx
from pydantic import BaseModel, ConfigDict

from graphabi.contracts.models import Contract
from graphabi.models.traces import TraceBundle


class ImpactResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    direct_consumer: str
    downstream_nodes: tuple[str, ...]
    terminal_paths: tuple[tuple[str, ...], ...]
    side_effecting_paths: tuple[tuple[str, ...], ...]
    shortest_affected_path: tuple[str, ...]
    unaffected_branches_exist: bool
    nearest_repair_location: str
    explanation: str


class OccurrenceImpactResult(BaseModel):
    """Observed downstream causal impact within one trace 0.2 run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    downstream_occurrences: tuple[str, ...]
    downstream_nodes: tuple[str, ...]
    terminal_occurrence_paths: tuple[tuple[str, ...], ...]
    side_effecting_occurrence_paths: tuple[tuple[str, ...], ...]
    shortest_occurrence_path: tuple[str, ...]


def analyze_impact(contract: Contract, edge_id: str) -> ImpactResult:
    """Calculate deterministic downstream impact for one contract edge."""
    edge = contract.edge(edge_id)
    graph = nx.DiGraph()
    graph.add_nodes_from(node.id for node in contract.nodes)
    graph.add_edges_from((item.producer, item.consumer) for item in contract.topology_edges)
    reachable = nx.descendants(graph, edge.consumer)
    affected = {edge.consumer, *reachable}
    try:
        order = list(nx.topological_sort(graph))
    except nx.NetworkXUnfeasible:
        order = sorted(graph.nodes)
    downstream = tuple(node for node in order if node in affected)
    terminals = {node.id for node in contract.nodes if node.terminal}
    side_effects = {node.id for node in contract.nodes if node.side_effecting}

    def paths_to(targets: set[str]) -> tuple[tuple[str, ...], ...]:
        paths: list[tuple[str, ...]] = []
        for target in sorted(targets & affected):
            paths.extend(tuple(path) for path in nx.all_simple_paths(graph, edge.consumer, target))
            if target == edge.consumer:
                paths.append((target,))
        return tuple(sorted(set(paths), key=lambda item: (len(item), item)))

    terminal_paths = paths_to(terminals)
    side_effecting_paths = paths_to(side_effects)
    candidates = terminal_paths or side_effecting_paths or ((edge.consumer,),)
    shortest = min(candidates, key=lambda item: (len(item), item))
    ancestors = nx.ancestors(graph, edge.consumer)
    unaffected = any(
        neighbor not in affected and neighbor not in ancestors
        for ancestor in ancestors
        for neighbor in graph.successors(ancestor)
    )
    repair = f"before {edge.consumer} consumes output from {edge.producer}"
    transitive = [node for node in downstream if node != edge.consumer]
    explanation = (
        f"{edge.consumer} is directly affected because it consumes the changed meaning at "
        f"{edge.producer} -> {edge.consumer}."
    )
    if transitive:
        explanation += f" {', '.join(transitive)} are transitively affected by reachability."
    if terminal_paths:
        explanation += f" The affected path reaches terminal node {terminal_paths[0][-1]}."
    explanation += f" The smallest repair point is {repair}."
    return ImpactResult(
        direct_consumer=edge.consumer,
        downstream_nodes=downstream,
        terminal_paths=terminal_paths,
        side_effecting_paths=side_effecting_paths,
        shortest_affected_path=shortest,
        unaffected_branches_exist=unaffected,
        nearest_repair_location=repair,
        explanation=explanation,
    )


def analyze_occurrence_impact(
    contract: Contract,
    candidate: TraceBundle,
    consumer_occurrence_id: str,
) -> OccurrenceImpactResult:
    """Follow observed causal occurrences from one breaking consumer execution."""
    if candidate.schema_version != "0.2" or len(candidate.runs) != 1:
        raise ValueError("occurrence impact requires one trace 0.2 candidate run")
    executions = {
        item.occurrence_id: item
        for item in candidate.runs[0].executions
        if item.occurrence_id is not None
    }
    if consumer_occurrence_id not in executions:
        raise ValueError(
            f"consumer occurrence {consumer_occurrence_id!r} is absent from candidate run"
        )
    graph = nx.DiGraph()
    graph.add_nodes_from(executions)
    for execution in executions.values():
        graph.add_edges_from(
            (parent_id, execution.occurrence_id)
            for parent_id in execution.causal_parent_occurrence_ids
        )
    affected = {consumer_occurrence_id, *nx.descendants(graph, consumer_occurrence_id)}
    ordered = tuple(
        occurrence_id
        for occurrence_id, _ in sorted(
            executions.items(),
            key=lambda item: (
                item[1].causal_sequence if item[1].causal_sequence is not None else -1,
                item[0],
            ),
        )
        if occurrence_id in affected
    )
    nodes = tuple(dict.fromkeys(executions[item].node_id for item in ordered))
    terminal_nodes = {node.id for node in contract.nodes if node.terminal}
    side_effecting_nodes = {node.id for node in contract.nodes if node.side_effecting}

    def paths_to(node_ids: set[str]) -> tuple[tuple[str, ...], ...]:
        paths = [
            tuple(path)
            for target_id in ordered
            if executions[target_id].node_id in node_ids
            for path in nx.all_simple_paths(graph, consumer_occurrence_id, target_id)
        ]
        if executions[consumer_occurrence_id].node_id in node_ids:
            paths.append((consumer_occurrence_id,))
        return tuple(sorted(set(paths), key=lambda path: (len(path), path)))

    terminal_paths = paths_to(terminal_nodes)
    side_effecting_paths = paths_to(side_effecting_nodes)
    candidates = terminal_paths or side_effecting_paths or ((consumer_occurrence_id,),)
    return OccurrenceImpactResult(
        downstream_occurrences=ordered,
        downstream_nodes=nodes,
        terminal_occurrence_paths=terminal_paths,
        side_effecting_occurrence_paths=side_effecting_paths,
        shortest_occurrence_path=min(candidates, key=lambda path: (len(path), path)),
    )
