"""Generate deterministic GraphABI raster assets from canonical SVG sources.

Run on macOS with:
    uv run --with pillow python scripts/generate_brand_assets.py

The project does not need Pillow at runtime. SVG rasterization uses the macOS
``sips`` command so the generated images retain the exact vector typography and
geometry used by the public assets.
"""

# ruff: noqa: E501, RUF001

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / "docs" / "assets" / "brand"


def _render_svg(source: Path, destination: Path) -> None:
    sips = shutil.which("sips")
    if sips is None:
        msg = "Brand raster generation requires macOS 'sips'; SVG sources remain portable."
        raise RuntimeError(msg)
    subprocess.run(
        [sips, "-s", "format", "png", str(source), "--out", str(destination)],
        check=True,
        capture_output=True,
        text=True,
    )


def _node(x: int, width: int, label: str, role: str, state: str, visible: bool) -> str:
    if not visible:
        return ""
    border = {"normal": "#556070", "breaking": "#EF4444", "affected": "#66363B"}[state]
    surface = {"normal": "#121820", "breaking": "#1C1418", "affected": "#17171C"}[state]
    role_color = "#EF4444" if state == "breaking" else "#EF8080" if state == "affected" else "#94A3B8"
    return f"""
      <g transform="translate({x} 0)">
        <rect width="{width}" height="96" rx="11" fill="{surface}" stroke="{border}"/>
        <text x="17" y="45" fill="#F8FAFC" font-size="14" font-weight="700">{label}</text>
        <text x="17" y="69" fill="{role_color}" font-size="10">{role}</text>
      </g>"""


