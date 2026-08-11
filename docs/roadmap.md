# Roadmap

The near-term and later sections are planned or exploratory. The implemented foundations section
names alpha behavior available in the current source tree.

## Near term

- Resolve original Pydantic and JSON schemas from recorded adapter metadata.
- Add contract authoring diagnostics for unreachable nodes and conflicting invariants.
- Add an approved conversion-policy interface that verifies unit and magnitude together.
- Import and export OpenTelemetry/OpenInference traces without changing core findings.
- Add one second framework adapter to validate the public adapter protocol.

## Later

- Baseline corpus selection and deterministic multi-run aggregation.
- Signed report manifests and reproducible build provenance.
- A formal compatibility policy for versioned contract, trace, and report schemas.
- Optional local/model-backed evaluator interfaces with mandatory uncertainty and evidence handling.

## Implemented foundations

- Pair loop, retry, repeated-edge, fan-out, fan-in, and nested-branch occurrences using a validated
  trace 0.2 causal DAG without timestamp or payload matching.
- Report an explicit graph-edge inventory, contracted and uncontracted edges, observed and
  unobserved edges, their intersections, insufficient-evidence branches, and a bounded percentage.
- Provide deterministic prompt and retriever migration examples.
- Provide an optional provider-interface model migration example whose default path is local and
  keyless.

These foundations remain alpha. Coverage describes selected observations and the live model path
does not establish universal behavior.

## Explicitly out of scope

GraphABI is not becoming a hosted observability platform, agent runtime, data warehouse, billing
system, universal semantic reasoner, or replacement for final-output evaluation.
