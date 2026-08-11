"""Generate reproducible, local GraphABI benchmark measurements."""

from __future__ import annotations

import json
import platform
import tempfile
import tracemalloc
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from graphabi.comparison import compare_schemas, compare_semantics
from graphabi.contracts.models import Contract
from graphabi.impact import analyze_impact
from graphabi.models.traces import EdgeObservation, GraphRun, NodeExecution, TraceBundle
from graphabi.reporting import CompatibilityReport, write_report
from graphabi.traces import export_json, load_bundle

ROOT = Path(__file__).resolve().parents[1]
STAMP = datetime(2026, 1, 1, tzinfo=UTC)


def synthetic(size: int) -> tuple[Contract, TraceBundle]:
    node_data = [
        {"id": f"node_{index}", "terminal": index == size - 1, "side_effecting": index == size - 1}
        for index in range(size)
    ]
    edge_data = []
    executions = []
    observations = []
    run_id = f"benchmark-{size}"
    for index in range(size):
        executions.append(
            NodeExecution(
                schema_version="0.2",
                run_id=run_id,
                graph_id=f"synthetic_{size}",
                graph_version="1",
                node_id=f"node_{index}",
                occurrence_id=f"node:{index}",
                parent_occurrence_id=f"node:{index - 1}" if index else None,
                causal_parent_occurrence_ids=((f"node:{index - 1}",) if index else ()),
                incoming_edge_id=f"edge_{index - 1}_{index}" if index else None,
                causal_sequence=index,
                branch_id="main",
                attempt=1,
                input={"value": index},
                output={"payload": {"verified": False, "value": index}},
                started_at=STAMP,
                ended_at=STAMP,
                duration_ms=0,
                status="success",
                framework="synthetic",
                framework_version="0.1",
            )
        )
        if index:
            edge_id = f"edge_{index - 1}_{index}"
            edge_data.append(
                {
                    "id": edge_id,
                    "producer": f"node_{index - 1}",
                    "consumer": f"node_{index}",
                    "invariants": [
                        {
                            "id": "verified_requires_source",
                            "evaluator": "implication",
                            "description": "Verified values require an opened source count.",
                            "severity": "breaking",
                            "when": {"path": "output.verified", "equals": True},
                            "require": {
                                "path": "metadata.opened_sources_count",
                                "greater_than": 0,
                            },
                        }
                    ],
                }
            )
            observations.append(
                EdgeObservation(
                    schema_version="0.2",
                    run_id=run_id,
                    graph_id=f"synthetic_{size}",
                    graph_version="1",
                    edge_id=edge_id,
                    producer=f"node_{index - 1}",
                    consumer=f"node_{index}",
                    occurrence_id=f"edge:{index - 1}",
                    producer_occurrence_id=f"node:{index - 1}",
                    consumer_occurrence_id=f"node:{index}",
                    causal_sequence=index - 1,
                    branch_id="main",
                    attempt=1,
                    input={"value": index - 1},
                    output={"verified": False, "value": index - 1},
                    metadata={"opened_sources_count": 0},
                    observed_at=STAMP,
                )
            )
    run = GraphRun(
        schema_version="0.2",
        run_id=run_id,
        graph_id=f"synthetic_{size}",
        graph_version="1",
        started_at=STAMP,
        ended_at=STAMP,
        status="success",
        input={"value": 0},
        output={"value": size - 1},
        executions=tuple(executions),
    )
    contract = Contract.model_validate(
        {
            "version": "0.2",
            "graph": f"synthetic_{size}",
            "nodes": node_data,
            "graph_edges": [
                {
                    "id": edge["id"],
                    "producer": edge["producer"],
                    "consumer": edge["consumer"],
                }
                for edge in edge_data
            ],
            "edges": edge_data,
        }
    )
    return contract, TraceBundle(
        schema_version="0.2",
        runs=(run,),
        edge_observations=tuple(observations),
    )


def measure(operation: Callable[[], Any]) -> tuple[float, float]:
    tracemalloc.start()
    started = perf_counter()
    operation()
    runtime_ms = (perf_counter() - started) * 1000
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return runtime_ms, peak / (1024 * 1024)


