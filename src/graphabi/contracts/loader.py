"""YAML loader with contextual, actionable validation errors."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from graphabi.contracts.models import Contract


class ContractLoadError(ValueError):
    """An invalid contract annotated with file, edge, invariant, and correction."""

    def __init__(
        self,
        *,
        file: Path,
        edge: str,
        invariant: str,
        invalid_field: str,
        expected: str,
        suggestion: str,
    ) -> None:
        self.file = file
        self.edge = edge
        self.invariant = invariant
        self.invalid_field = invalid_field
        self.expected = expected
        self.suggestion = suggestion
        super().__init__(
            f"{file}: edge={edge}; invariant={invariant}; invalid field={invalid_field}; "
            f"expected={expected}; suggested correction={suggestion}"
        )


def _context(raw: Any, location: tuple[int | str, ...]) -> tuple[str, str]:
    edge = "<graph>"
    invariant = "<none>"
    if not isinstance(raw, dict):
        return edge, invariant
    try:
        edge_index = location[1] if location and location[0] == "edges" else None
        if isinstance(edge_index, int):
            edge_raw = raw.get("edges", [])[edge_index]
            edge = str(edge_raw.get("id", f"index-{edge_index}"))
            if len(location) > 3 and location[2] == "invariants" and isinstance(location[3], int):
                invariant_raw = edge_raw.get("invariants", [])[location[3]]
                invariant = str(invariant_raw.get("id", f"index-{location[3]}"))
    except (IndexError, AttributeError, TypeError):
        pass
    return edge, invariant


def load_contract(path: Path) -> Contract:
    """Parse a YAML contract, raising one concise contextual error on failure."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ContractLoadError(
            file=path,
            edge="<none>",
            invariant="<none>",
            invalid_field="file",
            expected="a readable YAML contract",
            suggestion="check the path and file permissions",
        ) from exc
    except yaml.YAMLError as exc:
        raise ContractLoadError(
            file=path,
            edge="<parse>",
            invariant="<parse>",
            invalid_field="YAML syntax",
            expected=str(exc),
            suggestion="fix the reported indentation or YAML token",
        ) from exc
    try:
        return Contract.model_validate(raw)
    except ValidationError as exc:
        error = exc.errors(include_url=False)[0]
        location = tuple(error["loc"])
        edge, invariant = _context(raw, location)
        invalid_field = ".".join(str(part) for part in location) or "document"
        evaluator = "the selected evaluator"
        if isinstance(raw, dict) and edge != "<graph>":
            evaluator = f"invariant {invariant!r}"
        raise ContractLoadError(
            file=path,
            edge=edge,
            invariant=invariant,
            invalid_field=invalid_field,
            expected=str(error["msg"]),
            suggestion=(
                f"add or correct `{location[-1] if location else 'document'}` for {evaluator}"
            ),
        ) from exc
