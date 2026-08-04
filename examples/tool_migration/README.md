# Tool or retriever migration

This example replaces a live quote retriever with a cache. Both versions return the exact same
`QuotePacket` schema. The candidate trace records a three-day-old retrieval timestamp, while the
risk model contract requires evidence no more than one hour old.

```bash
uv run python -m examples.tool_migration.example
```

Expected result:

```text
Structural compatibility: PASS
Semantic compatibility: FAIL
First breaking edge: quote_retriever_to_risk_model
```

The example checks recorded freshness evidence. It does not judge source quality, market accuracy,
or whether a different maximum age would be appropriate for another consumer.
