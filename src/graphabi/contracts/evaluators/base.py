"""Evaluator protocol and common result model."""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict

from graphabi.contracts.models import Invariant
from graphabi.models.traces import EdgeObservation, JsonValue


class EvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["PASS", "WARNING", "BREAKING", "UNKNOWN", "INSUFFICIENT_EVIDENCE"]
    reason: str
    expectation: str
    observed: JsonValue = None
    relevant_paths: tuple[str, ...] = ()


class Evaluator(Protocol):
    name: str

    def evaluate(
        self,
        invariant: Invariant,
        candidate: EdgeObservation,
        baseline: EdgeObservation | None = None,
    ) -> EvaluationResult: ...


def failure_status(invariant: Invariant) -> Literal["WARNING", "BREAKING"]:
    return "WARNING" if invariant.severity == "warning" else "BREAKING"
