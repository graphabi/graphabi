"""Explicit evaluator registry and built-in registry factory."""

from __future__ import annotations

from graphabi.contracts.evaluators.base import Evaluator
from graphabi.contracts.evaluators.builtin import (
    AuthorityEvaluator,
    CompletenessEvaluator,
    FreshnessEvaluator,
    ImplicationEvaluator,
    ProvenanceEvaluator,
    SetPreservationEvaluator,
    UnitConsistencyEvaluator,
)


class EvaluatorRegistry:
    """Per-engine registry that external contributors can extend without core edits."""

    def __init__(self) -> None:
        self._evaluators: dict[str, Evaluator] = {}

    def register(self, evaluator: Evaluator, *, replace: bool = False) -> None:
        if evaluator.name in self._evaluators and not replace:
            raise ValueError(f"evaluator {evaluator.name!r} is already registered")
        self._evaluators[evaluator.name] = evaluator

    def get(self, name: str) -> Evaluator | None:
        return self._evaluators.get(name)

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._evaluators))


def default_registry() -> EvaluatorRegistry:
    registry = EvaluatorRegistry()
    for evaluator in (
        ImplicationEvaluator(),
        ProvenanceEvaluator(),
        SetPreservationEvaluator(),
        CompletenessEvaluator(),
        UnitConsistencyEvaluator(),
        AuthorityEvaluator(),
        FreshnessEvaluator(),
    ):
        registry.register(evaluator)
    return registry
