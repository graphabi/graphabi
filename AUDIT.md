# Hostile Independent Audit

Audit started: 2026-08-01  
Auditor stance: unfamiliar external maintainer; repository claims are untrusted until reproduced.

## Scope and method

This audit evaluates GraphABI as an installable public alpha, not merely as its bundled research
demo. The committed repository was first cloned with `git clone --no-local` into a new temporary
directory. The documented bootstrap, doctor, demo, lint, typecheck, test, benchmark, build, and
wheel-install paths were executed before production code was changed. Independent adversarial
probes are added under `tests/adversarial/`; a passing bundled test is not accepted as proof of a
claim by itself.

Severity meanings:

- **Critical:** corrupts data, fabricates compatibility, leaks sensitive values, or makes the core
  claim false in normal use.
- **High:** defeats a required compatibility/safety guarantee or breaks the public workflow.
- **Medium:** materially misleading, fragile, unsafe at an edge case, or unsuitable for dependable
  alpha use.
- **Low:** polish, clarity, or maintainability issue with limited behavioral impact.

## Initial external-developer verification

- Fresh local clone and `make bootstrap`: **PASS**.
- `make lint typecheck test benchmark`: **PASS** before audit changes (59 tests, 93.75% coverage).
- `make demo`: **PASS** and generated SQLite, JSON, and HTML output.
- `uv build`: **PASS** for sdist and wheel.
- Isolated `uv tool install` of the wheel: **PASS**.
- Installed-wheel demo from a directory outside the checkout on Python 3.13: **PASS**.

## Findings

### AUD-001 — `doctor` reports failure but exits successfully

- **Severity:** Medium
- **Status:** Fixed; missing report is now `INFO`, while required failures control exit status.
- **Reproduction:** In a clean checkout after `make bootstrap`, run `uv run graphabi doctor`; or
  install the wheel into an isolated tool environment and run `graphabi --plain doctor` from an
  empty directory.
- **Expected behavior:** A diagnostic labeled `FAIL` should make a CI-oriented doctor command exit
  non-zero, or an optional missing report should be labeled `INFO`/`SKIP` rather than `FAIL`.
- **Actual behavior:** `Latest report` is printed as `FAIL` while the process exits `0`.
- **Root cause:** Doctor output and process status are calculated independently; report absence is
  treated visually as failure without a corresponding exit policy.
- **Recommended correction:** Distinguish required checks from optional report state and make the
  exit code reflect failures of required checks. Test both fresh-install and post-demo behavior.

### AUD-002 — Trace identity is not bound to the contract and can fabricate `PASS`

- **Severity:** Critical
- **Status:** Fixed and covered by a wrong-identity adversarial regression.
- **Reproduction:** Run
  `uv run pytest tests/adversarial/test_semantic_independence.py::test_mismatched_edge_identity_cannot_pass`.
  Supply a candidate observation whose `edge_id` matches the contract but whose `graph_id`,
  producer, and consumer are unrelated.
- **Expected behavior:** The observation is rejected or produces `INSUFFICIENT_EVIDENCE`; it must
  not establish compatibility for a different edge.
- **Actual behavior:** `compare_semantics` indexes only by `edge_id`, evaluates the impostor payload,
  and returns overall `PASS`.
- **Root cause:** Candidate/baseline observations are never checked against contract graph and edge
  endpoint identity.
- **Recommended correction:** Validate graph, edge, producer, consumer, and selected run identity
  before evaluator dispatch. Identity mismatch must remain non-passing with an actionable reason.

### AUD-003 — Duplicate trace identities are accepted and may be silently overwritten

- **Severity:** High
- **Status:** Fixed; trace schema 0.1 rejects ambiguous identities before I/O.
- **Reproduction:** Run the three duplicate-identity tests in
  `tests/adversarial/test_inputs_storage_reporting.py`. Construct duplicate run IDs, duplicate node
  executions, or duplicate `(run_id, edge_id)` observations.
