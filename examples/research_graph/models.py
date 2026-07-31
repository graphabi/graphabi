"""Shared schemas for both versions of the research graph."""

from __future__ import annotations

from typing import Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field


class DemoModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ResearchResult(DemoModel):
    """The exact producer schema shared by baseline and candidate researchers."""

    claim: str
    confidence: float = Field(ge=0, le=1)
    verified: bool
    sources: list[str]
    entities: list[str]
    evidence_ids: list[str]
    authority_level: Literal["suggestion", "recommendation", "decision", "authorized"]
    provenance: dict[str, str]


class VerifierResult(DemoModel):
    accepted: bool
    checked_entities: list[str]
    reason: str
    authority_level: Literal["recommendation"] = "recommendation"


class DecisionResult(DemoModel):
    action: Literal["publish", "hold"]
    rationale: str
    authority_level: Literal["decision"] = "decision"


class PublicationResult(DemoModel):
    status: Literal["published", "withheld"]
    message: str
    authority_level: Literal["published", "draft"]


class ResearchState(TypedDict, total=False):
    topic: str
    required_entities: list[str]
    research_result: dict[str, object]
    verifier_result: dict[str, object]
    decision_result: dict[str, object]
    publication_result: dict[str, object]
    trace_metadata: dict[str, object]
    trace_tool_calls: list[dict[str, object]]
    trace_source_access: list[dict[str, object]]
