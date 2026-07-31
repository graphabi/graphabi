from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from graphabi.cli.app import app
from graphabi.comparison import compare_schemas, compare_semantics
from graphabi.comparison.models import SemanticReport
from graphabi.contracts import ContractLoadError, load_contract
from graphabi.contracts.models import Contract
from graphabi.demo import run_demo
from graphabi.models import EdgeObservation, GraphRun, NodeExecution, RedactedValue, TraceBundle
from graphabi.reporting import CompatibilityReport, write_report
from graphabi.storage import SQLiteTraceStore
from graphabi.traces import load_bundle

NOW = datetime(2026, 8, 1, tzinfo=UTC)


def run(run_id: str, executions: tuple[NodeExecution, ...] = ()) -> GraphRun:
    return GraphRun(
        run_id=run_id,
        graph_id="g",
        graph_version="1",
        started_at=NOW,
        ended_at=NOW,
        status="success",
        input={},
        output={},
        executions=executions,
    )


def observation(
    run_id: str,
    *,
    output: dict[str, object] | None = None,
    metadata: dict[str, object] | None = None,
) -> EdgeObservation:
    return EdgeObservation(
        run_id=run_id,
        graph_id="g",
        graph_version="1",
        edge_id="edge",
        producer="p",
        consumer="c",
        input={},
        output=output or {"value": "ok"},
        metadata=metadata or {},
        observed_at=NOW,
    )


def contract() -> Contract:
    return Contract.model_validate(
        {
            "version": "0.1",
            "graph": "g",
            "nodes": [{"id": "p"}, {"id": "c", "terminal": True}],
            "edges": [
                {
                    "id": "edge",
                    "producer": "p",
                    "consumer": "c",
                    "invariants": [
                        {
                            "id": "nested",
                            "evaluator": "implication",
                            "description": "flag requires proof",
                            "when": {"path": "output.payload.flag", "equals": True},
                            "require": {"path": "metadata.proof", "equals": True},
                        }
                    ],
                }
            ],
        }
    )


def test_duplicate_run_ids_are_rejected_before_storage() -> None:
    with pytest.raises(ValidationError, match="run IDs must be unique"):
        TraceBundle(runs=(run("duplicate"), run("duplicate")), edge_observations=())


def test_duplicate_node_execution_identity_is_rejected() -> None:
    execution = NodeExecution(
        run_id="r",
        graph_id="g",
        graph_version="1",
        node_id="node",
        input={},
        output={},
        started_at=NOW,
        ended_at=NOW,
        duration_ms=0,
        status="success",
        framework="test",
        framework_version="1",
    )
    with pytest.raises(ValidationError, match="node execution IDs must be unique"):
        run("r", (execution, execution))


def test_duplicate_edge_observations_are_rejected_for_trace_schema_v01() -> None:
    with pytest.raises(ValidationError, match="edge observations must be unique"):
        TraceBundle(
            runs=(run("r"),),
            edge_observations=(observation("r"), observation("r")),
        )


def test_edge_observation_must_match_its_run_graph_identity() -> None:
    mismatched = observation("r").model_copy(update={"graph_id": "other"})
    with pytest.raises(ValidationError, match="different graph identity"):
        TraceBundle(runs=(run("r"),), edge_observations=(mismatched,))


def test_semantic_comparison_rejects_ambiguous_multi_run_bundles() -> None:
    multi = TraceBundle(
        runs=(run("one"), run("two")),
        edge_observations=(observation("one"), observation("two")),
    )
    with pytest.raises(ValueError, match="exactly one baseline run"):
        compare_semantics(contract(), multi, multi)


def test_nested_witness_redaction_does_not_retain_unrelated_secret() -> None:
    secret = "sk-" + "hostile-audit-secret-value"
    trace = TraceBundle(
        runs=(run("r"),),
        edge_observations=(
            observation(
                "r",
                output={"payload": {"flag": True, "unrelated_secret": secret}},
                metadata={"proof": False},
            ),
        ),
    )
    finding = compare_semantics(contract(), trace, trace).breaking_findings[0]

    assert secret not in finding.witness.model_dump_json()
    assert secret not in repr(finding.witness)
    assert finding.witness.relevant_output["payload"]["flag"] is True
    assert finding.witness.relevant_output["payload"]["_unrelated"] == RedactedValue().model_dump(
        mode="json"
    )


