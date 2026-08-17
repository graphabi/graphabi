from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError
from typer.testing import CliRunner

from graphabi.cli.app import app
from graphabi.contracts.models import Invariant
from graphabi.inference import ContractSuggestion, infer_contracts
from graphabi.models.traces import EdgeObservation, GraphRun, SourceAccess, TraceBundle
from graphabi.storage import SQLiteTraceStore

NOW = datetime(2026, 8, 17, 10, 0, tzinfo=UTC)


def run(
    run_id: str,
    *,
    graph_id: str = "inference_graph",
    variant: str = "baseline",
    status: str = "success",
) -> GraphRun:
    return GraphRun.model_validate(
        {
            "run_id": run_id,
            "graph_id": graph_id,
            "graph_version": "1",
            "variant": variant,
            "started_at": NOW,
            "ended_at": NOW,
            "status": status,
            "input": {},
            "output": {},
            "executions": [],
        }
    )


def observation(
    run_id: str,
    *,
    graph_id: str = "inference_graph",
    output: dict[str, object] | None = None,
    metadata: dict[str, object] | None = None,
    supporting_source: bool = False,
) -> EdgeObservation:
    sources = (
        (
            SourceAccess(
                source_id="fixture-source",
                uri="fixture://source",
                attempted_at=NOW,
                opened=True,
                supports_claim=True,
            ),
        )
        if supporting_source
        else ()
    )
    return EdgeObservation.model_validate(
        {
            "run_id": run_id,
            "graph_id": graph_id,
            "graph_version": "1",
            "edge_id": "producer_to_consumer",
            "producer": "producer",
            "consumer": "consumer",
            "input": {},
            "output": output or {},
            "metadata": metadata or {},
            "source_access": sources,
            "observed_at": NOW,
        }
    )


def bundle(*items: tuple[GraphRun, EdgeObservation]) -> TraceBundle:
    return TraceBundle(
        runs=tuple(item[0] for item in items),
        edge_observations=tuple(item[1] for item in items),
        exported_at=NOW,
    )


def empirical_bundle() -> TraceBundle:
    first = observation(
        "baseline-1",
        output={
            "verified": True,
            "entities": ["alpha", "beta"],
            "authority_level": "recommendation",
            "score": 0.8,
        },
        metadata={
            "required_entities": ["alpha"],
            "score_unit": "points",
            "evidence_observed_at": (NOW - timedelta(seconds=30)).isoformat(),
        },
        supporting_source=True,
    )
    second = observation(
        "baseline-2",
        output={
            "verified": True,
            "entities": ["alpha"],
            "authority_level": "suggestion",
            "score": 80,
        },
        metadata={
            "required_entities": ["alpha", "beta"],
            "score_unit": "percent",
            "evidence_observed_at": (NOW - timedelta(seconds=45)).isoformat(),
        },
    )
    third = observation("baseline-3", output={"verified": False})
    failed = observation(
        "failed-1",
        output={"verified": True, "score": 1},
        metadata={"score_unit": "hostile-unit"},
    )
    return bundle(
        (run("baseline-1"), first),
        (run("baseline-2"), second),
        (run("baseline-3"), third),
        (run("failed-1", status="error"), failed),
    )


def by_evaluator(trace: TraceBundle) -> dict[str, ContractSuggestion]:
    return {item.evaluator: item for item in infer_contracts(trace)}


