"""JSON and self-contained accessible HTML report rendering."""

from __future__ import annotations

from html import escape
from pathlib import Path

from jinja2 import Environment, PackageLoader

from graphabi.contracts.models import Contract
from graphabi.reporting.models import CompatibilityReport


def graph_svg(contract: Contract, report: CompatibilityReport) -> str:
    """Render a deterministic, replayable inline SVG from compatibility findings."""
    node_width = 176
    node_gap = 74
    margin = 32
    width = (
        margin * 2 + len(contract.nodes) * node_width + max(0, len(contract.nodes) - 1) * node_gap
    )
    height = 204
    positions = {
        node.id: (margin + index * (node_width + node_gap), 74)
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
        "PASS": "var(--pass-text)",
        "BREAKING": "var(--fail-text)",
        "WARNING": "var(--unknown-text)",
        "UNKNOWN": "var(--unknown-text)",
        "INSUFFICIENT_EVIDENCE": "var(--unknown-text)",
        "UNCONTRACTED": "var(--subtle)",
    }
    affected_nodes = {
        node_id
        for finding in report.semantic.breaking_findings
        for node_id in finding.affected_downstream_nodes
    }
    parts = [
        f'<svg class="compatibility-graph" viewBox="0 0 {width} {height}" role="img" '
        'aria-labelledby="graph-title graph-desc" xmlns="http://www.w3.org/2000/svg">',
        '<title id="graph-title">GraphABI compatibility graph</title>',
        '<desc id="graph-desc">Semantic flow stops at the first breaking edge; dashed red edges '
        "identify downstream impact rather than successful propagation.</desc>",
        '<defs><marker id="graph-arrow" markerWidth="8" markerHeight="7" refX="7" '
        'refY="3.5" orient="auto"><path d="M0 0L8 3.5L0 7Z" fill="context-stroke"/>'
        "</marker></defs>",
    ]
    contracted_edge_ids = {edge.id for edge in contract.edges}
    for index, edge in enumerate(contract.topology_edges):
        x1, y1 = positions[edge.producer]
        x2, y2 = positions[edge.consumer]
        status = (
            status_by_edge.get(edge.id, "UNKNOWN")
            if edge.id in contracted_edge_ids
            else "UNCONTRACTED"
        )
        color = colors[status]
        line_start = x1 + node_width
        line_end = x2
        center_y = y1 + 34
        label_x = (line_start + line_end) / 2
        edge_id = escape(edge.id, quote=True)
        # An edge leaving an affected node is downstream of a break. Its own
        # contract may well have passed, and the label still says so, but the
        # rail must not draw a confident arrow into a node the same report
        # marks as affected.
        downstream = status != "BREAKING" and edge.producer in affected_nodes
        group_class = "graph-edge is-downstream" if downstream else "graph-edge"
        parts.append(f'<g class="{group_class}" data-edge="{edge_id}" data-edge-index="{index}">')
        # A breaking edge gets no arrowhead on its inactive rail: nothing
        # arrived, so nothing should point into the consumer.
        rail_marker = "" if status == "BREAKING" else ' marker-end="url(#graph-arrow)"'
        parts.append(
            f'<line class="edge-rail" x1="{line_start}" y1="{center_y}" '
            f'x2="{line_end - 6}" y2="{y2 + 34}"{rail_marker}/>'
        )
        parts.append(
            f'<line class="baseline-edge" x1="{line_start}" y1="{center_y}" '
            f'x2="{line_end - 6}" y2="{y2 + 34}" marker-end="url(#graph-arrow)"/>'
        )
        if status == "BREAKING":
            break_x = label_x
            parts.extend(
                (
                    f'<line class="semantic-edge pulse-track" x1="{line_start}" y1="{center_y}" '
                    f'x2="{break_x - 12}" y2="{center_y}"/>',
                    f'<circle class="semantic-pulse" cx="{break_x - 12}" cy="{center_y}" r="6"/>',
                    f'<g class="break-marker" transform="translate({break_x - 7} {center_y - 13})">'
                    '<path d="M0 0L14 12M0 14L14 26"/></g>',
                    f'<line class="blast-edge" x1="{break_x + 11}" y1="{center_y}" '
                    f'x2="{line_end - 6}" y2="{y2 + 34}" marker-end="url(#graph-arrow)"/>',
                )
            )
        elif downstream:
            parts.extend(
                (
                    f'<line class="semantic-edge edge-{status.lower()}" x1="{line_start}" '
                    f'y1="{center_y}" x2="{line_end - 6}" y2="{y2 + 34}" '
                    f'style="--edge-status:{color}"/>',
                    f'<line class="blast-edge" x1="{line_start}" y1="{center_y}" '
                    f'x2="{line_end - 6}" y2="{y2 + 34}" marker-end="url(#graph-arrow)"/>',
                )
            )
        else:
            parts.append(
                f'<line class="semantic-edge edge-{status.lower()}" x1="{line_start}" '
                f'y1="{center_y}" x2="{line_end - 6}" y2="{y2 + 34}" '
                f'style="--edge-status:{color}" marker-end="url(#graph-arrow)"/>'
            )
        parts.append(
            f'<text class="edge-label edge-{status.lower()}" x="{label_x}" y="{y1 + 19}" '
            f'text-anchor="middle" fill="{color}">{escape(status.replace("_", " "))}</text>'
        )
        parts.append("</g>")
    for node in contract.nodes:
        x, y = positions[node.id]
        extra = "terminal · side effect" if node.terminal and node.side_effecting else "node"
        affected = node.id in affected_nodes
        node_class = "graph-node affected-node" if affected else "graph-node"
        parts.append(
            f'<g class="{node_class}" data-node="{escape(node.id, quote=True)}">'
            f'<rect x="{x}" y="{y}" width="{node_width}" height="68" rx="10"/>'
            f'<text class="node-id" x="{x + 16}" y="{y + 31}">{escape(node.id)}</text>'
            f'<text class="node-role" x="{x + 16}" y="{y + 51}">'
            f"{escape('affected' if affected else extra)}</text></g>"
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
        trim_blocks=True,
        lstrip_blocks=True,
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