- **Expected behavior:** Trace schema 0.1 rejects ambiguous identities before comparison/storage.
- **Actual behavior:** All validate. Duplicate run rows use `INSERT OR REPLACE`; semantic comparison
  dictionary construction silently keeps one observation.
- **Root cause:** `GraphRun` and `TraceBundle` have only partial cross-record validation.
- **Recommended correction:** Add schema validators for unique runs, v0.1 node identities, edge
  observations, run references, and graph/version consistency. Retain SQLite rollback tests.

### AUD-004 — Unit evaluator passes a matching label with a non-numeric magnitude

- **Severity:** High
- **Status:** Fixed; non-finite/non-numeric values are `UNKNOWN` and ranges are checked.
- **Reproduction:** Run
  `uv run pytest tests/adversarial/test_semantic_independence.py::test_matching_unit_label_with_non_numeric_magnitude_is_not_pass`.
- **Expected behavior:** Unit consistency is not proven when the magnitude is a string; return
  `UNKNOWN` rather than `PASS`.
- **Actual behavior:** `{amount: "one hundred"}` with unit `USD` passes.
- **Root cause:** `UnitConsistencyEvaluator` checks only unit/representation labels and never checks
  that `value_path` resolves to a numeric magnitude.
- **Recommended correction:** Require finite numeric magnitudes, reject booleans, and validate
  explicit fraction/percent ranges conservatively.

### AUD-005 — Witness/report redaction leaks secrets and report HTML permits script injection

- **Severity:** High
- **Status:** Fixed; recursive minimization, report masking, and forced autoescaping are tested.
- **Reproduction:** Run the nested witness and report masking tests in
  `tests/adversarial/test_inputs_storage_reporting.py` with a nested sibling value named `api_key`
  containing a synthetic `sk-…` token.
- **Expected behavior:** An unrelated nested sibling is replaced with `RedactedValue`; obvious
  secret fields/tokens do not appear in witness repr/JSON or rendered JSON/HTML. Markup is escaped.
- **Actual behavior:** `_select` copies an entire top-level mapping for a deeper selected path,
  report rendering serializes complete raw observations, and the literal `<script>` payload is
  emitted unescaped. The exact token appears in JSON and HTML.
- **Root cause:** Selection is one level deep, there is no report-boundary sensitive-value
  sanitizer, and `select_autoescape(("html", "xml"))` does not enable escaping for the `.j2`
  template suffix.
- **Recommended correction:** Implement recursive path selection and recursive best-effort secret
  masking at the report boundary, force Jinja autoescaping for the report template, and document
  that masking is not general DLP.

### AUD-006 — Contract validation accepts malformed paths and CLI reports unknown evaluators as PASS

- **Severity:** Medium
- **Status:** Fixed; path grammar is strict and unregistered CLI evaluators exit 3.
- **Reproduction:** Run the malformed path and unknown evaluator CLI tests under
  `tests/adversarial/test_inputs_storage_reporting.py`.
- **Expected behavior:** `output..value` fails with contextual correction. A schema-valid external
  evaluator that is not registered locally is reported as `UNKNOWN` with exit code 3, not `PASS`.
- **Actual behavior:** Both `load_contract` and `graphabi check` report success.
- **Root cause:** Paths have only a minimum length constraint, and `check` does not consult the
  active built-in registry.
- **Recommended correction:** Validate path grammar/root without preventing external evaluator
  names; make CLI check distinguish schema validity from executable evaluator availability.

### AUD-007 — Corrupt SQLite payloads lose storage context

- **Severity:** Medium
- **Status:** Fixed with contextual `TraceStoreError` handling.
- **Reproduction:** Store a valid run, replace its `payload_json` with `not-json`, then call
  `load_run` (covered by the corrupt-row adversarial test).
- **Expected behavior:** A controlled storage exception names the database and run and identifies
  corruption. CLI consumers convert it to an actionable error.
