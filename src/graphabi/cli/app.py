"""The public `graphabi` command-line interface."""

from __future__ import annotations

import json
import os
import platform
import sqlite3
import sys
import tempfile
import webbrowser
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Annotated, Any, Never

import typer
import uvicorn
import yaml
from rich.console import Console
from rich.table import Table

from graphabi import __version__
from graphabi.adapters.otel import load_otlp_json
from graphabi.comparison import ContractCoverage, compare_schemas, compare_semantics
from graphabi.contracts import ContractLoadError, load_contract
from graphabi.contracts.evaluators import default_registry
from graphabi.contracts.models import Contract
from graphabi.demo import project_root, run_demo
from graphabi.inference import infer_contracts
from graphabi.models.traces import TraceBundle
from graphabi.reporting import CompatibilityReport, write_report
from graphabi.reporting.server import create_report_app
from graphabi.storage import SQLiteTraceStore, TraceStoreError
from graphabi.traces import export_json, load_bundle

app = typer.Typer(
    name="graphabi",
    help="Consumer-driven Semantic Compatibility Infrastructure for agent graph edges.",
    no_args_is_help=True,
    rich_markup_mode="markdown",
)


@dataclass
class CLIState:
    plain: bool = False
    json_output: bool = False
    verbose: bool = False
    no_color: bool = False

    @property
    def console(self) -> Console:
        return Console(no_color=self.no_color, force_terminal=False if self.plain else None)


def _state(context: typer.Context) -> CLIState:
    return context.ensure_object(CLIState)


@app.callback()
def main(
    context: typer.Context,
    plain: Annotated[bool, typer.Option("--plain", help="Use stable plain text for CI.")] = False,
    json_output: Annotated[
        bool, typer.Option("--json-output", help="Emit JSON for commands that support it.")
    ] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Show diagnostics.")] = False,
    no_color: Annotated[bool, typer.Option("--no-color", help="Disable terminal colors.")] = False,
) -> None:
    """Configure output shared by all commands."""
    context.obj = CLIState(plain=plain, json_output=json_output, verbose=verbose, no_color=no_color)


def _fail(message: str, *, code: int = 1) -> Never:
    typer.echo(f"GraphABI error: {message}", err=True)
    raise typer.Exit(code)


def _latest_report() -> Path:
    local = Path.cwd().resolve() / ".graphabi/reports/latest/index.html"
    if local.is_file():
        return local
    try:
        return project_root() / ".graphabi/reports/latest/index.html"
    except FileNotFoundError:
        return local


@app.command()
def doctor(context: typer.Context) -> None:
    """Check the local runtime, storage, demo contract, and LangGraph adapter."""
    state = _state(context)
    checks: list[dict[str, str]] = []

    def add(name: str, passed: bool, detail: str) -> None:
        checks.append({"check": name, "status": "PASS" if passed else "FAIL", "detail": detail})

    add("Python", (3, 12) <= sys.version_info[:2] < (3, 14), platform.python_version())
    add("Package", True, f"graphabi {__version__}")
    supported_architectures = {"arm64", "aarch64", "x86_64", "AMD64"}
    add(
        "Architecture",
        platform.machine() in supported_architectures,
        f"{platform.system()} {platform.machine()}",
    )
    try:
        with tempfile.NamedTemporaryFile(dir=Path.cwd()):
            pass
        add("Project writable", True, str(Path.cwd()))
    except OSError as exc:
        add("Project writable", False, str(exc))
    try:
        sqlite3.connect(":memory:").execute("SELECT 1").fetchone()
        add("SQLite", True, sqlite3.sqlite_version)
    except sqlite3.Error as exc:
        add("SQLite", False, str(exc))
    try:
        root = project_root()
        contract = load_contract(root / "examples/research_graph/contracts.yml")
        add("Contract parsing", True, f"contract schema {contract.version}")
    except (FileNotFoundError, ContractLoadError) as exc:
        add("Contract parsing", False, str(exc))
        root = Path.cwd()
    try:
        langgraph_version = version("langgraph")
        langgraph_parts = tuple(int(part) for part in langgraph_version.split(".")[:2])
        add(
            "LangGraph adapter",
            (1, 0) <= langgraph_parts < (1, 3),
            f"langgraph {langgraph_version}; supported >=1.0,<1.3",
        )
    except PackageNotFoundError:
        add("LangGraph adapter", False, "install the default project dependencies")
    latest = _latest_report()
    checks.append(
        {
            "check": "Latest report",
            "status": "PASS" if latest.is_file() else "INFO",
            "detail": (
                str(latest)
                if latest.is_file()
                else "optional; run `graphabi demo --allow-breaking` to create one"
            ),
        }
    )
    if state.json_output:
        typer.echo(json.dumps({"checks": checks}, indent=2))
    elif state.plain:
        for item in checks:
            typer.echo(f"{item['status']} {item['check']}: {item['detail']}")
    else:
        table = Table(title="GraphABI doctor")
        table.add_column("Check")
        table.add_column("Status")
        table.add_column("Detail")
        for item in checks:
            table.add_row(item["check"], item["status"], item["detail"])
        state.console.print(table)
    if any(item["status"] == "FAIL" and item["check"] != "Latest report" for item in checks):
        raise typer.Exit(1)


