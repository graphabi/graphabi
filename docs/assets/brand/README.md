# GraphABI brand assets

These are the canonical, repository-local sources for the GraphABI visual identity. The system is
defined in [`DESIGN_SYSTEM.md`](../../../DESIGN_SYSTEM.md).

The broken edge is the logo. Purple is semantic information in flight, green is a proven pass,
red is a breaking incompatibility, amber is unknown or insufficient evidence, and gray is
inactive graph structure.

Raster files are deterministic derivatives of the SVG or demo-animation sources. Do not edit a
raster derivative independently. Run `uv run python scripts/generate_brand_assets.py` after
changing a source asset, then inspect the output at 16 px, full size, and on both light and dark
backgrounds:

```bash
uv run --with pillow python scripts/generate_brand_assets.py
```

All assets are Apache-2.0 licensed with the repository. No third-party artwork or hosted font is
used.
