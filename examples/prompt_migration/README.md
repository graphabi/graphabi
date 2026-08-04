# Prompt migration

This example changes an advisor prompt while preserving the exact `AdvicePacket` Pydantic model.
The baseline returns a recommendation. The candidate returns a published decision. The consumer
contract allows recommendations, not authority escalation.

```bash
uv run python -m examples.prompt_migration.example
```

Expected result:

```text
Structural compatibility: PASS
Semantic compatibility: FAIL
First breaking edge: advisor_to_decision_maker
```

The strings are deterministic fixtures. This example proves the contract behavior, not how often
a particular model will react this way to a prompt revision.
