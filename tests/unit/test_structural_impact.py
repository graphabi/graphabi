from graphabi.comparison import compare_schemas
from graphabi.contracts.models import Contract
from graphabi.impact import analyze_impact


def schema(properties: dict[str, dict[str, object]], required: list[str]) -> dict[str, object]:
    return {"type": "object", "properties": properties, "required": required}


def test_structural_comparison_classifies_all_changes() -> None:
    baseline = schema(
        {
            "removed": {"type": "string"},
            "typed": {"type": "integer"},
            "optional": {"type": "string"},
            "enum": {"type": "string", "enum": ["a", "b"]},
            "items": {"type": "array", "items": {"type": "integer"}},
        },
        ["removed", "typed", "enum"],
    )
    candidate = schema(
        {
            "typed": {"type": "string"},
            "optional": {"type": "string"},
            "enum": {"type": "string", "enum": ["a"]},
            "items": {"type": "array", "items": {"type": "string"}},
            "added_optional": {"type": "boolean"},
            "added_required": {"type": "number"},
        },
        ["optional", "enum", "added_required"],
    )
    result = compare_schemas(baseline, candidate)
    assert result.status == "FAIL"
    kinds = {change.kind for change in result.changes}
    assert kinds == {
        "missing_field",
        "added_field",
        "changed_type",
        "changed_optionality",
        "changed_enum",
    }
    assert any(not change.breaking for change in result.changes)


def test_additive_optional_schema_is_compatible() -> None:
    baseline = schema({"x": {"type": "string", "enum": ["a"]}}, ["x"])
    candidate = schema(
        {
            "x": {"type": "string", "enum": ["a", "b"]},
            "y": {"type": "integer"},
        },
        ["x"],
    )
    report = compare_schemas(baseline, candidate)
    assert report.status == "PASS"
    assert not report.exact_schema_match


def test_impact_reaches_terminal_and_finds_unaffected_branch() -> None:
    contract = Contract.model_validate(
        {
            "version": "0.1",
            "graph": "branched",
            "nodes": [
                {"id": "a"},
                {"id": "b"},
                {"id": "c"},
                {"id": "terminal", "terminal": True, "side_effecting": True},
                {"id": "other", "terminal": True},
            ],
            "edges": [
                {
                    "id": "ab",
                    "producer": "a",
                    "consumer": "b",
                    "invariants": [{"id": "i", "evaluator": "custom", "description": "d"}],
                },
                {
                    "id": "bc",
                    "producer": "b",
                    "consumer": "c",
                    "invariants": [{"id": "i", "evaluator": "custom", "description": "d"}],
                },
                {
                    "id": "ct",
                    "producer": "c",
                    "consumer": "terminal",
                    "invariants": [{"id": "i", "evaluator": "custom", "description": "d"}],
                },
                {
                    "id": "ao",
                    "producer": "a",
                    "consumer": "other",
                    "invariants": [{"id": "i", "evaluator": "custom", "description": "d"}],
                },
            ],
        }
    )
    impact = analyze_impact(contract, "bc")
    assert impact.downstream_nodes == ("c", "terminal")
    assert impact.terminal_paths == (("c", "terminal"),)
    assert impact.side_effecting_paths == (("c", "terminal"),)
    assert impact.unaffected_branches_exist
    assert impact.nearest_repair_location == "before c consumes output from b"
    assert "terminal" in impact.explanation


def test_linear_upstream_ancestors_are_not_unaffected_branches() -> None:
    contract = Contract.model_validate(
        {
            "version": "0.1",
            "graph": "linear",
            "nodes": [{"id": "a"}, {"id": "b"}, {"id": "c", "terminal": True}],
            "edges": [
                {
                    "id": "ab",
                    "producer": "a",
                    "consumer": "b",
                    "invariants": [{"id": "i", "evaluator": "custom", "description": "d"}],
                },
                {
                    "id": "bc",
                    "producer": "b",
                    "consumer": "c",
                    "invariants": [{"id": "i", "evaluator": "custom", "description": "d"}],
                },
            ],
        }
    )
    assert analyze_impact(contract, "bc").unaffected_branches_exist is False