def test_inference_reports_counts_ratios_evidence_and_valid_yaml() -> None:
    suggestions = by_evaluator(empirical_bundle())

    provenance = suggestions["provenance"]
    assert provenance.status == "SUGGESTED"
    assert provenance.enforcement == "NOT ENFORCED"
    assert provenance.label == "SUGGESTED: NOT ENFORCED"
    assert provenance.observation_count == 2
    assert provenance.supporting_observation_count == 1
    assert provenance.counterexample_count == 1
    assert provenance.insufficient_evidence_count == 0
    assert provenance.empirical_support_ratio == 0.5
    assert provenance.confidence == provenance.empirical_support_ratio
    assert {item.outcome for item in provenance.evidence} == {
        "SUPPORTING",
        "COUNTEREXAMPLE",
    }

    preservation = suggestions["set_preservation"]
    assert preservation.observation_count == 3
    assert preservation.supporting_observation_count == 1
    assert preservation.counterexample_count == 1
    assert preservation.insufficient_evidence_count == 1
    assert preservation.empirical_support_ratio == 0.5

    units = suggestions["unit_consistency"]
    assert units.observation_count == 3
    assert units.supporting_observation_count == 1
    assert units.counterexample_count == 1
    assert units.insufficient_evidence_count == 1
    assert "hostile-unit" not in units.model_dump_json()

    authority = suggestions["authority"]
    assert authority.supporting_observation_count == 2
    assert authority.insufficient_evidence_count == 1
    assert authority.empirical_support_ratio == 1

    freshness = suggestions["freshness"]
    assert freshness.supporting_observation_count == 2
    assert freshness.insufficient_evidence_count == 1

    for suggestion in suggestions.values():
        Invariant.model_validate(yaml.safe_load(suggestion.yaml_snippet))


def test_inference_is_deterministic_under_trace_ordering() -> None:
    trace = empirical_bundle()
    reordered = trace.model_copy(
        update={
            "runs": tuple(reversed(trace.runs)),
            "edge_observations": tuple(reversed(trace.edge_observations)),
        }
    )

    assert infer_contracts(trace) == infer_contracts(reordered)


def test_inference_rejects_mixed_graph_identities() -> None:
    trace = bundle(
        (run("one"), observation("one")),
        (run("two", graph_id="other"), observation("two", graph_id="other")),
    )

    with pytest.raises(ValueError, match="requires one graph identity"):
        infer_contracts(trace)


def test_suggestion_model_rejects_inconsistent_counts() -> None:
    with pytest.raises(ValidationError, match="partition observation_count"):
        ContractSuggestion(
            suggestion_id="edge.candidate",
            edge="edge",
            evaluator="provenance",
            observation_count=2,
            supporting_observation_count=1,
            counterexample_count=0,
            insufficient_evidence_count=0,
            empirical_support_ratio=1,
            confidence=1,
            reason="test",
            evidence=(),
            yaml_snippet="id: candidate",
        )


def test_cli_aggregates_matching_baselines_and_repeated_run_options(tmp_path: Path) -> None:
    database = tmp_path / "traces.db"
    store = SQLiteTraceStore(database)
    for run_id in ("baseline-1", "baseline-2"):
        store.save_bundle(
            bundle(
                (
                    run(run_id),
                    observation(
                        run_id,
                        output={"verified": True},
                        supporting_source=True,
                    ),
                )
            )
        )
    runner = CliRunner()

    default = runner.invoke(
        app,
        ["--json-output", "infer", "--database", str(database)],
    )
    assert default.exit_code == 0
    default_provenance = next(
        item for item in yaml.safe_load(default.output) if item["evaluator"] == "provenance"
    )
    assert default_provenance["observation_count"] == 2

    selected = runner.invoke(
        app,
        [
            "--json-output",
            "infer",
            "--database",
            str(database),
            "--run",
            "baseline-1",
            "--run",
            "baseline-2",
        ],
    )
    assert selected.exit_code == 0
    assert yaml.safe_load(selected.output) == yaml.safe_load(default.output)


def test_cli_rejects_duplicate_or_non_baseline_runs(tmp_path: Path) -> None:
    database = tmp_path / "traces.db"
    store = SQLiteTraceStore(database)
    store.save_bundle(bundle((run("candidate", variant="candidate"), observation("candidate"))))
    runner = CliRunner()

    invalid = runner.invoke(
        app,
        ["infer", "--database", str(database), "--run", "candidate"],
    )
    assert invalid.exit_code == 1
    assert "requires successful baseline runs" in invalid.output

    duplicate = runner.invoke(
        app,
        [
            "infer",
            "--database",
            str(database),
            "--run",
            "candidate",
            "--run",
            "candidate",
        ],
    )
    assert duplicate.exit_code == 1
    assert "duplicate run ID" in duplicate.output
