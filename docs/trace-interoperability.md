# OpenTelemetry and OpenInference trace import

GraphABI implements one deliberately narrow local import profile:
`graphabi.otel.openinference/0.1`. It accepts the JSON protobuf representation of an OTLP
`ExportTraceServiceRequest`. It does not connect to a collector, accept OTLP protobuf, or claim
that arbitrary OpenTelemetry traces contain GraphABI graph semantics.

The profile follows the official
[OTLP JSON encoding](https://opentelemetry.io/docs/specs/otlp/#json-protobuf-encoding), including
lowerCamelCase field names, hexadecimal trace and span IDs, integer enum values, and decimal
strings for 64-bit timestamps. Role classification follows the current
[OpenInference span kinds](https://arize-ai.github.io/openinference/spec/semantic_conventions.html#span-kinds)
and the current OpenTelemetry
[Generative AI operation names](https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/#gen-ai-operation-name).

## Local command

```bash
graphabi import-otel traces.otlp.json --output .graphabi/imports/latest.json
graphabi record .graphabi/imports/latest.json
```

`import-otel` always writes a version 0.2 `TraceBundle` when the OTLP document is syntactically
valid. It returns exit code `0` for a complete supported mapping and `3` when any mapping is
`UNKNOWN`. A partial bundle may still be written on `UNKNOWN`, so automation must inspect the exit
code and diagnostics before using it. Use `--json-output` before the command for a JSON summary.
A telemetry import `PASS` means only that every span used the supported mapping profile. It is not
a compatibility finding and does not imply semantic safety.

The importer reads one local file and makes no network requests.

## Exact mapping table

| OTLP or semantic-convention field | GraphABI field | Rule |
|---|---|---|
| `traceId` | run grouping and retained metadata | One OTLP trace maps to at most one `GraphRun`. The original ID is retained. |
| `spanId` | `occurrence_id` | Mapped as `otel-span:<spanId>` for a supported node span. |
| `parentSpanId` | causal parent | Mapped only when the parent is another supported GraphABI node in the same trace. |
| span link | additional causal parent | Mapped only for a same-trace link with boolean `graphabi.causal_parent=true`. |
| start and end nanoseconds | execution and run timestamps | Parsed from OTLP decimal integers or decimal strings. |
| OTel status `ERROR` (`2`) | execution `error` | `UNSET` (`0`) and `OK` (`1`) mean the recorded operation did not report an error. They do not imply semantic correctness. |
| `openinference.span.kind` | retained `semantic_role` | Current documented values are accepted. A conflicting GenAI role produces `UNKNOWN`. |
| `gen_ai.operation.name` | retained `semantic_role` | `chat`, `text_completion`, and `generate_content` map to `LLM`; agent, tool, workflow, embedding, and retrieval operations map to their matching roles. |
| `input.value` and `output.value` | node input and output | Used only with the matching MIME type `application/json`, and only when the JSON value is an object. |
| `graphabi.node.input` and `.output` | node input and output | Explicit JSON-object overrides for sources that do not emit OpenInference payload fields. |
| all span and resource attributes | execution metadata | Retained under `metadata.telemetry`, including attributes not understood by GraphABI. |
| other span fields | execution metadata | Retained under `metadata.telemetry.unmapped_span_fields`; they do not create semantics. |

OpenInference `AGENT`, `LLM`, `TOOL`, and other kinds classify an explicitly identified node span.
They do not identify a graph, prove an edge crossing, or prove source support by themselves.

## Required GraphABI attributes

Graph identity attributes may be resource attributes or repeated on node spans. A span attribute
overrides a resource attribute with the same key.

| Attribute | Required | Meaning |
|---|---:|---|
| `graphabi.graph.id` | every node | Stable graph identifier. All imported nodes in one trace must agree. |
| `graphabi.graph.version` | every node | Graph version. All imported nodes in one trace must agree. |
| `graphabi.node.id` | every node | Marks a span as a node execution and gives the logical node ID. |
| `graphabi.span.kind=run` | run container only | Marks a non-node container span. It is not fabricated as a node occurrence. |
| `graphabi.run.id` | optional | Run ID. The OTLP trace ID is used when absent. Conflicting values produce `UNKNOWN`. |
| `graphabi.run.variant` | optional | `baseline`, `candidate`, or `other`; defaults to `other`. |
| `graphabi.run.input` | one span per trace | JSON object for the graph input. Missing or multiple values produce `UNKNOWN`. |
| `graphabi.run.output` | one span per trace | JSON object for the graph output. Missing or multiple values produce `UNKNOWN`. |
| `graphabi.branch.id` | optional | Stable branch identity when instrumentation has one. |
| `graphabi.attempt` | optional | Positive integer retry attempt; defaults to `1`. A repeated node without it produces `UNKNOWN`. |

An edge is created only when the consumer span supplies all of these attributes:

| Attribute | Meaning |
|---|---|
| `graphabi.edge.id` | Stable logical edge ID. |
| `graphabi.edge.producer` | Producer node ID. |
| `graphabi.edge.consumer` | Consumer node ID, which must match the current span. |
| `graphabi.edge.producer_span_id` | Exact producer occurrence span ID. |
| `graphabi.edge.output` | JSON object observed crossing the edge. |
| `graphabi.edge.metadata` | Optional JSON object of edge evidence. |

The named producer must be an imported parent occurrence or an explicitly causal linked
occurrence. Missing attributes, mismatched endpoints, and non-causal producers produce `UNKNOWN`;
the importer never guesses from span names, timestamps, payload equality, or nesting through an
unsupported span.

## Unsupported and ambiguous data

The JSON result and terminal output identify each unsupported span by trace ID, span ID, span name,
diagnostic code, and correction. Important cases include:

- a generic span without `graphabi.node.id` or `graphabi.span.kind=run`;
- missing or conflicting graph and run identity;
- non-object or missing node payloads;
- an unknown or conflicting OpenInference and GenAI role;
- repeated logical nodes without explicit retry attempts;
- incomplete or causally inconsistent edge attributes.

These cases remain `UNKNOWN`. They are not converted to passing evidence.

## Limitations and data handling

- One OTLP trace maps to at most one GraphABI run in profile 0.1.
- OTLP protobuf, Jaeger JSON, Zipkin JSON, collector configuration, and live receivers are not
  supported.
- A normal OTel parent can be a timing or containment relationship. GraphABI preserves it as a
  causal parent only when both spans are explicitly marked GraphABI nodes.
- OpenInference inputs, outputs, tool arguments, and retrieved documents can contain sensitive
  data. The importer retains local metadata as requested and performs no general DLP. Review and
  sanitize exports before storing or reporting them.
- A `RETRIEVER` span does not become `SourceAccess`. The conventions do not prove that a document
  was opened or supports a claim.
- GenAI or OpenInference classification is retained for audit. Current evaluators do not treat a
  role label as contract evidence.
- This profile has fixtures for an OpenInference export and an OpenTelemetry GenAI export. It is
  not universal vendor compatibility.
