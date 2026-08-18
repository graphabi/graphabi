# Local Ollama provider quick start

This example reproduces, in the repository, the exact free and local provider workflow validated
during the Alpha.3 production reality sprint: a verifier that opened the supplied source compared
against a verifier that claims `verified=true` without opening it, checked by the
`verified_requires_opened_supporting_source` provenance contract. No API key, cloud account, or
paid model is required at any point.

## Deterministic fixture mode

The default is local, keyless, deterministic, and makes no network request:

```bash
uv run python -m examples.local_provider_quickstart.example
```

The recorded baseline opens the bundled synthetic source; the recorded candidate claims
`verified=true` with no recorded source open. Structural compatibility is `PASS` and semantic
compatibility is `FAIL`, with the same reason GraphABI reported against real qwen3:8b inference in
the validation sprint: "verified=true had no successfully opened source recorded as supporting the
claim."

## Optional live mode

Live mode sends the bundled synthetic source to a local Ollama server over
`http://127.0.0.1:11434` and makes no request outside the loopback interface. It requires Ollama
running locally with a pulled model.

```bash
# Install Ollama (https://ollama.com) and start it, then in another terminal:
ollama pull qwen3:8b

uv run python -m examples.local_provider_quickstart.example --live
```

Use `--model` or the `GRAPHABI_OLLAMA_MODEL` environment variable to select a different pulled
model, for example the smaller `qwen3:4b`. If Ollama is not reachable, the command fails closed
with an actionable message instead of a bare connection error.

Live mode is not deterministic: the model can emit a different verified value or wording on each
run, and either the baseline or candidate call can fail independently. A single passing or failing
run is not a claim about the model's general reliability; it demonstrates the compatibility
technique against real inference, not a benchmark of the model.

## What this does and does not prove

- It proves GraphABI can record real local model output, treat `verified=true` without a recorded
  source open as a semantic break, and do so without any paid API, cloud account, or hosted
  service.
- It does not prove universal Ollama compatibility, GraphABI evaluator coverage beyond `provenance`,
  or that any specific model is safe to deploy. See [limitations](../../docs/limitations.md) and
  [contract format](../../docs/contract-format.md) for the full picture.
- This is an example provider client using the stdlib `urllib`, not a maintained GraphABI framework
  adapter. Pair it with the [LangGraph](../research_graph) or
  [OpenAI Agents SDK](../openai_agents_adapter) adapters to record a full local-provider graph, not
  just this one verifier edge.
