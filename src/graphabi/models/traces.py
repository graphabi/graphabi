"""Framework-independent GraphABI trace schema v0.1."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictBool, model_validator

type JsonValue = bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None


class TraceModel(BaseModel):
    """Base model for immutable, strictly validated trace records."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        allow_inf_nan=False,
        hide_input_in_errors=True,
    )


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
    started_at: AwareDatetime
    ended_at: AwareDatetime
    status: Literal["success", "error"]
    error: str | None = None


class SourceAccess(TraceModel):
    """A concrete attempt to access a source during a node execution."""

    source_id: str
    uri: str
    attempted_at: AwareDatetime
    opened: StrictBool
    supports_claim: StrictBool | None = None
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
    started_at: AwareDatetime
    ended_at: AwareDatetime
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
    started_at: AwareDatetime
    ended_at: AwareDatetime
    status: Literal["success", "error"]
    input: dict[str, JsonValue]
    output: dict[str, JsonValue]
    executions: tuple[NodeExecution, ...]

    @model_validator(mode="after")
    def execution_runs_match(self) -> GraphRun:
        mismatches = [item.node_id for item in self.executions if item.run_id != self.run_id]
        if mismatches:
            raise ValueError(f"executions have a different run_id: {', '.join(mismatches)}")
        identity_mismatches = [
            item.node_id
            for item in self.executions
            if item.graph_id != self.graph_id or item.graph_version != self.graph_version
        ]
        if identity_mismatches:
            raise ValueError(
                "executions have a different graph identity: " + ", ".join(identity_mismatches)
            )
        node_ids = [item.node_id for item in self.executions]
        if len(set(node_ids)) != len(node_ids):
            raise ValueError("node execution IDs must be unique within a run for trace schema 0.1")
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
    observed_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))


class TraceBundle(TraceModel):
    """Portable JSON representation of runs and derived edge observations."""

    schema_version: Literal["0.1"] = "0.1"
    exported_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))
    runs: tuple[GraphRun, ...]
    edge_observations: tuple[EdgeObservation, ...]

    @model_validator(mode="after")
    def identities_are_unambiguous(self) -> TraceBundle:
        run_ids = [run.run_id for run in self.runs]
        if len(set(run_ids)) != len(run_ids):
            raise ValueError("run IDs must be unique within a trace bundle")
        observation_ids = [
            (observation.run_id, observation.edge_id) for observation in self.edge_observations
        ]
        if len(set(observation_ids)) != len(observation_ids):
            raise ValueError(
                "edge observations must be unique by run_id and edge_id for trace schema 0.1"
            )
        runs_by_id = {run.run_id: run for run in self.runs}
        for observation in self.edge_observations:
            run = runs_by_id.get(observation.run_id)
            if run is None:
                raise ValueError(
                    f"edge observation {observation.edge_id!r} references unknown run "
                    f"{observation.run_id!r}"
                )
            if (
                observation.graph_id != run.graph_id
                or observation.graph_version != run.graph_version
            ):
                raise ValueError(
                    f"edge observation {observation.edge_id!r} has a different graph identity "
                    f"from run {run.run_id!r}"
                )
        return self
