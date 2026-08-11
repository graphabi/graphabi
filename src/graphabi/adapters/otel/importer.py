"""Fail-closed import of local OTLP/JSON and OpenInference span attributes."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from graphabi.models.traces import (
    EdgeObservation,
    GraphRun,
    JsonValue,
    NodeExecution,
    TraceBundle,
)

TELEMETRY_MAPPING_PROFILE = "graphabi.otel.openinference/0.1"

_JSON_VALUE = TypeAdapter(JsonValue)
_JSON_MAPPING = TypeAdapter(dict[str, JsonValue])
_HEX = frozenset("0123456789abcdefABCDEF")
_OPENINFERENCE_KINDS = frozenset(
    {
        "AGENT",
        "CHAIN",
        "EMBEDDING",
        "EVALUATOR",
        "GUARDRAIL",
        "LLM",
        "PROMPT",
        "RERANKER",
        "RETRIEVER",
        "TOOL",
    }
)
_GENAI_ROLES = {
    "chat": "LLM",
    "create_agent": "AGENT",
    "embeddings": "EMBEDDING",
    "execute_tool": "TOOL",
    "generate_content": "LLM",
    "invoke_agent": "AGENT",
    "invoke_workflow": "CHAIN",
    "retrieval": "RETRIEVER",
    "text_completion": "LLM",
}


class TelemetryImportDiagnostic(BaseModel):
    """One explicit import limitation or informational mapping decision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["INFO", "UNKNOWN"]
    code: str
    message: str
    trace_id: str | None = None
    span_id: str | None = None
    span_name: str | None = None


