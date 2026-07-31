from pathlib import Path

import pytest
from examples.research_graph.graph import run_graph
from pydantic import ValidationError

from graphabi.models.traces import GraphRun, RedactedValue, TraceBundle
from graphabi.storage import SQLiteTraceStore
from graphabi.traces import export_json, export_jsonl, load_bundle


def test_trace_json_and_jsonl_round_trip(tmp_path: Path) -> None:
    bundle, _ = run_graph("baseline", "roundtrip")
    json_path = tmp_path / "trace.json"
    jsonl_path = tmp_path / "trace.jsonl"
    export_json(bundle, json_path)
    export_jsonl(bundle, jsonl_path)
    assert load_bundle(json_path) == bundle
    jsonl = load_bundle(jsonl_path)
    assert jsonl.runs == bundle.runs
    assert jsonl.edge_observations == bundle.edge_observations


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


def test_empty_bundle_is_valid() -> None:
    assert TraceBundle(runs=(), edge_observations=()).schema_version == "0.1"