STARTER_CONTRACT = """version: "0.2"
graph: my_graph
nodes:
  - id: producer
  - id: consumer
    terminal: true
graph_edges:
  - id: producer_to_consumer
    producer: producer
    consumer: consumer
edges:
  - id: producer_to_consumer
    producer: producer
    consumer: consumer
    invariants:
      - id: required_value_non_empty
        evaluator: completeness
        description: The consumer requires a non-empty value.
        severity: breaking
        destination_path: output.value
"""


def _coverage_lines(coverage: ContractCoverage) -> list[str]:
    summary = coverage.summary
    return [
        f"Graph nodes: {summary.total_graph_nodes}",
        f"Graph edges: {summary.total_graph_edges}",
        f"Contracted: {summary.contracted_edges}",
        f"Uncontracted: {summary.uncontracted_edges}",
        f"Observed: {summary.observed_edges}",
        f"Unobserved: {summary.unobserved_edges}",
        f"Contracted and observed: {summary.contracted_and_observed}",
        f"Contracted but unobserved: {summary.contracted_but_unobserved}",
        f"Observed but uncontracted: {summary.observed_but_uncontracted}",
        f"Branches with insufficient evidence: {summary.branches_with_insufficient_evidence}",
        f"Observed contract coverage: {summary.observed_contract_coverage_percent:.1f}%",
        "Coverage is not correctness.",
    ]


@app.command("init")
def init_command(
    context: typer.Context,
    directory: Annotated[Path, typer.Argument(help="Project directory.")] = Path(),
    force: Annotated[
        bool, typer.Option("--force", help="Replace an existing starter contract.")
    ] = False,
) -> None:
    """Create a documented starter contract under .graphabi/."""
    del context
    target = directory.resolve() / ".graphabi/contracts.yml"
    if target.exists() and not force:
        _fail(f"{target} already exists; pass --force to replace it")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(STARTER_CONTRACT, encoding="utf-8")
    typer.echo(f"Created {target}")


@app.command()
def record(
    context: typer.Context,
    trace: Annotated[Path, typer.Argument(help="Trace bundle (.json or .jsonl).")],
    database: Annotated[
        Path, typer.Option("--database", "-d", help="SQLite trace database.")
    ] = Path(".graphabi/traces.db"),
) -> None:
    """Import framework-independent JSON or JSONL traces into SQLite."""
    del context
    try:
        bundle = load_bundle(trace)
        if not bundle.runs:
            _fail(f"could not record {trace}: trace bundle must contain at least one run")
        SQLiteTraceStore(database).save_bundle(bundle)
    except (OSError, ValueError, sqlite3.Error) as exc:
        _fail(f"could not record {trace}: {exc}")
    typer.echo(
        f"Recorded {len(bundle.runs)} run(s) and {len(bundle.edge_observations)} "
        f"edge observation(s) in {database}"
    )


