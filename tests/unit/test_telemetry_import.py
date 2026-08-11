from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from graphabi.adapters.otel import import_otlp_json, load_otlp_json


def _fixture(repository_root: Path, name: str) -> Path:
    return repository_root / "tests/fixtures/telemetry" / name


def _payload(repository_root: Path, name: str = "openinference-otlp.json") -> dict[str, Any]:
    return json.loads(_fixture(repository_root, name).read_text(encoding="utf-8"))


def _spans(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return payload["resourceSpans"][0]["scopeSpans"][0]["spans"]


def _attribute(key: str, value: dict[str, Any]) -> dict[str, Any]:
    return {"key": key, "value": value}


def test_imports_openinference_spans_and_explicit_edges(repository_root: Path) -> None:
    result = load_otlp_json(_fixture(repository_root, "openinference-otlp.json"))

    assert result.status == "PASS"
    assert result.source_span_count == 4
    assert result.imported_run_count == 1
    assert result.imported_node_count == 3
    assert result.imported_edge_count == 2
    run = result.bundle.runs[0]
    assert run.schema_version == "0.2"
    assert run.run_id == "otel-run-001"
    assert run.input == {"query": "release evidence"}
    assert run.output == {"published": True}
    assert [execution.node_id for execution in run.executions] == [
        "researcher",
        "answerer",
        "publisher",
    ]
    answerer = run.executions[1]
    assert answerer.occurrence_id == "otel-span:0000000000000003"
    assert answerer.parent_occurrence_id == "otel-span:0000000000000002"
    telemetry = answerer.metadata["telemetry"]
    assert isinstance(telemetry, dict)
    assert telemetry["trace_id"] == "11111111111111111111111111111111"
    assert telemetry["semantic_role"] == "LLM"
    attributes = telemetry["attributes"]
    assert isinstance(attributes, dict)
    assert attributes["demo.extra"] == "retained"
    unmapped = telemetry["unmapped_span_fields"]
    assert isinstance(unmapped, dict)
    assert unmapped["kind"] == 1
    assert result.bundle.edge_observations[0].output == {"brief": "Evidence gathered"}
    assert result.diagnostics[0].code == "external_or_container_parent"


def test_imports_current_opentelemetry_genai_roles(repository_root: Path) -> None:
    result = load_otlp_json(_fixture(repository_root, "opentelemetry-genai-otlp.json"))

    assert result.status == "PASS"
    run = result.bundle.runs[0]
    assert [execution.framework for execution in run.executions] == [
        "opentelemetry-genai",
        "opentelemetry-genai",
    ]
    roles = []
    for execution in run.executions:
        telemetry = execution.metadata["telemetry"]
        assert isinstance(telemetry, dict)
        roles.append(telemetry["semantic_role"])
    assert roles == ["AGENT", "TOOL"]
    assert run.executions[0].status == "success"


def test_decodes_otlp_values_scope_and_error_status(repository_root: Path) -> None:
    payload = _payload(repository_root, "opentelemetry-genai-otlp.json")
    resource_attributes = payload["resourceSpans"][0]["resource"]["attributes"]
    resource_attributes.extend(
        [
            _attribute("demo.bool", {"boolValue": True}),
            _attribute("demo.int", {"intValue": "42"}),
            _attribute("demo.double", {"doubleValue": 1.5}),
            _attribute("demo.bytes", {"bytesValue": "AQI="}),
            _attribute(
                "demo.array",
                {"arrayValue": {"values": [{"stringValue": "one"}, {"intValue": "2"}]}},
            ),
            _attribute(
                "demo.map",
                {"kvlistValue": {"values": [_attribute("nested", {"boolValue": False})]}},
            ),
        ]
    )
    scope = payload["resourceSpans"][0]["scopeSpans"][0]["scope"]
    scope["attributes"] = [_attribute("scope.mode", {"stringValue": "fixture"})]
    publisher = _spans(payload)[2]
    publisher["status"] = {"code": 2, "message": "fixture failure"}

    result = import_otlp_json(payload)

    assert result.status == "PASS"
    execution = result.bundle.runs[0].executions[-1]
    assert execution.status == "error"
    assert execution.error == "fixture failure"
    telemetry = execution.metadata["telemetry"]
    assert isinstance(telemetry, dict)
    resource = telemetry["resource_attributes"]
    assert isinstance(resource, dict)
    assert resource["demo.array"] == ["one", 2]
    assert resource["demo.map"] == {"nested": False}
    instrumentation_scope = telemetry["instrumentation_scope"]
    assert isinstance(instrumentation_scope, dict)
    assert instrumentation_scope["attributes"] == {"scope.mode": "fixture"}


def test_unsupported_and_conflicting_spans_are_unknown(repository_root: Path) -> None:
    payload = _payload(repository_root)
    spans = _spans(payload)
    generic = deepcopy(spans[1])
    generic["spanId"] = "0000000000000099"
    generic["parentSpanId"] = "0000000000000001"
    generic["name"] = "http request"
    generic["attributes"] = []
    spans.append(generic)
    answerer_attributes = spans[2]["attributes"]
    operation = next(item for item in answerer_attributes if item["key"] == "gen_ai.operation.name")
    operation["value"]["stringValue"] = "execute_tool"

    result = import_otlp_json(payload)

    assert result.status == "UNKNOWN"
    assert result.imported_node_count == 3
    codes = {diagnostic.code for diagnostic in result.diagnostics}
    assert "unsupported_span_shape" in codes
    assert "conflicting_span_role" in codes
    answerer = result.bundle.runs[0].executions[1]
    telemetry = answerer.metadata["telemetry"]
    assert isinstance(telemetry, dict)
    assert telemetry["semantic_role"] == "UNKNOWN"


def test_empty_document_and_nonstandard_role_case_are_unknown(repository_root: Path) -> None:
    empty = import_otlp_json({"resourceSpans": []})
    assert empty.status == "UNKNOWN"
    assert empty.diagnostics[0].code == "no_spans"

    payload = _payload(repository_root)
    role = next(
        item
        for item in _spans(payload)[1]["attributes"]
        if item["key"] == "openinference.span.kind"
    )
    role["value"]["stringValue"] = "agent"
    result = import_otlp_json(payload)
    assert result.status == "UNKNOWN"
    assert "unsupported_openinference_span_kind" in {item.code for item in result.diagnostics}


def test_explicit_causal_link_preserves_fan_in_parent(repository_root: Path) -> None:
    payload = _payload(repository_root)
    spans = _spans(payload)
    alternate = deepcopy(spans[2])
    alternate["spanId"] = "0000000000000005"
    alternate["name"] = "alternate_answerer"
    for item in alternate["attributes"]:
        if item["key"] == "graphabi.node.id":
            item["value"]["stringValue"] = "alternate_answerer"
        elif item["key"] == "openinference.span.kind":
            item["value"]["stringValue"] = "CHAIN"
        elif item["key"] == "gen_ai.operation.name":
            item["value"]["stringValue"] = "invoke_workflow"
    alternate["attributes"] = [
        item for item in alternate["attributes"] if not item["key"].startswith("graphabi.edge.")
    ]
    spans.insert(3, alternate)
    publisher = spans[4]
    publisher["links"] = [
        {
            "traceId": "11111111111111111111111111111111",
            "spanId": "0000000000000005",
            "attributes": [{"key": "graphabi.causal_parent", "value": {"boolValue": True}}],
        }
    ]

    result = import_otlp_json(payload)

    assert result.status == "PASS"
    publisher_execution = result.bundle.runs[0].executions[-1]
    assert publisher_execution.causal_parent_occurrence_ids == (
        "otel-span:0000000000000003",
        "otel-span:0000000000000005",
    )


def test_missing_payload_and_incomplete_edge_stay_unknown(repository_root: Path) -> None:
    payload = _payload(repository_root)
    answerer = _spans(payload)[2]
    answerer["attributes"] = [
        item
        for item in answerer["attributes"]
        if item["key"] not in {"output.value", "graphabi.edge.output"}
    ]

    result = import_otlp_json(payload)

    assert result.status == "UNKNOWN"
    assert result.bundle.runs[0].executions[1].output == {}
    assert result.imported_edge_count == 1
    codes = {diagnostic.code for diagnostic in result.diagnostics}
    assert "missing_node_payload" in codes
    assert "incomplete_edge_mapping" in codes


def test_missing_graph_identity_is_an_explicit_unknown(repository_root: Path) -> None:
    payload = _payload(repository_root)
    resource_attributes = payload["resourceSpans"][0]["resource"]["attributes"]
    payload["resourceSpans"][0]["resource"]["attributes"] = [
        item for item in resource_attributes if item["key"] != "graphabi.graph.id"
    ]

    result = import_otlp_json(payload)

    assert result.status == "UNKNOWN"
    assert result.imported_run_count == 0
    assert result.diagnostics[-1].code == "ambiguous_graph_identity"


def test_identity_and_run_ambiguities_remain_unknown(repository_root: Path) -> None:
    missing_nodes = _payload(repository_root)
    for span in _spans(missing_nodes):
        span["attributes"] = [
            item for item in span["attributes"] if item["key"] != "graphabi.node.id"
        ]
    result = import_otlp_json(missing_nodes)
    assert result.status == "UNKNOWN"
    assert "no_supported_nodes" in {item.code for item in result.diagnostics}

    missing_version = _payload(repository_root)
    resource_attributes = missing_version["resourceSpans"][0]["resource"]["attributes"]
    missing_version["resourceSpans"][0]["resource"]["attributes"] = [
        item for item in resource_attributes if item["key"] != "graphabi.graph.version"
    ]
    result = import_otlp_json(missing_version)
    assert result.status == "UNKNOWN"
    assert result.diagnostics[-1].code == "ambiguous_graph_version"

    conflicting_run = _payload(repository_root)
    _spans(conflicting_run)[1]["attributes"].append(
        _attribute("graphabi.run.id", {"stringValue": "different-run"})
    )
    result = import_otlp_json(conflicting_run)
    assert result.status == "UNKNOWN"
    assert result.diagnostics[-1].code == "ambiguous_run_identity"


def test_missing_run_payload_and_repeated_node_are_unknown(repository_root: Path) -> None:
    payload = _payload(repository_root)
    run_span = _spans(payload)[0]
    run_span["attributes"] = [
        item
        for item in run_span["attributes"]
        if item["key"] not in {"graphabi.run.input", "graphabi.run.output"}
    ]
    repeated = deepcopy(_spans(payload)[1])
    repeated["spanId"] = "0000000000000088"
    repeated["name"] = "researcher retry"
    _spans(payload).append(repeated)

    result = import_otlp_json(payload)

    assert result.status == "UNKNOWN"
    codes = [item.code for item in result.diagnostics]
    assert codes.count("missing_run_payload") == 2
    assert codes.count("ambiguous_repeated_node") == 2


def test_edge_endpoint_and_causal_ambiguities_are_unknown(repository_root: Path) -> None:
    endpoint_mismatch = _payload(repository_root)
    edge_attributes = _spans(endpoint_mismatch)[2]["attributes"]
    producer = next(item for item in edge_attributes if item["key"] == "graphabi.edge.producer")
    producer["value"]["stringValue"] = "wrong_producer"
    result = import_otlp_json(endpoint_mismatch)
    assert result.status == "UNKNOWN"
    assert "edge_endpoint_mismatch" in {item.code for item in result.diagnostics}

    noncausal = _payload(repository_root)
    edge_attributes = _spans(noncausal)[2]["attributes"]
    producer = next(item for item in edge_attributes if item["key"] == "graphabi.edge.producer")
    producer["value"]["stringValue"] = "publisher"
    producer_span = next(
        item for item in edge_attributes if item["key"] == "graphabi.edge.producer_span_id"
    )
    producer_span["value"]["stringValue"] = "0000000000000004"
    result = import_otlp_json(noncausal)
    assert result.status == "UNKNOWN"
    assert "edge_without_causal_parent" in {item.code for item in result.diagnostics}


def test_invalid_explicit_values_fail_with_corrections(repository_root: Path) -> None:
    duplicate = _payload(repository_root)
    attributes = _spans(duplicate)[1]["attributes"]
    attributes.append(deepcopy(attributes[0]))
    with pytest.raises(ValueError, match="duplicates attribute"):
        import_otlp_json(duplicate)

    bad_status = _payload(repository_root)
    _spans(bad_status)[0]["status"] = {"code": 9}
    with pytest.raises(ValueError, match=r"status\.code must be 0, 1, or 2"):
        import_otlp_json(bad_status)

    bad_time = _payload(repository_root)
    _spans(bad_time)[0]["endTimeUnixNano"] = "1"
    with pytest.raises(ValueError, match="invalid start or end timestamp"):
        import_otlp_json(bad_time)

    bad_attempt = _payload(repository_root)
    _spans(bad_attempt)[1]["attributes"].append(_attribute("graphabi.attempt", {"intValue": "0"}))
    with pytest.raises(ValueError, match="integer of at least 1"):
        import_otlp_json(bad_attempt)

    bad_json = _payload(repository_root)
    output_value = next(
        item for item in _spans(bad_json)[1]["attributes"] if item["key"] == "output.value"
    )
    output_value["value"]["stringValue"] = "{broken"
    with pytest.raises(ValueError, match="must contain valid JSON"):
        import_otlp_json(bad_json)


def test_rejects_non_otlp_json_names_and_invalid_identifiers(repository_root: Path) -> None:
    with pytest.raises(ValueError, match="lowerCamelCase resourceSpans"):
        import_otlp_json({"resource_spans": []})

    payload = _payload(repository_root)
    _spans(payload)[0]["traceId"] = "not-a-trace-id"
    with pytest.raises(ValueError, match="32-character hexadecimal identifier"):
        import_otlp_json(payload)


def test_local_loader_contextualizes_invalid_json(tmp_path: Path) -> None:
    trace = tmp_path / "broken.json"
    trace.write_text("{broken", encoding="utf-8")

    with pytest.raises(ValueError, match=r"broken.json:1:2: invalid JSON"):
        load_otlp_json(trace)
