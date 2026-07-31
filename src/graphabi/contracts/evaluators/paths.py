"""Deterministic nested path resolution and condition comparisons."""

from __future__ import annotations

from typing import Any

from graphabi.contracts.models import Condition
from graphabi.models.traces import EdgeObservation


class MissingValue:
    pass


MISSING = MissingValue()


def observation_context(observation: EdgeObservation) -> dict[str, Any]:
    return {
        "input": observation.input,
        "output": observation.output,
        "metadata": observation.metadata,
        "tool_calls": [item.model_dump(mode="json") for item in observation.tool_calls],
        "source_access": [item.model_dump(mode="json") for item in observation.source_access],
        "observed_at": observation.observed_at,
    }


def resolve_path(root: Any, path: str) -> Any:
    current = root
    for component in path.split("."):
        if isinstance(current, dict) and component in current:
            current = current[component]
        elif isinstance(current, (list, tuple)) and component.isdigit():
            index = int(component)
            if index >= len(current):
                return MISSING
            current = current[index]
        else:
            return MISSING
    return current


def evaluate_condition(condition: Condition, context: dict[str, Any]) -> tuple[bool | None, Any]:
    observed = resolve_path(context, condition.path)
    operation, expected = condition.operation
    if operation == "exists":
        return (observed is not MISSING) is bool(expected), observed
    if observed is MISSING:
        return None, observed
    try:
        if operation == "equals":
            if isinstance(observed, bool) != isinstance(expected, bool):
                return False, observed
            return observed == expected, observed
        if operation == "not_equals":
            if isinstance(observed, bool) != isinstance(expected, bool):
                return True, observed
            return observed != expected, observed
        if operation == "greater_than":
            if isinstance(observed, bool):
                return None, observed
            return observed > expected, observed
        if operation == "greater_than_or_equal":
            if isinstance(observed, bool):
                return None, observed
            return observed >= expected, observed
        if operation == "less_than":
            if isinstance(observed, bool):
                return None, observed
            return observed < expected, observed
        if operation == "non_empty":
            return bool(observed) is bool(expected), observed
        if operation == "contains":
            return expected in observed, observed
    except (TypeError, ValueError):
        return None, observed
    return None, observed
