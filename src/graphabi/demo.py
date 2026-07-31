"""Orchestration for the deterministic, fully local GraphABI demonstration."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from jsonschema import validate as validate_json_schema

from graphabi.comparison import compare_schemas, compare_semantics
from graphabi.contracts import load_contract
from graphabi.models.traces import TraceBundle
from graphabi.reporting import CompatibilityReport, write_report
from graphabi.storage import SQLiteTraceStore
from graphabi.traces import export_json, export_jsonl


@dataclass(frozen=True)
class DemoResult:
    report: CompatibilityReport
    report_json: Path
    report_html: Path
    database: Path


def project_root(start: Path | None = None) -> Path:
    """Find a checkout containing the deterministic example assets."""
    package_file = Path(__file__).resolve()
    candidates = [
        start or Path.cwd(),
        package_file.parents[1],
        package_file.parents[2],
    ]
    for candidate in candidates:
        candidate = candidate.resolve()
        for directory in (candidate, *candidate.parents):
            if (directory / "examples/research_graph/contracts.yml").is_file():
                return directory
    raise FileNotFoundError(
        "GraphABI demo assets were not found. Reinstall GraphABI or run from a source checkout."
    )


def _clean_directory(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def run_demo(root: Path | None = None) -> DemoResult:
    """Run both graphs, store real traces, compare them, and generate reports."""
    assets_root = project_root(root)
    output_root = (root or Path.cwd()).resolve()
    runtime = output_root / ".graphabi/demo"
    report_directory = output_root / ".graphabi/reports/latest"
    _clean_directory(runtime)
    _clean_directory(report_directory)

    # Import is intentionally local: the broken candidate remains an example fixture,
    # outside production package code and unavailable to the core comparison engine.
    from examples.research_graph.graph import run_graph
    from examples.research_graph.models import ResearchResult

    baseline_bundle, baseline_result = run_graph("baseline", "baseline-001")
    candidate_bundle, candidate_result = run_graph("candidate", "candidate-003")
    baseline_schema = ResearchResult.model_json_schema()
    candidate_schema = candidate_result.__class__.model_json_schema()
    validate_json_schema(baseline_result.model_dump(mode="json"), baseline_schema)
    validate_json_schema(candidate_result.model_dump(mode="json"), candidate_schema)
    structural = compare_schemas(
        baseline_schema,
        candidate_schema,
        same_pydantic_model=baseline_result.__class__ is candidate_result.__class__,
    )

    contract = load_contract(assets_root / "examples/research_graph/contracts.yml")
    combined = TraceBundle(
        runs=baseline_bundle.runs + candidate_bundle.runs,
        edge_observations=baseline_bundle.edge_observations + candidate_bundle.edge_observations,
    )
    database = runtime / "traces.db"
    store = SQLiteTraceStore(database)
    store.save_bundle(combined)
    export_json(baseline_bundle, runtime / "baseline.json")
    export_json(candidate_bundle, runtime / "candidate.json")
    export_jsonl(combined, runtime / "traces.jsonl")
    recorded_baseline = store.load_run(baseline_bundle.runs[0].run_id)
    recorded_candidate = store.load_run(candidate_bundle.runs[0].run_id)
    baseline_semantic = compare_semantics(contract, recorded_baseline, recorded_baseline)
    if baseline_semantic.status != "PASS":
        raise RuntimeError("the deterministic baseline violated its enforced semantic contract")
    semantic = compare_semantics(contract, recorded_baseline, recorded_candidate)

    report = CompatibilityReport(
        graph=contract.graph,
        baseline_run_id=recorded_baseline.runs[0].run_id,
        candidate_run_id=recorded_candidate.runs[0].run_id,
        structural=structural,
        semantic=semantic,
        limitations=(
            "GraphABI proves only the explicit deterministic contracts evaluated for "
            "observed traces.",
            "A passing result does not establish universal semantic equivalence or behavior "
            "on unseen inputs.",
            "Contract inference is observational and never becomes enforced without human review.",
        ),
        reproduction_command="graphabi demo --allow-breaking",
    )
    report_json, report_html = write_report(report, contract, report_directory)
    return DemoResult(
        report=report,
        report_json=report_json,
        report_html=report_html,
        database=database,
    )
