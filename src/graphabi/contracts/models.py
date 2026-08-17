"""Pydantic schema for GraphABI contract format v0.1."""

from __future__ import annotations

from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    field_validator,
    model_validator,
)

from graphabi.models.traces import JsonValue


class ContractModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        allow_inf_nan=False,
        hide_input_in_errors=True,
    )


_PATH_ROOTS = {"input", "output", "metadata", "tool_calls", "source_access", "observed_at"}


def _validate_path(value: str) -> str:
    parts = value.split(".")
    if any(not part or part != part.strip() for part in parts):
        raise ValueError("path must use non-empty dot-separated components")
    if parts[0] not in _PATH_ROOTS:
        raise ValueError(
            "path must start with input, output, metadata, tool_calls, source_access, "
            "or observed_at"
        )
    if parts[0] == "observed_at" and len(parts) != 1:
        raise ValueError("observed_at is a scalar path and cannot have child components")
    return value


class Condition(ContractModel):
    """A path comparison used by implication invariants."""

    path: str = Field(min_length=1)
    equals: JsonValue = None
    not_equals: JsonValue = None
    greater_than: StrictInt | StrictFloat | None = None
    greater_than_or_equal: StrictInt | StrictFloat | None = None
    less_than: StrictInt | StrictFloat | None = None
    exists: StrictBool | None = None
    non_empty: StrictBool | None = None
    contains: JsonValue = None

    @field_validator("path")
    @classmethod
    def path_is_valid(cls, value: str) -> str:
        return _validate_path(value)

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
    allow_conversion: StrictBool = False
    maximum_allowed: str | None = None
    set_relation: Literal["contains_all_required", "equal"] | None = None
    authority_order: tuple[str, ...] | None = None
    timestamp_path: str | None = None
    max_age_seconds: StrictInt | StrictFloat | None = Field(default=None, gt=0)

    @field_validator(
        "source_path",
        "destination_path",
        "value_path",
        "unit_path",
        "representation_path",
        "timestamp_path",
    )
    @classmethod
    def paths_are_valid(cls, value: str | None) -> str | None:
        return _validate_path(value) if value is not None else None

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
        if (
            self.evaluator == "unit_consistency"
            and self.expected_representation is not None
            and self.representation_path is None
        ):
            raise ValueError(
                "evaluator 'unit_consistency' requires representation_path when "
                "expected_representation is set"
            )
        if self.set_relation is not None and self.evaluator != "set_preservation":
            raise ValueError("set_relation is only valid for set_preservation invariants")
        if self.evaluator == "authority" and self.authority_order is not None:
            if not self.authority_order or len(set(self.authority_order)) != len(
                self.authority_order
            ):
                raise ValueError("authority_order must contain unique, non-empty labels")
            if any(not isinstance(level, str) or not level for level in self.authority_order):
                raise ValueError("authority_order must contain non-empty strings")
            if self.maximum_allowed not in self.authority_order:
                raise ValueError("maximum_allowed must appear in authority_order")
        authority_levels = {
            "suggestion",
            "recommendation",
            "draft",
            "decision",
            "authorized",
            "published",
        }
        if (
            self.evaluator == "authority"
            and self.authority_order is None
            and self.maximum_allowed not in authority_levels
        ):
            raise ValueError(
                "maximum_allowed must be one of: " + ", ".join(sorted(authority_levels))
            )
        return self


class SchemaReference(ContractModel):
    model: str = Field(min_length=1)


class GraphEdge(ContractModel):
    """One edge in the declared graph topology, with no semantic claim implied."""

    id: str = Field(min_length=1)
    producer: str = Field(min_length=1)
    consumer: str = Field(min_length=1)


class ContractEdge(GraphEdge):
    """A graph edge with one or more explicit consumer invariants."""

    schema_: SchemaReference | None = Field(default=None, alias="schema")
    invariants: tuple[Invariant, ...] = Field(min_length=1)


class ContractNode(ContractModel):
    id: str = Field(min_length=1)
    terminal: StrictBool = False
    side_effecting: StrictBool = False


class Contract(ContractModel):
    """Complete consumer-driven graph contract."""

    version: Literal["0.1", "0.2"]
    graph: str = Field(min_length=1)
    nodes: tuple[ContractNode, ...] = Field(min_length=1)
    graph_edges: tuple[GraphEdge, ...] | None = None
    edges: tuple[ContractEdge, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def graph_references_are_valid(self) -> Contract:
        node_ids = [node.id for node in self.nodes]
        if len(set(node_ids)) != len(node_ids):
            raise ValueError("node IDs must be unique")
        edge_ids = [edge.id for edge in self.edges]
        if len(set(edge_ids)) != len(edge_ids):
            raise ValueError("edge IDs must be unique")
        if self.version == "0.1" and self.graph_edges is not None:
            raise ValueError("graph_edges requires contract version '0.2'")
        if self.version == "0.2" and not self.graph_edges:
            raise ValueError(
                "contract version '0.2' requires graph_edges so total coverage has an "
                "explicit denominator"
            )
        known = set(node_ids)
        topology_edges = self.topology_edges
        topology_ids = [edge.id for edge in topology_edges]
        if len(set(topology_ids)) != len(topology_ids):
            raise ValueError("graph edge IDs must be unique")
        for edge in topology_edges:
            missing = {edge.producer, edge.consumer} - known
            if missing:
                raise ValueError(
                    f"graph edge {edge.id!r} references undefined node(s): "
                    f"{', '.join(sorted(missing))}"
                )
        topology_by_id = {edge.id: edge for edge in topology_edges}
        for edge in self.edges:
            topology_edge = topology_by_id.get(edge.id)
            if topology_edge is None:
                raise ValueError(f"contracted edge {edge.id!r} is absent from graph_edges")
            if (edge.producer, edge.consumer) != (
                topology_edge.producer,
                topology_edge.consumer,
            ):
                raise ValueError(f"contracted edge {edge.id!r} endpoints do not match graph_edges")
        return self

    @property
    def topology_edges(self) -> tuple[GraphEdge, ...]:
        """Return the explicit 0.2 topology or the contracted 0.1 fallback."""
        return self.graph_edges if self.graph_edges is not None else self.edges

    @property
    def graph_inventory_complete(self) -> bool:
        """Whether topology was explicitly declared independently of contracts."""
        return self.version == "0.2" and self.graph_edges is not None

    def edge(self, edge_id: str) -> ContractEdge:
        for edge in self.edges:
            if edge.id == edge_id:
                return edge
        raise KeyError(edge_id)
