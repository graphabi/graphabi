# Limitations

GraphABI v0.1 is an alpha proving a narrow compatibility technique. A `PASS` means every enforced
contract evaluated successfully for the supplied observations. It does not mean two models,
prompts, tools, or nodes are universally semantically equivalent.

- Contracts cover only assumptions people made explicit.
- Trace-based inference finds correlations, not logical necessities; suggestions are never
  automatically enforced.
- Observed traces do not cover unseen inputs or nondeterministic execution space.
- A dishonest or faulty adapter can record incorrect metadata. Provenance is only as trustworthy as
  instrumentation and source-access events.
- v0.1 pairs one observation per edge/run in the main comparison path. Fan-out, loops, and repeated
  edge crossings need explicit occurrence pairing in a later schema; ambiguous duplicates are
  rejected.
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
- Only LangGraph `>=1.0,<1.3` has a maintained adapter.
- The HTML report is designed for local inspection, not untrusted multi-user hosting.
- Benchmark graphs are synthetic linear chains and the single-iteration results are not capacity
  guarantees.

`UNKNOWN` and `INSUFFICIENT_EVIDENCE` are deliberate outcomes. Do not configure automation to treat
them as proof of compatibility.
