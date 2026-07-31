"""Deterministic JSON-schema structural comparison."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class StructuralChange(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    kind: Literal[
        "missing_field",
        "added_field",
        "changed_type",
        "changed_optionality",
        "changed_enum",
    ]
    breaking: bool
    baseline: Any = None
    candidate: Any = None
    reason: str


class StructuralReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["PASS", "FAIL"]
    pydantic_model_compatible: bool
    json_schema_compatible: bool
    exact_schema_match: bool
    changes: tuple[StructuralChange, ...]


def _walk(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    path: str,
    changes: list[StructuralChange],
) -> None:
    baseline_type = baseline.get("type")
    candidate_type = candidate.get("type")
    if baseline_type != candidate_type:
        changes.append(
            StructuralChange(
                path=path or "$",
                kind="changed_type",
                breaking=True,
                baseline=baseline_type,
                candidate=candidate_type,
                reason="primitive or container type changed",
            )
        )
        return
    baseline_enum = baseline.get("enum")
    candidate_enum = candidate.get("enum")
    if baseline_enum is not None or candidate_enum is not None:
        old = set(baseline_enum or [])
        new = set(candidate_enum or [])
        if old != new:
            removed = old - new
            changes.append(
                StructuralChange(
                    path=path or "$",
                    kind="changed_enum",
                    breaking=bool(removed),
                    baseline=baseline_enum,
                    candidate=candidate_enum,
                    reason=(
                        f"candidate removed enum values: {sorted(removed, key=str)}"
                        if removed
                        else "candidate added compatible enum values"
                    ),
                )
            )
    old_properties = baseline.get("properties", {})
    new_properties = candidate.get("properties", {})
    if isinstance(old_properties, dict) and isinstance(new_properties, dict):
        old_required = set(baseline.get("required", []))
        new_required = set(candidate.get("required", []))
        for name in sorted(old_properties.keys() - new_properties.keys()):
            changes.append(
                StructuralChange(
                    path=f"{path}.{name}".strip("."),
                    kind="missing_field",
                    breaking=True,
                    baseline=old_properties[name],
                    reason="field accepted by the baseline schema is missing",
                )
            )
        for name in sorted(new_properties.keys() - old_properties.keys()):
            required = name in new_required
            changes.append(
                StructuralChange(
                    path=f"{path}.{name}".strip("."),
                    kind="added_field",
                    breaking=required,
                    candidate=new_properties[name],
                    reason="new required field is breaking"
                    if required
                    else "optional additive field is compatible",
                )
            )
        for name in sorted(old_properties.keys() & new_properties.keys()):
            old_is_required = name in old_required
            new_is_required = name in new_required
            if old_is_required != new_is_required:
                changes.append(
                    StructuralChange(
                        path=f"{path}.{name}".strip("."),
                        kind="changed_optionality",
                        breaking=new_is_required,
                        baseline="required" if old_is_required else "optional",
                        candidate="required" if new_is_required else "optional",
                        reason="candidate requires a previously optional field"
                        if new_is_required
                        else "candidate made the field optional",
                    )
                )
            _walk(
                old_properties[name],
                new_properties[name],
                f"{path}.{name}".strip("."),
                changes,
            )
        return
    old_items = baseline.get("items")
    new_items = candidate.get("items")
    if isinstance(old_items, dict) and isinstance(new_items, dict):
        _walk(old_items, new_items, f"{path}[]", changes)


def compare_schemas(
    baseline_schema: dict[str, Any],
    candidate_schema: dict[str, Any],
    *,
    same_pydantic_model: bool = False,
) -> StructuralReport:
    """Classify structural differences, allowing optional additive changes."""
    changes: list[StructuralChange] = []
    _walk(baseline_schema, candidate_schema, "", changes)
    compatible = not any(change.breaking for change in changes)
    return StructuralReport(
        status="PASS" if compatible else "FAIL",
        pydantic_model_compatible=same_pydantic_model,
        json_schema_compatible=compatible,
        exact_schema_match=baseline_schema == candidate_schema,
        changes=tuple(changes),
    )
