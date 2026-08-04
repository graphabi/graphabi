from examples.model_migration.example import compare_model_migration, fixture_producers
from examples.prompt_migration.example import compare_prompt_migration
from examples.tool_migration.example import compare_tool_migration


def test_prompt_migration_preserves_schema_and_breaks_authority() -> None:
    structural, semantic = compare_prompt_migration()

    assert structural.status == "PASS"
    assert structural.exact_schema_match is True
    assert semantic.status == "FAIL"
    assert semantic.first_breaking_edge == "advisor_to_decision_maker"
    assert semantic.breaking_findings[0].witness.observed_conflict == "published"


def test_tool_migration_preserves_schema_and_breaks_freshness() -> None:
    structural, semantic = compare_tool_migration()

    assert structural.status == "PASS"
    assert structural.exact_schema_match is True
    assert semantic.status == "FAIL"
    assert semantic.first_breaking_edge == "quote_retriever_to_risk_model"
    assert semantic.breaking_findings[0].witness.observed_conflict == 259200.0


def test_model_migration_defaults_are_local_and_deterministic() -> None:
    baseline, candidate = fixture_producers()
    structural, semantic = compare_model_migration(baseline, candidate)

    assert structural.status == "PASS"
    assert structural.exact_schema_match is True
    assert semantic.status == "FAIL"
    assert semantic.first_breaking_edge == "model_producer_to_policy_gate"
    assert semantic.breaking_findings[0].witness.observed_conflict == "decision"
