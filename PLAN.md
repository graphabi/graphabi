# GraphABI v0.1 Alpha Delivery Plan

This plan records the build stages, acceptance criteria, and decisions for the first public alpha. A checked item means the behavior has been implemented and verified, not merely scaffolded.

## Stage 1: Reproducible project foundation

- [x] Pin Python 3.12 and project dependencies with `uv.lock`.
- [x] Configure package metadata, Ruff, Pyright, Pytest, Hypothesis, and coverage.
- [x] Provide `make bootstrap`, `lint`, `typecheck`, `test`, `demo`, `benchmark`, and `serve`.
- [x] Keep generated databases, reports, caches, builds, and benchmark outputs ignored.

Acceptance: a clean checkout can bootstrap without global Python packages and import `graphabi`.

## Stage 2: Complete vertical slice

- [x] Implement the deterministic local research graph using the supported LangGraph API.
- [x] Instrument node executions without persistence calls inside graph nodes.
- [x] Run baseline and intentionally broken candidate implementations against local fixtures.
- [x] Prove both use the same Pydantic model and JSON schema.
- [x] Detect the first semantic break at `researcher -> verifier` from actual executions.

Acceptance: `graphabi demo` produces a real schema-pass/semantics-fail result with a candidate witness.

## Stage 3: Core public architecture

- [x] Add versioned contracts validated by Pydantic with actionable diagnostics.
- [x] Add versioned framework-independent trace models and JSON/JSONL export.
- [x] Persist graph runs and node executions in SQLite behind a storage interface.
- [x] Implement implication, provenance, preservation, unit, authority, and freshness evaluators through a registry.
- [x] Compare Pydantic/JSON structures and classify structural changes.
- [x] Generate deterministic semantic findings, stable IDs, minimal witnesses, and explicit uncertainty states.
- [x] Calculate downstream/terminal/side-effect impact using NetworkX.

Acceptance: unit and property tests cover each family and core invariants without demo coupling.

## Stage 4: Product interfaces

- [x] Ship `doctor`, `init`, `record`, `infer`, `check`, `compare`, `report`, and `demo` CLI commands.
- [x] Support plain output, JSON where useful, no-color, verbose diagnostics, and consistent exit codes.
- [x] Conservatively infer unenforced contract suggestions from successful baseline traces.
- [x] Generate versioned JSON and self-contained accessible HTML reports from report models.
- [x] Serve reports locally and open them with the macOS browser on request.
- [x] Benchmark trace loading, evaluation, impact, and report generation at about 10/100/1,000 nodes.

Acceptance: every required command runs locally without a key, cloud service, Docker, or hidden network call.

## Stage 5: Verification and public-project readiness

- [x] Meet at least 85% core-package coverage.
- [x] Add unit, property, integration, and end-to-end tests around observed behavior.
- [x] Write architecture, contract, trace, demo, design, limitations, landscape, roadmap, and extension docs.
- [x] Add Apache-2.0 licensing, governance/security/contribution files, issue templates, CI, and package dry-run workflow.
- [x] Create a deterministic local README visual with no broken external asset dependency.
- [x] Build wheel and sdist, run a critical review, resolve all high and reasonable medium findings.
- [x] Re-run all completion commands from clean generated state and create logical commits.

Acceptance: all commands in the user-facing completion matrix succeed, distributions build, docs match reality, and the Git worktree is clean except ignored runtime output.

## Initial decisions

- Python 3.12 is the compatibility floor and the locked development interpreter.
- SQLite is accessed through a small standard-library persistence adapter to reduce dependency surface.
- Pydantic models are the interchange boundary; core logic remains synchronous and deterministic.
- LangGraph is an optional-but-default demo dependency, isolated below `adapters/langgraph`.
- HTML uses Jinja2 with inline CSS/SVG and minimal inline JavaScript; it has no CDN or build step.
- Reports distinguish `PASS`, `WARNING`, `BREAKING`, `UNKNOWN`, and `INSUFFICIENT_EVIDENCE` without collapsing uncertainty.
- The intentionally bad candidate exists only in `examples/research_graph`.
