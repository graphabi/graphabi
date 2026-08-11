import json
from decimal import Decimal
from pathlib import Path
from urllib.request import Request

import pytest
from examples.model_migration.example import (
    BASELINE_MODEL,
    MAX_OUTPUT_TOKENS,
    MODEL_PRICES,
    OPENAI_RESPONSES_URL,
    EvidenceSource,
    OpenAIResponsesProducer,
    TokenUsage,
    compare_model_migration,
    fixture_producers,
    live_cost_warning,
    live_producers,
    run_model_migration,
)
from examples.prompt_migration.example import compare_prompt_migration, run_prompt_migration
from examples.tool_migration.example import compare_tool_migration, run_tool_migration


def test_prompt_migration_uses_one_model_and_breaks_three_semantic_contracts() -> None:
    result = run_prompt_migration()
    structural, semantic = result.structural, result.semantic

    assert structural.status == "PASS"
    assert structural.exact_schema_match is True
    assert semantic.status == "FAIL"
    assert semantic.first_breaking_edge == "advisor_to_decision_maker"
    assert result.baseline.model_id == result.candidate.model_id
    assert result.baseline.prompt_sha256 != result.candidate.prompt_sha256
    assert result.baseline.source_access[0].supports_claim is True
    assert result.candidate.source_access[0].opened is False
    findings = {finding.contract_id.rsplit(":", 1)[-1]: finding for finding in semantic.findings}
    assert findings["advice_must_remain_a_recommendation"].status == "BREAKING"
    assert findings["advice_must_remain_a_recommendation"].witness.observed_conflict == "published"
    assert findings["verified_requires_opened_supporting_source"].status == "BREAKING"
    assert findings["evidence_identifiers_required"].status == "BREAKING"
    assert findings["evidence_identifiers_required"].witness.observed_conflict == []


def test_prompt_migration_compatibility_wrapper_remains_available() -> None:
    structural, semantic = compare_prompt_migration()

    assert structural.status == "PASS"
    assert semantic.status == "FAIL"


def test_tool_migration_preserves_schema_and_breaks_four_semantic_contracts() -> None:
    result = run_tool_migration()
    structural, semantic = result.structural, result.semantic

    assert structural.status == "PASS"
    assert structural.exact_schema_match is True
    assert semantic.status == "FAIL"
    assert semantic.first_breaking_edge == "quote_retriever_to_risk_model"
    assert result.baseline.source_access[0].opened is True
    assert result.baseline.source_access[0].supports_claim is True
    assert result.candidate.source_access[0].opened is False
    findings = {finding.contract_id.rsplit(":", 1)[-1]: finding for finding in semantic.findings}
    assert findings["quote_must_be_recent"].status == "BREAKING"
    assert findings["quote_must_be_recent"].witness.observed_conflict == 259200.0
    assert findings["quote_value_must_be_usd"].status == "BREAKING"
    assert findings["quote_value_must_be_usd"].witness.observed_conflict == {
        "value": 10_125.0,
        "unit": "cents",
        "representation": None,
    }
    assert findings["quote_evidence_identifiers_required"].status == "BREAKING"
    assert findings["quote_evidence_identifiers_required"].witness.observed_conflict == []
    assert findings["verified_quote_requires_opened_supporting_source"].status == "BREAKING"


def test_tool_migration_compatibility_wrapper_remains_available() -> None:
    structural, semantic = compare_tool_migration()

    assert structural.status == "PASS"
    assert semantic.status == "FAIL"


def test_model_migration_defaults_are_local_and_deterministic() -> None:
    baseline, candidate = fixture_producers()
    result = run_model_migration(baseline, candidate)
    structural, semantic = result.structural, result.semantic

    assert structural.status == "PASS"
    assert structural.exact_schema_match is True
    assert semantic.status == "FAIL"
    assert semantic.first_breaking_edge == "model_producer_to_policy_gate"
    assert semantic.breaking_findings[0].witness.observed_conflict == {
        "cited": ["helios-study"],
        "opened": 0,
        "supporting": 0,
    }
    assert result.baseline.mode == "fixture"
    assert result.baseline.source_access[0].opened is True
    assert result.baseline.source_access[0].supports_claim is True
    assert result.candidate.source_access[0].opened is False
    assert result.candidate.usage is None


def test_model_migration_compatibility_wrapper_remains_available() -> None:
    baseline, candidate = fixture_producers()
    structural, semantic = compare_model_migration(baseline, candidate)

    assert structural.status == "PASS"
    assert semantic.status == "FAIL"


def test_model_migration_does_not_force_a_live_style_candidate_failure() -> None:
    baseline, candidate = fixture_producers()
    candidate = candidate.__class__(candidate.name, candidate.packet, open_source=True)

    result = run_model_migration(baseline, candidate)

    assert result.structural.status == "PASS"
    assert result.semantic.status == "PASS"
    assert result.semantic.breaking_findings == ()


def test_openai_live_producer_uses_strict_responses_shape_without_network(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "evidence.txt"
    source_path.write_text(
        "The Helios battery retains 92% capacity after 1,000 charge cycles.",
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    def transport(request: Request, timeout: float) -> dict[str, object]:
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["authorization"] = request.get_header("Authorization")
        captured["body"] = json.loads(request.data or b"{}")
        return {
            "id": "resp_fixture",
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps(
                                {
                                    "answer": "92% after 1,000 cycles",
                                    "retained_capacity_percent": 92,
                                    "charge_cycles": 1_000,
                                    "verified": True,
                                    "sources": ["helios-study"],
                                }
                            ),
                        }
                    ],
                }
            ],
            "usage": {
                "input_tokens": 100,
                "input_tokens_details": {"cached_tokens": 20},
                "output_tokens": 10,
            },
        }

    producer = OpenAIResponsesProducer(BASELINE_MODEL, "not-a-real-key", transport=transport)
    result = producer.produce(
        "Use only the source.",
        EvidenceSource("helios-study", "fixture://test/helios", source_path),
    )

    assert captured["url"] == OPENAI_RESPONSES_URL
    assert captured["timeout"] == 60
    assert captured["authorization"] == "Bearer not-a-real-key"
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["store"] is False
    assert body["max_output_tokens"] == MAX_OUTPUT_TOKENS
    assert body["text"]["format"]["type"] == "json_schema"
    assert body["text"]["format"]["strict"] is True
    assert result.mode == "live"
    assert result.response_id == "resp_fixture"
    assert result.source_access[0].opened is True
    assert result.source_access[0].supports_claim is True
    assert result.usage == TokenUsage(100, 20, 10)


def test_live_mode_requires_explicit_cost_acknowledgement(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(SystemExit, match="acknowledge-cost"):
        live_producers(acknowledge_cost=False)
    with pytest.raises(SystemExit, match="OPENAI_API_KEY"):
        live_producers(acknowledge_cost=True)


def test_live_price_warning_and_usage_cost_are_exact_for_snapshot() -> None:
    warning = live_cost_warning()

    assert "makes two paid requests" in warning.lower()
    assert "combined maximum output-token charge is $0.003960" in warning
    assert MODEL_PRICES[BASELINE_MODEL].cost(TokenUsage(100, 20, 10)) == Decimal("0.000284")
