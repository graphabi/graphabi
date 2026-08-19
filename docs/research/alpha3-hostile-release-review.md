# Alpha 3 hostile release review

Status: engineering review, not a release decision. Written adversarially: assume Alpha.3 should
be rejected, and try to find the reason. This is a review of the actual `main` diff since
`v0.1.0-alpha.2` (`0bccea5`), not of intentions. Every finding below was checked directly, not
assumed. Findings that were fixed during this pass are marked; nothing was fixed by weakening
uncertainty semantics or by deleting a test.

## Findings

### 1. A merged regression test was genuinely flaky, not just theoretically racy (found and fixed)

While pushing this review's own documentation-only PR, CI failed on Python 3.13 (Linux) with
`test_langgraph_separate_parent_edges_fail_closed_on_premature_join` (added by #41, already merged)
raising `Failed: DID NOT RAISE ValueError`. That test passed locally on this machine every time it
was run, including 10 consecutive runs. Root-caused rather than dismissed as CI noise: LangGraph's
`BackgroundExecutor` runs same-superstep node tasks on separate OS threads
(`langgraph/pregel/_executor.py`, `concurrent.futures`); the test's "fast" branch triggering `join`
and "slow_1"→"slow_2" triggering `slow_2` land in the same superstep, so which node's thread
reaches GraphABI's recorder lock first is a genuine, unbounded OS thread race, not a guarantee. It
happened to resolve the same way in roughly 40+ local runs across this whole session and differently
on a single GitHub Actions run, which is exactly what an intermittent race looks like: confidence
from local repetition was not evidence of determinism.

**Verdict: this would have shipped a flaky test into the RC's CI signal**, undermining the exact
"all required CI passes" gate this release is supposed to satisfy, and calling into question whether
the "fails closed on premature join" claim in `docs/occurrence-pairing.md` and the production
reality sprint's P1 write-up was actually a reliable, reproducible property or an artifact of one
machine's thread-scheduling timing.

**Fixed:** added a small test-only helper, `_invoke_sequential`, that still runs the real LangGraph
engine and the real recorder, but with `config={"max_concurrency": 1}` so LangGraph's own task
queue (submission order) decides execution order instead of concurrent thread dispatch. Verified
empirically: 20/20 direct runs and 30/30 full-file `pytest` runs raised the expected `ValueError`
deterministically after the fix, versus the pre-fix version failing under real CI load. No
production code changed; the underlying fail-closed behavior is unchanged and still exercised
against genuine LangGraph execution, just without depending on which of two threads the OS
scheduler happens to run first.

### 2. A backward-incompatible behavior change had no changelog entry (found and fixed)

Commit `d14e9ab` (`fix: require explicit identity and authority semantics`), already on `main`
before this review began, changed `AuthorityEvaluator` so that any `authority` invariant without a
contract-declared `authority_order` now evaluates to `UNKNOWN` instead of comparing against the
previous implicit fixed six-level vocabulary. That is a real, silent regression for any existing
alpha.2 consumer's authority contract: the same contract, unchanged, now returns a different
compatibility status. The commit never touched `CHANGELOG.md`, and the draft Alpha.3 release notes
written earlier in this pass claimed "no new migration behavior... beyond what alpha.2 already
covers," which was false.

**Verdict: this alone would be sufficient grounds to reject the release as drafted.** A consumer
upgrading blind would see previously-passing authority checks silently downgrade to `UNKNOWN` with
no changelog signal telling them why or what to do about it.

**Fixed:** added a `CHANGELOG.md` entry under `[0.1.0-alpha.3]` and rewrote the release notes'
"Changed" section and compatibility table to state the break explicitly and give the exact
migration step (add `authority_order` to every existing `authority` invariant). This did not touch
`src/graphabi/`; the evaluator behavior itself (`docs/contract-format.md`'s own account of it) is
correct and intentional, is the more honest behavior, and was already correctly documented in
`docs/contract-format.md` and `docs/inference.md`. Only the changelog and release-notes silence
was the defect.

### 3. Personal, inaccessible filesystem paths in permanent documentation (found and fixed)

`docs/research/alpha3-rc-gap-analysis.md` and the draft release notes both cited evidence as
living at `~/Developer/graphabi-lab/...`. A home-directory-relative path is meaningless to any
reader who is not the author on the author's own machine, and it is exactly the kind of detail a
release-readiness pass is supposed to catch: it fails the RC brief's own "no personal paths"
requirement. A pre-existing instance of the identical problem, predating this review, was also
found in `docs/research/alpha3-hostile-validation.md` (`~/Developer/graphabi-lab` at line 40),
which had already merged to `main` in an earlier commit.

**Verdict: real, but low severity** (documentation only, not shipped in the package, not a security
issue) **and now fixed.** All three references were rewritten to name the separate `graphabi-lab`
directory without a home-relative prefix, matching the convention `alpha3-hostile-validation.md`
itself uses in its other reference to the same directory.

### 4. Self-inflicted README breakage during this same review (caught by an existing test, reverted)

While checking PyPI README rendering, this review rewrote `README.md`'s relative image and doc
links to absolute GitHub URLs, reasoning that Warehouse (PyPI) does not resolve relative links
against the source repository the way GitHub's own renderer does. That edit broke
`tests/unit/test_brand_assets.py::test_readme_local_image_references_resolve`, an existing,
deliberate regression test protecting the opposite property: that `README.md`'s asset paths resolve
from a local checkout. The edit was reverted in full before being committed anywhere.

**Verdict: not a defect in the shipped release** (nothing was ever committed), **but worth
recording**, because it shows the actual tension is real: GraphABI's README is optimized for
GitHub-native correctness, which is a deliberate, tested choice, at the cost of broken images and
dead links on a future PyPI project page. See `docs/research/alpha3-pypi-readiness.md` for the two
legitimate ways to resolve this (a build-time README rewrite, or accepting degraded PyPI rendering
for the alpha line) and why this review declined to pick one unilaterally.

### 5. A literal em dash inside this review's own validation table (found and fixed)

`docs/research/alpha3-rc-validation.md`'s "No em dash characters" row contained a literal em dash
as the subject of its own `grep` pattern, which is a real, if trivial, self-contradiction: the row
claiming zero em dashes was not itself free of one. Rewritten to describe the character (U+2014)
instead of including it. Repository-wide scan is clean after the fix.

### 6. Coverage, UNKNOWN semantics, and adapter claims: no false confidence found

Checked directly rather than assumed:

- `docs/limitations.md`, `README.md`, and every adapter doc state coverage is not correctness,
  repeatedly and explicitly, not as a single disclaimer buried once.
- `UNKNOWN` and `INSUFFICIENT_EVIDENCE` are real, reachable, tested outcomes
  (`tests/unit/test_correctness_sprint.py`), not decorative states. The authority change in finding
  2 makes `UNKNOWN` more conservative, not less; nothing in this release makes uncertainty easier to
  avoid.
- Both adapter version bounds (`LangGraph >=1.0,<1.3`, `OpenAI Agents SDK >=0.20,<0.21`) are
  enforced in `pyproject.toml`, checked live by `graphabi doctor`, and now explicitly documented as
  the tested boundary rather than an advisory one (this release's third change).
- No classifier, license, or project-URL claim in `pyproject.toml` overstates what exists; the
  `graphabi` name is confirmed unregistered on PyPI, not merely assumed available.

### 7. Occurrence handling and the LangGraph fan-in fix: correctly scoped, not a broader fix in disguise

The LangGraph list-parent fan-in change (#41) touches zero files under `src/graphabi/`; it is
documentation and regression tests confirming existing fail-closed behavior. A hostile read might
suspect a "fix" commit quietly shipped a behavior change under a documentation label. It did not:
verified directly that `git diff` for that PR touches no production source file.

### 8. Packaging: no issue found beyond the already-documented README rendering gap

`twine check` passes for both artifacts. Wheel and sdist install cleanly in isolated environments
on both supported Python versions. Uninstall leaves nothing behind, including CLI entry points.
SHA-256 hashes are recorded in `docs/research/alpha3-pypi-readiness.md`. No trusted-publishing
workflow exists yet, which is correct: one should not exist before publication is authorized.

### 9. Security: no issue found

The 25-test adversarial redaction/storage/reporting suite passes. The new local-provider example
only ever talks to `127.0.0.1:11434` by default; a user who overrides `--model`/`url` is
knowingly reconfiguring their own script, not a default risk. No secret-pattern scan hit anything
in tracked files.

## What this review declined to fix

- **PyPI README rendering** (finding 4): a real maintainer trade-off, not a bug, and not this
  review's call to make unilaterally.
- **`set_preservation`/`completeness` evaluator generalization** and **`graphabi init` topology
  discovery**: both already classified CAN WAIT in `docs/research/alpha3-rc-gap-analysis.md` with
  reasoning that still holds; re-litigated here and not overturned.
- **Widening the OpenAI Agents SDK version bound** to cover `0.21.x`: explicitly not done; the
  hostile-validation observation that it worked incidentally is not integration coverage.

## Verdict

Three real defects were found (findings 1, 2, and 3) and fixed without weakening any uncertainty
semantics, deleting any test, or hiding the authority-evaluator behavior change; if anything, it is
now stated more plainly than before. One self-inflicted issue (finding 4) was caught by an
existing test and fully reverted before ever being committed. One trivial documentation
self-contradiction (finding 5) was fixed. No BLOCKER remains open. Findings 1 and 2 were serious
enough to be legitimate grounds to reject this exact release as it stood before this review; finding
3 was real but low severity. None are grounds to reject it now that all three are fixed and
verified.