@app.command("import-otel")
def import_otel_command(
    context: typer.Context,
    trace: Annotated[Path, typer.Argument(help="Local OTLP/JSON trace export.")],
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="GraphABI TraceBundle JSON output.",
        ),
    ] = Path(".graphabi/imports/latest.json"),
) -> None:
    """Import the supported OTLP/JSON and OpenInference mapping profile."""
    state = _state(context)
    try:
        result = load_otlp_json(trace)
        export_json(result.bundle, output)
    except (OSError, ValueError) as exc:
        _fail(
            f"could not import {trace}: {exc}; supply an OTLP/JSON ExportTraceServiceRequest "
            "using lowerCamelCase protobuf JSON fields"
        )
    summary = {
        "status": result.status,
        "profile": result.profile,
        "source_span_count": result.source_span_count,
        "imported_run_count": result.imported_run_count,
        "imported_node_count": result.imported_node_count,
        "imported_edge_count": result.imported_edge_count,
        "output": str(output),
        "diagnostics": [item.model_dump(mode="json") for item in result.diagnostics],
    }
    if state.json_output:
        typer.echo(json.dumps(summary, indent=2))
    else:
        typer.echo(
            f"{result.status} Imported {result.imported_run_count} run(s), "
            f"{result.imported_node_count} node occurrence(s), and "
            f"{result.imported_edge_count} edge observation(s) to {output}"
        )
        for diagnostic in result.diagnostics:
            location = diagnostic.span_id or diagnostic.trace_id or "document"
            typer.echo(f"{diagnostic.status} {diagnostic.code} [{location}]: {diagnostic.message}")
    if result.status == "UNKNOWN":
        raise typer.Exit(3)


@app.command()
def infer(
    context: typer.Context,
    run_id: Annotated[
        str | None, typer.Option("--run", help="Baseline run ID; latest when omitted.")
    ] = None,
    database: Annotated[Path, typer.Option("--database", "-d")] = Path(".graphabi/demo/traces.db"),
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
) -> None:
    """Suggest unenforced contracts from successful baseline observations."""
    state = _state(context)
    store = SQLiteTraceStore(database)
    try:
        if run_id is None:
            runs = [run for run in store.list_runs() if run.variant == "baseline"]
            if not runs:
                _fail(f"no baseline runs in {database}; run `graphabi demo --allow-breaking`")
            run_id = runs[-1].run_id
        bundle = store.load_run(run_id)
    except (sqlite3.Error, KeyError, TraceStoreError) as exc:
        _fail(str(exc))
    suggestions = infer_contracts(bundle)
    data = [item.model_dump(mode="json") for item in suggestions]
    rendered = (
        json.dumps(data, indent=2)
        if state.json_output
        else yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    )
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        typer.echo(f"Wrote {len(suggestions)} suggestions to {output}; none are enforced")
    else:
        typer.echo(rendered)


@app.command()
def check(
    context: typer.Context,
    contract: Annotated[Path, typer.Argument(help="Contract YAML to validate.")],
    allow_unregistered: Annotated[
        bool,
        typer.Option(
            "--allow-unregistered",
            help="Accept evaluator names supplied later by a Python registry.",
        ),
    ] = False,
) -> None:
    """Validate a contract with contextual correction messages."""
    state = _state(context)
    try:
        parsed = load_contract(contract)
    except ContractLoadError as exc:
        _fail(str(exc))
    registered = set(default_registry().names)
    unknown = sorted(
        {
            invariant.evaluator
            for edge in parsed.edges
            for invariant in edge.invariants
            if invariant.evaluator not in registered
        }
    )
    if unknown and not allow_unregistered:
        result = {
            "status": "UNKNOWN",
            "graph": parsed.graph,
            "unregistered_evaluators": unknown,
            "suggestion": (
                "register these evaluators in Python or pass --allow-unregistered "
                "for schema-only validation"
            ),
        }
        typer.echo(
            json.dumps(result, indent=2)
            if state.json_output
            else (
                f"UNKNOWN {contract}: unregistered evaluator(s): {', '.join(unknown)}; "
                "register them in Python or pass --allow-unregistered for schema-only validation"
            )
        )
        raise typer.Exit(3)
    result = {
        "status": "PASS",
        "graph": parsed.graph,
        "edges": len(parsed.edges),
        "version": parsed.version,
    }
    typer.echo(
        json.dumps(result)
        if state.json_output
        else f"PASS {contract}: {len(parsed.edges)} edges, contract schema {parsed.version}"
    )