def test_witness_redacts_unselected_list_items_and_nested_siblings() -> None:
    secret = "ghp_" + "abcdefghijklmnopqrstuvwxyz123456"
    list_contract = Contract.model_validate(
        {
            "version": "0.1",
            "graph": "g",
            "nodes": [{"id": "p"}, {"id": "c"}],
            "edges": [
                {
                    "id": "edge",
                    "producer": "p",
                    "consumer": "c",
                    "invariants": [
                        {
                            "id": "list_path",
                            "evaluator": "implication",
                            "description": "selected list value requires proof",
                            "when": {"path": "output.items.0.flag", "equals": True},
                            "require": {"path": "metadata.proof", "equals": True},
                        }
                    ],
                }
            ],
        }
    )
    trace = TraceBundle(
        runs=(run("r"),),
        edge_observations=(
            observation(
                "r",
                output={
                    "items": [
                        {"flag": True, "token": secret},
                        {"entirely_unrelated": secret},
                    ]
                },
                metadata={"proof": False},
            ),
        ),
    )
    witness = compare_semantics(list_contract, trace, trace).breaking_findings[0].witness
    assert secret not in witness.model_dump_json()
    assert witness.relevant_output["items"][0]["flag"] is True
    assert witness.relevant_output["items"][1] == RedactedValue().model_dump(mode="json")


def test_report_masks_secret_like_values_and_escapes_html(tmp_path: Path) -> None:
    secret = "sk-" + "hostile-audit-secret-value"
    html_payload = "<script>alert('hostile')</script>"
    trace = TraceBundle(
        runs=(run("r"),),
        edge_observations=(
            observation(
                "r",
                output={
                    "payload": {
                        "flag": True,
                        "api_key": secret,
                        "markup": html_payload,
                    }
                },
                metadata={"proof": False},
            ),
        ),
    )
    semantic = compare_semantics(contract(), trace, trace)
    structural = compare_schemas(
        {"type": "object", "properties": {}},
        {"type": "object", "properties": {}},
    )
    report = CompatibilityReport(
        graph="g",
        baseline_run_id="r",
        candidate_run_id="r",
        structural=structural,
        semantic=semantic,
        limitations=(),
        reproduction_command="graphabi compare",
    )
    assert secret not in repr(report)
    assert secret not in report.model_dump_json()
    json_path, html_path = write_report(report, contract(), tmp_path)
    rendered_json = json_path.read_text(encoding="utf-8")
    rendered_html = html_path.read_text(encoding="utf-8")

    assert secret not in rendered_json
    assert secret not in rendered_html
    assert html_payload not in rendered_html
    assert "&lt;script&gt;" in rendered_html


@pytest.mark.parametrize(
    "contents",
    [
        "version: '0.1'\ngraph: missing_everything\n",
        "version: '0.1'\ngraph: g\nnodes: []\nedges: []\n",
        (
            "version: '0.1'\ngraph: g\nnodes: [{id: p}, {id: c}]\nedges:\n"
            "  - id: edge\n    producer: p\n    consumer: c\n    invariants:\n"
            "      - {id: x, evaluator: completeness, description: x, "
            "destination_path: 'output..value'}\n"
        ),
    ],
)
def test_malformed_contracts_fail_with_context(tmp_path: Path, contents: str) -> None:
    path = tmp_path / "bad.yml"
    path.write_text(contents, encoding="utf-8")
    with pytest.raises(ContractLoadError) as captured:
        load_contract(path)
    message = str(captured.value)
    assert str(path) in message
    assert "invalid field=" in message
    assert "suggested correction=" in message


