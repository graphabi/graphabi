# Optional real model migration

This example compares two producers through a small `ModelProducer` protocol. Both producers must
return the exact `ModelPacket` schema. GraphABI then checks whether the candidate crossed the
consumer's authority boundary.

The default command is local, keyless, deterministic, and uses recorded fixtures:

```bash
uv run python -m examples.model_migration.example
```

To make real requests, provide an endpoint that implements the narrow Chat Completions request and
response shape used in `example.py`:

```bash
export GRAPHABI_MODEL_ENDPOINT="https://your-provider.example/v1/chat/completions"
export GRAPHABI_BASELINE_MODEL="baseline-model-id"
export GRAPHABI_CANDIDATE_MODEL="candidate-model-id"
export GRAPHABI_MODEL_API_KEY="your-provider-key"
uv run python -m examples.model_migration.example --live
```

`GRAPHABI_MODEL_API_KEY` is optional for a local endpoint. The example never downloads a model and
the test suite never makes this request. A hosted endpoint can transmit the prompt, retain data, and
charge for both calls. Review that provider's privacy terms and current pricing first.

This is an example provider boundary, not a maintained GraphABI adapter. A passing result covers
only these two responses and the explicit authority contract. Temperature zero does not make model
output universally deterministic. Invalid or non-JSON output fails validation instead of being
silently repaired.
