"""Guard the generated PyPI long description built from README.md.

README.md itself stays relative so it keeps rendering correctly on GitHub
(protected separately by ``test_readme_local_image_references_resolve``); this
module renders the long description through the exact same
``hatch-fancy-pypi-readme`` code path hatchling calls during a build and checks
that every repository-relative link and image was rewritten to a resolvable,
version-pinned absolute GitHub URL, with nothing relative left behind.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from hatch_fancy_pypi_readme._builder import build_text
from hatch_fancy_pypi_readme._config import load_and_validate_config

ROOT = Path(__file__).resolve().parents[2]
REPO_URL = "https://github.com/graphabi/graphabi"


def _load_pyproject() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def _version_to_tag(version: str) -> str:
    match = re.fullmatch(r"(\d+\.\d+\.\d+)a(\d+)", version)
    assert match, f"unexpected pre-release version format: {version!r}"
    return f"v{match.group(1)}-alpha.{match.group(2)}"


def _render_long_description() -> str:
    data = _load_pyproject()
    hook_config = data["tool"]["hatch"]["metadata"]["hooks"]["fancy-pypi-readme"]
    config = load_and_validate_config(hook_config)
    return build_text(config.fragments, config.substitutions, version=data["project"]["version"])


def _ref_from_replacement(replacement: str) -> str:
    match = re.search(
        r"graphabi/graphabi/(?:blob|tree)/([^/]+)/"
        r"|raw\.githubusercontent\.com/graphabi/graphabi/([^/]+)/",
        replacement,
    )
    assert match, replacement
    return match.group(1) or match.group(2)


def test_pypi_readme_ref_matches_project_version() -> None:
    data = _load_pyproject()
    expected_ref = _version_to_tag(data["project"]["version"])
    hook_config = data["tool"]["hatch"]["metadata"]["hooks"]["fancy-pypi-readme"]
    refs = {_ref_from_replacement(sub["replacement"]) for sub in hook_config["substitutions"]}
    assert refs == {expected_ref}, (
        "every substitution must pin the same ref as [project].version; "
        f"got {refs}, expected {{{expected_ref!r}}}"
    )


def test_pypi_long_description_has_no_relative_links_or_images() -> None:
    text = _render_long_description()
    pattern = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
    offenders = [match for match in pattern.findall(text) if not re.match(r"https?://|#", match)]
    assert offenders == []


def test_pypi_long_description_links_are_pinned_github_urls() -> None:
    data = _load_pyproject()
    expected_ref = _version_to_tag(data["project"]["version"])
    text = _render_long_description()
    rewritten = re.findall(r"\]\((https://[^)]+)\)", text)
    # Only the links this hook rewrites take the blob/tree/raw form; pre-existing
    # absolute links in README.md (badges, the issue tracker, clone URL) use plain
    # github.com/graphabi/graphabi paths and are intentionally left untouched.
    graphabi_links = [
        url
        for url in rewritten
        if "/blob/" in url or "/tree/" in url or "raw.githubusercontent.com" in url
    ]
    assert graphabi_links, "expected at least one rewritten repository link"
    allowed_prefixes = (
        f"{REPO_URL}/blob/{expected_ref}/",
        f"{REPO_URL}/tree/{expected_ref}/",
        f"https://raw.githubusercontent.com/graphabi/graphabi/{expected_ref}/",
    )
    for url in graphabi_links:
        assert url.startswith(allowed_prefixes), url


def test_pypi_long_description_directory_links_use_tree_not_blob() -> None:
    text = _render_long_description()
    for directory in ("examples/local_provider_quickstart", "regression_corpus"):
        match = re.search(rf"\]\((https://[^)]*{re.escape(directory)}[^)]*)\)", text)
        assert match, f"expected a rewritten link for {directory}"
        assert "/tree/" in match.group(1)
        assert "/blob/" not in match.group(1)


def test_pypi_long_description_has_no_em_dash_private_path_or_gmail() -> None:
    text = _render_long_description()
    mac_user_prefix = "/" + "Users" + "/"
    assert chr(0x2014) not in text
    assert mac_user_prefix not in text
    assert "gmail" + ".com" not in text


def test_pypi_readme_source_still_uses_relative_links_for_github() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "docs/assets/brand/hero-graph.svg" in readme
    assert "https://raw.githubusercontent.com" not in readme
    assert f"{REPO_URL}/blob/" not in readme
