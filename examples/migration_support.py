"""Small helpers shared by the migration examples."""

from __future__ import annotations

from datetime import datetime

from graphabi.models import EdgeObservation, GraphRun, TraceBundle
from graphabi.models.traces import JsonValue


def one_edge_bundle(
    *,
    run_id: str,
    graph_id: str,
    graph_version: str,
    variant: str,
    edge_id: str,
    producer: str,
    consumer: str,
    output: dict[str, JsonValue],
    metadata: dict[str, JsonValue],
    observed_at: datetime,
) -> TraceBundle:
    """Build one framework-neutral observation without pretending to run a framework."""
    run = GraphRun(
        run_id=run_id,
        graph_id=graph_id,
        graph_version=graph_version,
        variant=variant,
        started_at=observed_at,
        ended_at=observed_at,
        status="success",
        input={},
        output=output,
        executions=(),
    )
    observation = EdgeObservation(
        run_id=run_id,
        graph_id=graph_id,
        graph_version=graph_version,
        edge_id=edge_id,
        producer=producer,
        consumer=consumer,
        input={},
        output=output,
        metadata=metadata,
        observed_at=observed_at,
    )
    return TraceBundle(runs=(run,), edge_observations=(observation,))
