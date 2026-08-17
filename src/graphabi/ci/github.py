"""Render a bounded GitHub job summary from a recorded compatibility report."""

from __future__ import annotations

import argparse
import html
from pathlib import Path

from graphabi.comparison.models import Finding
from graphabi.reporting import CompatibilityReport


def _inline(value: object) -> str:
    """Keep report-controlled values inside one Markdown table cell."""
    escaped = html.escape(str(value), quote=False).replace("\n", " ")
    for character in ("\\", "`", "*", "[", "]", "|"):
        escaped = escaped.replace(character, f"\\{character}")
    return escaped


def _first_breaking_finding(report: CompatibilityReport) -> Finding | None:
    edge = report.semantic.first_breaking_edge
    return next(
        (
            finding
            for finding in report.semantic.findings
            if finding.status == "BREAKING" and finding.edge == edge
        ),
        None,
    )


def render_github_summary(report: CompatibilityReport) -> str:
    """Return a deterministic Markdown summary without making a safety claim."""
    coverage = report.semantic.coverage.summary
    first = _first_breaking_finding(report)
    uncertain = sum(
        finding.status in {"UNKNOWN", "INSUFFICIENT_EVIDENCE"}
        for finding in report.semantic.findings
    )
    lines = [
        "# GraphABI",
        "",
        "| Check | Result |",
        "|---|---|",
        f"| Structural compatibility | {_inline(report.structural.status)} |",
        f"| Semantic compatibility | {_inline(report.semantic.status)} |",
        (
            "| Observed contract coverage | "
            f"{coverage.observed_contract_coverage_percent:.1f}% "
            f"({coverage.contracted_and_observed}/{coverage.total_graph_edges} graph edges) |"
        ),
        f"| Uncertain findings | {uncertain} |",
        "",
    ]
    if first is not None:
        edge = f"{first.producer} -> {first.consumer} ({first.edge})"
        downstream = ", ".join(first.affected_downstream_nodes) or "none"
        lines.extend(
            [
                f"**Breaking edge:** {_inline(edge)}",
                "",
                f"**Contract:** {_inline(first.contract_id)}",
                "",
                f"**Affected downstream nodes:** {_inline(downstream)}",
                "",
            ]
        )
    elif report.structural.status == "FAIL":
        lines.extend(
            [
                "The structural comparison failed. No semantic breaking edge is implied.",
                "",
            ]
        )
    elif report.semantic.status in {"UNKNOWN", "INSUFFICIENT_EVIDENCE"}:
        lines.extend(
            [
                "Semantic compatibility is unresolved because the recorded evidence is "
                "insufficient or ambiguous.",
                "",
            ]
        )
    lines.extend(
        [
            "Coverage is not correctness. It measures declared graph edges that were both "
            "contracted and observed in the candidate run.",
            "",
            "The uploaded HTML and JSON reports contain the trace-backed findings and explicit "
            "limitations.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render a GraphABI report as a GitHub job summary."
    )
    parser.add_argument("report", type=Path, help="Path to report.json")
    parser.add_argument("--output", required=True, type=Path, help="Markdown output path")
    args = parser.parse_args()
    try:
        report = CompatibilityReport.model_validate_json(args.report.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        parser.error(f"cannot load GraphABI report {args.report}: {exc}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_github_summary(report), encoding="utf-8")


if __name__ == "__main__":
    main()
