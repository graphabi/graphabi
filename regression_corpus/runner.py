"""Execute checked-in corpus traces through the real semantic comparison engine."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from graphabi.comparison import compare_semantics
from graphabi.contracts import load_contract
from graphabi.traces import load_bundle


def _finding_summary(finding: Any) -> dict[str, str]:
    return {
        "invariant": finding.contract_id.rsplit(":", 1)[-1],
        "status": finding.status,
        "occurrence_pairing": finding.occurrence_pairing,
    }


def run_corpus(root: Path) -> list[dict[str, object]]:
    """Return actual trace-derived outcomes and whether each matches its fixture assertion."""
    manifest_path = root / "manifest.yml"
    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_version") != "0.1":
        raise ValueError(f"{manifest_path}: expected regression corpus schema_version '0.1'")
    entries = raw.get("cases")
    if not isinstance(entries, list):
        raise ValueError(f"{manifest_path}: 'cases' must be a list")

    results: list[dict[str, object]] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"{manifest_path}: cases[{index}] must be an object")
        case_id = str(entry.get("id", ""))
        expected = entry.get("expected")
        if not isinstance(expected, dict):
            raise ValueError(f"{manifest_path}: case {case_id!r} is missing expected results")
        contract = load_contract(root / str(entry["contract"]))
        baseline = load_bundle(root / str(entry["baseline"]))
        candidate = load_bundle(root / str(entry["candidate"]))
        baseline_report = compare_semantics(contract, baseline, baseline)
        report = compare_semantics(contract, baseline, candidate)
        actual_findings = [_finding_summary(finding) for finding in report.findings]
        expected_findings = expected.get("findings")
        baseline_passes = baseline_report.status == "PASS"
        matches = (
            baseline_passes
            and report.status == expected.get("status")
            and report.first_breaking_edge == expected.get("first_breaking_edge")
            and actual_findings == expected_findings
        )
        results.append(
            {
                "id": case_id,
                "category": entry.get("category"),
                "rationale": entry.get("rationale"),
                "baseline_status": baseline_report.status,
                "actual_status": report.status,
                "expected_status": expected.get("status"),
                "first_breaking_edge": report.first_breaking_edge,
                "findings": actual_findings,
                "contract_coverage_percent": (
                    report.coverage.summary.observed_contract_coverage_percent
                ),
                "matches_expected": matches,
            }
        )
    return results