- **Actual behavior:** Raw Pydantic validation text escapes with no database/run context.
- **Root cause:** Deserialization exceptions are not wrapped at the storage boundary.
- **Recommended correction:** Add a public storage error type, exception chaining, and CLI handling.

### AUD-008 — Report model permits internally contradictory status

- **Severity:** Medium
- **Status:** Fixed; summary status and breaking-edge consistency are model invariants.
- **Reproduction:** Construct `SemanticReport(status="PASS", findings=(breaking_finding,))`.
- **Expected behavior:** Versioned machine-report models reject contradictory summaries.
- **Actual behavior:** The model validates and can be serialized as an apparently passing report.
- **Root cause:** `SemanticReport` has no cross-field status validator.
- **Recommended correction:** Derive/validate status against finding precedence and validate
  `first_breaking_edge` consistency.

### AUD-009 — Disconnected nodes are mislabeled as unaffected branches

- **Severity:** Medium
- **Status:** Fixed; only alternate outgoing paths from affected ancestors count as branches.
- **Reproduction:** Run
  `tests/adversarial/test_topology.py::test_disconnected_node_is_not_mislabeled_as_an_unaffected_branch`.
- **Expected behavior:** A disconnected node is excluded from impact and does not count as a branch
  of the affected graph component.
- **Actual behavior:** `unaffected_branches_exist` is `True` solely because the disconnected node
  exists.
- **Root cause:** The calculation subtracts affected nodes and ancestors from all graph nodes rather
  than looking for alternate outgoing paths from ancestors of the broken consumer.
- **Recommended correction:** Detect a reachable alternate branch from the broken path's ancestors;
  ignore disconnected components.

### AUD-010 — Empty trace import succeeds while recording nothing

- **Severity:** Medium
- **Status:** Fixed at the mutating CLI boundary; empty portable bundles remain representable.
- **Reproduction:** Run `graphabi record` against a valid trace bundle with zero runs and zero edge
  observations (covered by the empty-record adversarial test).
- **Expected behavior:** Exit 1 with an actionable “at least one run” message.
- **Actual behavior:** Exit 0 and print that zero runs were recorded.
- **Root cause:** Empty bundles are valid interchange values and the mutating CLI command adds no
  operational precondition.
- **Recommended correction:** Preserve an empty portable model if useful, but reject no-op imports
  at the `record` command boundary.

### AUD-011 — CLI structural comparison inspects only the first observation and exits zero

- **Severity:** High
- **Status:** Fixed; every contracted edge contributes to the derived schema and breaks exit 2.
- **Reproduction:** Store two-edge baseline/candidate runs where only the second edge changes from
  integer to string, then run `graphabi compare` (covered by the multi-edge CLI adversarial test).
- **Expected behavior:** Structural `FAIL` and CI exit code 2.
- **Actual behavior:** The first observation was identical, so the CLI printed structural `PASS`
  and exited 0 despite a later breaking type change.
- **Root cause:** `compare` derived schemas exclusively from `edge_observations[0]` and only semantic
  failure influenced exit status.
- **Recommended correction:** Derive a contract-edge-keyed aggregate schema and treat either
  structural or semantic failure as breaking.

### AUD-012 — Shipped LangGraph adapter does not implement the documented adapter protocol

- **Severity:** Medium
- **Status:** Fixed; `LangGraphRecorder.invoke` implements the runtime-checkable protocol.
- **Reproduction:** Compare `FrameworkAdapter.invoke` with the original public methods on
  `LangGraphRecorder`; the latter exposed only `begin`, `instrument`, and `finish`.
- **Expected behavior:** The first-party adapter demonstrates the public extension protocol.
- **Actual behavior:** Runtime conformance was false and no test connected documentation to code.
- **Root cause:** The protocol and concrete integration evolved independently.
- **Recommended correction:** Implement `invoke` around a compiled instrumented graph, mark the
  protocol runtime-checkable, and test conformance plus real invocation.

### AUD-013 — Structural report claims Pydantic compatibility without model evidence

