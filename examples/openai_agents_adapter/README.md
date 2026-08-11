# OpenAI Agents SDK adapter example

This example executes a real `Agent` and `Runner` workflow with one function tool and one handoff.
Both model responses are supplied by a deterministic local `Model` implementation. No API key,
provider request, SDK trace export, or network connection is used.

```bash
uv sync --extra openai-agents
uv run python -m examples.openai_agents_adapter.example
```

The adapter records each agent activation as a trace 0.2 occurrence. An SDK handoff becomes a
GraphABI edge observation only when the application declares a `HandoffEdgeSpec` and provides a
payload resolver. The resolver is responsible for returning the exact application payload whose
consumer assumptions will be evaluated. An undeclared handoff retains causal occurrence ancestry
but does not fabricate an edge payload.

The adapter always disables the OpenAI Agents SDK's own trace export for its run. Raw turn inputs,
model outputs, tool arguments, tool results, and resolver payloads remain in the local GraphABI
trace, so applications must sanitize sensitive values before recording them.