def test_unknown_evaluator_is_not_reported_as_valid_by_cli(tmp_path: Path) -> None:
    path = tmp_path / "unknown.yml"
    path.write_text(
        """version: "0.1"
graph: g
nodes: [{id: p}, {id: c}]
edges:
  - id: edge
    producer: p
    consumer: c
    invariants:
      - {id: x, evaluator: absent_plugin, description: external}
""",
        encoding="utf-8",
    )
    result = CliRunner().invoke(app, ["--plain", "check", str(path)])
    assert result.exit_code == 3
    assert "UNKNOWN" in result.output
    assert "absent_plugin" in result.output
    allowed = CliRunner().invoke(
        app,
        ["--plain", "check", str(path), "--allow-unregistered"],
    )
    assert allowed.exit_code == 0
    assert "PASS" in allowed.output


def test_storage_rolls_back_entire_bundle_after_mid_transaction_failure(tmp_path: Path) -> None:
    store = SQLiteTraceStore(tmp_path / "trace.db")
    original = TraceBundle(runs=(run("r"),), edge_observations=(observation("r"),))
    store.save_bundle(original)
    duplicate = TraceBundle.model_construct(
        runs=(run("r"),),
        edge_observations=(observation("r"), observation("r")),
        schema_version="0.1",
        exported_at=NOW,
    )

    with pytest.raises(sqlite3.IntegrityError):
        store.save_bundle(duplicate)
    assert store.load_run("r") == original


def test_corrupt_sqlite_payload_raises_contextual_storage_error(tmp_path: Path) -> None:
    store = SQLiteTraceStore(tmp_path / "trace.db")
    store.save_bundle(TraceBundle(runs=(run("r"),), edge_observations=(observation("r"),)))
    with sqlite3.connect(store.path) as connection:
        connection.execute("UPDATE graph_runs SET payload_json = 'not-json' WHERE run_id = 'r'")

    with pytest.raises(ValueError, match=r"trace database.*run 'r'.*corrupt"):
        store.load_run("r")