- **Severity:** Medium
- **Status:** Fixed; Pydantic compatibility is true only when integration proves shared identity.
- **Reproduction:** Call `compare_schemas` with identical raw schema dictionaries and leave
  `same_pydantic_model=False`.
- **Expected behavior:** JSON-schema compatibility may pass, but Pydantic-model compatibility is not
  proven.
- **Actual behavior:** `pydantic_model_compatible` became true whenever the limited JSON-schema
  comparison was compatible.
- **Root cause:** The implementation conflated schema compatibility with model-level evidence.
- **Recommended correction:** Keep report fields independent and document trace-derived limits.

### AUD-014 — Scalar coercion and timestamp ambiguity can bypass safe evaluation

- **Severity:** Medium
- **Status:** Fixed; security-relevant scalars are strict, timestamps require zones, booleans are
  distinct from numbers, and future freshness is `UNKNOWN`.
- **Reproduction:** Supply `opened: "yes"`, numeric comparison input `true`, or a naive observation
  timestamp.
- **Expected behavior:** Reject malformed inputs or return uncertainty without arithmetic errors.
- **Actual behavior:** Pydantic coerced selected fields and Python considers `True > 0`; naive/aware
  freshness subtraction could fail at runtime.
- **Root cause:** Default coercion and Python boolean-number semantics were used at trust boundaries.
- **Recommended correction:** Use strict scalar annotations, aware trace times, and numeric guards.

### AUD-015 — Precise static coverage/test claims become stale immediately

- **Severity:** Low
- **Status:** Fixed; the badge states the enforced `>=85%` policy and commands print measurements.
- **Reproduction:** Add audit tests; README still claims 59 tests and point-in-time 93.75%/94%.
- **Expected behavior:** Badges correspond to durable configuration or automated measurements.
- **Actual behavior:** Exact values became stale as soon as legitimate tests were added.
- **Root cause:** Point-in-time metrics were copied into long-lived repository metadata.
- **Recommended correction:** Badge the threshold and report exact values only in audit/releases.

### AUD-016 — Checkout action uses a mutable major-version tag

- **Severity:** Medium
- **Status:** Fixed; CI and release dry run pin the resolved official v6 commit.
- **Reproduction:** Inspect both workflow files: `actions/checkout@v6` is tag-based while setup-uv
  already uses a full commit SHA.
- **Expected behavior:** Release-relevant third-party actions are immutable and auditable.
- **Actual behavior:** Checkout could change without a repository diff.
- **Root cause:** Mixed action pinning policy.
- **Recommended correction:** Resolve the official v6 tag and pin
  `d23441a48e516b6c34aea4fa41551a30e30af803`, retaining a `# v6` update hint.

### AUD-017 — Existing Git author metadata contains a personal email address

- **Severity:** Medium (publication privacy)
- **Status:** Maintainer decision required; repository files are clean, history was not rewritten.
- **Reproduction:** Run `git log --format='%an <%ae>'`; existing commits use the local contributor's
  name and Gmail address.
- **Expected behavior:** The maintainer explicitly chooses whether public commit attribution should
  use that address or an established GitHub noreply identity.
- **Actual behavior:** A public push would expose the configured address in Git history.
- **Root cause:** Commits correctly inherited the user's local Git identity, but that identity has
  not been reviewed as a publication choice.
- **Recommended correction:** Before pushing, configure the desired verified/noreply identity and,
  only with explicit maintainer approval, rewrite local author metadata if privacy is desired.

## Adversarial experiment ledger

