"""Compare two real or recorded models against an explicit provenance contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field

from examples.migration_support import one_edge_bundle
from graphabi.comparison import SemanticReport, StructuralReport, compare_schemas, compare_semantics
from graphabi.contracts import load_contract
from graphabi.models import SourceAccess, TraceBundle

OBSERVED_AT = datetime(2026, 8, 1, 12, tzinfo=UTC)
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
BASELINE_MODEL = "gpt-5.6-terra"
CANDIDATE_MODEL = "gpt-5.6-luna"
MAX_OUTPUT_TOKENS = 300
SOURCE_ID = "helios-study"
SOURCE_URI = "fixture://model-migration/helios-study"
SOURCE_PATH = Path(__file__).parents[1] / "research_graph" / "fixtures" / "helios-study.txt"
FACT_PATTERN = re.compile(
    r"retains (?P<capacity>\d+(?:\.\d+)?)% capacity after (?P<cycles>[\d,]+) charge cycles",
    re.IGNORECASE,
)
PROMPT = """\
Answer only from the supplied source. Report the battery capacity retained after the recorded
charge-cycle count. Set verified=true only when the source explicitly supports both numeric values,
and include the source ID in sources when verified is true. Do not infer missing evidence.
"""
PRICING_URL = "https://developers.openai.com/api/docs/models/gpt-5.6-terra"
PRICING_SNAPSHOT = "2026-08-12"


class ModelPacket(BaseModel):
    """Provider-independent output schema required from both models."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    answer: str
    retained_capacity_percent: float = Field(ge=0, le=100)
    charge_cycles: int = Field(ge=0)
    verified: bool
    sources: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceSource:
    """A local source whose stable URI can be recorded without leaking a local path."""

    source_id: str
    uri: str
    path: Path


@dataclass(frozen=True)
class TokenUsage:
    """Token counts returned by one Responses API call."""

    input_tokens: int
    cached_input_tokens: int
    output_tokens: int

    def __post_init__(self) -> None:
        if min(self.input_tokens, self.cached_input_tokens, self.output_tokens) < 0:
            raise ValueError("token counts cannot be negative")
        if self.cached_input_tokens > self.input_tokens:
            raise ValueError("cached input tokens cannot exceed input tokens")


@dataclass(frozen=True)
class TokenPrice:
    """USD price per one million text tokens for a supported live model."""

    input_usd: Decimal
    cached_input_usd: Decimal
    output_usd: Decimal

    def cost(self, usage: TokenUsage) -> Decimal:
        multiplier = Decimal(2) if usage.input_tokens > 272_000 else Decimal(1)
        output_multiplier = Decimal("1.5") if usage.input_tokens > 272_000 else Decimal(1)
        uncached = usage.input_tokens - usage.cached_input_tokens
        return (
            Decimal(uncached) * self.input_usd * multiplier
            + Decimal(usage.cached_input_tokens) * self.cached_input_usd * multiplier
            + Decimal(usage.output_tokens) * self.output_usd * output_multiplier
        ) / Decimal(1_000_000)


MODEL_PRICES = {
    BASELINE_MODEL: TokenPrice(Decimal("2.00"), Decimal("0.20"), Decimal("12.00")),
    CANDIDATE_MODEL: TokenPrice(Decimal("0.20"), Decimal("0.02"), Decimal("1.20")),
}


@dataclass(frozen=True)
class ModelRun:
    """One model result and the evidence observed while producing it."""

    model: str
    mode: Literal["fixture", "live"]
    packet: ModelPacket
    source_access: tuple[SourceAccess, ...]
    usage: TokenUsage | None = None
    response_id: str | None = None


class ModelProducer(Protocol):
    """Narrow example interface, not a GraphABI framework adapter."""

    @property
    def name(self) -> str: ...

    def produce(self, prompt: str, source: EvidenceSource) -> ModelRun: ...


@dataclass(frozen=True)
class FixtureProducer:
    """Deterministic local producer that records whether it opened the bundled source."""

    name: str
    packet: ModelPacket
    open_source: bool

    def produce(self, prompt: str, source: EvidenceSource) -> ModelRun:
        del prompt
        if self.open_source:
            content = source.path.read_text(encoding="utf-8")
            access = _source_access(source, self.packet, content, OBSERVED_AT)
        else:
            access = SourceAccess(
                source_id=source.source_id,
                uri=source.uri,
                attempted_at=OBSERVED_AT,
                opened=False,
                error="recorded fixture omitted source access",
            )
        return ModelRun(
            model=self.name,
            mode="fixture",
            packet=self.packet,
            source_access=(access,),
        )


type ResponsesTransport = Callable[[Request, float], dict[str, object]]


