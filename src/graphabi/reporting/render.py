"""JSON and self-contained accessible HTML report rendering."""

from __future__ import annotations

from html import escape
from pathlib import Path

from jinja2 import Environment, PackageLoader

from graphabi.contracts.models import Contract
from graphabi.reporting.models import CompatibilityReport


def graph_svg(contract: Contract, report: CompatibilityReport) -> str:
    """Render a deterministic inline SVG with edge compatibility status."""
    node_width = 164
    node_gap = 64
    margin = 32
    width = (
        margin * 2 + len(contract.nodes) * node_width + max(0, len(contract.nodes) - 1) * node_gap
    )
    height = 180
    positions = {
        node.id: (margin + index * (node_width + node_gap), 60)
        for index, node in enumerate(contract.nodes)
    }
    status_by_edge: dict[str, str] = {}
    for finding in report.semantic.findings:
        current = status_by_edge.get(finding.edge, "PASS")
        if finding.status == "BREAKING" or current == "BREAKING":
            status_by_edge[finding.edge] = "BREAKING"
        elif finding.status == "WARNING" or current == "WARNING":
            status_by_edge[finding.edge] = "WARNING"
        elif finding.status in {"UNKNOWN", "INSUFFICIENT_EVIDENCE"}:
            status_by_edge[finding.edge] = finding.status
        else:
            status_by_edge.setdefault(finding.edge, "PASS")
    colors = {
        "PASS": "#237a57",
        "BREAKING": "#c23b3b",
        "WARNING": "#a56a00",
        "UNKNOWN": "#6b7280",
        "INSUFFICIENT_EVIDENCE": "#6b7280",
    }
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-labelledby="graph-title graph-desc" '
        'xmlns="http://www.w3.org/2000/svg">',
        '<title id="graph-title">GraphABI compatibility graph</title>',
        '<desc id="graph-desc">Nodes and semantic status of each directed edge.</desc>',
        '<defs><marker id="arrow" markerWidth="9" markerHeight="7" refX="8" refY="3.5" '
        'orient="auto">'
        '<polygon points="0 0, 9 3.5, 0 7" fill="context-stroke"/></marker></defs>',
    ]
    for edge in contract.edges:
        x1, y1 = positions[edge.producer]
        x2, y2 = positions[edge.consumer]
        status = status_by_edge.get(edge.id, "UNKNOWN")
        color = colors[status]
        line_start = x1 + node_width
        line_end = x2
        parts.append(
            f'<line x1="{line_start}" y1="{y1 + 30}" x2="{line_end - 5}" y2="{y2 + 30}" '
            f'stroke="{color}" stroke-width="4" marker-end="url(#arrow)"/>'
        )
        parts.append(
            f'<text x="{(line_start + line_end) / 2}" y="{y1 + 17}" text-anchor="middle" '
            f'fill="{color}" font-size="12" font-weight="700">{escape(status)}</text>'
        )
    for node in contract.nodes:
        x, y = positions[node.id]
        extra = "terminal · side effect" if node.terminal and node.side_effecting else "node"
        parts.append(
            f'<rect x="{x}" y="{y}" width="{node_width}" height="60" rx="9" '
            'fill="#172033" stroke="#52617a" stroke-width="2"/>'
        )
        parts.append(
            f'<text x="{x + node_width / 2}" y="{y + 27}" text-anchor="middle" '
            f'fill="#f7fafc" font-size="14" font-weight="700">{escape(node.id)}</text>'
        )
        parts.append(
            f'<text x="{x + node_width / 2}" y="{y + 45}" text-anchor="middle" '
            f'fill="#aebbd0" font-size="11">{escape(extra)}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def write_report(
    report: CompatibilityReport, contract: Contract, directory: Path
) -> tuple[Path, Path]:
    """Write versioned JSON and offline HTML from the same report model."""
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / "report.json"
    html_path = directory / "index.html"
    json_path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    environment = Environment(
        loader=PackageLoader("graphabi.reporting"),
        autoescape=True,
    )
    template = environment.get_template("report.html.j2")
    html_path.write_text(
        template.render(
            report=report,
            graph_svg=graph_svg(contract, report),
            breaking=report.semantic.breaking_findings,
        ),
        encoding="utf-8",
    )
    return json_path, html_path
