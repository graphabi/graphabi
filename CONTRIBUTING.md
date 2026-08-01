# Contributing to GraphABI

Thank you for improving semantic compatibility testing for agent graphs. GraphABI is early: small,
well-tested changes with explicit behavior are more valuable than broad abstraction.

## Set up

```bash
git clone https://github.com/graphabi/graphabi.git
cd graphabi
make bootstrap
make lint typecheck test
```

Python 3.12 and `uv` are the supported contributor path. No API key, Docker daemon, hosted model, or
customer data is needed.

## Choose work

Issues labeled `good first issue` should be independently actionable and name the relevant tests.
Good starting areas are actionable validation messages, trace-format examples, evaluator edge-case
tests, accessible report markup, and adapter documentation. Use the dedicated proposal template for
a new evaluator or framework adapter.

## Change workflow

1. Read `AGENTS.md`, the architecture guide, and the relevant format document.
2. Add or update a failing behavior test.
3. Make the smallest implementation change.
4. Run affected tests after every meaningful change.
5. Run `make lint typecheck test demo benchmark` and `uv build` before opening a pull request.
6. Update docs and `CHANGELOG.md` for public behavior.

Never weaken a contract to make a test pass, infer semantic equivalence from schemas, convert
uncertainty to success, or hardcode a demo report. Fixtures must be synthetic and public.

## Tests

- Unit tests cover contract/evaluator/model behavior.
- Property tests protect non-mutation, determinism, escalation, units, and redaction.
- Integration tests exercise real LangGraph execution, SQLite, inference, and reporting.
- End-to-end tests exercise public CLI exit codes and generated artifacts.

The coverage floor is 85% for the package. New code should normally exceed it.

## Commits and pull requests

Use focused imperative commit subjects, for example `Add evidence freshness evaluator`. Explain the
consumer assumption and uncertainty behavior in the PR. Maintainers may ask to split unrelated
changes.

By contributing, you agree that your contribution is licensed under Apache-2.0 and to follow the
[Code of Conduct](CODE_OF_CONDUCT.md).
