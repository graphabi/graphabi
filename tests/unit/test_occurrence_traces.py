from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from graphabi.comparison import compare_semantics, findings_fingerprint
from graphabi.contracts.models import Contract
from graphabi.models.traces import EdgeObservation, GraphRun, NodeExecution, TraceBundle
from graphabi.storage import SQLiteTraceStore

NOW = datetime(2026, 8, 11, tzinfo=UTC)


def execution(
    node_id: str,
    occurrence_id: str,
    sequence: int,
    *,
    parents: tuple[str, ...] = (),
    incoming_edge_id: str | None = None,
    branch_id: str | None = "main",
    attempt: int = 1,
    run_id: str = "r",
) -> NodeExecution:
    return NodeExecution(
        schema_version="0.2",
        run_id=run_id,
        graph_id="g",
        graph_version="2",
        node_id=node_id,
        occurrence_id=occurrence_id,
        parent_occurrence_id=parents[0] if parents else None,
        causal_parent_occurrence_ids=parents,
        incoming_edge_id=incoming_edge_id,
        causal_sequence=sequence,
        branch_id=branch_id,
        attempt=attempt,
        input={},
        output={"occurrence": occurrence_id},
        started_at=NOW,
        ended_at=NOW,
        duration_ms=0,
        status="success",
        framework="test",
        framework_version="1",
    )


def occurrence_bundle(
    executions: tuple[NodeExecution, ...],
    edges: tuple[tuple[str, str, str], ...],
    *,
    run_id: str = "r",
) -> TraceBundle:
    by_occurrence = {item.occurrence_id: item for item in executions}
    observations = tuple(
        EdgeObservation(
            schema_version="0.2",
            run_id=run_id,
            graph_id="g",
            graph_version="2",
            edge_id=edge_id,
            producer=by_occurrence[producer_id].node_id,
            consumer=by_occurrence[consumer_id].node_id,
            occurrence_id=f"edge:{index}",
            producer_occurrence_id=producer_id,
            consumer_occurrence_id=consumer_id,
            causal_sequence=index,
            branch_id=by_occurrence[producer_id].branch_id,
            attempt=by_occurrence[consumer_id].attempt,
            input={},
            output={"edge": edge_id},
            observed_at=NOW,
        )
        for index, (edge_id, producer_id, consumer_id) in enumerate(edges)
    )
    graph_run = GraphRun(
        schema_version="0.2",
        run_id=run_id,
        graph_id="g",
        graph_version="2",
        started_at=NOW,
        ended_at=NOW,
        status="success",
        input={},
        output={},
        executions=executions,
    )
    return TraceBundle(
        schema_version="0.2",
        exported_at=NOW,
        runs=(graph_run,),
        edge_observations=observations,
    )


def edge_contract(
    *,
    nodes: tuple[str, ...],
    graph_edges: tuple[tuple[str, str, str], ...],
    contracted_edge: str,
    terminal_nodes: tuple[str, ...] = (),
) -> Contract:
    selected = next(edge for edge in graph_edges if edge[0] == contracted_edge)
    return Contract.model_validate(
        {
            "version": "0.2",
            "graph": "g",
            "nodes": [{"id": node_id, "terminal": node_id in terminal_nodes} for node_id in nodes],
            "graph_edges": [
                {"id": edge_id, "producer": producer, "consumer": consumer}
                for edge_id, producer, consumer in graph_edges
            ],
            "edges": [
                {
                    "id": selected[0],
                    "producer": selected[1],
                    "consumer": selected[2],
                    "invariants": [
                        {
                            "id": "edge_payload_present",
                            "evaluator": "completeness",
                            "description": "edge payload is required",
                            "destination_path": "output.edge",
                        }
                    ],
                }
            ],
        }
    )


def with_edge_output(
    bundle: TraceBundle,
    occurrence_id: str,
    output: dict[str, object],
) -> TraceBundle:
    return bundle.model_copy(
        update={
            "edge_observations": tuple(
                item.model_copy(update={"output": output})
                if item.occurrence_id == occurrence_id
                else item
                for item in bundle.edge_observations
            )
        }
    )


