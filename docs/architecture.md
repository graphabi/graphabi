# Architecture

GraphABI v0.1 is a local, synchronous comparison pipeline. Its core boundary is the versioned,
framework-independent trace model, not LangGraph callbacks, database rows, or HTML.

```text
framework graph
  └─ adapter/instrumentation
       └─ TraceBundle 0.2
            ├─ JSON / JSONL export
            ├─ SQLiteTraceStore
            └─ edge observations
                 ├─ structural comparison
contract YAML ───┴─ evaluator registry
                       └─ semantic findings + witnesses
contract topology ─────┴─ impact analysis
                              └─ CompatibilityReport 0.3
                                   ├─ report.json
                                   └─ self-contained index.html
```

## Package boundaries

- `models/` owns immutable versioned interchange records.
- `adapters/` converts framework activity or supported external telemetry to those records.
  `adapters/langgraph/` instruments LangGraph, `adapters/openai_agents/` instruments OpenAI Agents
  SDK lifecycle hooks, and `adapters/otel/` imports the narrow local OTLP/JSON profile.
- `traces/` imports and exports portable JSON/JSONL.
- `storage/` exposes `TraceStore`; the first implementation stores lossless JSON in indexed SQLite
  rows.
- `contracts/` validates YAML and exposes an explicit per-engine evaluator registry.
- `comparison/` performs structural classification and deterministic semantic evaluation.
- semantic reports include graph-wide contract coverage for selected observations; coverage never
  changes a finding status or claims correctness.
- `impact/` uses NetworkX only after a finding is classified as breaking.
- `inference/` observes successful traces and returns evidence-counted suggestions; it has no
  write path to contract files and keeps insufficient evidence outside the empirical support ratio.
- `reporting/` separates `CompatibilityReport` from SVG/Jinja/FastAPI presentation.
- `ci/` renders a GitHub job summary from the recorded report model; it does not reclassify
  findings or read raw traces.
- `cli/` orchestrates public workflows and maps breaking changes to exit code `2`.
- `regression_corpus/` is repository test data outside the package core. Its runner loads recorded
  traces and contracts through public interfaces and compares actual findings with assertions.

## Data flow and trust

The adapter wraps a node callable and snapshots the state before invocation and the partial update
after invocation. It records every node occurrence, its causal parents, branch, retry attempt, and
topological sequence. Example nodes return trace activity through reserved demonstration-state
fields; the wrapper converts those to structured `ToolActivity` and `SourceAccess` records. The node
never writes SQLite directly. A completed run produces edge occurrences by joining concrete
producer and consumer executions.

Contracts are treated as consumer requirements. The evaluator receives the candidate observation
and, when available, its baseline counterpart. Built-ins are deterministic. A missing path produces
`INSUFFICIENT_EVIDENCE`; an unregistered evaluator or uninterpretable value produces `UNKNOWN`.

Findings carry both observations and a reduced witness. The witness recursively retains only paths
used by the evaluator and replaces other payload sections with `RedactedValue`. At the report-model
boundary, common credential keys, unmistakable token formats, and common local absolute paths are
masked before JSON, HTML, or CI summary serialization. Remaining observations stay locally
expandable. This best-effort masking reduces accidental exposure but is not a substitute for
sanitizing traces before capture.

## Stable identities

Finding IDs are a SHA-256 prefix of contract schema version, graph, edge, invariant, and, for trace
0.2, a logical causal pairing key. Run IDs, occurrence IDs, timestamps, sequence numbers, and payload
values are deliberately excluded. Re-evaluating the same causal contract location therefore yields
the same identity even when a scheduler changes execution order.

## Extension policy

An evaluator implements one method and registers in an `EvaluatorRegistry`. A framework adapter
must emit a `TraceBundle`. A storage backend implements `TraceStore`. These are ordinary Python
interfaces; v0.1 avoids entry-point discovery until more than one third-party plugin validates the
right packaging shape.

See [extensions](extensions.md), [contract format](contract-format.md), and
[trace format](trace-format.md). Repeated-edge behavior is documented in
[occurrence pairing](occurrence-pairing.md), and external span ingestion is defined in
[trace interoperability](trace-interoperability.md).