class TelemetryImportResult(BaseModel):
    """A trace bundle plus diagnostics that must travel with an uncertain import."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    profile: Literal["graphabi.otel.openinference/0.1"] = TELEMETRY_MAPPING_PROFILE
    status: Literal["PASS", "UNKNOWN"]
    source_span_count: int = Field(ge=0)
    imported_run_count: int = Field(ge=0)
    imported_node_count: int = Field(ge=0)
    imported_edge_count: int = Field(ge=0)
    diagnostics: tuple[TelemetryImportDiagnostic, ...]
    bundle: TraceBundle


@dataclass(frozen=True)
class _Span:
    trace_id: str
    span_id: str
    parent_span_id: str | None
    name: str
    start_ns: int
    end_ns: int
    status_code: int
    status_message: str | None
    attributes: dict[str, JsonValue]
    resource_attributes: dict[str, JsonValue]
    scope: dict[str, JsonValue]
    links: tuple[dict[str, JsonValue], ...]
    unmapped_fields: dict[str, JsonValue]
    raw_index: int

    @property
    def effective_attributes(self) -> dict[str, JsonValue]:
        return {**self.resource_attributes, **self.attributes}


def _object(value: object, location: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{location} must be a JSON object")
    return cast(dict[str, object], value)


def _array(value: object, location: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{location} must be a JSON array")
    return cast(list[object], value)


def _string(value: object, location: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{location} must be a non-empty string")
    return value


def _identifier(value: object, *, location: str, length: int, optional: bool = False) -> str | None:
    if optional and (value is None or value == ""):
        return None
    identifier = _string(value, location)
    if len(identifier) != length or any(character not in _HEX for character in identifier):
        raise ValueError(f"{location} must be a {length}-character hexadecimal identifier")
    return identifier.lower()


def _integer(value: object, location: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{location} must be an integer or a decimal integer string")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError as exc:
            raise ValueError(f"{location} must be an integer or a decimal integer string") from exc
    raise ValueError(f"{location} must be an integer or a decimal integer string")


def _any_value(raw: object, location: str) -> JsonValue:
    value = _object(raw, location)
    present = [
        key
        for key in (
            "stringValue",
            "boolValue",
            "intValue",
            "doubleValue",
            "arrayValue",
            "kvlistValue",
            "bytesValue",
        )
        if key in value
    ]
    if len(present) != 1:
        raise ValueError(f"{location} must contain exactly one OTLP AnyValue field")
    key = present[0]
    item = value[key]
    if key == "stringValue":
        if not isinstance(item, str):
            raise ValueError(f"{location}.stringValue must be a string")
        return item
    if key == "boolValue":
        if not isinstance(item, bool):
            raise ValueError(f"{location}.boolValue must be a boolean")
        return item
    if key == "intValue":
        return _integer(item, f"{location}.intValue")
    if key == "doubleValue":
        if isinstance(item, bool) or not isinstance(item, int | float):
            raise ValueError(f"{location}.doubleValue must be a number")
        return float(item)
    if key == "bytesValue":
        if not isinstance(item, str):
            raise ValueError(f"{location}.bytesValue must be a base64 string")
        return item
    container = _object(item, f"{location}.{key}")
    if key == "arrayValue":
        values = _array(container.get("values", []), f"{location}.arrayValue.values")
        return [
            _any_value(entry, f"{location}.arrayValue.values[{index}]")
            for index, entry in enumerate(values)
        ]
    values = _array(container.get("values", []), f"{location}.kvlistValue.values")
    return _attributes(values, f"{location}.kvlistValue.values")


def _attributes(raw: object, location: str) -> dict[str, JsonValue]:
    values = _array(raw, location)
    attributes: dict[str, JsonValue] = {}
    for index, item in enumerate(values):
        pair = _object(item, f"{location}[{index}]")
        key = _string(pair.get("key"), f"{location}[{index}].key")
        if key in attributes:
            raise ValueError(f"{location}[{index}].key duplicates attribute {key!r}")
        if "value" not in pair:
            raise ValueError(f"{location}[{index}] is missing value")
        attributes[key] = _any_value(pair["value"], f"{location}[{index}].value")
    return attributes


def _scope(raw: object, schema_url: object, location: str) -> dict[str, JsonValue]:
    scope = _object(raw, location) if raw is not None else {}
    result: dict[str, JsonValue] = {}
    for key in ("name", "version"):
        value = scope.get(key)
        if value is not None:
            result[key] = _string(value, f"{location}.{key}")
    if schema_url is not None:
        result["schema_url"] = _string(schema_url, f"{location}.schemaUrl")
    if "attributes" in scope:
        result["attributes"] = _attributes(scope["attributes"], f"{location}.attributes")
    return result


def _links(raw: object, location: str) -> tuple[dict[str, JsonValue], ...]:
    values = _array(raw, location)
    links: list[dict[str, JsonValue]] = []
    for index, item in enumerate(values):
        link = _object(item, f"{location}[{index}]")
        trace_id = _identifier(
            link.get("traceId"), location=f"{location}[{index}].traceId", length=32
        )
        span_id = _identifier(link.get("spanId"), location=f"{location}[{index}].spanId", length=16)
        links.append(
            {
                "trace_id": cast(str, trace_id),
                "span_id": cast(str, span_id),
                "attributes": _attributes(
                    link.get("attributes", []), f"{location}[{index}].attributes"
                ),
            }
        )
    return tuple(links)


def _parse_spans(payload: object) -> list[_Span]:
    document = _object(payload, "OTLP document")
    if "resource_spans" in document:
        raise ValueError(
            "OTLP document uses resource_spans; use protobuf JSON lowerCamelCase resourceSpans"
        )
    resource_spans = _array(document.get("resourceSpans"), "OTLP document.resourceSpans")
    parsed: list[_Span] = []
    for resource_index, raw_resource in enumerate(resource_spans):
        resource = _object(raw_resource, f"resourceSpans[{resource_index}]")
        resource_data = _object(
            resource.get("resource", {}), f"resourceSpans[{resource_index}].resource"
        )
        resource_attributes = _attributes(
            resource_data.get("attributes", []),
            f"resourceSpans[{resource_index}].resource.attributes",
        )
        scope_spans = _array(
            resource.get("scopeSpans", []), f"resourceSpans[{resource_index}].scopeSpans"
        )
        for scope_index, raw_scope_spans in enumerate(scope_spans):
            scope_data = _object(
                raw_scope_spans,
                f"resourceSpans[{resource_index}].scopeSpans[{scope_index}]",
            )
            scope = _scope(
                scope_data.get("scope"),
                scope_data.get("schemaUrl"),
                f"resourceSpans[{resource_index}].scopeSpans[{scope_index}].scope",
            )
            spans = _array(
                scope_data.get("spans", []),
                f"resourceSpans[{resource_index}].scopeSpans[{scope_index}].spans",
            )
            for span_index, raw_span in enumerate(spans):
                location = (
                    f"resourceSpans[{resource_index}].scopeSpans[{scope_index}].spans[{span_index}]"
                )
                span = _object(raw_span, location)
                start_ns = _integer(span.get("startTimeUnixNano"), f"{location}.startTimeUnixNano")
                end_ns = _integer(span.get("endTimeUnixNano"), f"{location}.endTimeUnixNano")
                if start_ns < 0 or end_ns < start_ns:
                    raise ValueError(f"{location} has an invalid start or end timestamp")
                status = _object(span.get("status", {}), f"{location}.status")
                status_code = _integer(status.get("code", 0), f"{location}.status.code")
                if status_code not in {0, 1, 2}:
                    raise ValueError(f"{location}.status.code must be 0, 1, or 2")
                status_message = status.get("message")
                if status_message is not None:
                    status_message = _string(status_message, f"{location}.status.message")
                parsed.append(
                    _Span(
                        trace_id=cast(
                            str,
                            _identifier(
                                span.get("traceId"), location=f"{location}.traceId", length=32
                            ),
                        ),
                        span_id=cast(
                            str,
                            _identifier(
                                span.get("spanId"), location=f"{location}.spanId", length=16
                            ),
                        ),
                        parent_span_id=_identifier(
                            span.get("parentSpanId"),
                            location=f"{location}.parentSpanId",
                            length=16,
                            optional=True,
                        ),
                        name=_string(span.get("name"), f"{location}.name"),
                        start_ns=start_ns,
                        end_ns=end_ns,
                        status_code=status_code,
                        status_message=cast(str | None, status_message),
                        attributes=_attributes(
                            span.get("attributes", []), f"{location}.attributes"
                        ),
                        resource_attributes=resource_attributes,
                        scope=scope,
                        links=_links(span.get("links", []), f"{location}.links"),
                        unmapped_fields=_JSON_MAPPING.validate_python(
                            {
                                key: value
                                for key, value in span.items()
                                if key
                                not in {
                                    "traceId",
                                    "spanId",
                                    "parentSpanId",
                                    "name",
                                    "startTimeUnixNano",
                                    "endTimeUnixNano",
                                    "status",
                                    "attributes",
                                    "links",
                                }
                            }
                        ),
                        raw_index=len(parsed),
                    )
                )
    identifiers = [(span.trace_id, span.span_id) for span in parsed]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("OTLP document contains duplicate traceId and spanId pairs")
    return parsed


def _timestamp(nanoseconds: int) -> datetime:
    seconds, remainder = divmod(nanoseconds, 1_000_000_000)
    return datetime.fromtimestamp(seconds, UTC).replace(microsecond=remainder // 1_000)


def _mapping(value: JsonValue, *, attribute: str, span: _Span) -> dict[str, JsonValue]:
    parsed: object = value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"span {span.span_id} attribute {attribute!r} must contain valid JSON: {exc.msg}"
            ) from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"span {span.span_id} attribute {attribute!r} must be a JSON object")
    return _JSON_MAPPING.validate_python(parsed)


def _payload(
    span: _Span,
    *,
    graphabi_key: str,
    openinference_key: str,
    mime_key: str,
) -> dict[str, JsonValue] | None:
    attributes = span.effective_attributes
    if graphabi_key in attributes:
        return _mapping(attributes[graphabi_key], attribute=graphabi_key, span=span)
    if openinference_key not in attributes:
        return None
    if attributes.get(mime_key) != "application/json":
        return None
    return _mapping(attributes[openinference_key], attribute=openinference_key, span=span)


def _text_attribute(span: _Span, key: str) -> str | None:
    value = span.effective_attributes.get(key)
    return value if isinstance(value, str) and value else None


def _semantic_role(span: _Span, diagnostics: list[TelemetryImportDiagnostic]) -> str:
    attributes = span.effective_attributes
    openinference_kind = attributes.get("openinference.span.kind")
    genai_operation = attributes.get("gen_ai.operation.name")
    oi_role = (
        openinference_kind
        if isinstance(openinference_kind, str) and openinference_kind in _OPENINFERENCE_KINDS
        else None
    )
    genai_role = _GENAI_ROLES.get(genai_operation) if isinstance(genai_operation, str) else None
    if openinference_kind is not None and oi_role is None:
        diagnostics.append(
            TelemetryImportDiagnostic(
                status="UNKNOWN",
                code="unsupported_openinference_span_kind",
                message=(
                    f"openinference.span.kind {openinference_kind!r} is not in the supported "
                    "OpenInference span-kind vocabulary"
                ),
                trace_id=span.trace_id,
                span_id=span.span_id,
                span_name=span.name,
            )
        )
    if genai_operation is not None and genai_role is None:
        diagnostics.append(
            TelemetryImportDiagnostic(
                status="UNKNOWN",
                code="unsupported_genai_operation",
                message=f"gen_ai.operation.name {genai_operation!r} has no supported role mapping",
                trace_id=span.trace_id,
                span_id=span.span_id,
                span_name=span.name,
            )
        )
    if oi_role is not None and genai_role is not None and oi_role != genai_role:
        diagnostics.append(
            TelemetryImportDiagnostic(
                status="UNKNOWN",
                code="conflicting_span_role",
                message=(
                    f"OpenInference maps this span to {oi_role}, while gen_ai.operation.name "
                    f"maps it to {genai_role}; semantic_role remains UNKNOWN"
                ),
                trace_id=span.trace_id,
                span_id=span.span_id,
                span_name=span.name,
            )
        )
        return "UNKNOWN"
    role = oi_role or genai_role
    if role is None:
        diagnostics.append(
            TelemetryImportDiagnostic(
                status="UNKNOWN",
                code="ambiguous_span_role",
                message=(
                    "span has no supported openinference.span.kind or gen_ai.operation.name; "
                    "semantic_role remains UNKNOWN"
                ),
                trace_id=span.trace_id,
                span_id=span.span_id,
                span_name=span.name,
            )
        )
        return "UNKNOWN"
    return role


def _causal_span_ids(span: _Span, nodes_by_span: Mapping[str, _Span]) -> tuple[str, ...]:
    parent_ids: list[str] = []
    if span.parent_span_id in nodes_by_span:
        parent_ids.append(cast(str, span.parent_span_id))
    for link in span.links:
        attributes = link.get("attributes")
        if not isinstance(attributes, dict) or attributes.get("graphabi.causal_parent") is not True:
            continue
        if link.get("trace_id") != span.trace_id:
            continue
        linked_span_id = link.get("span_id")
        if isinstance(linked_span_id, str) and linked_span_id in nodes_by_span:
            parent_ids.append(linked_span_id)
    return tuple(dict.fromkeys(parent_ids))


def _topological_spans(
    nodes: Sequence[_Span], diagnostics: list[TelemetryImportDiagnostic]
) -> list[_Span]:
    by_id = {span.span_id: span for span in nodes}
    parents = {span.span_id: _causal_span_ids(span, by_id) for span in nodes}
    remaining = {span.span_id for span in nodes}
    ordered: list[_Span] = []
    while remaining:
        ready = sorted(
            (
                span
                for span in nodes
                if span.span_id in remaining and not (set(parents[span.span_id]) & remaining)
            ),
            key=lambda span: span.raw_index,
        )
        if not ready:
            cycle = ", ".join(sorted(remaining))
            raise ValueError(f"GraphABI causal parent links contain a cycle among spans: {cycle}")
        for span in ready:
            ordered.append(span)
            remaining.remove(span.span_id)
    for span in nodes:
        if span.parent_span_id is not None and span.parent_span_id not in by_id:
            diagnostics.append(
                TelemetryImportDiagnostic(
                    status="INFO",
                    code="external_or_container_parent",
                    message=(
                        "OTel parent is not an imported GraphABI node; its span ID is retained "
                        "as telemetry metadata but is not fabricated as a node occurrence"
                    ),
                    trace_id=span.trace_id,
                    span_id=span.span_id,
                    span_name=span.name,
                )
            )
    return ordered


def _metadata(span: _Span, semantic_role: str) -> dict[str, JsonValue]:
    return _JSON_MAPPING.validate_python(
        {
            "telemetry": {
                "mapping_profile": TELEMETRY_MAPPING_PROFILE,
                "semantic_role": semantic_role,
                "trace_id": span.trace_id,
                "span_id": span.span_id,
                "parent_span_id": span.parent_span_id,
                "span_name": span.name,
                "status_code": span.status_code,
                "status_message": span.status_message,
                "attributes": span.attributes,
                "resource_attributes": span.resource_attributes,
                "instrumentation_scope": span.scope,
                "links": list(span.links),
                "unmapped_span_fields": span.unmapped_fields,
            }
        }
    )


def _int_attribute(span: _Span, key: str, default: int) -> int:
    value = span.effective_attributes.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"span {span.span_id} attribute {key!r} must be an integer of at least 1")
    return value


def _framework(span: _Span) -> tuple[str, str]:
    attributes = span.effective_attributes
    if "openinference.span.kind" in attributes:
        framework = "openinference"
    elif "gen_ai.operation.name" in attributes:
        framework = "opentelemetry-genai"
    else:
        framework = "opentelemetry"
    version = attributes.get("openinference.version") or attributes.get("telemetry.sdk.version")
    return framework, version if isinstance(version, str) and version else "unspecified"


def _run_payload(
    spans: Sequence[_Span], key: str, diagnostics: list[TelemetryImportDiagnostic]
) -> dict[str, JsonValue]:
    candidates = [span for span in spans if key in span.effective_attributes]
    if len(candidates) == 1:
        return _mapping(candidates[0].effective_attributes[key], attribute=key, span=candidates[0])
    trace_id = spans[0].trace_id
    if not candidates:
        message = f"trace is missing one explicit {key!r} JSON object; imported value is empty"
        code = "missing_run_payload"
    else:
        message = f"trace has multiple {key!r} values; imported value is empty"
        code = "ambiguous_run_payload"
    diagnostics.append(
        TelemetryImportDiagnostic(status="UNKNOWN", code=code, message=message, trace_id=trace_id)
    )
    return {}


def _make_run(
    spans: Sequence[_Span], diagnostics: list[TelemetryImportDiagnostic]
) -> tuple[GraphRun | None, tuple[EdgeObservation, ...]]:
    trace_id = spans[0].trace_id
    node_spans = [span for span in spans if _text_attribute(span, "graphabi.node.id") is not None]
    for span in spans:
        kind = _text_attribute(span, "graphabi.span.kind")
        if span not in node_spans and kind != "run":
            diagnostics.append(
                TelemetryImportDiagnostic(
                    status="UNKNOWN",
                    code="unsupported_span_shape",
                    message=(
                        "span is neither graphabi.span.kind=run nor an explicit GraphABI node; "
                        "add graphabi.node.id or leave it outside the import file"
                    ),
                    trace_id=trace_id,
                    span_id=span.span_id,
                    span_name=span.name,
                )
            )
    if not node_spans:
        diagnostics.append(
            TelemetryImportDiagnostic(
                status="UNKNOWN",
                code="no_supported_nodes",
                message="trace contains no spans with graphabi.node.id",
                trace_id=trace_id,
            )
        )
        return None, ()

    graph_ids = {_text_attribute(span, "graphabi.graph.id") for span in node_spans}
    graph_versions = {_text_attribute(span, "graphabi.graph.version") for span in node_spans}
    if None in graph_ids or len(graph_ids) != 1:
        diagnostics.append(
            TelemetryImportDiagnostic(
                status="UNKNOWN",
                code="ambiguous_graph_identity",
                message=(
                    "every imported node must have one consistent graphabi.graph.id; "
                    "the trace was not imported"
                ),
                trace_id=trace_id,
            )
        )
        return None, ()
    if None in graph_versions or len(graph_versions) != 1:
        diagnostics.append(
            TelemetryImportDiagnostic(
                status="UNKNOWN",
                code="ambiguous_graph_version",
                message=(
                    "every imported node must have one consistent graphabi.graph.version; "
                    "the trace was not imported"
                ),
                trace_id=trace_id,
            )
        )
        return None, ()
    graph_id = cast(str, next(iter(graph_ids)))
    graph_version = cast(str, next(iter(graph_versions)))
    run_ids = {
        value for span in spans if (value := _text_attribute(span, "graphabi.run.id")) is not None
    }
    if len(run_ids) > 1:
        diagnostics.append(
            TelemetryImportDiagnostic(
                status="UNKNOWN",
                code="ambiguous_run_identity",
                message="trace has conflicting graphabi.run.id values and was not imported",
                trace_id=trace_id,
            )
        )
        return None, ()
    run_id = next(iter(run_ids), trace_id)
    variants = {
        value
        for span in spans
        if (value := _text_attribute(span, "graphabi.run.variant")) is not None
    }
    if len(variants) > 1 or (
        variants and next(iter(variants)) not in {"baseline", "candidate", "other"}
    ):
        raise ValueError(
            f"trace {trace_id} graphabi.run.variant must consistently be baseline, "
            "candidate, or other"
        )
    variant = next(iter(variants), "other")

    ordered = _topological_spans(node_spans, diagnostics)
    by_id = {span.span_id: span for span in node_spans}
    node_ids = [_text_attribute(span, "graphabi.node.id") for span in node_spans]
    repeated_node_ids = {node_id for node_id in node_ids if node_ids.count(node_id) > 1}
    executions: list[NodeExecution] = []
    executions_by_span: dict[str, NodeExecution] = {}
    for sequence, span in enumerate(ordered):
        node_id = cast(str, _text_attribute(span, "graphabi.node.id"))
        if node_id in repeated_node_ids and "graphabi.attempt" not in span.effective_attributes:
            diagnostics.append(
                TelemetryImportDiagnostic(
                    status="UNKNOWN",
                    code="ambiguous_repeated_node",
                    message=(
                        f"node {node_id!r} repeats without graphabi.attempt; occurrence IDs remain "
                        "distinct, but retry meaning is unknown"
                    ),
                    trace_id=trace_id,
                    span_id=span.span_id,
                    span_name=span.name,
                )
            )
        input_data = _payload(
            span,
            graphabi_key="graphabi.node.input",
            openinference_key="input.value",
            mime_key="input.mime_type",
        )
        output_data = _payload(
            span,
            graphabi_key="graphabi.node.output",
            openinference_key="output.value",
            mime_key="output.mime_type",
        )
        if input_data is None or output_data is None:
            missing = "input" if input_data is None else "output"
            diagnostics.append(
                TelemetryImportDiagnostic(
                    status="UNKNOWN",
                    code="missing_node_payload",
                    message=(
                        f"node has no deterministic JSON-object {missing} mapping; use "
                        f"graphabi.node.{missing} or OpenInference {missing}.value with "
                        "application/json"
                    ),
                    trace_id=trace_id,
                    span_id=span.span_id,
                    span_name=span.name,
                )
            )
        semantic_role = _semantic_role(span, diagnostics)
        causal_span_ids = _causal_span_ids(span, by_id)
        causal_occurrences = tuple(f"otel-span:{parent_id}" for parent_id in causal_span_ids)
        framework, framework_version = _framework(span)
        execution = NodeExecution(
            schema_version="0.2",
            run_id=run_id,
            graph_id=graph_id,
            graph_version=graph_version,
            node_id=node_id,
            occurrence_id=f"otel-span:{span.span_id}",
            parent_occurrence_id=causal_occurrences[0] if causal_occurrences else None,
            causal_parent_occurrence_ids=causal_occurrences,
            incoming_edge_id=_text_attribute(span, "graphabi.edge.id"),
            causal_sequence=sequence,
            branch_id=_text_attribute(span, "graphabi.branch.id"),
            attempt=_int_attribute(span, "graphabi.attempt", 1),
            input=input_data or {},
            output=output_data or {},
            metadata=_metadata(span, semantic_role),
            started_at=_timestamp(span.start_ns),
            ended_at=_timestamp(span.end_ns),
            duration_ms=(span.end_ns - span.start_ns) / 1_000_000,
            status="error" if span.status_code == 2 else "success",
            error=span.status_message if span.status_code == 2 else None,
            framework=framework,
            framework_version=framework_version,
        )
        executions.append(execution)
        executions_by_span[span.span_id] = execution

    observations: list[EdgeObservation] = []
    edge_spans = [span for span in ordered if _text_attribute(span, "graphabi.edge.id") is not None]
    for edge_sequence, span in enumerate(edge_spans):
        attributes = span.effective_attributes
        edge_id = cast(str, _text_attribute(span, "graphabi.edge.id"))
        producer_id = _text_attribute(span, "graphabi.edge.producer")
        consumer_id = _text_attribute(span, "graphabi.edge.consumer")
        producer_span_id = _text_attribute(span, "graphabi.edge.producer_span_id")
        output_value = attributes.get("graphabi.edge.output")
        missing = [
            name
            for name, value in (
                ("graphabi.edge.producer", producer_id),
                ("graphabi.edge.consumer", consumer_id),
                ("graphabi.edge.producer_span_id", producer_span_id),
                ("graphabi.edge.output", output_value),
            )
            if value is None
        ]
        if missing:
            diagnostics.append(
                TelemetryImportDiagnostic(
                    status="UNKNOWN",
                    code="incomplete_edge_mapping",
                    message=(
                        f"edge {edge_id!r} is missing {', '.join(missing)} and was not imported"
                    ),
                    trace_id=trace_id,
                    span_id=span.span_id,
                    span_name=span.name,
                )
            )
            continue
        producer = executions_by_span.get(cast(str, producer_span_id))
        consumer = executions_by_span[span.span_id]
        if producer is None or producer.node_id != producer_id or consumer.node_id != consumer_id:
            diagnostics.append(
                TelemetryImportDiagnostic(
                    status="UNKNOWN",
                    code="edge_endpoint_mismatch",
                    message=(
                        f"edge {edge_id!r} endpoint IDs do not match imported producer and "
                        "consumer occurrences; the edge was not imported"
                    ),
                    trace_id=trace_id,
                    span_id=span.span_id,
                    span_name=span.name,
                )
            )
            continue
        if producer.occurrence_id not in consumer.causal_parent_occurrence_ids:
            diagnostics.append(
                TelemetryImportDiagnostic(
                    status="UNKNOWN",
                    code="edge_without_causal_parent",
                    message=(
                        f"edge {edge_id!r} names a producer that is not an OTel parent or an "
                        "explicit graphabi.causal_parent link; the edge was not imported"
                    ),
                    trace_id=trace_id,
                    span_id=span.span_id,
                    span_name=span.name,
                )
            )
            continue
        edge_output = _mapping(
            cast(JsonValue, output_value), attribute="graphabi.edge.output", span=span
        )
        edge_metadata_value = attributes.get("graphabi.edge.metadata", {})
        edge_metadata = _mapping(edge_metadata_value, attribute="graphabi.edge.metadata", span=span)
        observations.append(
            EdgeObservation(
                schema_version="0.2",
                run_id=run_id,
                graph_id=graph_id,
                graph_version=graph_version,
                edge_id=edge_id,
                producer=cast(str, producer_id),
                consumer=cast(str, consumer_id),
                occurrence_id=f"otel-edge:{span.span_id}:{edge_id}",
                producer_occurrence_id=producer.occurrence_id,
                consumer_occurrence_id=consumer.occurrence_id,
                causal_sequence=edge_sequence,
                branch_id=consumer.branch_id,
                attempt=consumer.attempt,
                input=consumer.input,
                output=edge_output,
                metadata=edge_metadata,
                observed_at=producer.ended_at,
            )
        )

    graph_run = GraphRun(
        schema_version="0.2",
        run_id=run_id,
        graph_id=graph_id,
        graph_version=graph_version,
        variant=cast(Any, variant),
        started_at=min(_timestamp(span.start_ns) for span in spans),
        ended_at=max(_timestamp(span.end_ns) for span in spans),
        status=(
            "error" if any(execution.status == "error" for execution in executions) else "success"
        ),
        input=_run_payload(spans, "graphabi.run.input", diagnostics),
        output=_run_payload(spans, "graphabi.run.output", diagnostics),
        executions=tuple(executions),
    )
    return graph_run, tuple(observations)


def import_otlp_json(payload: object) -> TelemetryImportResult:
    """Map an OTLP/JSON ExportTraceServiceRequest without network access."""
    spans = _parse_spans(payload)
    diagnostics: list[TelemetryImportDiagnostic] = []
    if not spans:
        diagnostics.append(
            TelemetryImportDiagnostic(
                status="UNKNOWN",
                code="no_spans",
                message="OTLP document contains no spans, so no GraphABI run can be mapped",
            )
        )
    spans_by_trace: dict[str, list[_Span]] = {}
    for span in spans:
        spans_by_trace.setdefault(span.trace_id, []).append(span)
    runs: list[GraphRun] = []
    observations: list[EdgeObservation] = []
    for trace_spans in spans_by_trace.values():
        run, run_observations = _make_run(trace_spans, diagnostics)
        if run is not None:
            runs.append(run)
            observations.extend(run_observations)
    bundle = TraceBundle(
        schema_version="0.2", runs=tuple(runs), edge_observations=tuple(observations)
    )
    return TelemetryImportResult(
        status="UNKNOWN" if any(item.status == "UNKNOWN" for item in diagnostics) else "PASS",
        source_span_count=len(spans),
        imported_run_count=len(runs),
        imported_node_count=sum(len(run.executions) for run in runs),
        imported_edge_count=len(observations),
        diagnostics=tuple(diagnostics),
        bundle=bundle,
    )


def load_otlp_json(path: Path) -> TelemetryImportResult:
    """Load one local OTLP/JSON ExportTraceServiceRequest and import supported spans."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}:{exc.lineno}:{exc.colno}: invalid JSON: {exc.msg}") from exc
    return import_otlp_json(payload)
