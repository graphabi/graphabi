"""Correct baseline researcher: semantic behavior matches its consumer contract."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from examples.research_graph.models import ResearchResult, ResearchState

CLAIM = "The Helios battery retains 92% capacity after 1,000 charge cycles."
SOURCE_ID = "helios-study"


def make_researcher(source_path: Path):
    """Create a researcher that opens and checks a real local evidence document."""

    def researcher(state: ResearchState) -> dict[str, object]:
        started_at = datetime.now(UTC)
        content = source_path.read_text(encoding="utf-8")
        ended_at = datetime.now(UTC)
        supported = CLAIM in content
        opened = True
        result = ResearchResult(
            claim=CLAIM,
            confidence=0.92 if supported else 0.15,
            verified=opened and supported,
            sources=[SOURCE_ID],
            entities=["Helios battery", "1,000 charge cycles"],
            evidence_ids=["helios-capacity-result"],
            authority_level="recommendation",
            provenance={"source_id": SOURCE_ID, "method": "opened-and-matched"},
        )
        return {
            "research_result": result.model_dump(mode="json"),
            "trace_metadata": {
                "opened_sources_count": 1,
                "claim_supported": supported,
                "required_entities": state["required_entities"],
                "confidence_basis": "evidential_support",
                "evidence_unit": "fraction",
                "evidence_observed_at": ended_at.isoformat(),
            },
            "trace_tool_calls": [
                {
                    "tool_name": "local_file.open",
                    "call_id": "baseline-open-001",
                    "input": {"path": str(source_path)},
                    "output": {"bytes_read": len(content.encode())},
                    "started_at": started_at,
                    "ended_at": ended_at,
                    "status": "success",
                }
            ],
            "trace_source_access": [
                {
                    "source_id": SOURCE_ID,
                    "uri": source_path.as_uri(),
                    "attempted_at": started_at,
                    "opened": True,
                    "supports_claim": supported,
                    "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
                }
            ],
        }

    return researcher
