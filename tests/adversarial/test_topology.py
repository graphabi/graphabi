from __future__ import annotations

from graphabi.contracts.models import Contract
from graphabi.impact import analyze_impact


def edge(edge_id: str, producer: str, consumer: str) -> dict[str, object]:
    return {
        "id": edge_id,
        "producer": producer,
        "consumer": consumer,
        "invariants": [{"id": "contract", "evaluator": "external", "description": "test"}],
    }


def test_broken_edge_affects_only_one_branch_and_two_terminals_are_separate() -> None:
    contract = Contract.model_validate(
        {
            "version": "0.1",
            "graph": "branching",
            "nodes": [
                {"id": "root"},
                {"id": "left"},
                {"id": "right"},
                {"id": "left_terminal", "terminal": True, "side_effecting": True},
                {"id": "right_terminal", "terminal": True},
            ],
            "edges": [
                edge("root_left", "root", "left"),
                edge("left_terminal", "left", "left_terminal"),
                edge("root_right", "root", "right"),
                edge("right_terminal", "right", "right_terminal"),
            ],
        }
    )

    impact = analyze_impact(contract, "root_left")
    assert impact.downstream_nodes == ("left", "left_terminal")
    assert impact.terminal_paths == (("left", "left_terminal"),)
    assert impact.side_effecting_paths == (("left", "left_terminal"),)
    assert impact.unaffected_branches_exist is True


def test_two_reachable_terminal_nodes_are_both_reported() -> None:
    contract = Contract.model_validate(
        {
            "version": "0.1",
            "graph": "two_terminals",
            "nodes": [
                {"id": "a"},
                {"id": "b"},
                {"id": "t1", "terminal": True},
                {"id": "t2", "terminal": True, "side_effecting": True},
            ],
            "edges": [
                edge("ab", "a", "b"),
                edge("bt1", "b", "t1"),
                edge("bt2", "b", "t2"),
            ],
        }
    )

    impact = analyze_impact(contract, "ab")
    assert impact.terminal_paths == (("b", "t1"), ("b", "t2"))
    assert impact.side_effecting_paths == (("b", "t2"),)
    assert impact.shortest_affected_path == ("b", "t1")


def test_bounded_cycle_is_analyzed_without_infinite_paths() -> None:
    contract = Contract.model_validate(
        {
            "version": "0.1",
            "graph": "cycle",
            "nodes": [
                {"id": "a"},
                {"id": "b"},
                {"id": "c"},
                {"id": "terminal", "terminal": True},
            ],
            "edges": [
                edge("ab", "a", "b"),
                edge("bc", "b", "c"),
                edge("cb", "c", "b"),
                edge("ct", "c", "terminal"),
            ],
        }
    )

    impact = analyze_impact(contract, "ab")
    assert impact.downstream_nodes == ("b", "c", "terminal")
    assert impact.terminal_paths == (("b", "c", "terminal"),)
    assert impact.shortest_affected_path == ("b", "c", "terminal")


def test_disconnected_node_is_not_mislabeled_as_an_unaffected_branch() -> None:
    contract = Contract.model_validate(
        {
            "version": "0.1",
            "graph": "disconnected",
            "nodes": [
                {"id": "a"},
                {"id": "b"},
                {"id": "terminal", "terminal": True},
                {"id": "unreachable"},
            ],
            "edges": [edge("ab", "a", "b"), edge("bt", "b", "terminal")],
        }
    )

    impact = analyze_impact(contract, "ab")
    assert "unreachable" not in impact.downstream_nodes
    assert impact.unaffected_branches_exist is False
