"""A prompt revision keeps the output shape and changes its authority semantics."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from examples.migration_support import one_edge_bundle
from graphabi.comparison import SemanticReport, StructuralReport, compare_schemas, compare_semantics
from graphabi.contracts import load_contract

OBSERVED_AT = datetime(2026, 8, 1, 12, tzinfo=UTC)


class AdvicePacket(BaseModel):
    """The stable producer schema used by both prompt versions."""

    model_config = ConfigDict(frozen=True)

    answer: str
    authority_level: Literal[
        "suggestion", "recommendation", "draft", "decision", "authorized", "published"
    ]
    sources: tuple[str, ...]


def baseline_producer() -> AdvicePacket:
    return AdvicePacket(
        answer="Recommend a staged rollout after the verifier approves the evidence.",
        authority_level="recommendation",
        sources=("migration-plan",),
    )


def candidate_producer() -> AdvicePacket:
    return AdvicePacket(
        answer="Publish the rollout decision immediately.",
        authority_level="published",
        sources=("migration-plan",),
    )


def compare_prompt_migration() -> tuple[StructuralReport, SemanticReport]:
    baseline = baseline_producer()
    candidate = candidate_producer()
    structural = compare_schemas(
        baseline.model_json_schema(),
        candidate.model_json_schema(),
        same_pydantic_model=baseline.__class__ is candidate.__class__,
    )
    contract = load_contract(Path(__file__).with_name("contracts.yml"))
    baseline_trace = one_edge_bundle(
        run_id="prompt-baseline",
        graph_id=contract.graph,
        graph_version="baseline-prompt",
        variant="baseline",
        edge_id="advisor_to_decision_maker",
        producer="advisor",
        consumer="decision_maker",
        output=baseline.model_dump(mode="json"),
        metadata={"prompt_revision": "baseline"},
        observed_at=OBSERVED_AT,
    )
    candidate_trace = one_edge_bundle(
        run_id="prompt-candidate",
        graph_id=contract.graph,
        graph_version="candidate-prompt",
        variant="candidate",
        edge_id="advisor_to_decision_maker",
        producer="advisor",
        consumer="decision_maker",
        output=candidate.model_dump(mode="json"),
        metadata={"prompt_revision": "candidate"},
        observed_at=OBSERVED_AT,
    )
    return structural, compare_semantics(contract, baseline_trace, candidate_trace)


if __name__ == "__main__":
    shape, meaning = compare_prompt_migration()
    print(f"Structural compatibility: {shape.status}")
    print(f"Semantic compatibility: {meaning.status}")
    print(f"First breaking edge: {meaning.first_breaking_edge}")
