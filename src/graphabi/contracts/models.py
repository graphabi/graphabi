"""Pydantic schema for GraphABI contract format v0.1."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from graphabi.models.traces import JsonValue


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class Condition(ContractModel):
    """A path comparison used by implication invariants."""

    path: str = Field(min_length=1)
    equals: JsonValue = None
    not_equals: JsonValue = None
    greater_than: float | None = None
    greater_than_or_equal: float | None = None
    less_than: float | None = None
    exists: bool | None = None
    non_empty: bool | None = None
    contains: JsonValue = None

    @model_validator(mode="after")
    def exactly_one_operator(self) -> Condition:
        operators = {
            "equals",
            "not_equals",
            "greater_than",
            "greater_than_or_equal",
            "less_than",
            "exists",
            "non_empty",
            "contains",
        }
        selected = operators.intersection(self.model_fields_set)
        if len(selected) != 1:
            raise ValueError(
                "condition must set exactly one comparison: equals, not_equals, greater_than, "
                "greater_than_or_equal, less_than, exists, non_empty, or contains"
            )
        return self

    @property
    def operation(self) -> tuple[str, JsonValue]:
        for name in (
            "equals",
            "not_equals",
            "greater_than",
            "greater_than_or_equal",
            "less_than",
            "exists",
            "non_empty",
            "contains",
        ):
            if name in self.model_fields_set:
                return name, getattr(self, name)
        raise AssertionError("validated condition has no operator")


class Invariant(ContractModel):
    """One evaluator invocation attached to a consumer-driven edge."""

    id: str = Field(min_length=1)
    evaluator: str = Field(min_length=1)
    description: str = Field(min_length=1)
    severity: Literal["warning", "breaking"] = "breaking"
    failure_message: str | None = None
    when: Condition | None = None
    require: Condition | None = None
    rule: str | None = None
    source_path: str | None = None
    destination_path: str | None = None
    value_path: str | None = None
    unit_path: str | None = None
    expected_unit: str | None = None
    representation_path: str | None = None
    expected_representation: Literal["fraction", "percent"] | None = None
    allow_conversion: bool = False
    maximum_allowed: str | None = None
    timestamp_path: str | None = None
    max_age_seconds: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def evaluator_fields_are_complete(self) -> Invariant:
        required: dict[str, tuple[str, ...]] = {
            "implication": ("when", "require"),
            "provenance": ("rule",),
            "set_preservation": ("source_path", "destination_path"),
            "completeness": ("destination_path",),
            "unit_consistency": ("value_path", "unit_path", "expected_unit"),
            "authority": ("source_path", "maximum_allowed"),
            "freshness": ("timestamp_path", "max_age_seconds"),
        }
        if self.evaluator not in required:
            return self
        missing = [field for field in required[self.evaluator] if getattr(self, field) is None]
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"evaluator {self.evaluator!r} requires field(s): {joined}")
        valid_rules = {
            "opened_source",
            "claim_support",
            "accessed_citations",
            "opened_supporting_source",
        }
        if self.evaluator == "provenance" and self.rule not in valid_rules:
            raise ValueError(f"provenance rule must be one of: {', '.join(sorted(valid_rules))}")
        return self


class SchemaReference(ContractModel):
    model: str = Field(min_length=1)


class ContractEdge(ContractModel):
    id: str = Field(min_length=1)
    producer: str = Field(min_length=1)
    consumer: str = Field(min_length=1)
    schema_: SchemaReference | None = Field(default=None, alias="schema")
    invariants: tuple[Invariant, ...] = Field(min_length=1)


class ContractNode(ContractModel):
    id: str = Field(min_length=1)
    terminal: bool = False
    side_effecting: bool = False


class Contract(ContractModel):
    """Complete consumer-driven graph contract."""

    version: Literal["0.1"]
    graph: str = Field(min_length=1)
    nodes: tuple[ContractNode, ...] = Field(min_length=1)
    edges: tuple[ContractEdge, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def graph_references_are_valid(self) -> Contract:
        node_ids = [node.id for node in self.nodes]
        if len(set(node_ids)) != len(node_ids):
            raise ValueError("node IDs must be unique")
        edge_ids = [edge.id for edge in self.edges]
        if len(set(edge_ids)) != len(edge_ids):
            raise ValueError("edge IDs must be unique")
        known = set(node_ids)
        for edge in self.edges:
            missing = {edge.producer, edge.consumer} - known
            if missing:
                raise ValueError(
                    f"edge {edge.id!r} references undefined node(s): {', '.join(sorted(missing))}"
                )
        return self

    def edge(self, edge_id: str) -> ContractEdge:
        for edge in self.edges:
            if edge.id == edge_id:
                return edge
        raise KeyError(edge_id)
