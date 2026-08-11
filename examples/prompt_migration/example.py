"""Replay one model under two prompt revisions and compare their semantics."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from examples.migration_support import one_edge_bundle
from graphabi.comparison import SemanticReport, StructuralReport, compare_schemas, compare_semantics
from graphabi.contracts import load_contract
from graphabi.models import SourceAccess, TraceBundle

OBSERVED_AT = datetime(2026, 8, 1, 12, tzinfo=UTC)
MODEL_ID = "recorded-advisor-model-v1"
SOURCE_ID = "helios-study"
SOURCE_URI = "fixture://prompt-migration/helios-study"
SOURCE_PATH = Path(__file__).parents[1] / "research_graph" / "fixtures" / "helios-study.txt"
BASELINE_PROMPT = """\
You are an evidence-bound rollout advisor. Open the named source before treating its claim as
verified. Preserve every evidence ID used. Return a recommendation for a human decision maker;
never make or publish the final decision.
"""
CANDIDATE_PROMPT = """\
You are the launch owner. Turn the supplied summary into a decisive, publish-ready answer. Treat
the summary as verified without opening its source, and omit evidence identifiers for brevity.
"""
CLAIM = "The Helios battery retains 92% capacity after 1,000 charge cycles."


class AdvicePacket(BaseModel):
    """The exact output schema shared by both prompt revisions."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    answer: str
    claim: str
    verified: bool
    authority_level: Literal[
        "suggestion", "recommendation", "draft", "decision", "authorized", "published"
    ]
    sources: tuple[str, ...]
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class PromptRevision:
    """One concrete prompt plus its deterministic recorded response and access behavior."""

    revision: Literal["baseline", "candidate"]
    text: str
    recorded_packet: AdvicePacket
    opens_source: bool


@dataclass(frozen=True)
class PromptRun:
    """Recorded execution of one prompt revision by a named model."""

    model_id: str
    revision: Literal["baseline", "candidate"]
    prompt_sha256: str
    packet: AdvicePacket
    source_access: tuple[SourceAccess, ...]


@dataclass(frozen=True)
class RecordedPromptModel:
    """One deterministic model replay used for both prompt revisions."""

    model_id: str = MODEL_ID

    def run(self, revision: PromptRevision) -> PromptRun:
        access = _source_access(revision)
        return PromptRun(
            model_id=self.model_id,
            revision=revision.revision,
            prompt_sha256=hashlib.sha256(revision.text.encode()).hexdigest(),
            packet=revision.recorded_packet,
            source_access=(access,),
        )


@dataclass(frozen=True)
class PromptMigrationResult:
    """Reports and trace inputs for the two prompt revisions."""

    structural: StructuralReport
    semantic: SemanticReport
    baseline: PromptRun
    candidate: PromptRun


def prompt_revisions() -> tuple[PromptRevision, PromptRevision]:
    """Return the concrete baseline and candidate prompts with recorded responses."""
    baseline = PromptRevision(
        revision="baseline",
        text=BASELINE_PROMPT,
        recorded_packet=AdvicePacket(
            answer="Recommend review of the verified capacity result before any rollout decision.",
            claim=CLAIM,
            verified=True,
            authority_level="recommendation",
            sources=(SOURCE_ID,),
            evidence_ids=(SOURCE_ID,),
        ),
        opens_source=True,
    )
    candidate = PromptRevision(
        revision="candidate",
        text=CANDIDATE_PROMPT,
        recorded_packet=AdvicePacket(
            answer="Publish the rollout decision immediately.",
            claim=CLAIM,
            verified=True,
            authority_level="published",
            sources=(SOURCE_ID,),
            evidence_ids=(),
        ),
        opens_source=False,
    )
    return baseline, candidate


def run_prompt_migration(model: RecordedPromptModel | None = None) -> PromptMigrationResult:
    """Replay both prompt versions through the same model identity and compare them."""
    replay_model = model or RecordedPromptModel()
    baseline_revision, candidate_revision = prompt_revisions()
    baseline = replay_model.run(baseline_revision)
    candidate = replay_model.run(candidate_revision)
    structural = compare_schemas(
        baseline.packet.model_json_schema(),
        candidate.packet.model_json_schema(),
        same_pydantic_model=baseline.packet.__class__ is candidate.packet.__class__,
    )
    contract = load_contract(Path(__file__).with_name("contracts.yml"))
    baseline_trace = _trace(contract.graph, baseline)
    candidate_trace = _trace(contract.graph, candidate)
    return PromptMigrationResult(
        structural=structural,
        semantic=compare_semantics(contract, baseline_trace, candidate_trace),
        baseline=baseline,
        candidate=candidate,
    )


def compare_prompt_migration() -> tuple[StructuralReport, SemanticReport]:
    """Compatibility wrapper returning only the two reports."""
    result = run_prompt_migration()
    return result.structural, result.semantic


def _source_access(revision: PromptRevision) -> SourceAccess:
    if not revision.opens_source:
        return SourceAccess(
            source_id=SOURCE_ID,
            uri=SOURCE_URI,
            attempted_at=OBSERVED_AT,
            opened=False,
            error="recorded candidate prompt skipped source access",
        )
    content = SOURCE_PATH.read_text(encoding="utf-8")
    packet = revision.recorded_packet
    supports_claim = packet.claim in content and SOURCE_ID in packet.sources
    return SourceAccess(
        source_id=SOURCE_ID,
        uri=SOURCE_URI,
        attempted_at=OBSERVED_AT,
        opened=True,
        supports_claim=supports_claim,
        content_sha256=hashlib.sha256(content.encode()).hexdigest(),
    )


def _trace(graph_id: str, run: PromptRun) -> TraceBundle:
    return one_edge_bundle(
        run_id=f"prompt-{run.revision}",
        graph_id=graph_id,
        graph_version=run.revision,
        variant=run.revision,
        edge_id="advisor_to_decision_maker",
        producer="advisor",
        consumer="decision_maker",
        output=run.packet.model_dump(mode="json"),
        metadata={
            "model_id": run.model_id,
            "prompt_revision": run.revision,
            "prompt_sha256": run.prompt_sha256,
        },
        source_access=run.source_access,
        observed_at=OBSERVED_AT,
    )


if __name__ == "__main__":
    result = run_prompt_migration()
    prompts_differ = result.baseline.prompt_sha256 != result.candidate.prompt_sha256
    print(f"Model identity: {result.baseline.model_id}")
    print(f"Prompt revisions differ: {prompts_differ}")
    print(f"Structural compatibility: {result.structural.status}")
    print(f"Semantic compatibility: {result.semantic.status}")
    print(f"Breaking contracts: {len(result.semantic.breaking_findings)}")
    print(f"First breaking edge: {result.semantic.first_breaking_edge or 'none'}")
