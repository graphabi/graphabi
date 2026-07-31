# GraphABI Repository Instructions

These instructions apply to every contributor and automated coding agent in this repository.

## Non-negotiable engineering rules

- Run affected tests after every meaningful change and the full quality suite before completion.
- Never weaken a semantic contract merely to make a test pass.
- Never claim semantic equivalence from schema compatibility alone.
- Never convert `UNKNOWN` or `INSUFFICIENT_EVIDENCE` into `PASS`.
- Keep framework-specific code behind `src/graphabi/adapters/`.
- Require no API keys for installation, tests, benchmarks, or the default demo.
- Put no customer data or personal data in fixtures, traces, examples, or reports.
- Document public behavior changes in the README, relevant docs, and changelog.
- Make CLI errors actionable: identify the failing file/object/field and suggest a correction when possible.
- Generate reports from recorded traces. Never hardcode demo findings or outcomes.
- Keep the demo deterministic and make no hidden network calls.
- Avoid unnecessary dependencies and Apple Silicon-incompatible tooling.
- Preserve backward compatibility of versioned contract, trace, and report schemas where reasonable.

## Development workflow

1. Use Python 3.12 through `uv` and keep `uv.lock` current.
2. Keep production behavior under `src/graphabi/`; examples may contain deliberately broken fixtures.
3. Add or update tests with behavior changes.
4. Run focused tests while iterating.
5. Before committing, run `make lint typecheck test demo benchmark` and `uv build`.
6. Do not commit `.graphabi/` runtime databases or reports except explicitly curated documentation assets.

## Architecture boundaries

- Core comparison and contract engines consume only framework-independent trace models.
- Evaluators register through the evaluator registry and must not depend on the research demo.
- Storage implements an interface; callers do not embed SQLite queries.
- Report data models are separate from renderers.
- I/O is explicit at orchestration boundaries. Evaluators and comparison logic remain deterministic.
- Version public interchange models and serialize them predictably.

