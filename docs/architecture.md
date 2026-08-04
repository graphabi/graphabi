# Architecture

GraphABI v0.1 is a local, synchronous comparison pipeline. Its core boundary is the versioned,
framework-independent trace model, not LangGraph callbacks, database rows, or HTML.

```text
framework graph
  └─ adapter/instrumentation
       └─ TraceBundle 0.1
            ├─ JSON / JSONL export
            ├─ SQLiteTraceStore
            └─ edge observations
                 ├─ structural comparison
contract YAML ───┴─ evaluator registry
                       └─ semantic findings + witnesses
contract topology ─────┴─ impact analysis
                              └─ CompatibilityReport 0.1
                                   ├─ report.json
                                   └─ self-contained index.html
```

## Package boundaries

- `models/` owns immutable versioned interchange records.
- `adapters/` converts framework activity to those records. Only
  `adapters/langgraph/` imports LangGraph.
- `traces/` imports and exports portable JSON/JSONL.
- `storage/` exposes `TraceStore`; the first implementation stores lossless JSON in indexed SQLite
  rows.
- `contracts/` validates YAML and exposes an explicit per-engine evaluator registry.
- `comparison/` performs structural classification and deterministic semantic evaluation.
- semantic reports include descriptive contract coverage for selected observations; coverage never
  changes a finding status.
- `impact/` uses NetworkX only after a finding is classified as breaking.
- `inference/` observes successful traces and returns suggestions; it has no write path to contract
  files.
- `reporting/` separates `CompatibilityReport` from SVG/Jinja/FastAPI presentation.
- `cli/` orchestrates public workflows and maps breaking changes to exit code `2`.

## Data flow and trust

The adapter wraps a node callable and snapshots the state before invocation and the partial update
after invocation. Example nodes return trace activity through reserved demonstration-state fields;
the wrapper converts those to structured `ToolActivity` and `SourceAccess` records. The node never
writes SQLite directly. A completed run produces edge observations by joining a producer execution
to the actual consumer input.

Contracts are treated as consumer requirements. The evaluator receives the candidate observation
and, when available, its baseline counterpart. Built-ins are deterministic. A missing path produces
`INSUFFICIENT_EVIDENCE`; an unregistered evaluator or uninterpretable value produces `UNKNOWN`.

Findings carry both observations and a reduced witness. The witness recursively retains only paths
used by the evaluator and replaces other payload sections with `RedactedValue`. At the report-model
boundary, common credential keys and unmistakable token formats are also masked before JSON or HTML
serialization. Remaining observations stay locally expandable. This best-effort masking reduces
accidental exposure but is not a substitute for sanitizing traces before capture.

## Stable identities

Finding IDs are a SHA-256 prefix of contract schema version, graph, edge, and invariant. Run IDs and
timestamps are deliberately excluded, so re-evaluating the same contract location yields the same
identity. Status and reason remain report fields and can change across versions.

## Extension policy

An evaluator implements one method and registers in an `EvaluatorRegistry`. A framework adapter
must emit a `TraceBundle`. A storage backend implements `TraceStore`. These are ordinary Python
interfaces; v0.1 avoids entry-point discovery until more than one third-party plugin validates the
right packaging shape.

See [extensions](extensions.md), [contract format](contract-format.md), and
[trace format](trace-format.md). Repeated-edge support is specified in the
[occurrence-pairing design](occurrence-pairing.md), and external span ingestion is assessed in
[trace interoperability](trace-interoperability.md).
