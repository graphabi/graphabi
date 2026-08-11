"""Machine-readable compatibility report schema v0.3."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from graphabi.comparison.models import SemanticReport
from graphabi.comparison.structural import StructuralReport
from graphabi.reporting.redaction import redact_sensitive


class CompatibilityReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["0.1", "0.2", "0.3"] = "0.3"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    graph: str
    baseline_run_id: str
    candidate_run_id: str
    structural: StructuralReport
    semantic: SemanticReport
    limitations: tuple[str, ...]
    reproduction_command: str

    @field_validator("semantic", mode="before")
    @classmethod
    def sensitive_trace_values_are_masked(cls, value: object) -> object:
        raw = (
            value.model_dump(mode="python", exclude_computed_fields=True)
            if isinstance(value, BaseModel)
            else value
        )
        return redact_sensitive(raw)

    @field_validator(
        "graph",
        "baseline_run_id",
        "candidate_run_id",
        "limitations",
        "reproduction_command",
        mode="before",
    )
    @classmethod
    def sensitive_summary_values_are_masked(cls, value: object) -> object:
        return redact_sensitive(value)
