"""Portable trace import and export."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from graphabi.models.traces import EdgeObservation, GraphRun, TraceBundle


def export_json(bundle: TraceBundle, path: Path) -> None:
    """Write a trace bundle as deterministic, indented JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(bundle.model_dump_json(indent=2) + "\n", encoding="utf-8")


def export_jsonl(bundle: TraceBundle, path: Path) -> None:
    """Write runs and observations as stream-friendly JSON Lines."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [
        json.dumps(
            {
                "kind": "trace_bundle",
                "data": {
                    "schema_version": bundle.schema_version,
                    "exported_at": bundle.exported_at.isoformat(),
                },
            },
            sort_keys=True,
        )
    ]
    for run in bundle.runs:
        lines.append(
            json.dumps({"kind": "graph_run", "data": run.model_dump(mode="json")}, sort_keys=True)
        )
    for observation in bundle.edge_observations:
        lines.append(
            json.dumps(
                {"kind": "edge_observation", "data": observation.model_dump(mode="json")},
                sort_keys=True,
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_bundle(path: Path) -> TraceBundle:
    """Load JSON bundle or JSONL records according to the filename suffix."""
    if path.suffix == ".jsonl":
        runs: list[GraphRun] = []
        observations: list[EdgeObservation] = []
        bundle_metadata: dict[str, object] = {}
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc.msg}") from exc
            if not isinstance(raw, dict):
                raise ValueError(f"{path}:{line_number}: trace record must be a JSON object")
            if "data" not in raw:
                raise ValueError(f"{path}:{line_number}: trace record is missing 'data'")
            if raw.get("kind") == "trace_bundle":
                if bundle_metadata:
                    raise ValueError(f"{path}:{line_number}: duplicate trace_bundle record")
                if not isinstance(raw["data"], dict):
                    raise ValueError(
                        f"{path}:{line_number}: trace_bundle data must be a JSON object"
                    )
                bundle_metadata = raw["data"]
            elif raw.get("kind") == "graph_run":
                runs.append(GraphRun.model_validate(raw["data"]))
            elif raw.get("kind") == "edge_observation":
                observations.append(EdgeObservation.model_validate(raw["data"]))
            else:
                raise ValueError(f"{path}:{line_number}: unknown trace record kind")
        inferred_version = (
            runs[0].schema_version
            if runs
            else observations[0].schema_version
            if observations
            else "0.1"
        )
        return TraceBundle.model_validate(
            {
                "schema_version": bundle_metadata.get("schema_version", inferred_version),
                "exported_at": bundle_metadata.get("exported_at", datetime.now(UTC)),
                "runs": tuple(runs),
                "edge_observations": tuple(observations),
            }
        )
    return TraceBundle.model_validate_json(path.read_text(encoding="utf-8"))
