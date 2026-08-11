"""Small lossless SQLite trace store using the standard library."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from graphabi.models.traces import EdgeObservation, GraphRun, TraceBundle
from graphabi.storage.base import TraceStoreError

SCHEMA = """
CREATE TABLE IF NOT EXISTS graph_runs (
    run_id TEXT PRIMARY KEY,
    graph_id TEXT NOT NULL,
    graph_version TEXT NOT NULL,
    variant TEXT NOT NULL,
    started_at TEXT NOT NULL,
    exported_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS edge_observations (
    run_id TEXT NOT NULL,
    occurrence_id TEXT NOT NULL,
    edge_id TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (run_id, occurrence_id),
    FOREIGN KEY (run_id) REFERENCES graph_runs(run_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_runs_graph ON graph_runs(graph_id, started_at);
CREATE INDEX IF NOT EXISTS idx_observations_edge
    ON edge_observations(run_id, edge_id, observed_at);
"""

EDGE_OBSERVATIONS_V2 = """
CREATE TABLE edge_observations (
    run_id TEXT NOT NULL,
    occurrence_id TEXT NOT NULL,
    edge_id TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (run_id, occurrence_id),
    FOREIGN KEY (run_id) REFERENCES graph_runs(run_id) ON DELETE CASCADE
)
"""


class SQLiteTraceStore:
    """Persist versioned trace JSON in queryable, transactional SQLite rows."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(SCHEMA)
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(graph_runs)").fetchall()
            }
            if "exported_at" not in columns:
                connection.execute(
                    "ALTER TABLE graph_runs ADD COLUMN exported_at TEXT NOT NULL "
                    "DEFAULT '1970-01-01T00:00:00+00:00'"
                )
            observation_columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(edge_observations)").fetchall()
            }
            if "occurrence_id" not in observation_columns:
                connection.execute("ALTER TABLE edge_observations RENAME TO edge_observations_v01")
                connection.execute(EDGE_OBSERVATIONS_V2)
                connection.execute(
                    """INSERT INTO edge_observations
                       (run_id, occurrence_id, edge_id, schema_version, observed_at, payload_json)
                       SELECT run_id, 'legacy:' || edge_id, edge_id, '0.1', observed_at,
                              payload_json
                       FROM edge_observations_v01"""
                )
                connection.execute("DROP TABLE edge_observations_v01")
                connection.execute(
                    """CREATE INDEX IF NOT EXISTS idx_observations_edge
                       ON edge_observations(run_id, edge_id, observed_at)"""
                )

    def save_bundle(self, bundle: TraceBundle) -> None:
        self.initialize()
        observations_by_run: dict[str, list[EdgeObservation]] = {}
        for observation in bundle.edge_observations:
            observations_by_run.setdefault(observation.run_id, []).append(observation)
        with self._connect() as connection:
            for run in bundle.runs:
                connection.execute(
                    """INSERT OR REPLACE INTO graph_runs
                       (run_id, graph_id, graph_version, variant, started_at, exported_at,
                        payload_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        run.run_id,
                        run.graph_id,
                        run.graph_version,
                        run.variant,
                        run.started_at.isoformat(),
                        bundle.exported_at.isoformat(),
                        run.model_dump_json(),
                    ),
                )
                connection.execute("DELETE FROM edge_observations WHERE run_id = ?", (run.run_id,))
                for observation in observations_by_run.get(run.run_id, []):
                    connection.execute(
                        """INSERT INTO edge_observations
                           (run_id, occurrence_id, edge_id, schema_version, observed_at,
                            payload_json) VALUES (?, ?, ?, ?, ?, ?)""",
                        (
                            run.run_id,
                            observation.occurrence_id or f"legacy:{observation.edge_id}",
                            observation.edge_id,
                            observation.schema_version,
                            observation.observed_at.isoformat(),
                            observation.model_dump_json(),
                        ),
                    )

    def load_run(self, run_id: str) -> TraceBundle:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json, exported_at FROM graph_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"run {run_id!r} was not found in {self.path}")
            observation_rows = connection.execute(
                """SELECT payload_json FROM edge_observations
                   WHERE run_id = ? ORDER BY rowid""",
                (run_id,),
            ).fetchall()
        try:
            parsed_run = GraphRun.model_validate_json(row[0])
            return TraceBundle(
                schema_version=parsed_run.schema_version,
                exported_at=datetime.fromisoformat(row[1]),
                runs=(parsed_run,),
                edge_observations=tuple(
                    EdgeObservation.model_validate_json(item[0]) for item in observation_rows
                ),
            )
        except (ValidationError, ValueError) as exc:
            raise TraceStoreError(
                f"trace database {self.path}: run {run_id!r} contains corrupt trace data: {exc}"
            ) from exc

    def list_runs(self) -> tuple[GraphRun, ...]:
        self.initialize()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM graph_runs ORDER BY started_at, run_id"
            ).fetchall()
        runs: list[GraphRun] = []
        for index, row in enumerate(rows):
            try:
                runs.append(GraphRun.model_validate_json(row[0]))
            except ValidationError as exc:
                raise TraceStoreError(
                    f"trace database {self.path}: graph_runs row {index} contains corrupt "
                    f"trace data: {exc}"
                ) from exc
        return tuple(runs)
