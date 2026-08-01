"""Guard the canonical, dependency-free GraphABI visual identity."""

from __future__ import annotations

import re
import struct
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[2]
BRAND = ROOT / "docs" / "assets" / "brand"


def test_canonical_brand_assets_exist_and_svg_sources_are_self_contained() -> None:
    expected = {
        "architecture.svg",
        "demo.gif",
        "favicon.svg",
        "hero-graph.svg",
        "icon.svg",
        "logo-dark.svg",
        "logo-light.svg",
        "logo-mark.svg",
        "logo-monochrome.svg",
        "logo.svg",
        "open-graph.png",
        "open-graph.svg",
        "organization-avatar.png",
        "organization-avatar.svg",
        "report-preview.svg",
        "social-preview.png",
        "social-preview.svg",
    }
    assert expected <= {path.name for path in BRAND.iterdir()}
    for source in BRAND.glob("*.svg"):
        ElementTree.parse(source)
        contents = source.read_text(encoding="utf-8")
        assert "http://www.w3.org/2000/svg" in contents
        assert not re.search(r"(?:href|src)=[\"']https?://", contents)


def test_broken_edge_is_the_shared_mark_and_is_favicon_safe() -> None:
    mark = (BRAND / "logo-mark.svg").read_text(encoding="utf-8")
    favicon = (BRAND / "favicon.svg").read_text(encoding="utf-8")
    for contents in (mark, favicon):
        assert "#A78BFA" in contents
        assert "#EF4444" in contents
        assert "#556070" in contents
        assert "M29 26L35 31" in contents or "M7.05 5.8L8.95 7.45" in contents
    assert 'width="16" height="16"' in favicon


def _png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    return struct.unpack(">II", data[16:24])


def test_raster_derivatives_have_exact_dimensions() -> None:
    assert _png_size(BRAND / "social-preview.png") == (1280, 640)
    assert _png_size(BRAND / "open-graph.png") == (1200, 630)
    assert _png_size(BRAND / "organization-avatar.png") == (512, 512)


def test_readme_demo_is_a_one_shot_gif() -> None:
    data = (BRAND / "demo.gif").read_bytes()
    assert data.startswith((b"GIF87a", b"GIF89a"))
    assert struct.unpack("<HH", data[6:10]) == (1000, 520)
    assert b"NETSCAPE2.0" not in data  # no looping extension; the reasoning sequence stops


def test_readme_local_image_references_resolve() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    image_paths = re.findall(r"(?:src=\"|\]\()(?P<path>docs/assets/[^\"\)]+)", readme)
    assert image_paths
    assert all((ROOT / path).is_file() for path in image_paths)
