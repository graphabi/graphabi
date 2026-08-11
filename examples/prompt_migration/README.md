# Prompt-version migration

This example replays two concrete prompts through the same recorded model identity. Both responses
validate against the exact `AdvicePacket` schema, but the candidate prompt weakens three consumer
assumptions:

- advice remains a recommendation rather than a published decision;
- `verified=true` requires an actually opened source recorded as supporting the claim;
- evidence identifiers required by the decision maker remain non-empty.

The baseline prompt is evidence-bound and advisory. The candidate prompt asks for a decisive,
publish-ready answer, permits trusting a supplied summary without opening its source, and makes
evidence identifiers optional. The recorded outputs show a possible authority escalation,
provenance weakening, and completeness regression.

```bash
uv run python -m examples.prompt_migration.example
```

Expected result:

```text
Model identity: recorded-advisor-model-v1
Prompt revisions differ: True
Structural compatibility: PASS
Semantic compatibility: FAIL
Breaking contracts: 3
First breaking edge: advisor_to_decision_maker
```

The example is entirely local, keyless, and deterministic. It records prompt digests and the model
identity in trace metadata. The responses are replay fixtures, so this demonstrates contract
behavior for one concrete pair of observations. It does not estimate how often any real model
would react this way to those prompts.