def _frame_svg(frame: int) -> str:
    node_count = min(4, max(1, frame // 2 + 1))
    baseline = 8 <= frame <= 17
    candidate = frame >= 18
    failed = frame >= 28
    blast = frame >= 31
    witness = frame >= 34

    pulse = ""
    pass_edges = ""
    if baseline:
        fraction = (frame - 8) / 9
        pulse_x = 180 + int(560 * fraction)
        pulse = f'<circle cx="{pulse_x}" cy="48" r="7" fill="#A78BFA"/>'
        if fraction > 0.31:
            pass_edges += '<path d="M180 48H250" stroke="#22C55E" stroke-width="4"/>'
        if fraction > 0.66:
            pass_edges += '<path d="M410 48H480" stroke="#22C55E" stroke-width="4"/>'
        if fraction > 0.94:
            pass_edges += '<path d="M670 48H740" stroke="#22C55E" stroke-width="4"/>'
    elif 18 <= frame < 28:
        fraction = (frame - 18) / 9
        pulse_x = 180 + int(44 * fraction)
        pulse = (
            f'<path d="M180 48H{pulse_x}" stroke="#A78BFA" stroke-width="5" '
            'stroke-linecap="round"/>'
            f'<circle cx="{pulse_x}" cy="48" r="7" fill="#A78BFA"/>'
        )
    elif failed:
        pulse = (
            '<path d="M180 48H224" stroke="#A78BFA" stroke-width="5" '
            'stroke-linecap="round"/><circle cx="224" cy="48" r="7" fill="#A78BFA"/>'
        )

    break_mark = ""
    if failed:
        break_mark = """
          <g transform="translate(229 34)" stroke="#EF4444" stroke-width="4" stroke-linecap="round">
            <path d="M0 0L15 13M0 15L15 28"/>
          </g>
          <text x="190" y="18" fill="#EF4444" font-family="Inter,-apple-system,sans-serif"
            font-size="10" font-weight="700" letter-spacing="1">FIRST BREAK</text>"""

    blast_path = ""
    if blast:
        blast_path = (
            '<path d="M250 48H410M410 48H480M670 48H740" stroke="#EF4444" '
            'stroke-width="2" stroke-dasharray="6 7" opacity=".8"/>'
        )

    schema = ""
    if candidate:
        schema = """
          <g transform="translate(657 36)" font-family="Inter,-apple-system,sans-serif">
            <rect width="135" height="48" rx="9" fill="#101C17" stroke="#205E39"/>
            <text x="13" y="20" fill="#94A3B8" font-size="9" font-weight="700">SCHEMA</text>
            <text x="13" y="39" fill="#22C55E" font-size="13" font-weight="700">✓ PASS</text>
          </g>"""
    semantics = ""
    if failed:
        semantics = """
          <g transform="translate(806 36)" font-family="Inter,-apple-system,sans-serif">
            <rect width="158" height="48" rx="9" fill="#211315" stroke="#6F2429"/>
            <text x="13" y="20" fill="#94A3B8" font-size="9" font-weight="700">SEMANTICS</text>
            <text x="13" y="39" fill="#EF4444" font-size="13" font-weight="700">× BREAKING</text>
          </g>"""

    witness_markup = ""
    if witness:
        witness_markup = """
        <g transform="translate(38 302)" font-family="Inter,-apple-system,sans-serif">
          <rect width="924" height="168" rx="12" fill="#121820" stroke="#3E262B"/>
          <rect width="5" height="168" rx="2.5" fill="#EF4444"/>
          <text x="24" y="31" fill="#EF4444" font-size="10" font-weight="700" letter-spacing="1.1">TRACE-BACKED WITNESS · CANDIDATE-003</text>
          <text x="24" y="63" fill="#F8FAFC" font-size="17" font-weight="620">verified=true arrived without an opened supporting source.</text>
          <text x="24" y="99" fill="#94A3B8" font-family="SFMono-Regular,Consolas,monospace" font-size="11">expected</text>
          <text x="112" y="99" fill="#22C55E" font-family="SFMono-Regular,Consolas,monospace" font-size="12">opened_sources_count &gt; 0</text>
          <text x="24" y="126" fill="#94A3B8" font-family="SFMono-Regular,Consolas,monospace" font-size="11">observed</text>
          <text x="112" y="126" fill="#EF4444" font-family="SFMono-Regular,Consolas,monospace" font-size="12">opened_sources_count = 0</text>
          <text x="24" y="151" fill="#94A3B8" font-size="11">Repair before verifier · affected path reaches publisher</text>
        </g>"""

    graph_state = "breaking" if failed else "normal"
    affected_state = "affected" if blast else "normal"
    graph = "".join(
        (
            _node(0, 180, "researcher", "producer · candidate", "normal", node_count >= 1),
            _node(250, 160, "verifier", "directly affected" if failed else "consumer", graph_state, node_count >= 2),
            _node(480, 190, "decision_maker", "affected" if blast else "consumer", affected_state, node_count >= 3),
            _node(740, 184, "publisher", "terminal", affected_state, node_count >= 4),
        )
    )
    phase = "BASELINE · ALL CONTRACTS PASS" if frame < 18 else "CANDIDATE SWAPPED · SAME PYDANTIC MODEL"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="520" viewBox="0 0 1000 520">
      <rect width="1000" height="520" fill="#0B0F14"/>
      <rect x="1" y="1" width="998" height="518" rx="15" fill="none" stroke="#273241" stroke-width="2"/>
      <g transform="translate(38 31)" font-family="Inter,-apple-system,sans-serif">
        <circle cx="8" cy="20" r="5" fill="#A78BFA"/><path d="M13 20H26" stroke="#A78BFA" stroke-width="4" stroke-linecap="round"/><path d="M34 20H47" stroke="#556070" stroke-width="4" stroke-linecap="round"/><circle cx="52" cy="20" r="5" fill="#556070"/><path d="M27 14L33 19M27 21L33 26" fill="none" stroke="#EF4444" stroke-width="3.5" stroke-linecap="round"/>
        <text x="70" y="29" fill="#F8FAFC" font-size="24" font-weight="650">GraphABI</text>
      </g>
      <text x="38" y="104" fill="#94A3B8" font-family="Inter,-apple-system,sans-serif" font-size="11" font-weight="700" letter-spacing="1.2">{phase}</text>
      {schema}{semantics}
      <g transform="translate(38 158)" font-family="SFMono-Regular,Consolas,monospace">
        <path d="M180 48H250M410 48H480M670 48H740" stroke="#556070" stroke-width="3" stroke-linecap="round"/>
        {pass_edges}{blast_path}{graph}{pulse}{break_mark}
      </g>
      {witness_markup}
    </svg>"""


def _generate_demo_gif() -> None:
    work_root = ROOT / ".graphabi"
    work_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="brand-frames-", dir=work_root) as temporary:
        frame_dir = Path(temporary)
        images: list[Image.Image] = []
        for frame in range(36):
            svg_path = frame_dir / f"frame-{frame:02d}.svg"
            png_path = frame_dir / f"frame-{frame:02d}.png"
            svg_path.write_text(_frame_svg(frame), encoding="utf-8")
            _render_svg(svg_path, png_path)
            with Image.open(png_path) as image:
                images.append(image.convert("P", palette=Image.Palette.ADAPTIVE, colors=128))
        durations = [100] * len(images)
        durations[17] = 650
        durations[27] = 400
        durations[30] = 350
        durations[-1] = 2500
        images[0].save(
            BRAND / "demo.gif",
            save_all=True,
            append_images=images[1:],
            duration=durations,
            optimize=True,
            disposal=2,
        )


def main() -> None:
    for name in ("social-preview", "open-graph", "organization-avatar"):
        _render_svg(BRAND / f"{name}.svg", BRAND / f"{name}.png")
    _generate_demo_gif()
    print("Generated GraphABI brand raster assets:")
    for path in sorted(BRAND.glob("*.png")) + sorted(BRAND.glob("*.gif")):
        print(f"- {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
