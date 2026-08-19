# PyPI readiness for v0.1.0-alpha.3

Status: readiness verification only. **Nothing was uploaded to PyPI or TestPyPI.** This records
what was checked, against the built `graphabi-0.1.0a3-py3-none-any.whl` and
`graphabi-0.1.0a3.tar.gz` artifacts, so a maintainer can decide whether to authorize publication
in a separate, later step.

## Checked and ready

| Item | Result |
|---|---|
| Package name availability | `graphabi` is unregistered: `https://pypi.org/pypi/graphabi/json` returns HTTP 404 as of this check. |
| `twine check` | PASSED for both the wheel and the sdist. |
| Classifiers | `Development Status :: 3 - Alpha`, `Programming Language :: Python :: 3.12`, `Programming Language :: Python :: 3.13`, `Typing :: Typed`. All are valid Trove classifiers. No legacy `License ::` classifier is present, which is correct: Warehouse rejects packages that declare both a PEP 639 SPDX `license` string (`Apache-2.0`, used here) and a legacy `License ::` classifier. |
| Python requirement | `requires-python = ">=3.12,<3.14"` matches the two classifiers and the actual CI test matrix exactly. |
| License metadata | SPDX `license = "Apache-2.0"` plus `license-files = ["LICENSE"]`; the file exists at the repository root and matches the SPDX identifier. |
| Project URLs | Homepage, Repository, Documentation, Issues, and Changelog are all present, all point to public `github.com`/`github.io` locations, and contain no personal contact information. |
| CLI entry points | Both `graphabi` and `graphabi-github-summary` (`[project.scripts]`) were verified present and runnable from a clean isolated install of the built wheel. |
| Clean-environment import | `import graphabi` succeeds from an isolated venv with only the wheel installed; fails cleanly with `ModuleNotFoundError` after `uv pip uninstall`, with no leftover entry-point scripts. |
| Wheel/sdist integrity | Both built and `twine check`-clean. SHA-256: wheel `8a13b22f9a5aa38e8216795252c8d15d98fe4425f2181b1f5081c227f703d248`, sdist `ea308b7bcb4b2a5eb1b67c093b6851bc36c40cb00743021f7e98490a493d2675`. These hashes are for this local build; a maintainer re-running `uv build` from the same source tree should reproduce them (`uv build` is not currently configured for byte-for-byte reproducibility across machines/timestamps, so treat this as a local integrity record, not a reproducible-build guarantee). |
| Install command | `uv tool install dist/graphabi-0.1.0a3-py3-none-any.whl` and `pip install`-equivalent isolated installs both verified working, on Python 3.12 and 3.13. |
| Uninstall behavior | `uv pip uninstall graphabi` removes the package and both CLI entry points cleanly; no orphaned files were observed. |

## README rendering: a real limitation, deliberately not changed here

`README.md` uses paths like `docs/assets/brand/logo-light.svg` (relative to the repository root)
for its images and internal doc links. On GitHub's own README renderer, relative links resolve
correctly against the current branch automatically, which is why the project uses them. Warehouse
(the PyPI package index) renders the README as a standalone page and does not rewrite relative
links against the source repository, so **on the PyPI project page specifically, the logo and the
two inline screenshots would not render, and internal doc links would 404.**

This was not fixed in this pass. An initial attempt to rewrite the README's links to absolute
GitHub URLs was reverted after it broke an existing, deliberate regression test
(`tests/unit/test_brand_assets.py::test_readme_local_image_references_resolve`), which exists
specifically to keep these paths resolvable from a local checkout. Changing that trade-off is a
real project decision (GitHub-native correctness vs. PyPI rendering), not a small RC fix, and
should not be made unilaterally inside a validation pass. Two real options exist for whoever
authorizes PyPI publication later:

1. Add a build-time README rewrite (for example `hatch-fancy-pypi-readme`) that only rewrites
   links in the built `long_description`, leaving the source `README.md` and its test unchanged.
2. Accept the degraded PyPI README rendering for the alpha line and revisit before a stable
   release.

Do not silently pick one; this needs a maintainer decision.

## Not yet built: trusted publishing

No publish workflow exists in `.github/workflows/` today, by design; `SECURITY.md` already states
release workflows build but do not publish automatically, and this pass did not add one. When
publication is separately authorized, the expected design (not yet implemented) is:

- A dedicated `publish.yml` workflow, triggered only on a signed release tag, not on every push.
- OIDC-based PyPI Trusted Publishing (`id-token: write` permission, `pypa/gh-action-pypi-publish`),
  so no long-lived PyPI API token needs to be stored as a repository secret.
- A GitHub Environment (for example `pypi`) with required-reviewer protection gating the publish
  job, separate from the existing `ci.yml` and `release-dry-run.yml` workflows.
- PEP 740 provenance attestations are generated automatically by trusted publishing through
  `gh-action-pypi-publish`; no extra step is needed to get them, but the workflow must use trusted
  publishing (not a manual API-token upload) for attestations to exist.

Building this workflow now, before anyone has approved publishing, would add unreviewed surface
that no one asked for; it belongs in the same change that receives explicit publish approval.

## Explicitly not done

- No `twine upload` or `--repository testpypi` was run.
- No PyPI or TestPyPI account/project was created or claimed.
- No API token or trusted-publisher configuration was created on pypi.org.

## Bottom line

Package metadata, classifiers, license, entry points, install/uninstall behavior, and artifact
integrity are all ready. The one open item is the README rendering trade-off above, which is a
maintainer decision, not a defect to silently patch. Nothing here changes the Alpha.3 recommendation
in `docs/research/alpha3-rc-gap-analysis.md`; it was already conditioned on human review before any
publish action.
