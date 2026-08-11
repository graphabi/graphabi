"""Thin node wrapper that records LangGraph executions without core type leakage."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import version
from threading import RLock
from time import perf_counter
from typing import Any, TypeVar, cast

from pydantic import TypeAdapter

from graphabi.models.traces import (
    EdgeObservation,
    GraphRun,
    JsonValue,
    NodeExecution,
    SourceAccess,
    ToolActivity,
    TraceBundle,
)

State = dict[str, Any]
Node = Callable[[State], Mapping[str, Any]]
BranchResolver = str | Callable[[State], str | None]
AttemptResolver = int | Callable[[State], int]
ParentOccurrenceResolver = Callable[[State], tuple[str, ...]]
T = TypeVar("T")
_JSON_ADAPTER = TypeAdapter(dict[str, JsonValue])
_ANY_ADAPTER: TypeAdapter[Any] = TypeAdapter(Any)


def _json_mapping(value: Mapping[str, Any]) -> dict[str, JsonValue]:
    encoded = _ANY_ADAPTER.dump_python(dict(value), mode="json")
    return _JSON_ADAPTER.validate_python(encoded)


@dataclass(frozen=True)
class EdgeSpec:
    """Describes how an instrumented producer output crosses an edge."""

    edge_id: str
    producer: str
    consumer: str
    output_key: str


class LangGraphRecorder:
    """Wrap LangGraph nodes and collect causal trace 0.2 records in memory."""

    framework_name = "langgraph"

    def __init__(
        self,
        *,
        run_id: str,
        graph_id: str,
        graph_version: str,
        variant: str,
        edges: tuple[EdgeSpec, ...],
    ) -> None:
        self.run_id = run_id
        self.graph_id = graph_id
        self.graph_version = graph_version
        self.variant = variant
        self.edges = edges
        self._executions: list[NodeExecution] = []
        self._executions_by_id: dict[str, NodeExecution] = {}
        self._node_occurrence_counts: dict[str, int] = {}
        self._next_sequence = 0
        self._lock = RLock()
        self._started_at: datetime | None = None

    def occurrence_ids(
        self,
        node_id: str,
        *,
        branch_id: str | None = None,
    ) -> tuple[str, ...]:
        """Return completed occurrence IDs for explicit loop or join wiring."""
        with self._lock:
            return tuple(
                item.occurrence_id
                for item in sorted(
                    self._executions,
                    key=lambda execution: (
                        execution.causal_sequence if execution.causal_sequence is not None else -1
                    ),
                )
                if item.node_id == node_id
                and (branch_id is None or item.branch_id == branch_id)
                and item.occurrence_id is not None
            )

    def instrument(
        self,
        node_id: str,
        node: Node,
        *,
        parent_node: str | None = None,
        parent_nodes: tuple[str, ...] = (),
        incoming_edge: str | None = None,
        branch_id: BranchResolver = "main",
        attempt: AttemptResolver = 1,
        parent_occurrences: ParentOccurrenceResolver | None = None,
    ) -> Node:
        """Return a drop-in node wrapper that records inputs, outputs, and activities."""
        if parent_node is not None and parent_nodes:
            raise ValueError("set parent_node or parent_nodes, not both")
        logical_parents = parent_nodes or ((parent_node,) if parent_node is not None else ())

        def resolve_branch(state: State) -> str | None:
            return branch_id(state) if callable(branch_id) else branch_id

        def resolve_attempt(state: State) -> int:
            return attempt(state) if callable(attempt) else attempt

        def latest_parent_occurrences(child_branch: str | None) -> tuple[str, ...]:
            parents: list[str] = []
            for logical_parent in logical_parents:
                matching = [
                    item
                    for item in self._executions
                    if item.node_id == logical_parent
                    and (item.branch_id == child_branch or item.branch_id == "main")
                ]
                if not matching:
                    matching = [item for item in self._executions if item.node_id == logical_parent]
                if not matching or matching[-1].occurrence_id is None:
                    raise ValueError(
                        f"node {node_id!r} started before parent node {logical_parent!r} "
                        "had a recorded occurrence; pass an explicit parent_occurrences resolver"
                    )
                parents.append(matching[-1].occurrence_id)
            return tuple(parents)

        def wrapped(state: State) -> Mapping[str, Any]:
            started_at = datetime.now(UTC)
            started_clock = perf_counter()
            resolved_branch = resolve_branch(state)
            resolved_attempt = resolve_attempt(state)
            with self._lock:
                sequence = self._next_sequence
                self._next_sequence += 1
                occurrence_index = self._node_occurrence_counts.get(node_id, 0)
                self._node_occurrence_counts[node_id] = occurrence_index + 1
                occurrence_id = f"{node_id}:{occurrence_index:04d}"
                causal_parents = (
                    parent_occurrences(state)
                    if parent_occurrences is not None
                    else latest_parent_occurrences(resolved_branch)
                )
                unknown_parents = [
                    parent_id
                    for parent_id in causal_parents
                    if parent_id not in self._executions_by_id
                ]
                if unknown_parents:
                    raise ValueError(
                        f"node {node_id!r} parent_occurrences returned unknown IDs: "
                        + ", ".join(unknown_parents)
                    )
            error: str | None = None
            result: Mapping[str, Any] = {}
            try:
                result = node(deepcopy(state))
                return result
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                raise
            finally:
                ended_at = datetime.now(UTC)
                raw_result = dict(result)
                metadata = cast(dict[str, Any], raw_result.pop("trace_metadata", {}))
                raw_tools = cast(list[dict[str, Any]], raw_result.pop("trace_tool_calls", []))
                raw_sources = cast(list[dict[str, Any]], raw_result.pop("trace_source_access", []))
                execution = NodeExecution(
                    schema_version="0.2",
                    run_id=self.run_id,
                    graph_id=self.graph_id,
                    graph_version=self.graph_version,
                    node_id=node_id,
                    occurrence_id=occurrence_id,
                    parent_occurrence_id=causal_parents[0] if causal_parents else None,
                    causal_parent_occurrence_ids=causal_parents,
                    incoming_edge_id=incoming_edge,
                    causal_sequence=sequence,
                    branch_id=resolved_branch,
                    attempt=resolved_attempt,
                    input=_json_mapping(state),
                    output=_json_mapping(raw_result),
                    metadata=_json_mapping(metadata),
                    tool_calls=tuple(ToolActivity.model_validate(item) for item in raw_tools),
                    source_access=tuple(SourceAccess.model_validate(item) for item in raw_sources),
                    started_at=started_at,
                    ended_at=ended_at,
                    duration_ms=(perf_counter() - started_clock) * 1000,
                    status="error" if error else "success",
                    error=error,
                    framework=self.framework_name,
                    framework_version=version("langgraph"),
                )
                with self._lock:
                    self._executions.append(execution)
                    self._executions_by_id[occurrence_id] = execution

        wrapped.__name__ = node_id
        return wrapped

    def begin(self) -> None:
        """Mark the beginning of the graph invocation."""
        self._started_at = datetime.now(UTC)

    def invoke(self, graph: Any, input_data: dict[str, Any]) -> TraceBundle:
        """Invoke a compiled, instrumented graph and return its framework-neutral trace."""
        self.begin()
        output = graph.invoke(deepcopy(input_data))
        if not isinstance(output, Mapping):
            raise TypeError("an instrumented LangGraph invocation must return a mapping")
        return self.finish(input_data, output)

    def finish(self, input_data: Mapping[str, Any], output_data: Mapping[str, Any]) -> TraceBundle:
        """Build a trace bundle after the compiled graph returns."""
        ended_at = datetime.now(UTC)
        started_at = self._started_at or min(item.started_at for item in self._executions)
        graph_run = GraphRun(
            schema_version="0.2",
            run_id=self.run_id,
            graph_id=self.graph_id,
            graph_version=self.graph_version,
            variant=cast(Any, self.variant),
            started_at=started_at,
            ended_at=ended_at,
            status="success"
            if all(item.status == "success" for item in self._executions)
            else "error",
            input=_json_mapping(input_data),
            output=_json_mapping(output_data),
            executions=tuple(
                sorted(
                    self._executions,
                    key=lambda item: (
                        item.causal_sequence if item.causal_sequence is not None else -1
                    ),
                )
            ),
        )
        observations: list[EdgeObservation] = []
        for consumer in graph_run.executions:
            for edge in self.edges:
                if consumer.node_id != edge.consumer:
                    continue
                producers = [
                    self._executions_by_id[parent_id]
                    for parent_id in consumer.causal_parent_occurrence_ids
                    if self._executions_by_id[parent_id].node_id == edge.producer
                ]
                for producer in producers:
                    payload = producer.output.get(edge.output_key)
                    if not isinstance(payload, dict):
                        raise ValueError(
                            f"producer occurrence {producer.occurrence_id!r} did not emit mapping "
                            f"key {edge.output_key!r}"
                        )
                    edge_sequence = len(observations)
                    observations.append(
                        EdgeObservation(
                            schema_version="0.2",
                            run_id=self.run_id,
                            graph_id=self.graph_id,
                            graph_version=self.graph_version,
                            edge_id=edge.edge_id,
                            producer=edge.producer,
                            consumer=edge.consumer,
                            occurrence_id=f"{edge.edge_id}:{edge_sequence:04d}",
                            producer_occurrence_id=producer.occurrence_id,
                            consumer_occurrence_id=consumer.occurrence_id,
                            causal_sequence=edge_sequence,
                            branch_id=producer.branch_id,
                            attempt=consumer.attempt,
                            input=consumer.input,
                            output=payload,
                            metadata=producer.metadata,
                            tool_calls=producer.tool_calls,
                            source_access=producer.source_access,
                            observed_at=producer.ended_at,
                        )
                    )
        return TraceBundle(
            schema_version="0.2",
            runs=(graph_run,),
            edge_observations=tuple(observations),
        )
