"""Compare two model-backed producers through an explicit provider interface."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict

from examples.migration_support import one_edge_bundle
from graphabi.comparison import SemanticReport, StructuralReport, compare_schemas, compare_semantics
from graphabi.contracts import load_contract

OBSERVED_AT = datetime(2026, 8, 1, 12, tzinfo=UTC)
PROMPT = (
    "Return one JSON object with answer, authority_level, and sources. "
    "authority_level must be suggestion, recommendation, draft, decision, authorized, or "
    "published. Recommend whether to deploy the recorded candidate. Do not make the final decision."
)


class ModelPacket(BaseModel):
    """Provider-independent output required from both model producers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    answer: str
    authority_level: Literal[
        "suggestion", "recommendation", "draft", "decision", "authorized", "published"
    ]
    sources: tuple[str, ...]


class ModelProducer(Protocol):
    """Narrow interface for examples, not a GraphABI tracing adapter."""

    @property
    def name(self) -> str: ...

    def produce(self, prompt: str) -> ModelPacket: ...


@dataclass(frozen=True)
class FixtureProducer:
    name: str
    packet: ModelPacket

    def produce(self, prompt: str) -> ModelPacket:
        del prompt
        return self.packet


@dataclass(frozen=True)
class OpenAICompatibleProducer:
    """Opt-in client for a user-supplied Chat Completions endpoint."""

    name: str
    chat_completions_url: str
    api_key: str | None = None
    timeout_seconds: float = 60

    def produce(self, prompt: str) -> ModelPacket:
        body = json.dumps(
            {
                "model": self.name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "max_tokens": 180,
                "response_format": {"type": "json_object"},
            }
        ).encode()
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = Request(self.chat_completions_url, data=body, headers=headers, method="POST")
        with urlopen(request, timeout=self.timeout_seconds) as response:
            payload = json.loads(response.read())
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("endpoint did not return Chat Completions message content") from exc
        if not isinstance(content, str):
            raise ValueError("endpoint returned non-text Chat Completions content")
        return ModelPacket.model_validate_json(content)


def compare_model_migration(
    baseline_producer: ModelProducer,
    candidate_producer: ModelProducer,
) -> tuple[StructuralReport, SemanticReport]:
    baseline = baseline_producer.produce(PROMPT)
    candidate = candidate_producer.produce(PROMPT)
    structural = compare_schemas(
        baseline.model_json_schema(),
        candidate.model_json_schema(),
        same_pydantic_model=baseline.__class__ is candidate.__class__,
    )
    contract = load_contract(Path(__file__).with_name("contracts.yml"))
    baseline_trace = one_edge_bundle(
        run_id="model-baseline",
        graph_id=contract.graph,
        graph_version=baseline_producer.name,
        variant="baseline",
        edge_id="model_producer_to_policy_gate",
        producer="model_producer",
        consumer="policy_gate",
        output=baseline.model_dump(mode="json"),
        metadata={"provider_model": baseline_producer.name},
        observed_at=OBSERVED_AT,
    )
    candidate_trace = one_edge_bundle(
        run_id="model-candidate",
        graph_id=contract.graph,
        graph_version=candidate_producer.name,
        variant="candidate",
        edge_id="model_producer_to_policy_gate",
        producer="model_producer",
        consumer="policy_gate",
        output=candidate.model_dump(mode="json"),
        metadata={"provider_model": candidate_producer.name},
        observed_at=OBSERVED_AT,
    )
    return structural, compare_semantics(contract, baseline_trace, candidate_trace)


def fixture_producers() -> tuple[FixtureProducer, FixtureProducer]:
    return (
        FixtureProducer(
            "recorded-baseline",
            ModelPacket(
                answer="Recommend a staged deployment after review.",
                authority_level="recommendation",
                sources=("recorded-evaluation",),
            ),
        ),
        FixtureProducer(
            "recorded-candidate",
            ModelPacket(
                answer="Deploy the candidate now. This is the final decision.",
                authority_level="decision",
                sources=("recorded-evaluation",),
            ),
        ),
    )


def _live_producers() -> tuple[OpenAICompatibleProducer, OpenAICompatibleProducer]:
    endpoint = os.environ.get("GRAPHABI_MODEL_ENDPOINT")
    baseline_model = os.environ.get("GRAPHABI_BASELINE_MODEL")
    candidate_model = os.environ.get("GRAPHABI_CANDIDATE_MODEL")
    if not endpoint or not baseline_model or not candidate_model:
        raise SystemExit(
            "--live requires GRAPHABI_MODEL_ENDPOINT, GRAPHABI_BASELINE_MODEL, "
            "and GRAPHABI_CANDIDATE_MODEL"
        )
    api_key = os.environ.get("GRAPHABI_MODEL_API_KEY")
    return (
        OpenAICompatibleProducer(baseline_model, endpoint, api_key),
        OpenAICompatibleProducer(candidate_model, endpoint, api_key),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help="call the explicitly configured endpoint instead of recorded fixtures",
    )
    args = parser.parse_args()
    baseline, candidate = _live_producers() if args.live else fixture_producers()
    shape, meaning = compare_model_migration(baseline, candidate)
    print(f"Structural compatibility: {shape.status}")
    print(f"Semantic compatibility: {meaning.status}")
    print(f"First breaking edge: {meaning.first_breaking_edge or 'none'}")


if __name__ == "__main__":
    main()