@dataclass(frozen=True)
class OpenAIResponsesProducer:
    """Opt-in OpenAI Responses API producer for one documented request shape."""

    name: str
    api_key: str = field(repr=False)
    timeout_seconds: float = 60
    transport: ResponsesTransport = field(default=lambda request, timeout: _send(request, timeout))

    def produce(self, prompt: str, source: EvidenceSource) -> ModelRun:
        attempted_at = datetime.now(UTC)
        try:
            content = source.path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ValueError(f"could not open local evidence source {source.path}: {exc}") from exc

        request = Request(
            OPENAI_RESPONSES_URL,
            data=json.dumps(_request_body(self.name, prompt, source, content)).encode(),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "graphabi-model-migration-example",
            },
            method="POST",
        )
        payload = self.transport(request, self.timeout_seconds)
        packet = ModelPacket.model_validate_json(_response_text(payload))
        access = _source_access(source, packet, content, attempted_at)
        return ModelRun(
            model=self.name,
            mode="live",
            packet=packet,
            source_access=(access,),
            usage=_response_usage(payload),
            response_id=_optional_string(payload.get("id")),
        )


@dataclass(frozen=True)
class MigrationResult:
    """Comparison reports plus the exact runs that produced them."""

    structural: StructuralReport
    semantic: SemanticReport
    baseline: ModelRun
    candidate: ModelRun


def run_model_migration(
    baseline_producer: ModelProducer,
    candidate_producer: ModelProducer,
    *,
    source: EvidenceSource | None = None,
) -> MigrationResult:
    """Run both producers and compare their common shape and provenance evidence."""
    evidence = source or default_source()
    baseline = baseline_producer.produce(PROMPT, evidence)
    candidate = candidate_producer.produce(PROMPT, evidence)
    structural = compare_schemas(
        baseline.packet.model_json_schema(),
        candidate.packet.model_json_schema(),
        same_pydantic_model=baseline.packet.__class__ is candidate.packet.__class__,
    )
    contract = load_contract(Path(__file__).with_name("contracts.yml"))
    baseline_trace = _trace(contract.graph, "baseline", baseline)
    candidate_trace = _trace(contract.graph, "candidate", candidate)
    return MigrationResult(
        structural=structural,
        semantic=compare_semantics(contract, baseline_trace, candidate_trace),
        baseline=baseline,
        candidate=candidate,
    )


def compare_model_migration(
    baseline_producer: ModelProducer,
    candidate_producer: ModelProducer,
) -> tuple[StructuralReport, SemanticReport]:
    """Compatibility wrapper returning only the public comparison reports."""
    result = run_model_migration(baseline_producer, candidate_producer)
    return result.structural, result.semantic


def default_source() -> EvidenceSource:
    return EvidenceSource(SOURCE_ID, SOURCE_URI, SOURCE_PATH)


def fixture_producers() -> tuple[FixtureProducer, FixtureProducer]:
    packet = ModelPacket(
        answer="The Helios battery retained 92% capacity after 1,000 charge cycles.",
        retained_capacity_percent=92,
        charge_cycles=1_000,
        verified=True,
        sources=(SOURCE_ID,),
    )
    return (
        FixtureProducer("recorded-baseline", packet, open_source=True),
        FixtureProducer("recorded-candidate", packet, open_source=False),
    )


def live_producers(
    *, acknowledge_cost: bool
) -> tuple[OpenAIResponsesProducer, OpenAIResponsesProducer]:
    if not acknowledge_cost:
        raise SystemExit("--live also requires --acknowledge-cost after reviewing the cost warning")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("--live requires OPENAI_API_KEY; set it locally and rerun")
    return (
        OpenAIResponsesProducer(BASELINE_MODEL, api_key),
        OpenAIResponsesProducer(CANDIDATE_MODEL, api_key),
    )


def live_cost_warning() -> str:
    terra = MODEL_PRICES[BASELINE_MODEL]
    luna = MODEL_PRICES[CANDIDATE_MODEL]
    maximum_output_cost = (
        (terra.output_usd + luna.output_usd) * MAX_OUTPUT_TOKENS / Decimal(1_000_000)
    )
    return (
        f"LIVE MODE SENDS THE BUNDLED SYNTHETIC SOURCE TO OPENAI AND MAKES TWO PAID REQUESTS.\n"
        f"Pricing snapshot {PRICING_SNAPSHOT}: {BASELINE_MODEL} costs "
        f"${terra.input_usd}/1M input, ${terra.cached_input_usd}/1M cached input, and "
        f"${terra.output_usd}/1M output tokens; {CANDIDATE_MODEL} costs "
        f"${luna.input_usd}/1M input, ${luna.cached_input_usd}/1M cached input, and "
        f"${luna.output_usd}/1M output tokens. Each response is capped at "
        f"{MAX_OUTPUT_TOKENS} output tokens, so the combined maximum output-token charge is "
        f"${maximum_output_cost:.6f}, plus input-token charges. Requests above 272K input tokens "
        f"use the documented higher rates. Verify current pricing from the model pages, starting "
        f"at {PRICING_URL}."
    )


