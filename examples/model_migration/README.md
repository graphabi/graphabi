# Real model migration example

This example sends the same local source and the same prompt to two models that must return the
same `ModelPacket` schema. GraphABI evaluates a separate semantic contract:

> `verified=true` requires a recorded source open that supports the numeric claim.

Schema compatibility does not prove that contract. The trace records the source open, a stable
non-local URI, the source digest, and whether the structured numeric response agrees with the
source. A source ID in model output is not treated as evidence by itself.

## Deterministic fixture mode

The default is local, keyless, deterministic, and makes no network request:

```bash
uv run python -m examples.model_migration.example
```

Both recorded producers return the same packet. The baseline opens the bundled synthetic source;
the candidate claims `verified=true` but has no recorded source open. Structural compatibility is
`PASS` and semantic compatibility is `FAIL`.

## Optional live mode

Live mode uses the OpenAI Responses API with strict JSON-schema output. It compares
`gpt-5.6-terra` with the lower-cost `gpt-5.6-luna`. The application opens the bundled source before
each request and supplies its content to the model. No hosted search or collector is involved.

```bash
export OPENAI_API_KEY="your-key"
uv run python -m examples.model_migration.example --live --acknowledge-cost
```

Both flags and a user-supplied key are required before any request occurs. Tests never enter live
mode. Live output is labelled `LIVE`; fixture output is labelled `FIXTURE`.

Pricing snapshot on 2026-08-12, per one million text tokens:

| Model | Input | Cached input | Output |
|---|---:|---:|---:|
| [`gpt-5.6-terra`](https://developers.openai.com/api/docs/models/gpt-5.6-terra) | $2.00 | $0.20 | $12.00 |
| [`gpt-5.6-luna`](https://developers.openai.com/api/docs/models/gpt-5.6-luna) | $0.20 | $0.02 | $1.20 |

Each response is capped at 300 output tokens. The combined maximum output-token charge is
$0.003960, plus input-token charges. For requests above 272,000 input tokens, the documented full
request multipliers apply. The example prints the observed token counts and a rate-based cost after
the calls. Review the linked official model pages before running because prices can change.

Live model behavior is not deterministic. Either model may pass or fail. If both runs record
supporting access, both report `PASS`; the example never forces a candidate failure. A pass applies
only to these two observations and this contract. It is not a universal quality or safety claim.

The integration is intentionally narrow. It supports these two OpenAI models, one Responses API
request shape, local source input, and text-token cost reporting. Supporting evidence is checked
against the structured capacity and cycle fields, not every assertion that might appear in the
free-form answer. It is an example provider client, not a maintained GraphABI tracing adapter.
