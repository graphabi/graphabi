from __future__ import annotations

import asyncio
import socket
from importlib.metadata import version
from typing import Any

import pytest
from examples.openai_agents_adapter.example import build_workflow, run_example

from graphabi.adapters import FrameworkAdapter
from graphabi.adapters.openai_agents import HandoffEdgeSpec, OpenAIAgentsAdapter
from graphabi.comparison import compare_semantics
from graphabi.contracts.models import (
    Contract,
    ContractEdge,
    ContractNode,
    GraphEdge,
    Invariant,
)


@pytest.mark.integration
def test_real_sdk_runner_records_tool_handoff_and_occurrences(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    def reject_network(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("the local OpenAI Agents adapter fixture attempted a network call")

    monkeypatch.setattr(socket.socket, "connect", reject_network)
    bundle = run_example()

    assert bundle.schema_version == "0.2"
    run = bundle.runs[0]
    assert run.status == "success"
    assert run.input == {"input": "Inspect fixture-001 and publish it."}
    assert run.output == {"value": "Fixture published"}
    assert [execution.node_id for execution in run.executions] == ["researcher", "publisher"]
    researcher, publisher = run.executions
    assert researcher.occurrence_id == "openai-agent:researcher:0001"
    assert publisher.parent_occurrence_id == researcher.occurrence_id
    assert publisher.incoming_edge_id == "researcher_to_publisher"
    assert publisher.causal_sequence == 1
    assert len(researcher.tool_calls) == 1
    tool = researcher.tool_calls[0]
    assert tool.tool_name == "inspect_record"
    assert tool.call_id == "inspect-call-1"
    assert tool.input == {"record_id": "fixture-001"}
    assert tool.output == "record fixture-001 is complete"
    metadata = researcher.metadata["openai_agents"]
    assert isinstance(metadata, dict)
    assert metadata["llm_calls"] == 2
    assert metadata["sdk_tracing_disabled"] is True
    assert len(bundle.edge_observations) == 1
    observation = bundle.edge_observations[0]
    assert observation.edge_id == "researcher_to_publisher"
    assert observation.output == {
        "record_id": "fixture-001",
        "complete": True,
        "authority_level": "recommendation",
    }
    assert observation.producer_occurrence_id == researcher.occurrence_id
    assert observation.consumer_occurrence_id == publisher.occurrence_id
    contract = Contract(
        version="0.2",
        graph="openai_agents_adapter_demo",
        nodes=(ContractNode(id="researcher"), ContractNode(id="publisher", terminal=True)),
        graph_edges=(
            GraphEdge(
                id="researcher_to_publisher",
                producer="researcher",
                consumer="publisher",
            ),
        ),
        edges=(
            ContractEdge(
                id="researcher_to_publisher",
                producer="researcher",
                consumer="publisher",
                invariants=(
                    Invariant(
                        id="advisory_only",
                        evaluator="authority",
                        description="The publisher receives no more than a recommendation.",
                        source_path="output.authority_level",
                        maximum_allowed="recommendation",
                    ),
                ),
            ),
        ),
    )
    semantic = compare_semantics(contract, bundle, bundle)
    assert semantic.status == "PASS"
    assert semantic.coverage.summary.observed_contract_coverage_percent == 100.0


@pytest.mark.integration
def test_async_runner_retains_causality_without_fabricating_an_edge() -> None:
    starting_agent, context = build_workflow()
    adapter = OpenAIAgentsAdapter(
        run_id="async-fixture",
        graph_id="openai_agents_adapter_demo",
        graph_version="1.0",
        context=context,
    )

    bundle = asyncio.run(adapter.invoke_async(starting_agent, {"input": "Run locally."}))

    assert bundle.edge_observations == ()
    executions = bundle.runs[0].executions
    assert executions[1].parent_occurrence_id == executions[0].occurrence_id
    assert executions[1].incoming_edge_id is None


def test_adapter_protocol_version_bounds_and_configuration_errors() -> None:
    adapter = OpenAIAgentsAdapter(
        run_id="protocol",
        graph_id="test",
        graph_version="1",
    )
    assert isinstance(adapter, FrameworkAdapter)
    installed = tuple(int(part) for part in version("openai-agents").split(".")[:2])
    assert installed == (0, 20)

    def payload(context: Any, source: Any, target: Any) -> dict[str, Any]:
        del context, source, target
        return {"value": "fixture"}

    edge = HandoffEdgeSpec("edge", "a", "b", payload)
    with pytest.raises(ValueError, match="pairs must be unique"):
        OpenAIAgentsAdapter(
            run_id="bad",
            graph_id="test",
            graph_version="1",
            edges=(edge, HandoffEdgeSpec("other", "a", "b", payload)),
        )
    with pytest.raises(ValueError, match="edge IDs must be unique"):
        OpenAIAgentsAdapter(
            run_id="bad",
            graph_id="test",
            graph_version="1",
            edges=(edge, HandoffEdgeSpec("edge", "b", "c", payload)),
        )
    with pytest.raises(ValueError, match="variant"):
        OpenAIAgentsAdapter(
            run_id="bad",
            graph_id="test",
            graph_version="1",
            variant="unsafe",
        )
    with pytest.raises(ValueError, match="max_turns"):
        OpenAIAgentsAdapter(
            run_id="bad",
            graph_id="test",
            graph_version="1",
            max_turns=0,
        )
    with pytest.raises(ValueError, match="edge_id must not be empty"):
        HandoffEdgeSpec("", "a", "b", payload)
    with pytest.raises(TypeError, match=r"must be an agents\.Agent"):
        adapter.invoke(object(), {"input": "valid"})
    starting_agent, _ = build_workflow()
    with pytest.raises(ValueError, match=r"input_data\['input'\]"):
        adapter.invoke(starting_agent, {"input": 3})
