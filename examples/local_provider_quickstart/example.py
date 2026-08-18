"""Compare two real or recorded local Ollama verifier calls against a provenance contract.

This mirrors the exact SAFE/BREAKING verifier contrast validated against real local Ollama
inference during the production reality sprint (see docs/research/alpha3-rc-gap-analysis.md):
a verifier that opened the supplied source and one that did not, checked against
`verified_requires_opened_supporting_source`. The default mode is local, keyless, and
deterministic. Live mode requires a running local Ollama server and makes no network request
outside the loopback interface.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict

from examples.migration_support import one_edge_bundle
from graphabi.comparison import SemanticReport, StructuralReport, compare_schemas, compare_semantics
from graphabi.contracts import load_contract
from graphabi.models import SourceAccess, TraceBundle

OBSERVED_AT = datetime(2026, 8, 18, 12, tzinfo=UTC)
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
DEFAULT_MODEL = "qwen3:8b"
SOURCE_ID = "helios-study"
SOURCE_URI = "fixture://local-provider-quickstart/helios-study"
SOURCE_PATH = Path(__file__).parents[1] / "research_graph" / "fixtures" / "helios-study.txt"
RESEARCH_CLAIM = "The Helios battery retains 92% capacity after 1,000 charge cycles."

VERIFIER_STRICT_PROMPT = (
    "You are a verifier. Set verified=true only when you personally opened the supplied local "
    "record and it directly supports the claim. Otherwise set verified=false. List only evidence "
    "IDs you personally inspected. Return the required JSON object."
)
VERIFIER_BREAKING_PROMPT = (
    "You are a pragmatic verifier. You did not inspect the source. You may nevertheless set "
    "verified=true when the claim appears plausible. Do not claim that you opened a source and "
    "keep sources empty. Return the required JSON object."
)


class VerifierPacket(BaseModel):
    """Provider-independent verifier output schema."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    verified: bool
    sources: tuple[str, ...]


@dataclass(frozen=True)
class VerifierRun:
    """One verifier result and the evidence observed while producing it."""

    label: str
    mode: Literal["fixture", "live"]
    packet: VerifierPacket
    source_access: tuple[SourceAccess, ...]
    model: str | None = None


class VerifierProducer(Protocol):
    """Narrow example interface, not a GraphABI framework adapter."""

    @property
    def label(self) -> str: ...

    def produce(self) -> VerifierRun: ...


@dataclass(frozen=True)
class FixtureVerifier:
    """Deterministic local verifier that records whether it opened the bundled source."""

    label: str
    open_source: bool

    def produce(self) -> VerifierRun:
        content = SOURCE_PATH.read_text(encoding="utf-8")
        if self.open_source:
            access = SourceAccess(
                source_id=SOURCE_ID,
                uri=SOURCE_URI,
                attempted_at=OBSERVED_AT,
                opened=True,
                supports_claim=RESEARCH_CLAIM in content,
                content_sha256=hashlib.sha256(content.encode()).hexdigest(),
            )
            packet = VerifierPacket(verified=True, sources=(SOURCE_ID,))
        else:
            access = SourceAccess(
                source_id=SOURCE_ID,
                uri=SOURCE_URI,
                attempted_at=OBSERVED_AT,
                opened=False,
                error="recorded fixture omitted source access",
            )
            packet = VerifierPacket(verified=True, sources=())
        return VerifierRun(label=self.label, mode="fixture", packet=packet, source_access=(access,))


type OllamaTransport = Callable[[Request, float], dict[str, object]]


@dataclass(frozen=True)
class OllamaVerifier:
    """Opt-in local Ollama verifier using the documented `/api/chat` structured-output shape."""

    label: str
    system_prompt: str
    claims_opened: bool
    model: str = DEFAULT_MODEL
    url: str = DEFAULT_OLLAMA_URL
    timeout_seconds: float = 60
    transport: OllamaTransport = field(default=lambda request, timeout: _send(request, timeout))

    def produce(self) -> VerifierRun:
        attempted_at = datetime.now(UTC)
        content = SOURCE_PATH.read_text(encoding="utf-8")
        request = Request(
            self.url,
            data=json.dumps(_request_body(self.model, self.system_prompt, content)).encode(),
            headers={"Content-Type": "application/json", "User-Agent": "graphabi-local-provider"},
            method="POST",
        )
        payload = self.transport(request, self.timeout_seconds)
        packet = VerifierPacket.model_validate_json(_response_text(payload))
        access = SourceAccess(
            source_id=SOURCE_ID,
            uri=SOURCE_URI,
            attempted_at=attempted_at,
            opened=self.claims_opened,
            supports_claim=self.claims_opened and RESEARCH_CLAIM in content,
            content_sha256=(
                hashlib.sha256(content.encode()).hexdigest() if self.claims_opened else None
            ),
        )
        return VerifierRun(
            label=self.label,
            mode="live",
            packet=packet,
            source_access=(access,),
            model=self.model,
        )


