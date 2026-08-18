import sqlite3
from pathlib import Path

import pytest
from examples.research_graph.graph import run_graph
from pydantic import ValidationError

from graphabi.comparison import compare_semantics
from graphabi.contracts import load_contract
from graphabi.models.traces import (
    EdgeObservation,
    GraphRun,
    NodeExecution,
    RedactedValue,
    SourceAccess,
    TraceBundle,
)
from graphabi.storage import SQLiteTraceStore
from graphabi.traces import export_json, export_jsonl, load_bundle, upgrade_trace_bundle_v1

ROOT = Path(__file__).resolve().parents[2]


def legacy_demo_bundle(run_id: str) -> TraceBundle:
    modern, _ = run_graph("baseline", run_id)
    node_by_occurrence = {item.occurrence_id: item.node_id for item in modern.runs[0].executions}
    executions = tuple(
        NodeExecution.model_validate(
            {
                **item.model_dump(mode="python"),
                "schema_version": "0.1",
                "occurrence_id": None,
                "parent_occurrence_id": None,
                "causal_parent_occurrence_ids": (),
                "incoming_edge_id": None,
                "causal_sequence": None,
                "branch_id": None,
                "attempt": None,
                "parent_node": (
                    node_by_occurrence[item.parent_occurrence_id]
                    if item.parent_occurrence_id is not None
                    else None
                ),
                "incoming_edge": item.incoming_edge_id,
            }
        )
        for item in modern.runs[0].executions
    )
    graph_run = GraphRun.model_validate(
        {
            **modern.runs[0].model_dump(mode="python"),
            "schema_version": "0.1",
            "executions": executions,
        }
    )
    observations = tuple(
        EdgeObservation.model_validate(
            {
                **item.model_dump(mode="python"),
                "schema_version": "0.1",
                "occurrence_id": None,
                "producer_occurrence_id": None,
                "consumer_occurrence_id": None,
                "causal_sequence": None,
                "branch_id": None,
                "attempt": None,
            }
        )
        for item in modern.edge_observations
    )
    return TraceBundle(
        schema_version="0.1",
        exported_at=modern.exported_at,
        runs=(graph_run,),
        edge_observations=observations,
    )


def test_trace_json_and_jsonl_round_trip(tmp_path: Path) -> None:
    bundle, _ = run_graph("baseline", "roundtrip")
    json_path = tmp_path / "trace.json"
    jsonl_path = tmp_path / "trace.jsonl"
    export_json(bundle, json_path)
    export_jsonl(bundle, jsonl_path)
    assert load_bundle(json_path) == bundle
    jsonl = load_bundle(jsonl_path)
    assert jsonl == bundle