def test_bounded_loop_keeps_repeated_node_occurrences_distinct() -> None:
    bundle = occurrence_bundle(
        (
            execution("start", "start:0", 0),
            execution("body", "body:0", 1, parents=("start:0",), incoming_edge_id="enter"),
            execution("body", "body:1", 2, parents=("body:0",), incoming_edge_id="repeat"),
            execution("done", "done:0", 3, parents=("body:1",), incoming_edge_id="exit"),
        ),
        (
            ("enter", "start:0", "body:0"),
            ("repeat", "body:0", "body:1"),
            ("exit", "body:1", "done:0"),
        ),
    )

    body_occurrences = [
        item.occurrence_id for item in bundle.runs[0].executions if item.node_id == "body"
    ]
    assert body_occurrences == ["body:0", "body:1"]


def test_retry_loop_records_attempts_without_discarding_failures() -> None:
    first = execution("worker", "worker:0", 1, parents=("start:0",), attempt=1)
    first = first.model_copy(update={"status": "error", "error": "retryable"})
    bundle = occurrence_bundle(
        (
            execution("start", "start:0", 0),
            first,
            execution("worker", "worker:1", 2, parents=("worker:0",), attempt=2),
        ),
        (("dispatch", "start:0", "worker:0"), ("retry", "worker:0", "worker:1")),
    )

    attempts = [item.attempt for item in bundle.runs[0].executions if item.node_id == "worker"]
    assert attempts == [1, 2]
    assert bundle.runs[0].executions[1].status == "error"


def test_parallel_two_way_fan_out_has_stable_branch_ids() -> None:
    bundle = occurrence_bundle(
        (
            execution("root", "root:0", 0),
            execution("worker", "worker:left", 1, parents=("root:0",), branch_id="left"),
            execution("worker", "worker:right", 2, parents=("root:0",), branch_id="right"),
        ),
        (("fan_out", "root:0", "worker:left"), ("fan_out", "root:0", "worker:right")),
    )

    assert [item.branch_id for item in bundle.runs[0].executions[1:]] == ["left", "right"]
    assert len({item.occurrence_id for item in bundle.edge_observations}) == 2


def test_fan_in_merge_preserves_every_causal_parent() -> None:
    bundle = occurrence_bundle(
        (
            execution("root", "root:0", 0),
            execution("left", "left:0", 1, parents=("root:0",), branch_id="left"),
            execution("right", "right:0", 2, parents=("root:0",), branch_id="right"),
            execution(
                "merge",
                "merge:0",
                3,
                parents=("left:0", "right:0"),
                incoming_edge_id="left_to_merge",
                branch_id="join",
            ),
        ),
        (
            ("root_to_left", "root:0", "left:0"),
            ("root_to_right", "root:0", "right:0"),
            ("left_to_merge", "left:0", "merge:0"),
            ("right_to_merge", "right:0", "merge:0"),
        ),
    )

    merge = bundle.runs[0].executions[-1]
    assert merge.parent_occurrence_id == "left:0"
    assert merge.causal_parent_occurrence_ids == ("left:0", "right:0")


def test_nested_branches_retain_causal_ancestry() -> None:
    bundle = occurrence_bundle(
        (
            execution("root", "root:0", 0),
            execution("outer", "outer:a", 1, parents=("root:0",), branch_id="a"),
            execution("inner", "inner:a/1", 2, parents=("outer:a",), branch_id="a/1"),
            execution("inner", "inner:a/2", 3, parents=("outer:a",), branch_id="a/2"),
        ),
        (
            ("outer", "root:0", "outer:a"),
            ("inner", "outer:a", "inner:a/1"),
            ("inner", "outer:a", "inner:a/2"),
        ),
    )

    assert bundle.runs[0].executions[-1].causal_parent_occurrence_ids == ("outer:a",)


