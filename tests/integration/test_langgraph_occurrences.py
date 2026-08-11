from __future__ import annotations

from graphabi.adapters.langgraph import EdgeSpec, LangGraphRecorder


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
