"""Storage protocol consumed by GraphABI orchestration."""

from __future__ import annotations

from typing import Protocol

from graphabi.models.traces import GraphRun, TraceBundle


class TraceStore(Protocol):
    def initialize(self) -> None: ...

    def save_bundle(self, bundle: TraceBundle) -> None: ...

    def load_run(self, run_id: str) -> TraceBundle: ...

    def list_runs(self) -> tuple[GraphRun, ...]: ...
