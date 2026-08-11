"""Framework-independent GraphABI trace schemas v0.1 and v0.2."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    model_validator,
)

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

    schema_version: Literal["0.1", "0.2"] = "0.1"
    run_id: str
    graph_id: str
    graph_version: str
    node_id: str
    occurrence_id: str | None = Field(default=None, min_length=1)
    parent_occurrence_id: str | None = Field(default=None, min_length=1)
    causal_parent_occurrence_ids: tuple[str, ...] = ()
    incoming_edge_id: str | None = Field(default=None, min_length=1)
    causal_sequence: StrictInt | None = Field(default=None, ge=0)
    branch_id: str | None = Field(default=None, min_length=1)
    attempt: StrictInt | None = Field(default=None, ge=1)
    # Logical ancestry retained for strict trace 0.1 readers.
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

    @model_validator(mode="after")
    def occurrence_identity_matches_version(self) -> NodeExecution:
        occurrence_values = (
            self.occurrence_id,
            self.parent_occurrence_id,
            self.incoming_edge_id,
            self.causal_sequence,
            self.branch_id,
            self.attempt,
        )
        if self.schema_version == "0.1":
            if any(value is not None for value in occurrence_values) or (
                self.causal_parent_occurrence_ids
            ):
                raise ValueError("occurrence identity fields require trace schema 0.2")
            return self
        required = {
            "occurrence_id": self.occurrence_id,
            "causal_sequence": self.causal_sequence,
            "attempt": self.attempt,
        }
        missing = [name for name, value in required.items() if value is None]
        if missing:
            raise ValueError("trace schema 0.2 execution is missing " + ", ".join(missing))
        if len(set(self.causal_parent_occurrence_ids)) != len(self.causal_parent_occurrence_ids):
            raise ValueError("causal parent occurrence IDs must be unique")
        if self.occurrence_id in self.causal_parent_occurrence_ids:
            raise ValueError("an execution cannot be its own causal parent")
        if self.parent_occurrence_id is not None and (
            self.parent_occurrence_id not in self.causal_parent_occurrence_ids
        ):
            raise ValueError("parent_occurrence_id must be one of causal_parent_occurrence_ids")
        if self.parent_node is not None or self.incoming_edge is not None:
            raise ValueError(
                "trace schema 0.2 uses parent_occurrence_id and incoming_edge_id instead of "
                "trace 0.1 logical ancestry fields"
            )
        return self


class GraphRun(TraceModel):
    """One graph invocation and all node executions it produced."""

    schema_version: Literal["0.1", "0.2"] = "0.1"
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
        schema_mismatches = [
            item.node_id for item in self.executions if item.schema_version != self.schema_version
        ]
        if schema_mismatches:
            raise ValueError(
                "executions have a different trace schema version: " + ", ".join(schema_mismatches)
            )
        if self.schema_version == "0.1":
            node_ids = [item.node_id for item in self.executions]
            if len(set(node_ids)) != len(node_ids):
                raise ValueError(
                    "node execution IDs must be unique within a run for trace schema 0.1"
                )
            return self
        by_occurrence = {
            item.occurrence_id: item for item in self.executions if item.occurrence_id is not None
        }
        if len(by_occurrence) != len(self.executions):
            raise ValueError("execution occurrence IDs must be unique within a trace 0.2 run")
        sequences = [item.causal_sequence for item in self.executions]
        if len(set(sequences)) != len(sequences):
            raise ValueError("execution causal_sequence values must be unique within a run")
        for execution in self.executions:
            for parent_id in execution.causal_parent_occurrence_ids:
                parent = by_occurrence.get(parent_id)
                if parent is None:
                    raise ValueError(
                        f"execution {execution.occurrence_id!r} references missing causal parent "
                        f"{parent_id!r}"
                    )
                if parent.causal_sequence is None or execution.causal_sequence is None:
                    raise ValueError("trace 0.2 causal sequence is missing")
                if parent.causal_sequence >= execution.causal_sequence:
                    raise ValueError(
                        f"causal parent {parent_id!r} must precede execution "
                        f"{execution.occurrence_id!r}"
                    )
        return self


class EdgeObservation(TraceModel):
    """Producer output as it crosses a graph edge into a consumer."""

    schema_version: Literal["0.1", "0.2"] = "0.1"
    run_id: str
    graph_id: str
    graph_version: str
    edge_id: str
    producer: str
    consumer: str
    occurrence_id: str | None = Field(default=None, min_length=1)
    producer_occurrence_id: str | None = Field(default=None, min_length=1)
    consumer_occurrence_id: str | None = Field(default=None, min_length=1)
    causal_sequence: StrictInt | None = Field(default=None, ge=0)
    branch_id: str | None = Field(default=None, min_length=1)
    attempt: StrictInt | None = Field(default=None, ge=1)
    input: dict[str, JsonValue]
    output: dict[str, JsonValue]
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    tool_calls: tuple[ToolActivity, ...] = ()
    source_access: tuple[SourceAccess, ...] = ()
    observed_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def occurrence_identity_matches_version(self) -> EdgeObservation:
        occurrence_values = (
            self.occurrence_id,
            self.producer_occurrence_id,
            self.consumer_occurrence_id,
            self.causal_sequence,
            self.branch_id,
            self.attempt,
        )
        if self.schema_version == "0.1":
            if any(value is not None for value in occurrence_values):
                raise ValueError("occurrence identity fields require trace schema 0.2")
            return self
        required = {
            "occurrence_id": self.occurrence_id,
            "producer_occurrence_id": self.producer_occurrence_id,
            "consumer_occurrence_id": self.consumer_occurrence_id,
            "causal_sequence": self.causal_sequence,
            "attempt": self.attempt,
        }
        missing = [name for name, value in required.items() if value is None]
        if missing:
            raise ValueError("trace schema 0.2 edge observation is missing " + ", ".join(missing))
        return self


class TraceBundle(TraceModel):
    """Portable JSON representation of runs and derived edge observations."""

    schema_version: Literal["0.1", "0.2"] = "0.1"
    exported_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))
    runs: tuple[GraphRun, ...]
    edge_observations: tuple[EdgeObservation, ...]

    @model_validator(mode="after")
    def identities_are_unambiguous(self) -> TraceBundle:
        run_ids = [run.run_id for run in self.runs]
        if len(set(run_ids)) != len(run_ids):
            raise ValueError("run IDs must be unique within a trace bundle")
        schema_mismatches = [
            run.run_id for run in self.runs if run.schema_version != self.schema_version
        ] + [
            observation.edge_id
            for observation in self.edge_observations
            if observation.schema_version != self.schema_version
        ]
        if schema_mismatches:
            raise ValueError(
                "trace records have a different schema version: " + ", ".join(schema_mismatches)
            )
        observation_ids = (
            [(observation.run_id, observation.edge_id) for observation in self.edge_observations]
            if self.schema_version == "0.1"
            else [
                (observation.run_id, observation.occurrence_id)
                for observation in self.edge_observations
            ]
        )
        if len(set(observation_ids)) != len(observation_ids):
            identity = "edge_id for trace schema 0.1"
            if self.schema_version == "0.2":
                identity = "occurrence_id for trace schema 0.2"
            raise ValueError(f"edge observations must be unique by run_id and {identity}")
        runs_by_id = {run.run_id: run for run in self.runs}
        edge_sequences_by_run: dict[str, set[int]] = {}
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
            if self.schema_version == "0.2":
                executions = {execution.occurrence_id: execution for execution in run.executions}
                producer = executions.get(observation.producer_occurrence_id)
                consumer = executions.get(observation.consumer_occurrence_id)
                if producer is None or consumer is None:
                    raise ValueError(
                        f"edge occurrence {observation.occurrence_id!r} references missing "
                        "producer or consumer occurrence"
                    )
                if producer.node_id != observation.producer:
                    raise ValueError(
                        f"edge occurrence {observation.occurrence_id!r} producer does not match "
                        "its execution"
                    )
                if consumer.node_id != observation.consumer:
                    raise ValueError(
                        f"edge occurrence {observation.occurrence_id!r} consumer does not match "
                        "its execution"
                    )
                if observation.producer_occurrence_id not in (
                    consumer.causal_parent_occurrence_ids
                ):
                    raise ValueError(
                        f"edge occurrence {observation.occurrence_id!r} producer is not a causal "
                        "parent of its consumer"
                    )
                if observation.attempt != consumer.attempt:
                    raise ValueError(
                        f"edge occurrence {observation.occurrence_id!r} attempt does not match "
                        "its consumer execution"
                    )
                if observation.causal_sequence is None:
                    raise ValueError("trace 0.2 edge causal sequence is missing")
                seen_sequences = edge_sequences_by_run.setdefault(observation.run_id, set())
                if observation.causal_sequence in seen_sequences:
                    raise ValueError(
                        f"edge causal_sequence {observation.causal_sequence} is duplicated in "
                        f"run {observation.run_id!r}"
                    )
                seen_sequences.add(observation.causal_sequence)
        return self
