# Trace format 0.1

GraphABI's core consumes a framework-independent `TraceBundle`. All models reject unknown fields,
are immutable after validation, and serialize through Pydantic in JSON mode.

## TraceBundle

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `"0.1"` | Trace bundle schema version |
| `exported_at` | ISO-8601 timestamp | Export time preserved by SQLite |
| `runs` | `GraphRun[]` | Complete graph invocations |
| `edge_observations` | `EdgeObservation[]` | Values seen at producer/consumer boundaries |

## GraphRun

Records `run_id`, `graph_id`, `graph_version`, `variant`, start/end timestamps, status, graph input,
graph output, and ordered `NodeExecution` values. Every execution must carry the same `run_id`.

## NodeExecution

Records:

- trace schema version;
- run, graph, graph-version, and node identifiers;
- parent node and incoming edge;
- input, partial output, and metadata;
- structured tool calls and source-access events;
- start/end timestamps and measured duration;
- success/error status and error text;
- framework name and installed framework version.

## EdgeObservation

Records the exact producer payload, the consumer's observed input state, producer metadata and
activities, edge endpoints, graph/run identities, and observation timestamp. Contract evaluators
operate on this model; they do not inspect LangGraph state classes.

## ToolActivity

A tool activity contains `tool_name`, stable `call_id`, input/output, timestamps, success/error
status, and optional error. It is evidence that a call was attempted, not automatically evidence
that its result supports a claim.

## SourceAccess

A source-access event contains `source_id`, URI, attempt time, `opened`, optional
`supports_claim`, optional content SHA-256, and error. Provenance evaluators rely on this record.
A citation identifier in ordinary output never implies `opened=true`.

## RedactedValue

Human witnesses replace unrelated payload sections with:

```json
{"redacted": true, "reason": "unrelated to this finding"}
```

The original value is not retained in that marker. Reports additionally mask common credential
keys and unmistakable token formats, then HTML-escape all trace strings. Non-sensitive observation
details remain locally expandable. This is defense in depth, not a general DLP guarantee; sanitize
traces before capture when payloads may contain confidential data.

## Export and import

JSON stores one `TraceBundle`. JSONL stores tagged `graph_run` and `edge_observation` records, one
per line. Both round-trip through the same Pydantic models.

Trace schema 0.1 requires unique run IDs, unique node IDs within a run, and unique
`(run_id, edge_id)` observations. Observations must reference a run with the same graph identity.
Repeated/looped executions need a future occurrence identity and are rejected rather than silently
collapsed.

```bash
graphabi record .graphabi/demo/traces.jsonl --database .graphabi/traces.db
```

Schema evolution follows [versioning policy](versioning.md). Readers reject an unsupported schema
version rather than guessing.
