# OpenTelemetry and OpenInference interoperability assessment

Status: evaluated, not implemented.

GraphABI's core can ingest any source that produces an honest `TraceBundle`. Generic span ingestion
is not yet honest enough to ship as a maintained adapter because neither OpenTelemetry spans nor
OpenInference attributes universally encode a graph edge crossing and the consumer assumption
attached to it.

| GraphABI record | Possible source | Missing guarantee |
|---|---|---|
| `GraphRun` | root span or trace | one trace can contain unrelated work or multiple graph runs |
| `NodeExecution` | framework or agent span | node identity and graph version are not universal |
| `EdgeObservation` | producer and consumer span relationship | explicit edge ID and exact crossing payload are not universal |
| `ToolActivity` | tool span | call identity and sanitized input/output conventions vary |
| `SourceAccess` | retrieval span or event | opened and supports-claim evidence is not standardized |
| occurrence identity | span and parent IDs | trace 0.2 also needs explicit join parents, branch, and retry attempt |

OpenInference provides useful agent, model, tool, retrieval, input, and output conventions on top of
OpenTelemetry. Those conventions reduce custom mapping but do not prove that a retrieved document
was opened by this execution or supports the produced claim. Payload capture is also optional and
can expose sensitive data.

## Minimum honest ingestion profile

A future adapter should require explicitly configured attributes for graph ID, graph version, node
ID, edge ID, producer, consumer, run variant, and sanitized crossing payload. Missing identity must
produce an import diagnostic or `INSUFFICIENT_EVIDENCE`, never a guessed edge. Source support should
require a dedicated event or attribute supplied by instrumentation that actually observed it.

The adapter should also:

- accept an allowlist of attributes rather than storing every span field;
- preserve original trace and span IDs for audit without using them as semantic IDs;
- map explicit causal parents, branch IDs, and retry attempts into trace 0.2, while retaining
  ambiguity when the source cannot supply them;
- record the semantic-convention version and mapping profile;
- test against exported fixtures from more than one instrumentation source;
- make no network requests when importing a local OTLP JSON or protobuf export.

## Decision

Do not advertise OpenTelemetry or OpenInference support yet. Trace 0.2 now provides the occurrence
target, but a narrow mapping profile still needs validation against real exported traces. A small
adapter is justified only when it can fail closed on missing graph semantics and remain independent
of vendor-specific span names.
