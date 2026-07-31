"""Framework-independent GraphABI trace schema v0.1."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

type JsonValue = bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None


class TraceModel(BaseModel):
    """Base model for immutable, strictly validated trace records."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class RedactedValue(TraceModel):
    """Marker replacing a trace value intentionally omitted from a report."""

    redacted: Literal[True] = True
    reason: str = "unrelated to this finding"


class ToolActivity(TraceModel):
    """One tool invocation observed while a node executed."""

    tool_name: str
    call_id: str
    input: dict[str, JsonValue] = Field(default_factory=dict)
    output: JsonValue = None
    started_at: datetime
    ended_at: datetime
    status: Literal["success", "error"]
    error: str | None = None


class SourceAccess(TraceModel):
    """A concrete attempt to access a source during a node execution."""

    source_id: str
    uri: str
    attempted_at: datetime
    opened: bool
    supports_claim: bool | None = None
    content_sha256: str | None = None
    error: str | None = None


class NodeExecution(TraceModel):
    """A single framework-neutral node execution."""

    schema_version: Literal["0.1"] = "0.1"
    run_id: str
    graph_id: str
    graph_version: str
    node_id: str
    parent_node: str | None = None
    incoming_edge: str | None = None
    input: dict[str, JsonValue]
    output: dict[str, JsonValue]
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    tool_calls: tuple[ToolActivity, ...] = ()
    source_access: tuple[SourceAccess, ...] = ()
    started_at: datetime
    ended_at: datetime
    duration_ms: float = Field(ge=0)
    status: Literal["success", "error"]
    error: str | None = None
    framework: str
    framework_version: str


class GraphRun(TraceModel):
    """One graph invocation and all node executions it produced."""

    schema_version: Literal["0.1"] = "0.1"
    run_id: str
    graph_id: str
    graph_version: str
    variant: Literal["baseline", "candidate", "other"] = "other"
    started_at: datetime
    ended_at: datetime
    status: Literal["success", "error"]
    input: dict[str, JsonValue]
    output: dict[str, JsonValue]
    executions: tuple[NodeExecution, ...]

    @model_validator(mode="after")
    def execution_runs_match(self) -> GraphRun:
        mismatches = [item.node_id for item in self.executions if item.run_id != self.run_id]
        if mismatches:
            raise ValueError(f"executions have a different run_id: {', '.join(mismatches)}")
        return self


class EdgeObservation(TraceModel):
    """Producer output as it crosses a graph edge into a consumer."""

    schema_version: Literal["0.1"] = "0.1"
    run_id: str
    graph_id: str
    graph_version: str
    edge_id: str
    producer: str
    consumer: str
    input: dict[str, JsonValue]
    output: dict[str, JsonValue]
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    tool_calls: tuple[ToolActivity, ...] = ()
    source_access: tuple[SourceAccess, ...] = ()
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TraceBundle(TraceModel):
    """Portable JSON representation of runs and derived edge observations."""

    schema_version: Literal["0.1"] = "0.1"
    exported_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    runs: tuple[GraphRun, ...]
    edge_observations: tuple[EdgeObservation, ...]
