"""Explicit, conservative migrations between versioned trace schemas."""

from __future__ import annotations

from graphabi.models.traces import EdgeObservation, GraphRun, NodeExecution, TraceBundle


def upgrade_trace_bundle_v1(bundle: TraceBundle) -> TraceBundle:
    """Upgrade an unambiguous trace 0.1 bundle to causal trace 0.2.

    Trace 0.1 already rejects repeated logical node and edge identities. This
    converter therefore assigns occurrence IDs only to those singleton records.
    It refuses observations whose producer or consumer execution is absent.
    """
    if bundle.schema_version == "0.2":
        return bundle

    upgraded_runs: list[GraphRun] = []
    occurrence_by_run_and_node: dict[tuple[str, str], str] = {}
    upgraded_execution_by_id: dict[tuple[str, str], NodeExecution] = {}
    for run in bundle.runs:
        upgraded_executions: list[NodeExecution] = []
        for sequence, execution in enumerate(run.executions):
            occurrence_id = f"node:{sequence:04d}:{execution.node_id}"
            occurrence_by_run_and_node[(run.run_id, execution.node_id)] = occurrence_id
            parent_occurrence_id = (
                occurrence_by_run_and_node.get((run.run_id, execution.parent_node))
                if execution.parent_node is not None
                else None
            )
            if execution.parent_node is not None and parent_occurrence_id is None:
                raise ValueError(
                    f"trace 0.1 run {run.run_id!r}: execution {execution.node_id!r} names "
                    f"parent_node {execution.parent_node!r} that was not recorded earlier; "
                    "record a trace 0.2 causal parent explicitly"
                )
            upgraded = execution.model_copy(
                update={
                    "schema_version": "0.2",
                    "occurrence_id": occurrence_id,
                    "parent_occurrence_id": parent_occurrence_id,
                    "causal_parent_occurrence_ids": (
                        (parent_occurrence_id,) if parent_occurrence_id is not None else ()
                    ),
                    "incoming_edge_id": execution.incoming_edge,
                    "causal_sequence": sequence,
                    "branch_id": "legacy-singleton",
                    "attempt": 1,
                    "parent_node": None,
                    "incoming_edge": None,
                }
            )
            upgraded_executions.append(upgraded)
            upgraded_execution_by_id[(run.run_id, occurrence_id)] = upgraded
        upgraded_runs.append(
            run.model_copy(
                update={"schema_version": "0.2", "executions": tuple(upgraded_executions)}
            )
        )

    observations_by_run: dict[str, list[EdgeObservation]] = {}
    for observation in bundle.edge_observations:
        observations_by_run.setdefault(observation.run_id, []).append(observation)
    upgraded_observations: list[EdgeObservation] = []
    for run in bundle.runs:
        for sequence, observation in enumerate(observations_by_run.get(run.run_id, [])):
            producer_occurrence_id = occurrence_by_run_and_node.get(
                (run.run_id, observation.producer)
            )
            consumer_occurrence_id = occurrence_by_run_and_node.get(
                (run.run_id, observation.consumer)
            )
            if producer_occurrence_id is None or consumer_occurrence_id is None:
                raise ValueError(
                    f"trace 0.1 run {run.run_id!r}: edge {observation.edge_id!r} cannot be "
                    "upgraded because its producer or consumer execution is missing"
                )
            consumer = upgraded_execution_by_id[(run.run_id, consumer_occurrence_id)]
            if producer_occurrence_id not in consumer.causal_parent_occurrence_ids:
                raise ValueError(
                    f"trace 0.1 run {run.run_id!r}: edge {observation.edge_id!r} cannot be "
                    "upgraded because the producer is not the recorded consumer parent"
                )
            upgraded_observations.append(
                observation.model_copy(
                    update={
                        "schema_version": "0.2",
                        "occurrence_id": f"edge:{sequence:04d}:{observation.edge_id}",
                        "producer_occurrence_id": producer_occurrence_id,
                        "consumer_occurrence_id": consumer_occurrence_id,
                        "causal_sequence": sequence,
                        "branch_id": "legacy-singleton",
                        "attempt": 1,
                    }
                )
            )
    return TraceBundle(
        schema_version="0.2",
        exported_at=bundle.exported_at,
        runs=tuple(upgraded_runs),
        edge_observations=tuple(upgraded_observations),
    )
