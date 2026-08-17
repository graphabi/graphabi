## What changed

<!-- Describe the consumer assumption or public behavior affected. -->

## Evidence

- [ ] Added or updated behavior tests
- [ ] Ran affected tests during development
- [ ] `make lint`
- [ ] `make typecheck`
- [ ] `make test`
- [ ] `make proof`
- [ ] `make demo`
- [ ] `make benchmark`
- [ ] `make corpus`
- [ ] `uv build`

## Semantic safety

- [ ] No contract was weakened merely to pass a test
- [ ] `UNKNOWN` / `INSUFFICIENT_EVIDENCE` remain distinct from `PASS`
- [ ] Reports derive from recorded traces
- [ ] Public behavior and changelog are documented
- [ ] No secrets, customer data, hidden network calls, or required API keys were added
