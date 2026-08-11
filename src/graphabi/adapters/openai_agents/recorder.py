"""OpenAI Agents SDK lifecycle instrumentation behind the adapter boundary."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib.metadata import version
from time import perf_counter
from typing import Any, cast

from agents.agent import Agent
from agents.items import ModelResponse, TResponseInputItem
from agents.lifecycle import RunHooks
from agents.run import Runner
from agents.run_config import RunConfig
from agents.run_context import AgentHookContext, RunContextWrapper
from agents.tool import Tool
from agents.tool_context import ToolContext
from pydantic import TypeAdapter

from graphabi.models.traces import (
    EdgeObservation,
    GraphRun,
    JsonValue,
    NodeExecution,
    ToolActivity,
    TraceBundle,
)

type HandoffPayloadResolver = Callable[
    [RunContextWrapper[Any], Agent[Any], Agent[Any]], Mapping[str, Any]
]

_ANY_ADAPTER: TypeAdapter[Any] = TypeAdapter(Any)
_JSON_VALUE = TypeAdapter(JsonValue)
_JSON_MAPPING = TypeAdapter(dict[str, JsonValue])


def _json_value(value: Any) -> JsonValue:
    encoded = _ANY_ADAPTER.dump_python(value, mode="json")
    return _JSON_VALUE.validate_python(encoded)


def _json_mapping(value: Mapping[str, Any]) -> dict[str, JsonValue]:
    return _JSON_MAPPING.validate_python(_json_value(dict(value)))


def _output_mapping(value: Any) -> dict[str, JsonValue]:
    encoded = _json_value(value)
    if isinstance(encoded, dict):
        return encoded
    return {"value": encoded}


@dataclass(frozen=True)
class HandoffEdgeSpec:
    """An explicit GraphABI edge and its observed handoff-payload resolver."""

    edge_id: str
    producer: str
    consumer: str
    payload_resolver: HandoffPayloadResolver

    def __post_init__(self) -> None:
        for name, value in (
            ("edge_id", self.edge_id),
            ("producer", self.producer),
            ("consumer", self.consumer),
        ):
            if not value:
                raise ValueError(f"OpenAI Agents handoff {name} must not be empty")


@dataclass
class _StartedTool:
    tool_name: str
    call_id: str
    input: dict[str, JsonValue]
    started_at: datetime


@dataclass
class _Occurrence:
    agent: Agent[Any]
    occurrence_id: str
    parent_occurrence_id: str | None
    incoming_edge_id: str | None
    causal_sequence: int
    attempt: int
    input: dict[str, JsonValue]
    started_at: datetime
    started_clock: float
    tool_calls: list[ToolActivity] = field(default_factory=list)
    pending_tools: dict[str, _StartedTool] = field(default_factory=dict)
    model_outputs: list[JsonValue] = field(default_factory=list)
    model_response_ids: list[str] = field(default_factory=list)
    llm_calls: int = 0


@dataclass
class _Handoff:
    source_occurrence_id: str
    target_agent_key: int
    target_agent_name: str
    observed_at: datetime
    spec: HandoffEdgeSpec | None
    payload: dict[str, JsonValue] | None
    consumer_occurrence_id: str | None = None


class _GraphABIRunHooks(RunHooks):
    def __init__(
        self,
        *,
        run_id: str,
        graph_id: str,
        graph_version: str,
        variant: str,
        graph_input: dict[str, JsonValue],
        edges: tuple[HandoffEdgeSpec, ...],
    ) -> None:
        self.run_id = run_id
        self.graph_id = graph_id
        self.graph_version = graph_version
        self.variant = variant
        self.graph_input = graph_input
        self.edge_specs = {(edge.producer, edge.consumer): edge for edge in edges}
        self.executions: list[NodeExecution] = []
        self._execution_counts: dict[str, int] = {}
        self._active: _Occurrence | None = None
        self._pending_handoff: _Handoff | None = None
        self._handoffs: list[_Handoff] = []
        self._started_at = datetime.now(UTC)
        self._sdk_version = version("openai-agents")

    def _require_active(self, agent: Agent[Any], event: str) -> _Occurrence:
        active = self._active
        if active is None or active.agent is not agent:
            raise RuntimeError(
                f"OpenAI Agents emitted {event} for {agent.name!r} without a matching active "
                "agent occurrence"
            )
        return active

    async def on_agent_start(self, context: AgentHookContext[Any], agent: Agent[Any]) -> None:
        if self._active is not None:
            raise RuntimeError(
                f"OpenAI Agents started {agent.name!r} while {self._active.agent.name!r} "
                "was still active"
            )
        pending = self._pending_handoff
        parent_occurrence_id: str | None = None
        incoming_edge_id: str | None = None
        if pending is not None:
            if pending.target_agent_key != id(agent):
                raise RuntimeError(
                    f"OpenAI Agents handed off to {pending.target_agent_name!r} but started "
                    f"{agent.name!r}"
                )
            parent_occurrence_id = pending.source_occurrence_id
            incoming_edge_id = pending.spec.edge_id if pending.spec is not None else None
        count = self._execution_counts.get(agent.name, 0) + 1
        self._execution_counts[agent.name] = count
        occurrence = _Occurrence(
            agent=agent,
            occurrence_id=f"openai-agent:{agent.name}:{count:04d}",
            parent_occurrence_id=parent_occurrence_id,
            incoming_edge_id=incoming_edge_id,
            causal_sequence=len(self.executions),
            attempt=count,
            input={"items": cast(JsonValue, _json_value(context.turn_input))},
            started_at=datetime.now(UTC),
            started_clock=perf_counter(),
        )
        self._active = occurrence
        if pending is not None:
            pending.consumer_occurrence_id = occurrence.occurrence_id
            self._pending_handoff = None

    async def on_llm_start(
        self,
        context: RunContextWrapper[Any],
        agent: Agent[Any],
        system_prompt: str | None,
        input_items: list[TResponseInputItem],
    ) -> None:
        del context, system_prompt, input_items
        self._require_active(agent, "on_llm_start").llm_calls += 1

    async def on_llm_end(
        self,
        context: RunContextWrapper[Any],
        agent: Agent[Any],
        response: ModelResponse,
    ) -> None:
        del context
        active = self._require_active(agent, "on_llm_end")
        active.model_outputs.append(_json_value(response.output))
        if response.response_id:
            active.model_response_ids.append(response.response_id)

    async def on_tool_start(
        self, context: RunContextWrapper[Any], agent: Agent[Any], tool: Tool
    ) -> None:
        active = self._require_active(agent, "on_tool_start")
        tool_name = str(getattr(tool, "name", type(tool).__name__))
        call_id = (
            f"{active.occurrence_id}:tool:{len(active.pending_tools) + len(active.tool_calls)}"
        )
        arguments: object = {}
        if isinstance(context, ToolContext):
            call_id = context.tool_call_id
            tool_name = context.qualified_tool_name
            try:
                arguments = json.loads(context.tool_arguments)
            except json.JSONDecodeError:
                arguments = {"raw": context.tool_arguments}
        input_data = _output_mapping(arguments)
        if call_id in active.pending_tools:
            raise RuntimeError(f"OpenAI Agents repeated active tool call ID {call_id!r}")
        active.pending_tools[call_id] = _StartedTool(
            tool_name=tool_name,
            call_id=call_id,
            input=input_data,
            started_at=datetime.now(UTC),
        )

    async def on_tool_end(
        self,
        context: RunContextWrapper[Any],
        agent: Agent[Any],
        tool: Tool,
        result: object,
    ) -> None:
        active = self._require_active(agent, "on_tool_end")
        call_id = context.tool_call_id if isinstance(context, ToolContext) else None
        if call_id is None:
            tool_name = str(getattr(tool, "name", type(tool).__name__))
            matching = [
                item.call_id
                for item in active.pending_tools.values()
                if item.tool_name == tool_name
            ]
            if len(matching) != 1:
                raise RuntimeError(
                    f"OpenAI Agents ended tool {tool_name!r} without one identifiable start"
                )
            call_id = matching[0]
        started = active.pending_tools.pop(call_id, None)
        if started is None:
            raise RuntimeError(f"OpenAI Agents ended unknown tool call ID {call_id!r}")
        ended_at = datetime.now(UTC)
        active.tool_calls.append(
            ToolActivity(
                tool_name=started.tool_name,
                call_id=started.call_id,
                input=started.input,
                output=_json_value(result),
                started_at=started.started_at,
                ended_at=ended_at,
                status="success",
            )
        )

    async def on_handoff(
        self,
        context: RunContextWrapper[Any],
        from_agent: Agent[Any],
        to_agent: Agent[Any],
    ) -> None:
        active = self._require_active(from_agent, "on_handoff")
        spec = self.edge_specs.get((from_agent.name, to_agent.name))
        payload = (
            _json_mapping(spec.payload_resolver(context, from_agent, to_agent))
            if spec is not None
            else None
        )
        observed_at = datetime.now(UTC)
        self._finish_active(
            output={"model_outputs": active.model_outputs},
            ended_at=observed_at,
            handoff_to=to_agent.name,
        )
        handoff = _Handoff(
            source_occurrence_id=active.occurrence_id,
            target_agent_key=id(to_agent),
            target_agent_name=to_agent.name,
            observed_at=observed_at,
            spec=spec,
            payload=payload,
        )
        self._handoffs.append(handoff)
        self._pending_handoff = handoff

    async def on_agent_end(
        self,
        context: AgentHookContext[Any],
        agent: Agent[Any],
        output: Any,
    ) -> None:
        del context
        self._require_active(agent, "on_agent_end")
        self._finish_active(output=_output_mapping(output), ended_at=datetime.now(UTC))

    def _finish_active(
        self,
        *,
        output: dict[str, JsonValue],
        ended_at: datetime,
        handoff_to: str | None = None,
    ) -> None:
        active = self._active
        if active is None:
            raise RuntimeError("OpenAI Agents has no active occurrence to finish")
        if active.pending_tools:
            unresolved = ", ".join(sorted(active.pending_tools))
            raise RuntimeError(f"OpenAI Agents occurrence has unfinished tool calls: {unresolved}")
        metadata = {
            "openai_agents": {
                "agent_name": active.agent.name,
                "llm_calls": active.llm_calls,
                "model_response_ids": active.model_response_ids,
                "handoff_to": handoff_to,
                "sdk_tracing_disabled": True,
            }
        }
        parent_ids = (
            (active.parent_occurrence_id,) if active.parent_occurrence_id is not None else ()
        )
        self.executions.append(
            NodeExecution(
                schema_version="0.2",
                run_id=self.run_id,
                graph_id=self.graph_id,
                graph_version=self.graph_version,
                node_id=active.agent.name,
                occurrence_id=active.occurrence_id,
                parent_occurrence_id=active.parent_occurrence_id,
                causal_parent_occurrence_ids=parent_ids,
                incoming_edge_id=active.incoming_edge_id,
                causal_sequence=active.causal_sequence,
                branch_id="main",
                attempt=active.attempt,
                input=active.input,
                output=output,
                metadata=_json_mapping(metadata),
                tool_calls=tuple(active.tool_calls),
                started_at=active.started_at,
                ended_at=ended_at,
                duration_ms=(perf_counter() - active.started_clock) * 1000,
                status="success",
                framework="openai-agents",
                framework_version=self._sdk_version,
            )
        )
        self._active = None

    def finish(self, final_output: Any) -> TraceBundle:
        if self._active is not None:
            raise RuntimeError(
                f"OpenAI Agents run returned while {self._active.agent.name!r} was active"
            )
        if self._pending_handoff is not None:
            raise RuntimeError(
                f"OpenAI Agents run returned before handoff target "
                f"{self._pending_handoff.target_agent_name!r} started"
            )
        ended_at = datetime.now(UTC)
        ordered_executions = tuple(
            sorted(self.executions, key=lambda execution: cast(int, execution.causal_sequence))
        )
        graph_run = GraphRun(
            schema_version="0.2",
            run_id=self.run_id,
            graph_id=self.graph_id,
            graph_version=self.graph_version,
            variant=cast(Any, self.variant),
            started_at=self._started_at,
            ended_at=ended_at,
            status="success",
            input=self.graph_input,
            output=_output_mapping(final_output),
            executions=ordered_executions,
        )
        by_occurrence = {
            execution.occurrence_id: execution
            for execution in ordered_executions
            if execution.occurrence_id is not None
        }
        observations: list[EdgeObservation] = []
        for handoff in self._handoffs:
            if handoff.spec is None or handoff.payload is None:
                continue
            if handoff.consumer_occurrence_id is None:
                raise RuntimeError(
                    f"OpenAI Agents handoff to {handoff.target_agent_name!r} has no consumer "
                    "occurrence"
                )
            producer = by_occurrence[handoff.source_occurrence_id]
            consumer = by_occurrence[handoff.consumer_occurrence_id]
            observations.append(
                EdgeObservation(
                    schema_version="0.2",
                    run_id=self.run_id,
                    graph_id=self.graph_id,
                    graph_version=self.graph_version,
                    edge_id=handoff.spec.edge_id,
                    producer=handoff.spec.producer,
                    consumer=handoff.spec.consumer,
                    occurrence_id=(
                        f"openai-handoff:{handoff.source_occurrence_id}:"
                        f"{handoff.consumer_occurrence_id}"
                    ),
                    producer_occurrence_id=producer.occurrence_id,
                    consumer_occurrence_id=consumer.occurrence_id,
                    causal_sequence=len(observations),
                    branch_id=consumer.branch_id,
                    attempt=consumer.attempt,
                    input=consumer.input,
                    output=handoff.payload,
                    metadata={"event": "handoff"},
                    tool_calls=producer.tool_calls,
                    source_access=producer.source_access,
                    observed_at=handoff.observed_at,
                )
            )
        return TraceBundle(
            schema_version="0.2",
            runs=(graph_run,),
            edge_observations=tuple(observations),
        )


class OpenAIAgentsAdapter:
    """Run an OpenAI Agents SDK workflow and emit framework-neutral trace 0.2 records."""

    framework_name = "openai-agents"

    def __init__(
        self,
        *,
        run_id: str,
        graph_id: str,
        graph_version: str,
        variant: str = "other",
        edges: tuple[HandoffEdgeSpec, ...] = (),
        context: Any = None,
        max_turns: int = 10,
    ) -> None:
        pairs = [(edge.producer, edge.consumer) for edge in edges]
        edge_ids = [edge.edge_id for edge in edges]
        if len(set(pairs)) != len(pairs):
            raise ValueError(
                "OpenAI Agents handoff edge producer and consumer pairs must be unique"
            )
        if len(set(edge_ids)) != len(edge_ids):
            raise ValueError("OpenAI Agents handoff edge IDs must be unique")
        if variant not in {"baseline", "candidate", "other"}:
            raise ValueError("OpenAI Agents variant must be baseline, candidate, or other")
        if max_turns < 1:
            raise ValueError("OpenAI Agents max_turns must be at least 1")
        self.run_id = run_id
        self.graph_id = graph_id
        self.graph_version = graph_version
        self.variant = variant
        self.edges = edges
        self.context = context
        self.max_turns = max_turns

    def _prepare(
        self, input_data: dict[str, Any]
    ) -> tuple[str | list[TResponseInputItem], _GraphABIRunHooks]:
        agent_input = input_data.get("input")
        if not isinstance(agent_input, str | list):
            raise ValueError(
                "OpenAI Agents adapter input_data['input'] must be a string or Responses input "
                "item list"
            )
        hooks = _GraphABIRunHooks(
            run_id=self.run_id,
            graph_id=self.graph_id,
            graph_version=self.graph_version,
            variant=self.variant,
            graph_input=_json_mapping(input_data),
            edges=self.edges,
        )
        return cast(str | list[TResponseInputItem], agent_input), hooks

    @staticmethod
    def _run_config(graph_id: str) -> RunConfig:
        return RunConfig(
            tracing_disabled=True,
            trace_include_sensitive_data=False,
            workflow_name=f"GraphABI {graph_id}",
        )

    def invoke(self, graph: Any, input_data: dict[str, Any]) -> TraceBundle:
        """Run one agent workflow synchronously with SDK tracing disabled."""
        if not isinstance(graph, Agent):
            raise TypeError("OpenAI Agents adapter graph must be an agents.Agent")
        agent_input, hooks = self._prepare(input_data)
        result = Runner.run_sync(
            graph,
            agent_input,
            context=self.context,
            max_turns=self.max_turns,
            hooks=hooks,
            run_config=self._run_config(self.graph_id),
        )
        return hooks.finish(result.final_output)

    async def invoke_async(self, graph: Agent[Any], input_data: dict[str, Any]) -> TraceBundle:
        """Run one agent workflow asynchronously with SDK tracing disabled."""
        agent_input, hooks = self._prepare(input_data)
        result = await Runner.run(
            graph,
            agent_input,
            context=self.context,
            max_turns=self.max_turns,
            hooks=hooks,
            run_config=self._run_config(self.graph_id),
        )
        return hooks.finish(result.final_output)
