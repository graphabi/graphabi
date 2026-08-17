# Post-alpha.1 baseline

Status: complete on 2026-08-11.

## Exact commits

- Audited `graphabi/graphabi` product baseline:
  `8855346a08442f496e9bd6db6900b4c8ac262b25`.
- `v0.1.0-alpha.1` annotated tag target:
  `a1649b2bed1c1a8c116590f7f4265b318667e9a1`.
- Website `main`: `3eaef342da8f283c3805eed324fbf63e0ac81c2a`.
- Organization profile `main`: `0461ee4e2c634f14966306c115740d8663f5fa40`.
- Preserved website review-media branch: `assets/pr-media` at
  `ffd040cb9ffd32dd45bf4b8d595ee3db03e0bcd0`.

The exact product baseline for the next development phase is `8855346a08442f496e9bd6db6900b4c8ac262b25`.
The commit that adds this record is necessarily later and documentation-only. It does not change
the package, trace schemas, reports, examples, or runtime behavior audited at that product commit.

## Measured proof

- Tests: 115 passed on Python 3.12.13.
- Coverage: 93.08% with a 90% enforced floor.
- Ruff: clean.
- Pyright: 0 errors, 0 warnings.
- Python CI matrix: 3.12 and 3.13.
- Default demo: deterministic, local, keyless, and intentionally reports semantic `FAIL` while
  structural compatibility remains `PASS`.
- Benchmark: local single-iteration synthetic linear graphs at 10, 100, and 1,000 nodes. These
  measurements are not production-scale or capacity claims.
- Package: source distribution and universal wheel built successfully. The wheel installed into a
  new Python 3.12 environment; `graphabi doctor` and `graphabi demo --allow-breaking` passed there.
- Report: JSON parsed successfully and the HTML contained no external stylesheet, script, or URL.

The checked-in public proof data matches the measured 115 tests, 93.08% coverage, seven evaluator
families, Python 3.12 and 3.13, and one maintained adapter.

## Public surfaces

- Repository: <https://github.com/graphabi/graphabi>
- Website repository: <https://github.com/graphabi/graphabi.github.io>
- Organization metadata repository: <https://github.com/graphabi/.github>
- Organization profile: <https://github.com/graphabi>
- Website: <https://graphabi.github.io>
- Alpha.1 release: <https://github.com/graphabi/graphabi/releases/tag/v0.1.0-alpha.1>

Anonymous clones of all three repositories succeeded with credential helpers disabled. All public
links in the tracked repository, website, and organization-profile text returned a successful or
redirect response. The deployed website assets byte-match website `main`, and GitHub Pages reports
a successful HTTPS build from that commit.

Lighthouse 13.4.1 results for the deployed site were:

| Form factor | Performance | Accessibility | Best practices | SEO |
|---|---:|---:|---:|---:|
| Mobile | 97 | 100 | 100 | 100 |
| Desktop | 100 | 100 | 100 | 100 |

The live site was also checked at 320 px, 390 px, 768 px, and 1440 px in light and dark schemes.
Reduced motion produced no running animations. The ambient field is hidden from accessibility
tools, uses `pointer-events: none`, made requests only to the website origin, and did not block the
setup controls. The 27-frame README/profile GIF is public, rendered by GitHub as animated media,
and matches the canonical core asset byte for byte.

## Supported adapters

- LangGraph `>=1.0,<1.3` through `src/graphabi/adapters/langgraph/`.

No other framework adapter is represented as shipped.

## Evaluator families

- `implication`
- `provenance`
- `set_preservation`
- `completeness`
- `unit_consistency`
- `authority`
- `freshness`

Every evaluator is deterministic and retains `UNKNOWN` and `INSUFFICIENT_EVIDENCE` as non-pass
outcomes.

## Release and repository state

- The alpha.1 release is a published prerelease. Its tag remains annotated and fixed at the reviewed
  PR #13 merge commit.
- Release asset SHA-256 values match the release notes:
  - wheel: `411bf5f7950bd0c6d230dbc7425d8cdd113ed27f49db398b545b581ec1b5888e`
  - source: `643baeb13e52de865f615a9999da7e26858cf6e2144fae0abdebbde20e0e1b25`
- A 2026-08-17 archive-content audit found that the uploaded assets match the packaged source tree
  at reviewed commit `c7bb16345900588b66203c750307a852de7633ec` and its package-equivalent
  workflow-only successor `ede31be5b95021586d63462c893a2d72b02e1a0a`, not the later annotated tag
  commit. The wheel's Python modules match the tag, but its dependency metadata and the source
  archive's changelog predate the tag. The immutable assets were not replaced and the tag was not
  moved; the release documentation records the distinction explicitly.
- PyPI and TestPyPI both return 404 for `graphabi`; neither index contains a GraphABI publication.
- PR #14, the reviewed Typer and Hypothesis update, was merged and its branch deleted.
- The website `design/field-and-instrument` and organization-profile
  `design/profile-and-hygiene` branches had no patch absent from `main` and were deleted as
  superseded squash-merge sources.
- No draft PR, open human-authored PR, Claude branch, Codex branch, or other useful reviewed patch
  remains stranded.
- `assets/pr-media` remains intentionally orphaned as historical review evidence.
- All reachable public commit authors and committers use GitHub noreply identities. No Gmail
  address was found in reachable history.
- Current tracked project text contains no private absolute path or em dash character.

The core repository has Issues and Discussions enabled, current descriptions, homepage URLs, and
topics. The active `main` rulesets require an up-to-date pull request, resolved conversations, and
the documented checks. Core requires `quality (3.12)`, `quality (3.13)`, and `build-and-install`;
the website and organization profile require `Static integrity`. Force pushes and branch deletion
are blocked for `main`.

Secret scanning and push protection are enabled on all three repositories. Private vulnerability
reporting and automated security fixes are enabled on the core repository. Vulnerability alerts
are enabled and no open Dependabot alerts were returned. The two static repositories have no
package dependency graph, so automated dependency fixes are not active there.

The organization uses the custom Semantic Pulse avatar. As of 2026-08-17, the repository metadata
references a custom `repository-images.githubusercontent.com` social preview. No public
organization pins are configured, so GitHub's signed-out popular-repository ordering is used. The
missing pins remain explicit organization-polish work rather than claimed completed customization.

## Current limitations

- A pass covers only observed executions and enforced contracts. Coverage is not correctness or a
  proof of safety on unseen inputs.
- Trace schema 0.1 permits one observation for an edge in a run. Repeated nodes, loops, retries,
  fan-out, fan-in, and repeated edge crossings do not yet have causal occurrence identities;
  ambiguous duplicates are rejected.
- Contract coverage can describe contracted and observed trace edges and configured branches. It
  cannot discover graph edges absent from both contracts and traces.
- OpenTelemetry and OpenInference ingestion has been assessed but is not implemented or advertised
  as supported.
- LangGraph is the only maintained framework adapter.
- Stored payloads cannot reconstruct every original Pydantic or JSON Schema constraint.
- Unit checking does not silently convert values, and a permitted conversion remains unknown until
  an application supplies verified policy.
- SQLite is a local single-process store. Report masking is not general data-loss prevention.
- The optional live-model example is a provider-boundary demonstration, can incur user-directed
  cost, and is not a maintained provider adapter.

## Baseline decision

Every intended existing production change is present on the audited product baseline. No useful
reviewed work remains only on a feature branch. The alpha.1 tag and assets remain immutable and
checksum-verifiable, with their source-provenance distinction documented above. Development after
this record may proceed from the documented baseline without changing or retagging
`v0.1.0-alpha.1`.
