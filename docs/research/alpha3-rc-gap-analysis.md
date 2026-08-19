# Alpha 3 release-candidate gap analysis

Status: engineering analysis, not a release decision. Performed after merging the LangGraph
list-parent fan-in documentation and regression tests (`e43f619`). It uses the production reality
sprint evidence in the separate `graphabi-lab` directory
(`production-reality/provider-local/20260818T125131Z/`) and the local hostile-validation record in
`docs/research/alpha3-hostile-validation.md`. No item below was added without a cited evidence
source.

## Method

Every remaining gap is classified as:

- **BLOCKER**: must be fixed before an Alpha.3 release candidate can be proposed.
- **SHOULD FIX**: small, evidence-backed, low-risk change that materially improves real usage;
  included in this RC if it stays within a narrow diff.
- **CAN WAIT**: real but out of scope for a minimal RC; requires a larger design decision, more
  evidence, or upstream conditions GraphABI does not control.

## Findings

### 1. Unclosed SQLite connections in `SQLiteTraceStore` (SHOULD FIX)

`src/graphabi/storage/sqlite.py` opens every connection through `with self._connect() as
connection:`. In the standard library, `sqlite3.Connection.__exit__` commits or rolls back the
transaction; it does not close the connection. All four call sites (`initialize`, `save_bundle`,
`load_run`, `list_runs`) leak a connection per call. Running the full suite under Python 3.13
confirms this directly: 12+ `ResourceWarning: unclosed database in <sqlite3.Connection ...>`
warnings appear that do not appear under 3.12 (3.13 finalizes and warns more aggressively).

This is core storage code, not test code, so the leak is real in `graphabi compare`, `graphabi
record`, `graphabi report --serve`, and every GitHub Action invocation. It has not previously been
flagged in `AUDIT.md`. Evidence: direct reproduction, `uv run --python 3.13 pytest -q -W default`.

### 2. No committed local-provider (Ollama) quick start (SHOULD FIX)

The production reality sprint validated a real local Ollama + LangGraph + OpenAI Agents SDK
workflow end to end (SAFE 10/10, BREAKING 10/10, UNKNOWN 10/10, deterministic replay, real
occurrence pairing), but none of that harness is committed to `graphabi`; it lives only in the
separate `graphabi-lab` directory. `FINAL_REPORT.md` lists as remaining blocker #1: "A user still
must author framework instrumentation and an explicit contract; `init` does not produce a provider
trace or project-specific comparison by itself," and `USABILITY.md` states manual instrumentation
authoring "is the remaining dominant usability cost." The repository already has a pattern for this
kind of example (`examples/model_migration`, deterministic fixture by default with an explicit
opt-in live path), but no equivalent exists for a local, free, keyless provider. This is exactly
the "local-provider examples" / "local-provider quick start" gap named in the RC brief, and it is
the single most evidence-backed improvement available.

### 3. OpenAI Agents SDK adapter version-bound policy is not explicit (SHOULD FIX)

`docs/research/alpha3-hostile-validation.md` records that an external checkout resolved
`openai-agents==0.21.1` and the adapter still worked, while GraphABI pins and enforces
`>=0.20,<0.21` everywhere (`pyproject.toml`, `graphabi doctor`, `docs/openai-agents-adapter.md`,
`docs/limitations.md`). The hostile-validation doc's own conclusion: "support boundaries need an
explicit compatibility policy." The fix is documentation only: state plainly that the pinned range
is the tested and enforced boundary, that versions outside it are unsupported regardless of
incidental compatibility, and that widening the bound requires new adapter-integration evidence.
Do not widen the dependency bound itself; there is no regression evidence for `0.21.x` behavior.

### 4. Preservation evaluator generalization (CAN WAIT)

`alpha3-hostile-validation.md` notes two entity-preservation mutations against real external repos
landed as `WARNING` rather than a clean evidence-backed finding, and recommends improving
`set_preservation`/`completeness` so "defensible entity invariants produce evidence-backed
findings." The same document says this "requires a generalized regression fixture before
implementation." That fixture does not exist yet, and the sample (two mutations) is too narrow to
safely generalize an evaluator without risking a new false positive. This is real but not minimal;
it needs its own evidence-gathering pass before implementation, not an RC-sized patch.