def test_repeated_producer_consumer_edge_keeps_both_crossings() -> None:
    bundle = occurrence_bundle(
        (
            execution("producer", "producer:0", 0),
            execution("consumer", "consumer:0", 1, parents=("producer:0",)),
            execution("producer", "producer:1", 2, parents=("consumer:0",)),
            execution("consumer", "consumer:1", 3, parents=("producer:1",)),
        ),
        (
            ("producer_to_consumer", "producer:0", "consumer:0"),
            ("consumer_to_producer", "consumer:0", "producer:1"),
            ("producer_to_consumer", "producer:1", "consumer:1"),
        ),
    )

    repeated = [item for item in bundle.edge_observations if item.edge_id == "producer_to_consumer"]
    assert [item.occurrence_id for item in repeated] == ["edge:0", "edge:2"]


def test_repeated_edge_occurrences_round_trip_through_sqlite(tmp_path: Path) -> None:
    bundle = occurrence_bundle(
        (
            execution("producer", "producer:0", 0),
            execution("consumer", "consumer:0", 1, parents=("producer:0",)),
            execution("producer", "producer:1", 2, parents=("consumer:0",)),
            execution("consumer", "consumer:1", 3, parents=("producer:1",)),
        ),
        (
            ("producer_to_consumer", "producer:0", "consumer:0"),
            ("consumer_to_producer", "consumer:0", "producer:1"),
            ("producer_to_consumer", "producer:1", "consumer:1"),
        ),
    )
    store = SQLiteTraceStore(tmp_path / "occurrences.db")

    store.save_bundle(bundle)

    assert store.load_run("r") == bundle


def test_multiple_terminal_paths_remain_separate_occurrences() -> None:
    bundle = occurrence_bundle(
        (
            execution("root", "root:0", 0),
            execution("terminal", "terminal:left", 1, parents=("root:0",), branch_id="left"),
            execution("terminal", "terminal:right", 2, parents=("root:0",), branch_id="right"),
        ),
        (("finish", "root:0", "terminal:left"), ("finish", "root:0", "terminal:right")),
    )

    assert len([item for item in bundle.runs[0].executions if item.node_id == "terminal"]) == 2


def test_occurrence_dag_rejects_missing_or_noncausal_parents() -> None:
    with pytest.raises(ValidationError, match="missing causal parent"):
        occurrence_bundle(
            (execution("child", "child:0", 1, parents=("missing:0",)),),
            (),
        )
    with pytest.raises(ValidationError, match="must precede"):
        occurrence_bundle(
            (
                execution("child", "child:0", 0, parents=("parent:0",)),
                execution("parent", "parent:0", 1),
            ),
            (),
        )


def test_edge_occurrence_must_reference_its_causal_executions() -> None:
    producer = execution("producer", "producer:0", 0)
    consumer = execution("consumer", "consumer:0", 1)
    with pytest.raises(ValidationError, match="not a causal parent"):
        occurrence_bundle((producer, consumer), (("edge", "producer:0", "consumer:0"),))


def test_edge_causal_sequence_must_be_unique_within_run() -> None:
    bundle = occurrence_bundle(
        (
            execution("root", "root:0", 0),
            execution("worker", "worker:left", 1, parents=("root:0",), branch_id="left"),
            execution("worker", "worker:right", 2, parents=("root:0",), branch_id="right"),
        ),
        (("fan_out", "root:0", "worker:left"), ("fan_out", "root:0", "worker:right")),
    )
    duplicated = bundle.edge_observations[1].model_copy(update={"causal_sequence": 0})
    with pytest.raises(ValidationError, match="edge causal_sequence 0 is duplicated"):
        TraceBundle(
            schema_version="0.2",
            exported_at=NOW,
            runs=bundle.runs,
            edge_observations=(bundle.edge_observations[0], duplicated),
        )


