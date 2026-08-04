"""A retriever replacement keeps the output shape and weakens freshness."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from examples.migration_support import one_edge_bundle
from graphabi.comparison import SemanticReport, StructuralReport, compare_schemas, compare_semantics
from graphabi.contracts import load_contract

OBSERVED_AT = datetime(2026, 8, 1, 12, tzinfo=UTC)


class QuotePacket(BaseModel):
    """The stable producer schema used by both retrievers."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    value: float
    currency: str
    source: str


def compare_tool_migration() -> tuple[StructuralReport, SemanticReport]:
    baseline = QuotePacket(symbol="ACME", value=101.25, currency="USD", source="market-feed")
    candidate = QuotePacket(symbol="ACME", value=101.25, currency="USD", source="cache")
    structural = compare_schemas(
        baseline.model_json_schema(),
        candidate.model_json_schema(),
        same_pydantic_model=baseline.__class__ is candidate.__class__,
    )
    contract = load_contract(Path(__file__).with_name("contracts.yml"))
    baseline_trace = one_edge_bundle(
        run_id="tool-baseline",
        graph_id=contract.graph,
        graph_version="live-retriever",
        variant="baseline",
        edge_id="quote_retriever_to_risk_model",
        producer="quote_retriever",
        consumer="risk_model",
        output=baseline.model_dump(mode="json"),
        metadata={"retrieved_at": (OBSERVED_AT - timedelta(minutes=5)).isoformat()},
        observed_at=OBSERVED_AT,
    )
    candidate_trace = one_edge_bundle(
        run_id="tool-candidate",
        graph_id=contract.graph,
        graph_version="cached-retriever",
        variant="candidate",
        edge_id="quote_retriever_to_risk_model",
        producer="quote_retriever",
        consumer="risk_model",
        output=candidate.model_dump(mode="json"),
        metadata={"retrieved_at": (OBSERVED_AT - timedelta(days=3)).isoformat()},
        observed_at=OBSERVED_AT,
    )
    return structural, compare_semantics(contract, baseline_trace, candidate_trace)


if __name__ == "__main__":
    shape, meaning = compare_tool_migration()
    print(f"Structural compatibility: {shape.status}")
    print(f"Semantic compatibility: {meaning.status}")
    print(f"First breaking edge: {meaning.first_breaking_edge}")