### 5. Guided graph-topology discovery in `graphabi init` (CAN WAIT)

The same manual-instrumentation friction behind item 2 could theoretically be reduced by having
`init` inspect running code or imports to suggest topology. `docs/init.md` and `README.md` both
document the current behavior ("never guesses graph topology") as a deliberate safety property, not
an oversight: a guess here risks fabricating structure the recorder never observed. Loosening it is
a design decision with real correctness risk, not a small RC fix, and no evidence in this sprint
shows the conservative behavior caused a wrong result, only added friction. Documented in the
roadmap already.

### 6. Native provider OTLP export / broader tool-span mapping (CAN WAIT)

`FINAL_REPORT.md` confirms Ollama has no native OTLP export today; the sprint's OTLP path was
application-generated. Local evidence-tool spans stayed `UNKNOWN`/unmapped by design, because a
generic tool or retriever span cannot prove a source was opened. This is an upstream and
epistemic limitation, not a GraphABI defect, and the current conservative behavior is correct.
`docs/trace-interoperability.md` and `docs/limitations.md` already state this plainly. No change
needed beyond confirming the docs still match behavior (they do).

### 7. GitHub Enterprise Server support for the Action (CAN WAIT)

`docs/github-action.md` and `docs/limitations.md` already disclose that the artifact dependency
does not support GHES. No user evidence in any validation sprint asked for GHES support. Out of
scope for a minimal RC.

### 8. Human adoption evidence (CAN WAIT, not an engineering task)

`FINAL_REPORT.md` item 25.4 and `alpha3-hostile-validation.md` both state zero external adoption,
contributor, or endorsement evidence exists. This cannot be produced by code changes and is
explicitly out of scope per the RC brief ("no ... contact external maintainers ... no ...
announce publicly").

## Areas checked with no evidence-backed gap found

- **Contract authoring ergonomics / UNKNOWN explanation / importer clarity**: `docs/inference.md`,
  `docs/trace-interoperability.md`, `docs/occurrence-pairing.md`, and `docs/contract-format.md`
  already state mechanism, evidence fields, and failure/UNKNOWN reasons precisely, with worked
  examples. No hostile-validation or production-reality finding named a confusion here.
- **`graphabi doctor` diagnostics**: covers Python version, architecture, writability, SQLite,
  contract parsing, both adapter version bounds, and latest-report presence, with correct
  required-vs-informational exit-code separation (`AUD-001`, already fixed pre-alpha.2). No sprint
  evidence names a missing or misleading check.
- **Security / privacy hygiene**: no em dash characters, no local filesystem paths, and no Gmail
  addresses exist in any tracked file (checked directly). `.github/CODEOWNERS` contains only a
  public GitHub handle, which is appropriate. `SECURITY.md` and the production-reality security
  record are consistent with actual behavior.
- **Package metadata**: `pyproject.toml` classifiers, license, Python requirement, and project URLs
  are accurate and contain no personal contact info. The `graphabi` name is unregistered on PyPI
  (`https://pypi.org/pypi/graphabi/json` returns 404 as of this analysis), so it remains available.
- **Compatibility from Alpha.2**: no schema, CLI, or storage compatibility break was introduced by
  the merged LangGraph documentation change; `docs/releases/v0.1.0-alpha.2.md`'s compatibility
  table still describes current behavior correctly.

## Summary

| Classification | Count | Items |
|---|---:|---|
| BLOCKER | 0 | none |
| SHOULD FIX | 3 | SQLite connection leak; committed local-provider (Ollama) quick start; OpenAI Agents SDK version-bound policy clarification |
| CAN WAIT | 5 | preservation evaluator generalization; guided topology discovery; native OTLP export; GHES support; human adoption evidence |

No BLOCKER was found. The three SHOULD FIX items are implemented next, each as the smallest change
that resolves the cited evidence.