def _trace(
    graph_id: str,
    variant: Literal["baseline", "candidate"],
    run: ModelRun,
) -> TraceBundle:
    usage = None
    if run.usage is not None:
        usage = {
            "input_tokens": run.usage.input_tokens,
            "cached_input_tokens": run.usage.cached_input_tokens,
            "output_tokens": run.usage.output_tokens,
        }
    return one_edge_bundle(
        run_id=f"model-{variant}",
        graph_id=graph_id,
        graph_version=run.model,
        variant=variant,
        edge_id="model_producer_to_policy_gate",
        producer="model_producer",
        consumer="policy_gate",
        output=run.packet.model_dump(mode="json"),
        metadata={"mode": run.mode, "provider_model": run.model, "token_usage": usage},
        source_access=run.source_access,
        observed_at=OBSERVED_AT,
    )


def _request_body(
    model: str,
    prompt: str,
    source: EvidenceSource,
    content: str,
) -> dict[str, object]:
    return {
        "model": model,
        "store": False,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "input": [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": f"Source ID: {source.source_id}\n\n{content}",
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "model_packet",
                "strict": True,
                "schema": ModelPacket.model_json_schema(),
            }
        },
    }


def _send(request: Request, timeout: float) -> dict[str, object]:
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read())
    except HTTPError as exc:
        detail = exc.read(4096).decode(errors="replace")
        raise ValueError(f"OpenAI Responses API returned HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise ValueError(f"could not reach the OpenAI Responses API: {exc.reason}") from exc
    if not isinstance(payload, dict):
        raise ValueError("OpenAI Responses API returned a non-object JSON payload")
    return payload


def _response_text(payload: dict[str, object]) -> str:
    status = payload.get("status")
    if status != "completed":
        raise ValueError(f"OpenAI response was not completed (status={status!r})")
    output = payload.get("output")
    if not isinstance(output, list):
        raise ValueError("OpenAI response did not contain an output list")
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "refusal":
                raise ValueError(f"OpenAI model refused the request: {part.get('refusal')!r}")
            text = part.get("text")
            if part.get("type") == "output_text" and isinstance(text, str):
                return text
    raise ValueError("OpenAI response did not contain message output_text")


def _response_usage(payload: dict[str, object]) -> TokenUsage:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        raise ValueError("OpenAI response did not contain token usage")
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    details = usage.get("input_tokens_details", {})
    cached_tokens = details.get("cached_tokens", 0) if isinstance(details, dict) else 0
    if not all(
        isinstance(value, int) and not isinstance(value, bool)
        for value in (input_tokens, output_tokens, cached_tokens)
    ):
        raise ValueError("OpenAI response token usage was not integer-valued")
    return TokenUsage(input_tokens, cached_tokens, output_tokens)


def _source_access(
    source: EvidenceSource,
    packet: ModelPacket,
    content: str,
    attempted_at: datetime,
) -> SourceAccess:
    fact = FACT_PATTERN.search(content)
    supports_claim = False
    if fact is not None:
        capacity = float(fact.group("capacity"))
        cycles = int(fact.group("cycles").replace(",", ""))
        supports_claim = (
            packet.retained_capacity_percent == capacity
            and packet.charge_cycles == cycles
            and source.source_id in packet.sources
        )
    return SourceAccess(
        source_id=source.source_id,
        uri=source.uri,
        attempted_at=attempted_at,
        opened=True,
        supports_claim=supports_claim,
        content_sha256=hashlib.sha256(content.encode()).hexdigest(),
    )


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _print_cost(label: str, run: ModelRun) -> Decimal:
    if run.usage is None:
        return Decimal(0)
    price = MODEL_PRICES[run.model]
    cost = price.cost(run.usage)
    print(
        f"{label} usage: {run.usage.input_tokens} input "
        f"({run.usage.cached_input_tokens} cached), {run.usage.output_tokens} output tokens; "
        f"estimated text-token cost ${cost:.8f}"
    )
    return cost


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help="make two paid OpenAI Responses API calls instead of using the local fixture",
    )
    parser.add_argument(
        "--acknowledge-cost",
        action="store_true",
        help="confirm the live-mode pricing warning; has no effect without --live",
    )
    args = parser.parse_args()
    if args.live:
        print(live_cost_warning())
        baseline, candidate = live_producers(acknowledge_cost=args.acknowledge_cost)
    else:
        baseline, candidate = fixture_producers()
    result = run_model_migration(baseline, candidate)
    print(f"Execution mode: {result.baseline.mode.upper()}")
    print(f"Structural compatibility: {result.structural.status}")
    print(f"Semantic compatibility: {result.semantic.status}")
    print(f"First breaking edge: {result.semantic.first_breaking_edge or 'none'}")
    if args.live:
        total = _print_cost("Baseline", result.baseline)
        total += _print_cost("Candidate", result.candidate)
        print(f"Estimated combined text-token cost: ${total:.8f}")
        print("A PASS applies only to these recorded runs and this explicit provenance contract.")


if __name__ == "__main__":
    main()