def _schema_for(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return {
            "type": "object",
            "properties": {str(key): _schema_for(item) for key, item in value.items()},
            "required": sorted(str(key) for key in value),
        }
    if isinstance(value, list):
        return {"type": "array", "items": _schema_for(value[0]) if value else {}}
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, int):
        return {"type": "integer"}
    if isinstance(value, float):
        return {"type": "number"}
    if value is None:
        return {"type": "null"}
    return {"type": "string"}


def _edge_output_schema(bundle: TraceBundle, contract: Contract) -> dict[str, Any]:
    observations = {item.edge_id: item for item in bundle.edge_observations}
    properties = {
        edge.id: _schema_for(observations[edge.id].output)
        for edge in contract.edges
        if edge.id in observations
    }
    return {
        "type": "object",
        "properties": properties,
        "required": sorted(properties),
    }


@app.command()
def compare(
    context: typer.Context,
    baseline_run: Annotated[str, typer.Option("--baseline-run", help="Stored baseline run ID.")],
    candidate_run: Annotated[str, typer.Option("--candidate-run", help="Stored candidate run ID.")],
    contract_path: Annotated[Path, typer.Option("--contract", help="Consumer contract YAML.")],
    database: Annotated[Path, typer.Option("--database", "-d")] = Path(".graphabi/demo/traces.db"),
    allow_breaking: Annotated[bool, typer.Option("--allow-breaking")] = False,
) -> None:
    """Compare two stored executions and generate the latest report."""
    state = _state(context)
    try:
        contract = load_contract(contract_path)
        store = SQLiteTraceStore(database)
        baseline = store.load_run(baseline_run)
        candidate = store.load_run(candidate_run)
    except (ContractLoadError, KeyError, sqlite3.Error, TraceStoreError) as exc:
        _fail(str(exc))
    if not baseline.edge_observations or not candidate.edge_observations:
        _fail("both stored runs need at least one edge observation before comparison")
    structural = compare_schemas(
        _edge_output_schema(baseline, contract),
        _edge_output_schema(candidate, contract),
    )
    semantic = compare_semantics(contract, baseline, candidate)
    report_model = CompatibilityReport(
        graph=contract.graph,
        baseline_run_id=baseline_run,
        candidate_run_id=candidate_run,
        structural=structural,
        semantic=semantic,
        limitations=("Trace-derived schemas cannot recover original Pydantic constraints.",),
        reproduction_command=(
            f"graphabi compare --baseline-run {baseline_run} --candidate-run {candidate_run} "
            f"--contract {contract_path} --database {database}"
        ),
    )
    directory = Path(".graphabi/reports/latest")
    write_report(report_model, contract, directory)
    summary = {
        "structural": structural.status,
        "semantic": semantic.status,
        "first_breaking_edge": semantic.first_breaking_edge,
        "contract_coverage": semantic.coverage.model_dump(mode="json"),
    }
    typer.echo(
        json.dumps(summary, indent=2)
        if state.json_output
        else (
            f"Structural: {structural.status}\nSemantic: {semantic.status}\n"
            f"First breaking edge: {semantic.first_breaking_edge or 'none'}\n"
            + "\n".join(_coverage_lines(semantic.coverage))
        )
    )
    if (structural.status == "FAIL" or semantic.status == "FAIL") and not allow_breaking:
        raise typer.Exit(2)
    if semantic.status in {"UNKNOWN", "INSUFFICIENT_EVIDENCE"}:
        raise typer.Exit(3)


