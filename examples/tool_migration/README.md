# Tool or retriever migration

This example replaces Retriever A, a local market-feed reader, with Retriever B, a cached quote
reader. Both return the exact `QuotePacket` schema. The risk-model consumer depends on four
semantic assumptions that the schema does not establish:

- the quote is no more than one hour old;
- the numeric value is denominated in USD;
- required evidence identifiers are non-empty;
- `verified=true` has a recorded opened source that supports the quote.

Retriever A actually opens, validates, and hashes a bundled synthetic JSON quote. Retriever B
returns a three-day-old cached value in cents, omits evidence identifiers, and has no recorded
source open. The candidate is structurally valid but breaks all four contracts.

```bash
uv run python -m examples.tool_migration.example
```

Expected result:

```text
Baseline retriever: local-market-feed-v1
Candidate retriever: cached-quote-v2
Structural compatibility: PASS
Semantic compatibility: FAIL
Breaking contracts: 4
First breaking edge: quote_retriever_to_risk_model
```

The example is local, keyless, and deterministic. Its ACME quote is synthetic and is not market
data. It demonstrates consumer-specific freshness, unit, completeness, and provenance checks; it
does not judge source quality or prescribe the correct maximum age for another consumer.
