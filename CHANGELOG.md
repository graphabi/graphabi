# Changelog

All notable changes are documented here. GraphABI follows [Semantic Versioning](docs/versioning.md).

## [Unreleased]

### Added

- First-user readiness documentation for the PyPI alpha: 5-minute quick start, LangGraph quick
  start, OpenAI Agents SDK quick start, UNKNOWN explanation, human-test protocol, launch drafts,
  and a local human-only adoption ledger.

### Changed

- `graphabi doctor` now categorizes required runtime checks, adapter availability, local project
  state, trace-store state, contracts, and report artifacts while preserving stable plain output
  prefixes.
- `graphabi init` starter guidance now points new users to `doctor` first and links the maintained
  onboarding documents.

## [0.1.0-alpha.3] - 2026-08-19

### Added

- A committed local Ollama provider quick start example
  (`examples/local_provider_quickstart`) reproducing the production reality sprint's SAFE/BREAKING
  verifier contrast against real local inference, with a deterministic fixture default and an
  explicit `--live` opt-in. No API key, cloud account, or paid model is required.
- `set_preservation` invariants may now declare an optional `set_relation` of
  `contains_all_required` (default, matches prior behavior exactly) or `equal`. Existing contracts
  that do not set `set_relation` are unaffected.

### Changed

- **Compatibility note:** the `authority` evaluator now requires an explicit contract-declared
  `authority_order`. GraphABI no longer compares an observed authority label against an implicit
  fixed six-level vocabulary. An existing contract that omits `authority_order` still loads, but
  every `authority` invariant on it now evaluates to `UNKNOWN` instead of `PASS`/`BREAKING`. Add
  `authority_order: [level, level, ...]` (contract-local, any labels) to any existing `authority`
  invariant to restore confident comparison. See [contract format](docs/contract-format.md#authority).

### Fixed

- `SQLiteTraceStore` and the `graphabi doctor` SQLite check now close every connection they open.
  `with connection:` only commits or rolls back a transaction; it does not close the connection, so
  every `save_bundle`, `load_run`, `list_runs`, and `initialize` call previously leaked one. This is
  most visible under Python 3.13's stricter `ResourceWarning` reporting, but the leak affected every
  Python version and every long-running process (`graphabi compare`, `graphabi report --serve`, the
  GitHub Action).
- The PyPI long description now renders correctly: `README.md`'s repository-relative links and
  images, which resolve on GitHub but would break on the PyPI project page, are rewritten to
  absolute GitHub URLs at build time. `README.md` itself is unchanged and still renders correctly
  on GitHub.

### Documentation

- Clarified LangGraph list-parent fan-in construction and added framework-native regression
  coverage showing that separate incoming edges are independent triggers and that GraphABI fails
  closed rather than fabricating a parent for a premature uneven-branch join.
- Stated explicitly that the OpenAI Agents SDK `>=0.20,<0.21` bound is the tested and enforced
  compatibility boundary, not an advisory minimum: a version outside it is unsupported even if it
  happens to run, because it has no adapter integration coverage.

## [0.1.0-alpha.2] - 2026-08-17

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
- A real model migration path comparing GPT-5.6 Terra and GPT-5.6 Luna through the Responses API,
  with strict shared output schema, recorded local source access, explicit cost acknowledgement,
  usage-based cost reporting, and an unchanged keyless fixture path.
- A same-model prompt-version replay with concrete prompts and trace-backed authority, provenance,
  and evidence-completeness regressions.
- A concrete retriever replacement example with trace-backed freshness, unit, completeness, and
  provenance regressions over one shared output schema.
- Conservative `graphabi init` onboarding with manifest-only adapter hints, starter config,
  trace-recording guidance, runtime ignore rules, and a clearly unenforced sample contract.
- A reusable GitHub Action that compares pre-recorded runs, preserves stable CLI exit semantics,
  writes an uncertainty-aware job summary, and uploads the offline report without posting comments.
- A checked-in, reproducible semantic regression corpus covering provenance, preservation, units,
  authority, freshness, loops, fan-out, and model, prompt, and tool migrations.

### Changed

- Updated contribution, review ownership, pull-request, and private vulnerability reporting paths
  to match the current test floor, CI surface, adapters, corpus, and enabled GitHub controls.
- Raised the enforced test-coverage floor from 85% to 90% after the alpha.1 baseline measured
  93.08%.
- Updated Typer to 0.27.1 and Hypothesis to 6.165.2 through the reviewed dependency group.
- Compatibility reports now default to schema 0.3, retain schema 0.1 and 0.2 as accepted input
  versions, use complete declared topology, and include causal pairing plus observed occurrence
  impact in findings and witnesses.
- SQLite trace storage now keys edge observations by occurrence and migrates trace 0.1 databases;
  JSONL exports preserve bundle version metadata in a header record.
- Contract inference now aggregates compatible successful baselines, partitions support,
  counterexamples, and insufficient evidence, emits bounded trace references and valid YAML, and
  labels its empirical ratio as distinct from correctness or statistical confidence.
- Alpha.1 release documentation now distinguishes the fixed tag commit from the older reviewed
  source snapshot used to build the checksum-pinned GitHub release assets.
- Report serialization now masks common local absolute paths before JSON, HTML, and CI artifact
  output while leaving locally stored raw traces lossless.

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

[Unreleased]: https://github.com/graphabi/graphabi/compare/v0.1.0-alpha.3...HEAD
[0.1.0-alpha.3]: https://github.com/graphabi/graphabi/compare/v0.1.0-alpha.2...v0.1.0-alpha.3
[0.1.0-alpha.2]: https://github.com/graphabi/graphabi/compare/v0.1.0-alpha.1...v0.1.0-alpha.2
[0.1.0-alpha.1]: https://github.com/graphabi/graphabi/releases/tag/v0.1.0-alpha.1
