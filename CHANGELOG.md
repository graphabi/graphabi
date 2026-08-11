# Changelog

All notable changes are documented here. GraphABI follows [Semantic Versioning](docs/versioning.md).

## [Unreleased]

### Added

- First-class contract coverage for total graph nodes and edges, contracted and uncontracted edges,
  candidate-observed and unobserved edges, their intersections, insufficient-evidence branches,
  and a clearly bounded percentage in JSON, CLI, and offline HTML reports.
- Contract format 0.2 `graph_edges` topology declarations, with version 0.1 loading and report
  migration retained for backward compatibility.
- Trace schema 0.2 causal occurrence identities and deterministic pairing for repeated nodes,
  repeated edges, loops, retries, fan-out, fan-in, and nested branches.
- A local OTLP/JSON importer with a narrow OpenInference and OpenTelemetry GenAI mapping profile,
  retained unknown metadata, exact parent identities, and explicit `UNKNOWN` diagnostics for
  unsupported or ambiguous spans.
- An optional OpenAI Agents SDK `>=0.20,<0.21` adapter for agent activations, tool calls, handoff
  causality, and explicitly resolved handoff edge payloads, with a keyless local example.

### Changed

- Raised the enforced test-coverage floor from 85% to 90% after the alpha.1 baseline measured
  93.08%.
- Updated Typer to 0.27.1 and Hypothesis to 6.165.2 through the reviewed dependency group.
- Compatibility reports now default to schema 0.3, retain schema 0.1 and 0.2 as accepted input
  versions, use complete declared topology, and include causal pairing plus observed occurrence
  impact in findings and witnesses.
- SQLite trace storage now keys edge observations by occurrence and migrates trace 0.1 databases;
  JSONL exports preserve bundle version metadata in a header record.

## [0.1.0-alpha.1] - 2026-08-11

### Added

- Versioned consumer-driven YAML contracts and seven deterministic evaluator families.
- Versioned framework-independent trace, source-access, tool-activity, witness, and report models.
- LangGraph `StateGraph` instrumentation with deterministic baseline/candidate research demo.
- SQLite persistence plus JSON and JSONL trace export/import.
- Pydantic/JSON structural comparison and explicit semantic uncertainty states.
- Stable findings, minimal redacted witnesses, and NetworkX downstream impact analysis.
- Conservative unenforced inference suggestions.
- `graphabi` CLI with all v0.1 commands and self-contained JSON/HTML reporting.
- Local 10/100/1,000-node benchmark and 85% coverage gate.
- Initial public repository policy, CI, and packaging dry run.
- Independent adversarial tests for repaired candidates, units, authority, topology, malformed
  inputs, redaction, persistence, and clean wheel installation.
- Semantic Pulse visual identity with a broken-edge logo, deterministic README animation,
  architecture/report illustrations, and repository social assets.
- Contract coverage for contracted edges, uncontracted observed edges, observed and unobserved
  branches, and insufficient evidence.
- Deterministic prompt and retriever migration examples plus an opt-in provider-interface model
  migration example.
- A real model migration path comparing GPT-5.6 Terra and GPT-5.6 Luna through the Responses API,
  with strict shared output schema, recorded local source access, explicit cost acknowledgement,
  usage-based cost reporting, and an unchanged keyless fixture path.

### Changed

- Reports now evaluate traces reloaded from SQLite, mask common secret shapes, and force HTML
  escaping.
- Trace schema 0.1 rejects ambiguous identities; contract paths and scalar types validate more
  strictly.
- CLI comparison covers every contract edge and uses explicit exit codes for structural breaks and
  unregistered evaluators.
- The offline HTML report now replays semantic flow, freezes at the first recorded break, reveals
  its witness, supports reduced motion, and shares one accessible visual system with the project.
- Project positioning now leads with Semantic Compatibility Infrastructure and a shorter,
  proof-first README.
- The public design doctrine now separates the neutral ambient website field from deterministic
  product instruments.

### Fixed

- Prevented wrong-graph observations, non-numeric unit values, and contradictory report summaries
  from establishing compatibility.
- Corrected disconnected-branch impact analysis and contextualized corrupt SQLite records.
- Reject malformed contract-coverage partitions and run the required wheel smoke test on every
  pull request, including documentation-only changes.
- Add grouped weekly dependency updates for the `uv` lock and pinned GitHub Actions.

[Unreleased]: https://github.com/graphabi/graphabi/compare/v0.1.0-alpha.1...HEAD
[0.1.0-alpha.1]: https://github.com/graphabi/graphabi/releases/tag/v0.1.0-alpha.1
