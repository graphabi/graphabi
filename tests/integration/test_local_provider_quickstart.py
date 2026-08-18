import json
from urllib.error import URLError
from urllib.request import Request

import pytest
from examples.local_provider_quickstart.example import (
    DEFAULT_MODEL,
    DEFAULT_OLLAMA_URL,
    OllamaVerifier,
    check_ollama_reachable,
    fixture_producers,
    live_producers,
    run_quickstart,
)


def test_local_provider_quickstart_defaults_are_local_and_deterministic() -> None:
    baseline, candidate = fixture_producers()
    result = run_quickstart(baseline, candidate)

    assert result.structural.status == "PASS"
    assert result.structural.exact_schema_match is True
    assert result.semantic.status == "FAIL"
    assert result.semantic.first_breaking_edge == "researcher_to_verifier"
    assert result.baseline.mode == "fixture"
    assert result.baseline.source_access[0].opened is True
    assert result.baseline.source_access[0].supports_claim is True
    assert result.candidate.source_access[0].opened is False


def test_local_provider_quickstart_passes_when_candidate_also_opens_source() -> None:
    baseline, _ = fixture_producers()
    candidate = baseline.__class__("recorded-candidate", open_source=True)

    result = run_quickstart(baseline, candidate)

    assert result.structural.status == "PASS"
    assert result.semantic.status == "PASS"
    assert result.semantic.breaking_findings == ()


def test_live_producers_default_to_configured_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GRAPHABI_OLLAMA_MODEL", raising=False)

    baseline, candidate = live_producers()

    assert baseline.model == DEFAULT_MODEL
    assert candidate.model == DEFAULT_MODEL
    assert baseline.claims_opened is True
    assert candidate.claims_opened is False


def test_live_producers_honor_model_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GRAPHABI_OLLAMA_MODEL", "qwen3:4b")

    baseline, candidate = live_producers()

    assert baseline.model == "qwen3:4b"
    assert candidate.model == "qwen3:4b"

    baseline, candidate = live_producers(model="qwen3:1b")

    assert baseline.model == "qwen3:1b"
    assert candidate.model == "qwen3:1b"


def test_ollama_verifier_uses_documented_chat_shape_without_network() -> None:
    captured: dict[str, object] = {}

    def transport(request: Request, timeout: float) -> dict[str, object]:
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["body"] = json.loads(request.data or b"{}")
        return {"message": {"content": json.dumps({"verified": True, "sources": ["helios-study"]})}}

    verifier = OllamaVerifier("recorded-baseline", "verify strictly", True, transport=transport)
    run = verifier.produce()

    assert captured["url"] == DEFAULT_OLLAMA_URL
    assert captured["timeout"] == 60
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["stream"] is False
    assert body["model"] == DEFAULT_MODEL
    assert "format" in body
    assert run.mode == "live"
    assert run.packet.verified is True
    assert run.source_access[0].opened is True
    assert run.source_access[0].supports_claim is True


def test_check_ollama_reachable_fails_closed_with_actionable_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_url_error(*args: object, **kwargs: object) -> None:
        raise URLError("refused")

    monkeypatch.setattr("examples.local_provider_quickstart.example.urlopen", raise_url_error)

    with pytest.raises(SystemExit, match="could not reach a local Ollama server"):
        check_ollama_reachable()
