from pathlib import Path

import pytest
from pydantic import ValidationError

from graphabi.contracts import ContractLoadError, load_contract
from graphabi.contracts.models import Condition, Contract, ContractNode, Invariant

ROOT = Path(__file__).resolve().parents[2]


def test_demo_contract_loads_and_resolves_edge() -> None:
    contract = load_contract(ROOT / "examples/research_graph/contracts.yml")
    assert contract.version == "0.2"
    assert contract.edge("researcher_to_verifier").consumer == "verifier"
    with pytest.raises(KeyError):
        contract.edge("missing")


@pytest.mark.parametrize(
    "raw",
    [
        {"path": "output.x"},
        {"path": "output.x", "equals": 1, "exists": True},
    ],
)
def test_condition_requires_exactly_one_operator(raw: dict[str, object]) -> None:
    with pytest.raises(ValidationError, match="exactly one comparison"):
        Condition.model_validate(raw)


@pytest.mark.parametrize(
    "raw",
    [
        {"path": "output.x", "greater_than": "1"},
        {"path": "output.x", "exists": "yes"},
        {"path": "output.x", "non_empty": 1},
    ],
)
def test_condition_rejects_coerced_operator_types(raw: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Condition.model_validate(raw)


def test_contract_node_rejects_coerced_boolean_flags() -> None:
    with pytest.raises(ValidationError):
        ContractNode.model_validate({"id": "n", "terminal": "yes"})


@pytest.mark.parametrize(
    ("evaluator", "data"),
    [
        ("implication", {}),
        ("provenance", {"rule": "invented"}),
        ("set_preservation", {"source_path": "x"}),
        ("completeness", {}),
        ("unit_consistency", {"value_path": "x"}),
        ("authority", {"source_path": "x"}),
        ("freshness", {"timestamp_path": "x"}),
    ],
)
def test_invalid_evaluator_combinations_fail(evaluator: str, data: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Invariant(id="bad", evaluator=evaluator, description="bad", **data)


def test_unknown_evaluator_is_valid_for_external_registry() -> None:
    invariant = Invariant(id="custom", evaluator="my_plugin", description="plugin")
    assert invariant.evaluator == "my_plugin"


def test_graph_references_and_ids_are_validated() -> None:
    raw = {
        "version": "0.1",
        "graph": "g",
        "nodes": [{"id": "a"}, {"id": "a"}],
        "edges": [
            {
                "id": "e",
                "producer": "a",
                "consumer": "missing",
                "invariants": [{"id": "i", "evaluator": "custom", "description": "d"}],
            }
        ],
    }
    with pytest.raises(ValidationError, match="node IDs must be unique"):
        Contract.model_validate(raw)
    raw["nodes"] = [{"id": "a"}, {"id": "b"}]
    with pytest.raises(ValidationError, match="undefined node"):
        Contract.model_validate(raw)


def test_contract_02_separates_graph_topology_from_contracted_edges() -> None:
    contract = Contract.model_validate(
        {
            "version": "0.2",
            "graph": "g",
            "nodes": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
            "graph_edges": [
                {"id": "a_to_b", "producer": "a", "consumer": "b"},
                {"id": "b_to_c", "producer": "b", "consumer": "c"},
            ],
            "edges": [
                {
                    "id": "a_to_b",
                    "producer": "a",
                    "consumer": "b",
                    "invariants": [{"id": "i", "evaluator": "custom", "description": "d"}],
                }
            ],
        }
    )

    assert contract.version == "0.2"
    assert contract.graph_inventory_complete
    assert tuple(edge.id for edge in contract.topology_edges) == ("a_to_b", "b_to_c")
    assert tuple(edge.id for edge in contract.edges) == ("a_to_b",)


@pytest.mark.parametrize(
    ("version", "graph_edges", "message"),
    (
        ("0.2", None, "requires graph_edges"),
        (
            "0.2",
            [{"id": "different", "producer": "a", "consumer": "b"}],
            "absent from graph_edges",
        ),
        (
            "0.2",
            [{"id": "a_to_b", "producer": "b", "consumer": "a"}],
            "endpoints do not match",
        ),
        (
            "0.1",
            [{"id": "a_to_b", "producer": "a", "consumer": "b"}],
            "requires contract version '0.2'",
        ),
    ),
)
def test_contract_topology_version_and_identity_are_validated(
    version: str,
    graph_edges: list[dict[str, str]] | None,
    message: str,
) -> None:
    raw = {
        "version": version,
        "graph": "g",
        "nodes": [{"id": "a"}, {"id": "b"}],
        "edges": [
            {
                "id": "a_to_b",
                "producer": "a",
                "consumer": "b",
                "invariants": [{"id": "i", "evaluator": "custom", "description": "d"}],
            }
        ],
    }
    if graph_edges is not None:
        raw["graph_edges"] = graph_edges

    with pytest.raises(ValidationError, match=message):
        Contract.model_validate(raw)


def test_loader_error_has_actionable_context(tmp_path: Path) -> None:
    contract = tmp_path / "bad.yml"
    contract.write_text(
        """version: "0.1"
graph: bad
nodes: [{id: a}, {id: b}]
edges:
  - id: a_to_b
    producer: a
    consumer: b
    invariants:
      - id: broken
        evaluator: implication
        description: missing requirement
""",
        encoding="utf-8",
    )
    with pytest.raises(ContractLoadError) as captured:
        load_contract(contract)
    message = str(captured.value)
    assert str(contract) in message
    assert "edge=a_to_b" in message
    assert "invariant=broken" in message
    assert "invalid field" in message
    assert "expected=" in message
    assert "suggested correction=" in message


def test_loader_reports_yaml_and_missing_file(tmp_path: Path) -> None:
    malformed = tmp_path / "malformed.yml"
    malformed.write_text("edges: [", encoding="utf-8")
    with pytest.raises(ContractLoadError, match="YAML syntax"):
        load_contract(malformed)
    with pytest.raises(ContractLoadError, match="readable YAML"):
        load_contract(tmp_path / "missing.yml")