@app.command()
def report(
    context: typer.Context,
    open_report: Annotated[
        bool, typer.Option("--open", help="Open the latest HTML report.")
    ] = False,
    serve: Annotated[
        bool, typer.Option("--serve", help="Serve the latest report locally.")
    ] = False,
    host: Annotated[str, typer.Option(help="Local bind address.")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Local port.")] = 8765,
) -> None:
    """Locate, open, or locally serve the latest self-contained report."""
    del context
    latest = _latest_report()
    if not latest.is_file():
        _fail(f"{latest} does not exist; run `graphabi demo --allow-breaking` first")
    if open_report:
        opened = webbrowser.open(latest.as_uri())
        if not opened:
            _fail(f"could not open the browser; open {latest} manually")
        typer.echo(f"Opened {latest}")
    elif serve:
        typer.echo(f"Serving GraphABI report at http://{host}:{port}")
        uvicorn.run(create_report_app(latest), host=host, port=port, log_level="warning")
    else:
        typer.echo(str(latest))


@app.command()
def demo(
    context: typer.Context,
    allow_breaking: Annotated[
        bool,
        typer.Option("--allow-breaking", help="Return zero for the deliberate semantic break."),
    ] = False,
) -> None:
    """Run the deterministic schema-pass/semantics-fail research graph demonstration."""
    state = _state(context)
    try:
        result = run_demo()
    except Exception as exc:
        if state.verbose:
            raise
        _fail(str(exc))
    report_model = result.report
    first = next(
        (item for item in report_model.semantic.findings if item.status == "BREAKING"), None
    )
    summary = {
        "structural_compatibility": report_model.structural.status,
        "semantic_compatibility": report_model.semantic.status,
        "first_breaking_edge": report_model.semantic.first_breaking_edge,
        "breaking_contract": first.contract_id.split(":")[-1] if first else None,
        "reason": first.reason if first else None,
        "affected_downstream_nodes": list(first.affected_downstream_nodes) if first else [],
        "affected_downstream_occurrences": (
            list(first.affected_downstream_occurrences) if first else []
        ),
        "occurrence_pairing": first.occurrence_pairing if first else None,
        "candidate_occurrence_id": first.candidate_occurrence_id if first else None,
        "witness_run": first.run_id if first else None,
        "reports": [str(result.report_json), str(result.report_html)],
        "contract_coverage": report_model.semantic.coverage.model_dump(mode="json"),
    }
    if state.json_output:
        typer.echo(json.dumps(summary, indent=2))
    else:
        lines = [
            "GraphABI semantic compatibility report",
            f"Structural compatibility: {report_model.structural.status}",
            f"Semantic compatibility: {report_model.semantic.status}",
            "First breaking edge:",
            f"{first.producer} -> {first.consumer}" if first else "none",
            "Breaking contract:",
            first.contract_id.split(":")[-1] if first else "none",
            "Reason:",
            first.reason.strip() if first else "none",
            "Affected downstream nodes:",
            ", ".join(first.affected_downstream_nodes) if first else "none",
            "Witness:",
            f"run {first.run_id}" if first else "none",
            "Occurrence pairing:",
            first.occurrence_pairing.replace("_", " ") if first else "none",
            "Candidate occurrence:",
            first.candidate_occurrence_id if first and first.candidate_occurrence_id else "none",
            "Contract coverage:",
            *_coverage_lines(report_model.semantic.coverage),
            "Reports:",
            os.path.relpath(result.report_json, Path.cwd()),
            os.path.relpath(result.report_html, Path.cwd()),
        ]
        typer.echo("\n".join(lines))
    if report_model.semantic.status == "FAIL" and not allow_breaking:
        raise typer.Exit(2)


if __name__ == "__main__":
    app()