def run_case(size: int) -> dict[str, Any]:
    fixture_holder: list[tuple[Contract, TraceBundle]] = []
    fixture_generation = measure(lambda: fixture_holder.append(synthetic(size)))
    contract, bundle = fixture_holder[0]
    with tempfile.TemporaryDirectory(prefix="graphabi-benchmark-") as temporary:
        directory = Path(temporary)
        trace_path = directory / "trace.json"
        export_json(bundle, trace_path)
        loading = measure(lambda: load_bundle(trace_path))
        semantic_holder: list[Any] = []
        evaluation = measure(
            lambda: semantic_holder.append(compare_semantics(contract, bundle, bundle))
        )
        impact = measure(lambda: analyze_impact(contract, contract.edges[0].id))
        structural = compare_schemas(
            {"type": "object", "properties": {"value": {"type": "integer"}}, "required": ["value"]},
            {"type": "object", "properties": {"value": {"type": "integer"}}, "required": ["value"]},
            same_pydantic_model=True,
        )
        report = CompatibilityReport(
            graph=contract.graph,
            baseline_run_id=bundle.runs[0].run_id,
            candidate_run_id=bundle.runs[0].run_id,
            structural=structural,
            semantic=semantic_holder[0],
            limitations=(
                "Synthetic linear graph; results are local measurements, not capacity claims.",
            ),
            reproduction_command="make benchmark",
        )
        rendering = measure(lambda: write_report(report, contract, directory / "report"))
    return {
        "nodes": size,
        "edges": size - 1,
        "observations": size - 1,
        "contracts": size - 1,
        "fixture_generation_ms": round(fixture_generation[0], 3),
        "trace_loading_ms": round(loading[0], 3),
        "contract_evaluation_ms": round(evaluation[0], 3),
        "impact_analysis_ms": round(impact[0], 3),
        "report_generation_ms": round(rendering[0], 3),
        "peak_memory_mib": round(
            max(
                fixture_generation[1],
                loading[1],
                evaluation[1],
                impact[1],
                rendering[1],
            ),
            3,
        ),
    }


def main() -> None:
    output_directory = ROOT / "benchmarks"
    output_directory.mkdir(exist_ok=True)
    results = {
        "benchmark_schema_version": "0.1",
        "generated_at": datetime.now(UTC).isoformat(),
        "machine": {
            "architecture": platform.machine(),
            "platform": platform.platform(),
            "python": platform.python_version(),
        },
        "method": (
            "One measured iteration per phase; deterministic fixture construction is reported "
            "separately rather than hidden. Peak memory is the tracemalloc Python allocation "
            "peak for the largest phase."
        ),
        "limitations": [
            "Synthetic graphs are linear and do not represent every topology.",
            "Single-iteration local measurements include interpreter and filesystem variance.",
            "tracemalloc excludes some native-library allocations.",
        ],
        "results": [run_case(size) for size in (10, 100, 1000)],
    }
    json_path = output_directory / "latest.json"
    markdown_path = output_directory / "latest.md"
    json_path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    rows = [
        "# GraphABI local benchmark",
        "",
        f"Generated: {results['generated_at']}",
        f"Machine: {results['machine']['architecture']}; Python {results['machine']['python']}",
        "",
        "| Nodes | Edges | Observations | Contracts | Fixture ms | Load ms | Evaluate ms | "
        "Impact ms | Report ms | Peak MiB |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in results["results"]:
        rows.append(
            f"| {item['nodes']} | {item['edges']} | {item['observations']} | {item['contracts']} | "
            f"{item['fixture_generation_ms']} | {item['trace_loading_ms']} | "
            f"{item['contract_evaluation_ms']} | "
            f"{item['impact_analysis_ms']} | {item['report_generation_ms']} | "
            f"{item['peak_memory_mib']} |"
        )
    rows.extend(["", "## Method", "", str(results["method"]), "", "## Limitations", ""])
    rows.extend(f"- {item}" for item in results["limitations"])
    markdown_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"Wrote {json_path}")
    print(f"Wrote {markdown_path}")


if __name__ == "__main__":
    main()