def test_jsonl_scalar_and_missing_data_fail_with_file_and_line(tmp_path: Path) -> None:
    scalar = tmp_path / "scalar.jsonl"
    scalar.write_text("42\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r"scalar.jsonl:1: trace record must be a JSON object"):
        load_bundle(scalar)
    missing = tmp_path / "missing.jsonl"
    missing.write_text('{"kind":"graph_run"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match=r"missing.jsonl:1: trace record is missing 'data'"):
        load_bundle(missing)


def test_extremely_deep_payload_fails_as_validation_error_not_recursion_crash() -> None:
    value: object = "bottom"
    for _ in range(1000):
        value = {"nested": value}
    raw = observation("r").model_dump()
    raw["output"] = {"deep": value}
    with pytest.raises(ValidationError):
        EdgeObservation.model_validate(raw)


def test_validation_exception_hides_secret_input_value() -> None:
    secret = "sk-" + "hostile-audit-secret-value"
    raw = observation("r", output={"api_key": secret}).model_dump()
    raw["run_id"] = None
    with pytest.raises(ValidationError) as captured:
        EdgeObservation.model_validate(raw)
    assert secret not in str(captured.value)
    assert secret not in repr(captured.value)


def test_naive_trace_timestamp_is_rejected_before_freshness_math() -> None:
    raw = observation("r").model_dump()
    raw["observed_at"] = datetime(2026, 8, 1)
    with pytest.raises(ValidationError, match="timezone"):
        EdgeObservation.model_validate(raw)


def test_unicode_and_long_strings_round_trip_through_sqlite(tmp_path: Path) -> None:
    value = "意味🔐" + "長" * 100_000
    bundle = TraceBundle(
        runs=(run("unicode"),),
        edge_observations=(observation("unicode", output={"value": value}),),
    )
    store = SQLiteTraceStore(tmp_path / "trace.db")
    store.save_bundle(bundle)
    assert store.load_run("unicode") == bundle


def test_empty_trace_record_command_fails_actionably(tmp_path: Path) -> None:
    trace = tmp_path / "empty.json"
    trace.write_text(
        json.dumps({"schema_version": "0.1", "runs": [], "edge_observations": []}),
        encoding="utf-8",
    )
    result = CliRunner().invoke(
        app,
        ["--plain", "record", str(trace), "--database", str(tmp_path / "trace.db")],
    )
    assert result.exit_code == 1
    assert "at least one run" in result.output


def test_unknown_and_insufficient_results_never_become_pass() -> None:
    trace = TraceBundle(runs=(run("r"),), edge_observations=())
    missing = compare_semantics(contract(), trace, trace)
    assert missing.status == "INSUFFICIENT_EVIDENCE"
    assert "PASS" not in {finding.status for finding in missing.findings}

    unknown_contract = contract().model_copy(
        update={
            "edges": (
                contract()
                .edges[0]
                .model_copy(
                    update={
                        "invariants": (
                            contract()
                            .edges[0]
                            .invariants[0]
                            .model_copy(update={"evaluator": "not_registered"}),
                        )
                    }
                ),
            )
        }
    )
    observed = TraceBundle(runs=(run("r"),), edge_observations=(observation("r"),))
    unknown = compare_semantics(unknown_contract, observed, observed)
    assert unknown.status == "UNKNOWN"
    assert unknown.findings[0].status == "UNKNOWN"


def test_semantic_report_model_rejects_pass_with_breaking_finding() -> None:
    trace = TraceBundle(
        runs=(run("r"),),
        edge_observations=(
            observation("r", output={"payload": {"flag": True}}, metadata={"proof": False}),
        ),
    )
    finding = compare_semantics(contract(), trace, trace).breaking_findings[0]
    with pytest.raises(ValidationError, match="PASS report cannot contain"):
        SemanticReport(status="PASS", findings=(finding,))


def test_demo_report_semantics_equal_re_evaluation_of_persisted_traces(tmp_path: Path) -> None:
    result = run_demo(tmp_path)
    store = SQLiteTraceStore(result.database)
    baseline = store.load_run(result.report.baseline_run_id)
    candidate = store.load_run(result.report.candidate_run_id)
    enforced = load_contract(
        Path(__file__).resolve().parents[2] / "examples/research_graph/contracts.yml"
    )
    assert result.report.semantic == compare_semantics(enforced, baseline, candidate)


def test_cli_structural_comparison_checks_every_contract_edge_and_exits_two(
    tmp_path: Path,
) -> None:
    contract_path = tmp_path / "contract.yml"
    contract_path.write_text(
        """version: "0.1"
graph: g
nodes: [{id: p}, {id: middle}, {id: c, terminal: true}]
edges:
  - id: first
    producer: p
    consumer: middle
    invariants:
      - id: first_value
        evaluator: completeness
        description: value
        destination_path: output.value
  - id: second
    producer: middle
    consumer: c
    invariants:
      - id: second_value
        evaluator: completeness
        description: value
        destination_path: output.value
""",
        encoding="utf-8",
    )

    def edge_observation(
        run_id: str, edge_id: str, producer: str, consumer: str, value: object
    ) -> EdgeObservation:
        return EdgeObservation(
            run_id=run_id,
            graph_id="g",
            graph_version="1",
            edge_id=edge_id,
            producer=producer,
            consumer=consumer,
            input={},
            output={"value": value},
            observed_at=NOW,
        )

    baseline = TraceBundle(
        runs=(run("structural-before"),),
        edge_observations=(
            edge_observation("structural-before", "first", "p", "middle", "same"),
            edge_observation("structural-before", "second", "middle", "c", 1),
        ),
    )
    candidate = TraceBundle(
        runs=(run("structural-after"),),
        edge_observations=(
            edge_observation("structural-after", "first", "p", "middle", "same"),
            edge_observation("structural-after", "second", "middle", "c", "one"),
        ),
    )
    database = tmp_path / "traces.db"
    store = SQLiteTraceStore(database)
    store.save_bundle(baseline)
    store.save_bundle(candidate)

    result = CliRunner().invoke(
        app,
        [
            "--plain",
            "compare",
            "--baseline-run",
            "structural-before",
            "--candidate-run",
            "structural-after",
            "--contract",
            str(contract_path),
            "--database",
            str(database),
        ],
    )
    assert result.exit_code == 2
    assert "Structural: FAIL" in result.output
    assert "Semantic: PASS" in result.output