| Experiment | Status | Evidence |
|---|---|---|
| A. Remove semantic regression | Pass | Monkeypatched candidate uses actual opened/supporting source; full semantic report becomes PASS. |
| B. Independent unit regression | Pass | Separate `commerce_flow`, USD baseline versus INR candidate, correct breaking contract. |
| C. Independent authority escalation | Pass | Separate `approval_flow`, recommendation versus authorized, correct breaking contract. |
| D. Branches, cycles, disconnected nodes, multiple terminals | Pass | Branch isolation, two terminals, bounded cycle, and disconnected-component behavior are asserted. |
| E. Malformed/adversarial inputs | Pass | Deep payloads, Unicode/long values, duplicates, bad paths/types, empty input, corrupt rows, HTML, and secret shapes fail safely or round-trip as appropriate. |
| Same model and JSON schema identity | Pass | Runtime class identity and schema equality asserted for baseline, broken candidate, and repaired candidate. |
| No hardcoded demo identifiers/outcomes | Pass | Independent commerce, approval, math/plugin graph IDs and run IDs produce data-derived findings. |
| Reports derived from stored traces | Pass | Demo persists and reloads both runs; report semantics equal independent re-evaluation of those SQLite records. |
| Transactional SQLite failure behavior | Pass | Mid-bundle unique-key failure rolls back and preserves prior bundle byte-equivalent model state. |
| Stable CI exit codes | Pass | Success=0, operational/validation=1, breaking=2, uncertainty=3; optional report is INFO. |
| Benchmark methodology | Pass | Each requested operation invokes production code; synthetic setup is now separately measured, not hidden. Single-iteration and topology limits remain disclosed. |
| Wheel install outside checkout | Pass | Isolated `uv tool install`; demo executed on Python 3.13. |

## Final disposition

### Verification after remediation

- `make bootstrap`: **PASS**.
- `make lint`: **PASS** (79 files formatted; all Ruff rules pass).
- `make typecheck`: **PASS** (0 errors, 0 warnings).
- `make test`: **PASS** (100 tests; 92.98% branch-aware package coverage; 85% required).
- `make demo`: **PASS** with the expected schema `PASS`, semantics `FAIL`, first breaking edge, and
  persisted witness.
- `make benchmark`: **PASS** with separately reported fixture/load/evaluation/impact/report phases.
- `uv build`: **PASS** for `graphabi-0.1.0a1.tar.gz` and the universal wheel.
- `uv run graphabi doctor`: **PASS**.
- `uv run graphabi demo --allow-breaking`: **PASS**.
- Final wheel demo from unrelated temporary directories: **PASS** on Python 3.12.13 and 3.13.14.
- Secret/personal/absolute-path scan of repository files: **PASS** with no matches. Git author
  metadata is separately disclosed in AUD-017.
- GitHub action versions were checked against the primary
  [checkout](https://github.com/actions/checkout) and
  [setup-uv](https://github.com/astral-sh/setup-uv) repositories; third-party actions are pinned.

Finding totals: 1 critical, 4 high, 11 medium, and 1 low. Every technical critical/high finding and
reasonable technical medium finding is fixed with a regression test; AUD-017 requires an explicit
maintainer privacy decision rather than an automatic history rewrite.

### Remaining limitations

- Compatibility remains contract- and observation-scoped; it is not arbitrary semantic
  understanding or exhaustive behavioral equivalence.
- Trace schema 0.1 deliberately rejects repeated node/edge occurrences rather than pairing loops
  or fan-out executions.
- Structural analysis is a documented subset of JSON Schema compatibility, not formal subsumption.
- Provenance trusts adapter-generated source activity.
- Secret masking is best effort; raw SQLite and trace exports retain captured data.
- SQLite, the local report server, and single-iteration synthetic benchmarks are alpha-scale local
  facilities, not distributed or multi-user infrastructure.
- Installing a generic top-level `examples` package is a packaging compromise used to keep the
  offline installed-wheel demo functional; a future asset layout should avoid potential namespace
  collision.

### Approval

**Approve technically for public alpha release, conditional on reviewing AUD-017 before push.**
This is a genuinely working narrow alpha, not merely a hardcoded deterministic demonstration. Its
bundled demo is intentionally deterministic, but the same engine independently detects unit and
authority regressions under unrelated graph, edge, contract, and run identifiers; a repaired
candidate naturally passes; findings change with changed behavior; reports are re-derived from
persisted trace records. Approval does not extend beyond the explicit limitations above.
