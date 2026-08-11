# Trace format 0.2

GraphABI's core consumes a framework-independent `TraceBundle`. All models reject unknown fields,
are immutable after validation, and serialize through Pydantic in JSON mode.

Trace 0.2 represents a logical graph that may contain cycles as an acyclic graph of concrete
execution occurrences. It does not pair repeated work by timestamps or payload values.

## TraceBundle

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `"0.1"` or `"0.2"` | One version shared by every nested trace record |
| `exported_at` | ISO-8601 timestamp | Export time preserved by JSONL and SQLite |
| `runs` | `GraphRun[]` | Complete graph invocations |
| `edge_observations` | `EdgeObservation[]` | Values seen at concrete producer/consumer boundaries |

## GraphRun

Records `run_id`, `graph_id`, `graph_version`, `variant`, start/end timestamps, status, graph input,
graph output, and ordered `NodeExecution` values. Every nested execution has the same run, graph,
and trace-schema identity.

## NodeExecution 0.2

Each execution records:

- `node_id`: the logical node, which may repeat;
- `occurrence_id`: an adapter-observed identity unique within the run;
- `parent_occurrence_id`: the primary causal parent, or null for a root;
- `causal_parent_occurrence_ids`: every causal parent, including all fan-in inputs;
- `incoming_edge_id`: the primary logical incoming edge when known;
- `causal_sequence`: a unique non-negative topological sequence within the run;
- `branch_id`: a stable branch or map key when the framework exposes one;
- `attempt`: a positive retry attempt number;
- input, partial output, metadata, tool calls, source access, timing, status, error, and framework
  identity.

Every parent must exist and have a lower causal sequence. An occurrence cannot parent itself. These
rules make the occurrence graph acyclic even when the logical graph loops.

## EdgeObservation 0.2

Each crossing keeps the logical `edge_id`, producer, and consumer, plus:

- its own run-unique `occurrence_id`;
- `producer_occurrence_id` and `consumer_occurrence_id`;
- a deterministic edge `causal_sequence`;
- the producer branch and consumer retry attempt;
- the exact producer payload, consumer input, producer metadata and activities, and observation
  time.

The referenced executions must exist and match the logical endpoints. The producer occurrence must
be a declared causal parent of the consumer occurrence.

## ToolActivity and SourceAccess

A tool activity contains `tool_name`, stable `call_id`, input/output, timestamps, success/error
status, and optional error. It is evidence that a call was attempted, not automatically evidence
that its result supports a claim.

A source-access event contains `source_id`, URI, attempt time, `opened`, optional `supports_claim`,
optional content SHA-256, and error. A citation identifier in ordinary output never implies
`opened=true`.

## Export, import, and storage

JSON stores one `TraceBundle`. JSONL begins with a tagged `trace_bundle` header that preserves the
schema version and export timestamp, followed by `graph_run` and `edge_observation` records. The
loader still accepts headerless trace 0.1 JSONL.

SQLite keys edge rows by `(run_id, occurrence_id)`. Opening a trace 0.1 database migrates its old
`(run_id, edge_id)` rows to `legacy:<edge_id>` occurrence keys without changing the stored payload.
Both schema versions remain readable.

```bash
graphabi record .graphabi/demo/traces.jsonl --database .graphabi/traces.db
```

## Trace 0.1 compatibility

Trace 0.1 remains strict: node IDs and `(run_id, edge_id)` observations must be unique, and new
occurrence fields are rejected. Existing JSON, JSONL, and SQLite data remains loadable.

`upgrade_trace_bundle_v1` is an explicit conservative converter. It assigns occurrence IDs only
when the trace 0.1 singleton executions contain an earlier recorded parent for every observed
edge. Missing executions or unverifiable parent links raise an actionable error. The converter
never reconstructs loops or branches that trace 0.1 did not record.

## Redaction boundary

Human witnesses replace unrelated payload sections with a `RedactedValue`. Reports additionally
mask common credential keys and unmistakable token formats, then HTML-escape trace strings. This is
defense in depth, not general data-loss prevention; sanitize traces before capture when payloads
may contain confidential data.

Schema evolution follows the [versioning policy](versioning.md). Readers reject unsupported schema
versions rather than guessing.
