"""Compare two retrievers with one output schema and different evidence semantics."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal, Protocol

from pydantic import AwareDatetime, BaseModel, ConfigDict

from examples.migration_support import one_edge_bundle
from graphabi.comparison import SemanticReport, StructuralReport, compare_schemas, compare_semantics
from graphabi.contracts import load_contract
from graphabi.models import SourceAccess, TraceBundle

OBSERVED_AT = datetime(2026, 8, 1, 12, tzinfo=UTC)
SOURCE_URI = "fixture://tool-migration/acme-quote"
SOURCE_PATH = Path(__file__).with_name("fixtures") / "acme-quote.json"


class QuotePacket(BaseModel):
    """The exact producer schema shared by both retrievers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str
    value: float
    unit: str
    verified: bool
    sources: tuple[str, ...]
    evidence_ids: tuple[str, ...]


class QuoteEvidence(BaseModel):
    """Strict shape of the bundled synthetic market record."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_id: str
    symbol: str
    value: float
    unit: str
    observed_at: AwareDatetime


@dataclass(frozen=True)
class RetrievalRun:
    """One retriever result and its observed evidence behavior."""

    retriever: str
    packet: QuotePacket
    retrieved_at: datetime
    source_access: tuple[SourceAccess, ...]


class QuoteRetriever(Protocol):
    """Narrow interface used by the retriever migration example."""

    @property
    def name(self) -> str: ...

    def retrieve(self) -> RetrievalRun: ...


@dataclass(frozen=True)
class LocalMarketFeedRetriever:
    """Retriever A opens and validates the bundled quote evidence."""

    name: str = "local-market-feed-v1"
    source_path: Path = SOURCE_PATH

    def retrieve(self) -> RetrievalRun:
        content = self.source_path.read_text(encoding="utf-8")
        evidence = QuoteEvidence.model_validate_json(content)
        packet = QuotePacket(
            symbol=evidence.symbol,
            value=evidence.value,
            unit=evidence.unit,
            verified=True,
            sources=(evidence.evidence_id,),
            evidence_ids=(evidence.evidence_id,),
        )
        access = SourceAccess(
            source_id=evidence.evidence_id,
            uri=SOURCE_URI,
            attempted_at=OBSERVED_AT,
            opened=True,
            supports_claim=(
                packet.symbol == evidence.symbol
                and packet.value == evidence.value
                and packet.unit == evidence.unit
                and evidence.evidence_id in packet.sources
            ),
            content_sha256=hashlib.sha256(content.encode()).hexdigest(),
        )
        return RetrievalRun(self.name, packet, evidence.observed_at, (access,))


@dataclass(frozen=True)
class CachedQuoteRetriever:
    """Retriever B returns a stale, differently scaled cache record without source access."""

    name: str = "cached-quote-v2"

    def retrieve(self) -> RetrievalRun:
        packet = QuotePacket(
            symbol="ACME",
            value=10_125,
            unit="cents",
            verified=True,
            sources=("cached-market-feed",),
            evidence_ids=(),
        )
        access = SourceAccess(
            source_id="cached-market-feed",
            uri="cache://tool-migration/acme-quote",
            attempted_at=OBSERVED_AT,
            opened=False,
            error="recorded cache result had no source open",
        )
        return RetrievalRun(
            self.name,
            packet,
            OBSERVED_AT - timedelta(days=3),
            (access,),
        )


@dataclass(frozen=True)
class ToolMigrationResult:
    """Reports and exact retrieval runs used by the comparison."""

    structural: StructuralReport
    semantic: SemanticReport
    baseline: RetrievalRun
    candidate: RetrievalRun


def run_tool_migration(
    baseline_retriever: QuoteRetriever | None = None,
    candidate_retriever: QuoteRetriever | None = None,
) -> ToolMigrationResult:
    """Run both retrievers and evaluate consumer assumptions beyond their common schema."""
    baseline = (baseline_retriever or LocalMarketFeedRetriever()).retrieve()
    candidate = (candidate_retriever or CachedQuoteRetriever()).retrieve()
    structural = compare_schemas(
        baseline.packet.model_json_schema(),
        candidate.packet.model_json_schema(),
        same_pydantic_model=baseline.packet.__class__ is candidate.packet.__class__,
    )
    contract = load_contract(Path(__file__).with_name("contracts.yml"))
    baseline_trace = _trace(contract.graph, "baseline", baseline)
    candidate_trace = _trace(contract.graph, "candidate", candidate)
    return ToolMigrationResult(
        structural=structural,
        semantic=compare_semantics(contract, baseline_trace, candidate_trace),
        baseline=baseline,
        candidate=candidate,
    )


def compare_tool_migration() -> tuple[StructuralReport, SemanticReport]:
    """Compatibility wrapper returning only the two reports."""
    result = run_tool_migration()
    return result.structural, result.semantic


def _trace(
    graph_id: str,
    variant: Literal["baseline", "candidate"],
    run: RetrievalRun,
) -> TraceBundle:
    return one_edge_bundle(
        run_id=f"tool-{variant}",
        graph_id=graph_id,
        graph_version=run.retriever,
        variant=variant,
        edge_id="quote_retriever_to_risk_model",
        producer="quote_retriever",
        consumer="risk_model",
        output=run.packet.model_dump(mode="json"),
        metadata={
            "retriever": run.retriever,
            "retrieved_at": run.retrieved_at.isoformat(),
        },
        source_access=run.source_access,
        observed_at=OBSERVED_AT,
    )


if __name__ == "__main__":
    result = run_tool_migration()
    print(f"Baseline retriever: {result.baseline.retriever}")
    print(f"Candidate retriever: {result.candidate.retriever}")
    print(f"Structural compatibility: {result.structural.status}")
    print(f"Semantic compatibility: {result.semantic.status}")
    print(f"Breaking contracts: {len(result.semantic.breaking_findings)}")
    print(f"First breaking edge: {result.semantic.first_breaking_edge or 'none'}")
