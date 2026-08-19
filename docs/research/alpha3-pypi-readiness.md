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
| Wheel/sdist integrity | Both built and `twine check`-clean. SHA-256: wheel `eccde70c325251209948f6ccc47fd9738bef3b93a7b3083b1ed0505e9d5719f2`, sdist `5e911b4feeb3541e6163b0d27e9d01b40946d62a7e4ca071a81c106bbba17185`. These hashes are for this local build, made after adding the PyPI long-description rewrite below, and differ from the pre-fix hashes recorded earlier in this document's history for that reason, not because of build non-determinism. A maintainer re-running `uv build` from the same source tree should reproduce the wheel hash exactly; the sdist embeds build timestamps and is not byte-for-byte reproducible across runs, so treat only the wheel hash as a reproducibility check. |
| Install command | `uv tool install dist/graphabi-0.1.0a3-py3-none-any.whl` and `pip install`-equivalent isolated installs both verified working, on Python 3.12 and 3.13. |
| Uninstall behavior | `uv pip uninstall graphabi` removes the package and both CLI entry points cleanly; no orphaned files were observed. |

## README rendering: resolved with a build-time rewrite

`README.md` uses paths like `docs/assets/brand/logo-light.svg` (relative to the repository root)
for its images and internal doc links. On GitHub's own README renderer, relative links resolve
correctly against the current branch automatically, which is why the project uses them. Warehouse
(the PyPI package index) renders the README as a standalone page and does not rewrite relative
links against the source repository, so without a fix, the logo, the two inline screenshots, and
every internal doc link would have been broken on the PyPI project page specifically.

This is now fixed with option 1 from the two previously identified: `[project].readme` is
`dynamic`, and `hatch-fancy-pypi-readme` (a `build-system` requirement, not a runtime dependency)
renders the PyPI long description from `README.md` at build time, rewriting only
repository-relative links and images to absolute GitHub URLs pinned to this release's tag
(`v0.1.0-alpha.3`), configured in `[tool.hatch.metadata.hooks.fancy-pypi-readme]` in
`pyproject.toml`. `README.md` itself, and the existing regression test protecting it
(`tests/unit/test_brand_assets.py::test_readme_local_image_references_resolve`), are both
unchanged and still pass; GitHub continues to render the source file exactly as before.
`tests/unit/test_pypi_readme.py` renders the long description through the same code path
hatchling calls during a real build and asserts: no relative link or image survives the rewrite;
every rewritten link is pinned to the ref matching `[project].version`; directory links use
`/tree/` and file links use `/blob/`; image embeds use `raw.githubusercontent.com`; and the
rendered text contains no em dash, no personal absolute path, and no Gmail address.

The pinned ref is a plain string kept in sync with `[project].version` by that same test, matching
the project's existing versioning convention: the tag does not exist until the release is actually
cut (this pass does not create it), exactly like `version = "0.1.0a3"` in `[project]` already
predates the `v0.1.0-alpha.3` tag it will correspond to. Until the tag exists, the rewritten links
in a long description built from this exact source tree return 404; they resolve correctly once
the tag is pushed, which by this project's own release sequence happens before PyPI publication is
authorized.

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

Package metadata, classifiers, license, entry points, install/uninstall behavior, artifact
integrity, and PyPI README rendering are all ready. Nothing here changes the Alpha.3
recommendation in `docs/research/alpha3-rc-gap-analysis.md`; it was already conditioned on human
review before any publish action.