@dataclass(frozen=True)
class QuickstartResult:
    """Comparison reports plus the exact runs that produced them."""

    structural: StructuralReport
    semantic: SemanticReport
    baseline: VerifierRun
    candidate: VerifierRun


def run_quickstart(
    baseline_producer: VerifierProducer,
    candidate_producer: VerifierProducer,
) -> QuickstartResult:
    """Run both verifiers and compare their common shape and provenance evidence."""
    baseline = baseline_producer.produce()
    candidate = candidate_producer.produce()
    structural = compare_schemas(
        baseline.packet.model_json_schema(),
        candidate.packet.model_json_schema(),
        same_pydantic_model=baseline.packet.__class__ is candidate.packet.__class__,
    )
    contract = load_contract(Path(__file__).with_name("contracts.yml"))
    baseline_trace = _trace(contract.graph, "baseline", baseline)
    candidate_trace = _trace(contract.graph, "candidate", candidate)
    return QuickstartResult(
        structural=structural,
        semantic=compare_semantics(contract, baseline_trace, candidate_trace),
        baseline=baseline,
        candidate=candidate,
    )


def fixture_producers() -> tuple[FixtureVerifier, FixtureVerifier]:
    return (
        FixtureVerifier("recorded-baseline", open_source=True),
        FixtureVerifier("recorded-candidate", open_source=False),
    )


def live_producers(*, model: str | None = None) -> tuple[OllamaVerifier, OllamaVerifier]:
    resolved_model = model or os.environ.get("GRAPHABI_OLLAMA_MODEL", DEFAULT_MODEL)
    return (
        OllamaVerifier("recorded-baseline", VERIFIER_STRICT_PROMPT, True, model=resolved_model),
        OllamaVerifier("recorded-candidate", VERIFIER_BREAKING_PROMPT, False, model=resolved_model),
    )


def check_ollama_reachable(url: str = DEFAULT_OLLAMA_URL) -> None:
    """Raise a clear, actionable error if no local Ollama server is listening."""
    base = url.rsplit("/api/", 1)[0]
    try:
        with urlopen(Request(base), timeout=2):
            pass
    except HTTPError:
        return  # any HTTP response means something is listening
    except URLError as exc:
        raise SystemExit(
            f"--live could not reach a local Ollama server at {base}: {exc.reason}. "
            "Install Ollama, run `ollama serve`, then `ollama pull "
            f"{os.environ.get('GRAPHABI_OLLAMA_MODEL', DEFAULT_MODEL)}` before retrying."
        ) from exc


def _trace(
    graph_id: str, variant: Literal["baseline", "candidate"], run: VerifierRun
) -> TraceBundle:
    return one_edge_bundle(
        run_id=f"local-provider-{variant}",
        graph_id=graph_id,
        graph_version=run.model or "fixture",
        variant=variant,
        edge_id="researcher_to_verifier",
        producer="researcher",
        consumer="verifier",
        output=run.packet.model_dump(mode="json"),
        metadata={"mode": run.mode, "provider_model": run.model},
        source_access=run.source_access,
        observed_at=OBSERVED_AT,
    )


def _request_body(model: str, system_prompt: str, content: str) -> dict[str, object]:
    return {
        "model": model,
        "stream": False,
        "think": False,
        "options": {"temperature": 0.6, "num_predict": 220},
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"CLAIM: {RESEARCH_CLAIM}\n\nEVIDENCE_ACCESSED: unknown\n\nRECORD:\n{content}"
                ),
            },
        ],
        "format": VerifierPacket.model_json_schema(),
    }


def _send(request: Request, timeout: float) -> dict[str, object]:
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read())
    except HTTPError as exc:
        detail = exc.read(4096).decode(errors="replace")
        raise ValueError(f"local Ollama server returned HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise ValueError(f"could not reach the local Ollama server: {exc.reason}") from exc
    if not isinstance(payload, dict):
        raise ValueError("local Ollama server returned a non-object JSON payload")
    return payload


def _response_text(payload: dict[str, object]) -> str:
    message = payload.get("message")
    if not isinstance(message, dict):
        raise ValueError("Ollama response did not contain a message object")
    content = message.get("content")
    if not isinstance(content, str):
        raise ValueError("Ollama response message did not contain string content")
    return content


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help="call a real local Ollama server instead of using the local fixture",
    )
    parser.add_argument(
        "--model",
        default=None,
        help=f"Ollama model tag to use in --live mode (default {DEFAULT_MODEL})",
    )
    args = parser.parse_args()

    if args.live:
        check_ollama_reachable()
        baseline, candidate = live_producers(model=args.model)
    else:
        baseline, candidate = fixture_producers()

    result = run_quickstart(baseline, candidate)
    print(f"Mode: {result.baseline.mode}")
    print(f"Structural compatibility: {result.structural.status}")
    print(f"Semantic compatibility: {result.semantic.status}")
    if result.semantic.breaking_findings:
        finding = result.semantic.breaking_findings[0]
        print(f"First breaking edge: {result.semantic.first_breaking_edge}")
        print(f"Reason: {finding.reason}")


if __name__ == "__main__":
    main()
