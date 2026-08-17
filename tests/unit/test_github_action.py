import sys
from pathlib import Path

import pytest

from graphabi.ci.github import main, render_github_summary
from graphabi.demo import run_demo

ROOT = Path(__file__).resolve().parents[2]


def test_github_summary_is_trace_backed_and_bounded(tmp_path: Path) -> None:
    report = run_demo(tmp_path).report

    summary = render_github_summary(report)

    assert "Structural compatibility | PASS" in summary
    assert "Semantic compatibility | FAIL" in summary
    assert "researcher -&gt; verifier (researcher_to_verifier)" in summary
    assert "verified_requires_opened_supporting_source" in summary
    assert "verifier, decision_maker, publisher" in summary
    assert "100.0% (3/3 graph edges)" in summary
    assert "Coverage is not correctness." in summary


def test_github_summary_escapes_report_controlled_markdown(tmp_path: Path) -> None:
    report = run_demo(tmp_path).report
    first = report.semantic.findings[0].model_copy(
        update={"contract_id": "unsafe\n| forged | PASS | <script>"}
    )
    semantic = report.semantic.model_copy(
        update={"findings": (first, *report.semantic.findings[1:])}
    )

    summary = render_github_summary(report.model_copy(update={"semantic": semantic}))

    assert "<script>" not in summary
    assert "\\| forged \\| PASS \\| &lt;script&gt;" in summary


def test_github_summary_calls_out_unresolved_evidence(tmp_path: Path) -> None:
    report = run_demo(tmp_path).report
    uncertain = report.semantic.findings[0].model_copy(update={"status": "UNKNOWN"})
    semantic = report.semantic.model_copy(
        update={
            "status": "UNKNOWN",
            "first_breaking_edge": None,
            "findings": (uncertain, *report.semantic.findings[1:]),
        }
    )

    summary = render_github_summary(report.model_copy(update={"semantic": semantic}))

    assert "Semantic compatibility | UNKNOWN" in summary
    assert "Uncertain findings | 1" in summary
    assert "Semantic compatibility is unresolved" in summary


def test_github_summary_command_writes_markdown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = run_demo(tmp_path)
    output = tmp_path / "summary.md"
    monkeypatch.setattr(
        sys,
        "argv",
        ["graphabi-github-summary", str(result.report_json), "--output", str(output)],
    )

    main()

    assert output.read_text(encoding="utf-8").startswith("# GraphABI\n")


def test_action_metadata_uses_pinned_dependencies_and_no_comments() -> None:
    metadata = (ROOT / "action.yml").read_text(encoding="utf-8")

    assert "using: composite" in metadata
    assert "astral-sh/setup-uv@20cfd1bf945f4377ade1205e4dbc17946fc9a30d" in metadata
    assert "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02" in metadata
    assert "include-hidden-files: true" in metadata
    assert "pull-requests: write" not in metadata
    assert "gh pr comment" not in metadata
