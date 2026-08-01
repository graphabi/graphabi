# Changelog

All notable changes are documented here. GraphABI follows [Semantic Versioning](docs/versioning.md).

## [Unreleased]

### Added

- Initial public repository policy, CI, and packaging dry run.
- Independent adversarial tests for repaired candidates, units, authority, topology, malformed
  inputs, redaction, persistence, and clean wheel installation.

### Changed

- Reports now evaluate traces reloaded from SQLite, mask common secret shapes, and force HTML
  escaping.
- Trace schema 0.1 rejects ambiguous identities; contract paths and scalar types validate more
  strictly.
- CLI comparison covers every contract edge and uses explicit exit codes for structural breaks and
  unregistered evaluators.

### Fixed

- Prevented wrong-graph observations, non-numeric unit values, and contradictory report summaries
  from establishing compatibility.
- Corrected disconnected-branch impact analysis and contextualized corrupt SQLite records.

## [0.1.0-alpha.1] — 2026-07-31

### Added

- Versioned consumer-driven YAML contracts and six deterministic evaluator families.
- Versioned framework-independent trace, source-access, tool-activity, witness, and report models.
- LangGraph `StateGraph` instrumentation with deterministic baseline/candidate research demo.
- SQLite persistence plus JSON and JSONL trace export/import.
- Pydantic/JSON structural comparison and explicit semantic uncertainty states.
- Stable findings, minimal redacted witnesses, and NetworkX downstream impact analysis.
- Conservative unenforced inference suggestions.
- `graphabi` CLI with all v0.1 commands and self-contained JSON/HTML reporting.
- Local 10/100/1,000-node benchmark and 85% coverage gate.

[Unreleased]: https://github.com/parvbansal11/graphabi/compare/v0.1.0-alpha.1...HEAD
[0.1.0-alpha.1]: https://github.com/parvbansal11/graphabi/releases/tag/v0.1.0-alpha.1
