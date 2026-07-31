"""INTENTIONALLY BROKEN demo fixture; never use this researcher in production."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from examples.research_graph.baseline import CLAIM, SOURCE_ID
from examples.research_graph.models import ResearchResult, ResearchState


def make_researcher(source_path: Path):
    """Create a schema-valid researcher with deliberate, realistic semantic regressions."""

    def researcher(state: ResearchState) -> dict[str, object]:
        started_at = datetime.now(UTC)
        error: str | None = None
        try:
            source_path.read_text(encoding="utf-8")
        except OSError as exc:
            error = f"{type(exc).__name__}: source could not be opened"
        ended_at = datetime.now(UTC)

        # Intentionally broken fixture behavior: plausibility is mislabeled as verification,
        # writing confidence is placed in an evidence field, an unopened source is cited,
        # and a consumer-required entity is omitted. The Pydantic shape remains identical.
        result = ResearchResult(
            claim=CLAIM,
            confidence=0.97,
            verified=True,
            sources=[SOURCE_ID],
            entities=["Helios battery"],
            evidence_ids=["helios-capacity-result"],
            authority_level="recommendation",
            provenance={"source_id": SOURCE_ID, "method": "plausibility-only"},
        )
        return {
            "research_result": result.model_dump(mode="json"),
            "trace_metadata": {
                "opened_sources_count": 0,
                "claim_supported": False,
                "required_entities": state["required_entities"],
                "confidence_basis": "writing_quality",
                "evidence_unit": "fraction",
                "evidence_observed_at": ended_at.isoformat(),
            },
            "trace_tool_calls": [
                {
                    "tool_name": "local_file.open",
                    "call_id": "candidate-open-003",
                    "input": {"path": str(source_path)},
                    "output": None,
                    "started_at": started_at,
                    "ended_at": ended_at,
                    "status": "error",
                    "error": error,
                }
            ],
            "trace_source_access": [
                {
                    "source_id": SOURCE_ID,
                    "uri": source_path.as_uri(),
                    "attempted_at": started_at,
                    "opened": False,
                    "supports_claim": None,
                    "error": error,
                }
            ],
        }

    return researcher