def test_jsonl_rejects_unknown_record(tmp_path: Path) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_text('{"kind":"mystery","data":{}}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="unknown trace record kind"):
        load_bundle(path)


def test_sqlite_round_trip_replace_and_missing(tmp_path: Path) -> None:
    bundle, _ = run_graph("baseline", "stored")
    store = SQLiteTraceStore(tmp_path / "nested/traces.db")
    store.save_bundle(bundle)
    store.save_bundle(bundle)
    assert store.load_run("stored") == bundle
    assert [run.run_id for run in store.list_runs()] == ["stored"]
    with pytest.raises(KeyError, match="was not found"):
        store.load_run("missing")


def test_sqlite_store_closes_every_connection(tmp_path: Path) -> None:
    bundle, _ = run_graph("baseline", "closed")
    store = SQLiteTraceStore(tmp_path / "traces.db")
    opened: list[sqlite3.Connection] = []
    real_connect = sqlite3.connect

    def tracking_connect(*args: object, **kwargs: object) -> sqlite3.Connection:
        connection = real_connect(*args, **kwargs)  # type: ignore[arg-type]
        opened.append(connection)
        return connection

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(sqlite3, "connect", tracking_connect)
        store.save_bundle(bundle)
        store.load_run("closed")
        store.list_runs()

    assert opened, "the store should have opened at least one connection"
    for connection in opened:
        with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
            connection.execute("SELECT 1")


def test_graph_run_rejects_mismatched_execution_run() -> None:
    bundle, _ = run_graph("baseline", "correct")
    raw = bundle.runs[0].model_dump()
    raw["run_id"] = "different"
    with pytest.raises(ValidationError, match="different run_id"):
        GraphRun.model_validate(raw)


def test_redacted_value_cannot_serialize_original() -> None:
    secret = "never-serialize-this"
    marker = RedactedValue(reason="sensitive")
    assert secret not in marker.model_dump_json()
    assert marker.model_dump() == {"redacted": True, "reason": "sensitive"}


def test_source_access_rejects_coerced_opened_flag() -> None:
    with pytest.raises(ValidationError):
        SourceAccess.model_validate(
            {
                "source_id": "s",
                "uri": "file:///s",
                "attempted_at": "2026-08-01T00:00:00Z",
                "opened": "yes",
            }
        )


def test_empty_bundle_is_valid() -> None:
    assert TraceBundle(runs=(), edge_observations=()).schema_version == "0.1"


def test_trace_v1_upgrade_assigns_singleton_causal_occurrences() -> None:
    legacy = legacy_demo_bundle("upgrade")

    upgraded = upgrade_trace_bundle_v1(legacy)

    assert upgraded.schema_version == "0.2"
    assert all(run.schema_version == "0.2" for run in upgraded.runs)
    assert all(item.schema_version == "0.2" for item in upgraded.runs[0].executions)
    assert all(item.schema_version == "0.2" for item in upgraded.edge_observations)
    assert len({item.occurrence_id for item in upgraded.runs[0].executions}) == 4
    assert upgraded.edge_observations[0].producer_occurrence_id == "node:0000:researcher"
    assert upgraded.edge_observations[0].consumer_occurrence_id == "node:0001:verifier"
    assert upgrade_trace_bundle_v1(upgraded) is upgraded


def test_trace_v1_upgrade_rejects_observation_without_executions() -> None:
    legacy = legacy_demo_bundle("missing-executions")
    without_executions = legacy.model_copy(
        update={
            "runs": (legacy.runs[0].model_copy(update={"executions": ()}),),
        }
    )

    with pytest.raises(ValueError, match="producer or consumer execution is missing"):
        upgrade_trace_bundle_v1(without_executions)


def test_singleton_trace_v1_and_v2_compare_without_fabricated_occurrence_pairing() -> None:
    legacy = legacy_demo_bundle("legacy-baseline")
    modern, _ = run_graph("baseline", "modern-candidate")
    contract = load_contract(ROOT / "examples/research_graph/contracts.yml")

    report = compare_semantics(contract, legacy, modern)

    assert report.status == "PASS"
    assert {item.occurrence_pairing for item in report.findings} == {"LOGICAL_SINGLETON"}


def test_sqlite_migrates_trace_v01_edge_primary_key(tmp_path: Path) -> None:
    legacy = legacy_demo_bundle("legacy-storage")
    database = tmp_path / "legacy.db"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE graph_runs (
                run_id TEXT PRIMARY KEY, graph_id TEXT NOT NULL, graph_version TEXT NOT NULL,
                variant TEXT NOT NULL, started_at TEXT NOT NULL, exported_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE edge_observations (
                run_id TEXT NOT NULL, edge_id TEXT NOT NULL, observed_at TEXT NOT NULL,
                payload_json TEXT NOT NULL, PRIMARY KEY (run_id, edge_id)
            );
            """
        )
        run = legacy.runs[0]
        connection.execute(
            "INSERT INTO graph_runs VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                run.run_id,
                run.graph_id,
                run.graph_version,
                run.variant,
                run.started_at.isoformat(),
                legacy.exported_at.isoformat(),
                run.model_dump_json(),
            ),
        )
        connection.executemany(
            "INSERT INTO edge_observations VALUES (?, ?, ?, ?)",
            [
                (
                    item.run_id,
                    item.edge_id,
                    item.observed_at.isoformat(),
                    item.model_dump_json(),
                )
                for item in legacy.edge_observations
            ],
        )

    store = SQLiteTraceStore(database)
    assert store.load_run("legacy-storage") == legacy
    with sqlite3.connect(database) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(edge_observations)")}
    assert {"occurrence_id", "schema_version"} <= columns