def test_repeated_edge_occurrences_pair_by_causal_ancestry() -> None:
    topology = (
        ("producer_to_consumer", "producer", "consumer"),
        ("consumer_to_producer", "consumer", "producer"),
    )
    contract = edge_contract(
        nodes=("producer", "consumer"),
        graph_edges=topology,
        contracted_edge="producer_to_consumer",
    )

    def loop_bundle(run_id: str, prefix: str) -> TraceBundle:
        return occurrence_bundle(
            (
                execution("producer", f"{prefix}:p0", 0, run_id=run_id),
                execution(
                    "consumer",
                    f"{prefix}:c0",
                    1,
                    parents=(f"{prefix}:p0",),
                    run_id=run_id,
                ),
                execution(
                    "producer",
                    f"{prefix}:p1",
                    2,
                    parents=(f"{prefix}:c0",),
                    run_id=run_id,
                ),
                execution(
                    "consumer",
                    f"{prefix}:c1",
                    3,
                    parents=(f"{prefix}:p1",),
                    run_id=run_id,
                ),
            ),
            (
                ("producer_to_consumer", f"{prefix}:p0", f"{prefix}:c0"),
                ("consumer_to_producer", f"{prefix}:c0", f"{prefix}:p1"),
                ("producer_to_consumer", f"{prefix}:p1", f"{prefix}:c1"),
            ),
            run_id=run_id,
        )

    baseline = loop_bundle("baseline", "b")
    candidate = with_edge_output(loop_bundle("candidate", "c"), "edge:2", {"edge": ""})
    report = compare_semantics(contract, baseline, candidate)

    assert report.status == "FAIL"
    assert len(report.findings) == 2
    assert {item.occurrence_pairing for item in report.findings} == {"CAUSAL_MATCH"}
    assert {item.status for item in report.findings} == {"PASS", "BREAKING"}
    assert len({item.finding_id for item in report.findings}) == 2

    missing_candidate = TraceBundle(
        schema_version="0.2",
        exported_at=NOW,
        runs=candidate.runs,
        edge_observations=(),
    )
    missing = compare_semantics(contract, baseline, missing_candidate)
    assert missing.status == "INSUFFICIENT_EVIDENCE"
    assert len(missing.findings) == 2
    assert missing.coverage.insufficient_evidence_contracts == (
        "g:producer_to_consumer:edge_payload_present",
    )


def test_fan_out_pairing_is_stable_when_scheduling_order_changes() -> None:
    topology = (("fan_out", "root", "worker"),)
    contract = edge_contract(
        nodes=("root", "worker"),
        graph_edges=topology,
        contracted_edge="fan_out",
    )
    baseline = occurrence_bundle(
        (
            execution("root", "b:root", 0, run_id="baseline"),
            execution(
                "worker", "b:left", 1, parents=("b:root",), branch_id="left", run_id="baseline"
            ),
            execution(
                "worker",
                "b:right",
                2,
                parents=("b:root",),
                branch_id="right",
                run_id="baseline",
            ),
        ),
        (("fan_out", "b:root", "b:left"), ("fan_out", "b:root", "b:right")),
        run_id="baseline",
    )
    candidate = occurrence_bundle(
        (
            execution("root", "c:root", 0, run_id="candidate"),
            execution(
                "worker",
                "c:right",
                1,
                parents=("c:root",),
                branch_id="right",
                run_id="candidate",
            ),
            execution(
                "worker", "c:left", 2, parents=("c:root",), branch_id="left", run_id="candidate"
            ),
        ),
        (("fan_out", "c:root", "c:right"), ("fan_out", "c:root", "c:left")),
        run_id="candidate",
    )

    first = compare_semantics(contract, baseline, candidate)
    second = compare_semantics(contract, baseline, candidate)

    assert first.status == "PASS"
    assert len(first.findings) == 2
    assert findings_fingerprint(first) == findings_fingerprint(second)
    assert {item.candidate_occurrence_id for item in first.findings} == {"edge:0", "edge:1"}


