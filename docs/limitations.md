# Limitations

GraphABI v0.1 is an alpha proving a narrow compatibility technique. A `PASS` means every enforced
contract evaluated successfully for the supplied observations. It does not mean two models,
prompts, tools, or nodes are universally semantically equivalent.

- Contracts cover only assumptions people made explicit.
- Trace-based inference finds correlations, not logical necessities; suggestions are never
  automatically enforced. Empirical support ratios exclude insufficient evidence and are not
  statistical confidence, semantic correctness, or safety probabilities.
- Observed traces do not cover unseen inputs or nondeterministic execution space.
- Contract coverage uses explicit 0.2 graph topology. Version 0.1 contracts and unexpected observed
  edges produce an incomplete inventory warning. Full observed coverage is not proof over unseen
  inputs and is not a semantic-correctness metric.
- A dishonest or faulty adapter can record incorrect metadata. Provenance is only as trustworthy as
  instrumentation and source-access events.
- Trace 0.2 pairs repeated observations by logical causal ancestry, branch, and retry attempt.
  Siblings that remain indistinguishable under those fields produce `INSUFFICIENT_EVIDENCE`;
  GraphABI does not guess from timestamps or payload similarity.
- Structural comparison supports fields, primitive/container types, optionality, enums, arrays,
  and compatible optional additions. It is not a complete JSON Schema subsumption solver.
- `compare` infers structure from stored payloads and cannot reconstruct every original Pydantic
  validator. Integrations should supply original schemas when available.
- Unit checking verifies explicit labels and representations. It does not silently convert values.
- Authority ordering is a fixed v0.1 vocabulary; domain-specific scales need a custom evaluator.
- Freshness uses recorded edge time as the comparison clock and trusts ISO-8601 metadata.
- Redaction recursively minimizes witnesses and masks common credential keys/token formats in
  reports, but it is not a general DLP or secrets scanner. Raw trace exports and SQLite data retain
  captured values.
- SQLite supports local workflows, not concurrent distributed ingestion.
- Maintained adapters cover LangGraph `>=1.0,<1.3` and optional OpenAI Agents SDK `>=0.20,<0.21`.
  The OpenAI Agents adapter covers ordinary non-streamed `Agent` runs, local tools, and sequential
  handoffs. Realtime, voice, sandbox, session-resume, and streamed-run surfaces are not yet mapped.
- OpenAI Agents handoffs become GraphABI edge observations only through an explicit
  `HandoffEdgeSpec` payload resolver. Undeclared handoffs retain causal ancestry but are not
  contract evidence.
- The telemetry importer supports local OTLP/JSON only through
  `graphabi.otel.openinference/0.1`. Generic OpenTelemetry and OpenInference spans do not provide
  graph or edge semantics, so explicit `graphabi.*` identity and edge attributes are required.
- Telemetry import retains all span and resource attributes for audit. Those attributes may
  contain sensitive data and require review before storage or reporting.
- The HTML report is designed for local inspection, not untrusted multi-user hosting.
- Benchmark graphs are synthetic linear chains and the single-iteration results are not capacity
  guarantees.
- The optional live model migration example supports only GPT-5.6 Terra and GPT-5.6 Luna through
  one OpenAI Responses API request shape. It is not a maintained model adapter. It sends the
  bundled synthetic source to OpenAI and can incur cost only after explicit acknowledgement. Its
  evidence check covers the structured capacity and cycle fields, not arbitrary free-form claims.

`UNKNOWN` and `INSUFFICIENT_EVIDENCE` are deliberate outcomes. Do not configure automation to treat
them as proof of compatibility.
