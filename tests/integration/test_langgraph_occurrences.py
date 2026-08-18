from __future__ import annotations

import operator
from typing import Annotated, TypedDict

import pytest
from langgraph.graph import END, START, StateGraph

from graphabi.adapters.langgraph import EdgeSpec, LangGraphRecorder


class UnevenFanInState(TypedDict, total=False):
    events: Annotated[list[str], operator.add]


def test_langgraph_recorder_preserves_fanout_and_fanin_occurrences() -> None:
    recorder = LangGraphRecorder(
        run_id="fanout-fanin",
        graph_id="fanout-fanin",
        graph_version="1",
        variant="other",
        edges=(
            EdgeSpec("root_to_worker", "root", "worker", "root_result"),
            EdgeSpec("worker_to_merge", "worker", "merge", "worker_result"),
        ),
    )
    root = recorder.instrument(
        "root",
        lambda state: {"root_result": {"request": state["request"]}},
    )
    worker = recorder.instrument(
        "worker",
        lambda state: {"worker_result": {"branch": state["branch"]}},
        parent_node="root",
        incoming_edge="root_to_worker",
        branch_id=lambda state: str(state["branch"]),
    )
    merge = recorder.instrument(
        "merge",
        lambda state: {"merged": True},
        incoming_edge="worker_to_merge",
        branch_id="join",
        parent_occurrences=lambda _: recorder.occurrence_ids("worker"),
    )
    recorder.begin()
    root({"request": "work"})
    worker({"request": "work", "branch": "left"})
    worker({"request": "work", "branch": "right"})
    merge({"request": "work", "branch": "join"})

    bundle = recorder.finish(
        {"request": "work"},
        {"merged": True},
    )

    assert bundle.schema_version == "0.2"
    assert [item.node_id for item in bundle.runs[0].executions] == [
        "root",
        "worker",
        "worker",
        "merge",
    ]
    merge_execution = bundle.runs[0].executions[-1]
    assert merge_execution.causal_parent_occurrence_ids == (
        "worker:0000",
        "worker:0001",
    )
    assert [item.edge_id for item in bundle.edge_observations] == [
        "root_to_worker",
        "root_to_worker",
        "worker_to_merge",
        "worker_to_merge",
    ]
    assert len({item.occurrence_id for item in bundle.edge_observations}) == 4


def test_langgraph_recorder_rejects_unknown_explicit_parent_occurrence() -> None:
    recorder = LangGraphRecorder(
        run_id="unknown-parent",
        graph_id="g",
        graph_version="1",
        variant="other",
        edges=(),
    )
    child = recorder.instrument(
        "child",
        lambda _: {},
        parent_occurrences=lambda _: ("missing:0000",),
    )

    try:
        child({})
    except ValueError as exc:
        assert "unknown IDs" in str(exc)
        assert "missing:0000" in str(exc)
    else:
        raise AssertionError("unknown causal parents must fail before node execution")


def _uneven_fan_in_graph(*, combined_parent_edge: bool) -> tuple[LangGraphRecorder, object]:
    recorder = LangGraphRecorder(
        run_id="uneven-fan-in",
        graph_id="uneven-fan-in",
        graph_version="1",
        variant="other",
        edges=(),
    )
    graph = StateGraph(UnevenFanInState)
    graph.add_node("root", recorder.instrument("root", lambda _: {"events": ["root"]}))
    graph.add_node(
        "fast",
        recorder.instrument("fast", lambda _: {"events": ["fast"]}, parent_node="root"),
    )
    graph.add_node(
        "slow_1",
        recorder.instrument("slow_1", lambda _: {"events": ["slow_1"]}, parent_node="root"),
    )
    graph.add_node(
        "slow_2",
        recorder.instrument("slow_2", lambda _: {"events": ["slow_2"]}, parent_node="slow_1"),
    )
    graph.add_node(
        "join",
        recorder.instrument(
            "join", lambda _: {"events": ["join"]}, parent_nodes=("fast", "slow_2")
        ),
    )
    graph.add_edge(START, "root")
    graph.add_edge("root", "fast")
    graph.add_edge("root", "slow_1")
    graph.add_edge("slow_1", "slow_2")
    if combined_parent_edge:
        graph.add_edge(["fast", "slow_2"], "join")
    else:
        graph.add_edge("fast", "join")
        graph.add_edge("slow_2", "join")
    graph.add_edge("join", END)
    return recorder, graph.compile()


def test_langgraph_list_parent_edge_records_uneven_fan_in_once() -> None:
    recorder, graph = _uneven_fan_in_graph(combined_parent_edge=True)

    bundle = recorder.invoke(graph, {"events": []})

    joins = [item for item in bundle.runs[0].executions if item.node_id == "join"]
    assert len(joins) == 1
    assert joins[0].causal_parent_occurrence_ids == ("fast:0000", "slow_2:0000")


def test_langgraph_separate_parent_edges_fail_closed_on_premature_join() -> None:
    recorder, graph = _uneven_fan_in_graph(combined_parent_edge=False)

    with pytest.raises(
        ValueError,
        match="node 'join' started before parent node 'slow_2' had a recorded occurrence",
    ):
        recorder.invoke(graph, {"events": []})