def test_ambiguous_sibling_occurrences_stay_insufficient_evidence() -> None:
    topology = (("fan_out", "root", "worker"),)
    contract = edge_contract(
        nodes=("root", "worker"),
        graph_edges=topology,
        contracted_edge="fan_out",
    )

    def ambiguous_bundle(run_id: str, prefix: str) -> TraceBundle:
        return occurrence_bundle(
            (
                execution("root", f"{prefix}:root", 0, run_id=run_id),
                execution(
                    "worker",
                    f"{prefix}:one",
                    1,
                    parents=(f"{prefix}:root",),
                    branch_id=None,
                    run_id=run_id,
                ),
                execution(
                    "worker",
                    f"{prefix}:two",
                    2,
                    parents=(f"{prefix}:root",),
                    branch_id=None,
                    run_id=run_id,
                ),
            ),
            (
                ("fan_out", f"{prefix}:root", f"{prefix}:one"),
                ("fan_out", f"{prefix}:root", f"{prefix}:two"),
            ),
            run_id=run_id,
        )

    report = compare_semantics(
        contract,
        ambiguous_bundle("baseline", "b"),
        ambiguous_bundle("candidate", "c"),
    )

    assert report.status == "INSUFFICIENT_EVIDENCE"
    assert report.findings[0].occurrence_pairing == "AMBIGUOUS"
    assert "edge:0" in report.findings[0].reason
    assert "edge:1" in report.findings[0].reason


def test_retry_attempts_pair_independently() -> None:
    topology = (("dispatch", "start", "worker"), ("retry", "worker", "worker"))
    contract = edge_contract(
        nodes=("start", "worker"),
        graph_edges=topology,
        contracted_edge="retry",
    )

    def retry_bundle(run_id: str, prefix: str) -> TraceBundle:
        return occurrence_bundle(
            (
                execution("start", f"{prefix}:start", 0, run_id=run_id),
                execution(
                    "worker",
                    f"{prefix}:attempt1",
                    1,
                    parents=(f"{prefix}:start",),
                    attempt=1,
                    run_id=run_id,
                ),
                execution(
                    "worker",
                    f"{prefix}:attempt2",
                    2,
                    parents=(f"{prefix}:attempt1",),
                    attempt=2,
                    run_id=run_id,
                ),
            ),
            (
                ("dispatch", f"{prefix}:start", f"{prefix}:attempt1"),
                ("retry", f"{prefix}:attempt1", f"{prefix}:attempt2"),
            ),
            run_id=run_id,
        )

    report = compare_semantics(
        contract,
        retry_bundle("baseline", "b"),
        retry_bundle("candidate", "c"),
    )

    assert report.status == "PASS"
    assert report.findings[0].occurrence_pairing == "CAUSAL_MATCH"
    assert report.findings[0].candidate_observation is not None
    assert report.findings[0].candidate_observation.attempt == 2


def test_fan_in_break_reports_observed_occurrence_impact() -> None:
    topology = (
        ("root_to_left", "root", "left"),
        ("root_to_right", "root", "right"),
        ("left_to_merge", "left", "merge"),
        ("right_to_merge", "right", "merge"),
    )
    contract = edge_contract(
        nodes=("root", "left", "right", "merge"),
        graph_edges=topology,
        contracted_edge="left_to_merge",
        terminal_nodes=("merge",),
    )

    def merge_bundle(run_id: str, prefix: str) -> TraceBundle:
        return occurrence_bundle(
            (
                execution("root", f"{prefix}:root", 0, run_id=run_id),
                execution("left", f"{prefix}:left", 1, parents=(f"{prefix}:root",), run_id=run_id),
                execution(
                    "right", f"{prefix}:right", 2, parents=(f"{prefix}:root",), run_id=run_id
                ),
                execution(
                    "merge",
                    f"{prefix}:merge",
                    3,
                    parents=(f"{prefix}:left", f"{prefix}:right"),
                    branch_id="join",
                    run_id=run_id,
                ),
            ),
            (
                ("root_to_left", f"{prefix}:root", f"{prefix}:left"),
                ("root_to_right", f"{prefix}:root", f"{prefix}:right"),
                ("left_to_merge", f"{prefix}:left", f"{prefix}:merge"),
                ("right_to_merge", f"{prefix}:right", f"{prefix}:merge"),
            ),
            run_id=run_id,
        )

    baseline = merge_bundle("baseline", "b")
    candidate = with_edge_output(
        merge_bundle("candidate", "c"),
        "edge:2",
        {"edge": ""},
    )
    finding = compare_semantics(contract, baseline, candidate).breaking_findings[0]

    assert finding.affected_downstream_occurrences == ("c:merge",)
    assert finding.shortest_affected_occurrence_path == ("c:merge",)
    assert finding.witness.candidate_occurrence_id == "edge:2"
