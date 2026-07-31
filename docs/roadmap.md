# Roadmap

Everything below is planned or exploratory; none is part of the implemented v0.1 guarantee.

## Near term

- Pair repeated and looped edge observations by occurrence and causal parent.
- Resolve original Pydantic and JSON schemas from recorded adapter metadata.
- Add contract authoring diagnostics for unreachable nodes and conflicting invariants.
- Add an approved conversion-policy interface that verifies unit and magnitude together.
- Import and export OpenTelemetry/OpenInference traces without changing core findings.
- Add one second framework adapter to validate the public adapter protocol.

## Later

- Contract coverage reports showing uncontracted edges and unobserved branches.
- Baseline corpus selection and deterministic multi-run aggregation.
- Signed report manifests and reproducible build provenance.
- A formal compatibility policy for versioned contract, trace, and report schemas.
- Optional local/model-backed evaluator interfaces with mandatory uncertainty and evidence handling.

## Explicitly out of scope

GraphABI is not becoming a hosted observability platform, agent runtime, data warehouse, billing
system, universal semantic reasoner, or replacement for final-output evaluation.
