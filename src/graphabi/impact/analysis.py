"""Downstream reachability and repair analysis for a breaking edge."""

from __future__ import annotations

import networkx as nx
from pydantic import BaseModel, ConfigDict

from graphabi.contracts.models import Contract


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


def analyze_impact(contract: Contract, edge_id: str) -> ImpactResult:
    """Calculate deterministic downstream impact for one contract edge."""
    edge = contract.edge(edge_id)
    graph = nx.DiGraph()
    graph.add_nodes_from(node.id for node in contract.nodes)
    graph.add_edges_from((item.producer, item.consumer) for item in contract.edges)
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
