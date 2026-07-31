"""Thin node wrapper that records LangGraph executions without core type leakage."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import version
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
    """Wrap LangGraph nodes and collect v0.1 framework-neutral traces in memory."""

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
        self._started_at: datetime | None = None

    def instrument(
        self,
        node_id: str,
        node: Node,
        *,
        parent_node: str | None = None,
        incoming_edge: str | None = None,
    ) -> Node:
        """Return a drop-in node wrapper that records inputs, outputs, and activities."""

        def wrapped(state: State) -> Mapping[str, Any]:
            started_at = datetime.now(UTC)
            started_clock = perf_counter()
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
                self._executions.append(
                    NodeExecution(
                        run_id=self.run_id,
                        graph_id=self.graph_id,
                        graph_version=self.graph_version,
                        node_id=node_id,
                        parent_node=parent_node,
                        incoming_edge=incoming_edge,
                        input=_json_mapping(state),
                        output=_json_mapping(raw_result),
                        metadata=_json_mapping(metadata),
                        tool_calls=tuple(ToolActivity.model_validate(item) for item in raw_tools),
                        source_access=tuple(
                            SourceAccess.model_validate(item) for item in raw_sources
                        ),
                        started_at=started_at,
                        ended_at=ended_at,
                        duration_ms=(perf_counter() - started_clock) * 1000,
                        status="error" if error else "success",
                        error=error,
                        framework=self.framework_name,
                        framework_version=version("langgraph"),
                    )
                )

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
            executions=tuple(self._executions),
        )
        by_node = {item.node_id: item for item in self._executions}
        observations: list[EdgeObservation] = []
        for edge in self.edges:
            producer = by_node[edge.producer]
            consumer = by_node[edge.consumer]
            payload = producer.output.get(edge.output_key)
            if not isinstance(payload, dict):
                raise ValueError(
                    f"producer {edge.producer!r} did not emit mapping key {edge.output_key!r}"
                )
            observations.append(
                EdgeObservation(
                    run_id=self.run_id,
                    graph_id=self.graph_id,
                    graph_version=self.graph_version,
                    edge_id=edge.edge_id,
                    producer=edge.producer,
                    consumer=edge.consumer,
                    input=consumer.input,
                    output=payload,
                    metadata=producer.metadata,
                    tool_calls=producer.tool_calls,
                    source_access=producer.source_access,
                    observed_at=producer.ended_at,
                )
            )
        return TraceBundle(runs=(graph_run,), edge_observations=tuple(observations))
