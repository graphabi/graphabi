"""Record a local scripted OpenAI Agents SDK handoff with no API key or network."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any, cast

from agents import Agent, function_tool
from agents.handoffs import Handoff
from agents.items import ModelResponse, TResponseOutputItem, TResponseStreamEvent
from agents.models.interface import Model
from agents.usage import Usage
from openai.types.responses import (
    ResponseFunctionToolCall,
    ResponseOutputMessage,
    ResponseOutputText,
)

from graphabi.adapters.openai_agents import HandoffEdgeSpec, OpenAIAgentsAdapter
from graphabi.models.traces import TraceBundle


class ScriptedModel(Model):
    """Small deterministic SDK model used only by this keyless example."""

    def __init__(self, outputs: list[list[TResponseOutputItem]]) -> None:
        self.outputs = list(outputs)
        self.call_count = 0

    async def get_response(self, *args: Any, **kwargs: Any) -> ModelResponse:
        del args, kwargs
        if not self.outputs:
            raise RuntimeError("scripted model has no remaining output")
        self.call_count += 1
        return ModelResponse(
            output=self.outputs.pop(0),
            usage=Usage(),
            response_id=f"scripted-response-{self.call_count}",
        )

    async def stream_response(
        self, *args: Any, **kwargs: Any
    ) -> AsyncIterator[TResponseStreamEvent]:
        del args, kwargs
        if False:
            yield cast(TResponseStreamEvent, {})
        raise NotImplementedError("the deterministic example uses non-streaming Runner.run")


def _message(text: str, item_id: str) -> ResponseOutputMessage:
    return ResponseOutputMessage(
        id=item_id,
        type="message",
        role="assistant",
        content=[
            ResponseOutputText(
                text=text,
                type="output_text",
                annotations=[],
                logprobs=[],
            )
        ],
        status="completed",
    )


@function_tool
def inspect_record(record_id: str) -> str:
    """Inspect one deterministic local record."""
    return f"record {record_id} is complete"


def build_workflow() -> tuple[Agent[Any], dict[str, Any]]:
    """Build a two-agent workflow backed only by scripted local model responses."""
    publisher = Agent(
        name="publisher",
        instructions="Return the final local fixture result.",
        model=ScriptedModel([[_message("Fixture published", "publisher-message")]]),
    )
    researcher = Agent(
        name="researcher",
        instructions="Inspect the record, then hand off to the publisher.",
        tools=[inspect_record],
        handoffs=[publisher],
        model=ScriptedModel(
            [
                [
                    ResponseFunctionToolCall(
                        id="inspect-item",
                        call_id="inspect-call-1",
                        type="function_call",
                        name=inspect_record.name,
                        arguments=json.dumps({"record_id": "fixture-001"}),
                    )
                ],
                [
                    ResponseFunctionToolCall(
                        id="handoff-item",
                        call_id="handoff-call-1",
                        type="function_call",
                        name=Handoff.default_tool_name(publisher),
                        arguments="{}",
                    )
                ],
            ]
        ),
    )
    context = {
        "handoff_payload": {
            "record_id": "fixture-001",
            "complete": True,
            "authority_level": "recommendation",
        }
    }
    return researcher, context


def _handoff_payload(context: Any, from_agent: Any, to_agent: Any) -> dict[str, Any]:
    del from_agent, to_agent
    local_context = context.context
    if not isinstance(local_context, dict):
        raise TypeError("example context must be a mapping")
    payload = local_context.get("handoff_payload")
    if not isinstance(payload, dict):
        raise TypeError("example context is missing handoff_payload")
    return payload


def run_example() -> TraceBundle:
    """Execute the local workflow and return its GraphABI trace bundle."""
    starting_agent, context = build_workflow()
    adapter = OpenAIAgentsAdapter(
        run_id="openai-agents-fixture-001",
        graph_id="openai_agents_adapter_demo",
        graph_version="1.0",
        variant="other",
        context=context,
        edges=(
            HandoffEdgeSpec(
                edge_id="researcher_to_publisher",
                producer="researcher",
                consumer="publisher",
                payload_resolver=_handoff_payload,
            ),
        ),
    )
    return adapter.invoke(starting_agent, {"input": "Inspect fixture-001 and publish it."})


def main() -> None:
    bundle = run_example()
    run = bundle.runs[0]
    print("OpenAI Agents SDK adapter fixture")
    print(f"Run status: {run.status}")
    print(f"Node occurrences: {len(run.executions)}")
    print(f"Handoff edges: {len(bundle.edge_observations)}")
    print("Network calls: 0")


if __name__ == "__main__":
    main()
