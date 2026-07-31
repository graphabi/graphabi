"""Machine-readable compatibility report schema v0.1."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from graphabi.comparison.models import SemanticReport
from graphabi.comparison.structural import StructuralReport


class CompatibilityReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["0.1"] = "0.1"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    graph: str
    baseline_run_id: str
    candidate_run_id: str
    structural: StructuralReport
    semantic: SemanticReport
    limitations: tuple[str, ...]
    reproduction_command: str
