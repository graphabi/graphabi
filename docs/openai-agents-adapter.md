# OpenAI Agents SDK adapter

GraphABI supports OpenAI Agents SDK `>=0.20,<0.21` as its second maintained framework adapter. The
dependency is optional:

```bash
uv sync --extra openai-agents
```

The default GraphABI installation and demo do not require an OpenAI API key. Adapter integration
tests use a real SDK `Agent`, `Runner`, function tool, and handoff with deterministic local model
responses. SDK trace export is disabled for every adapter run.

## Selection record

The framework review was performed on 2026-08-12. GitHub stars are included only as a rough public
adoption signal, not as a usage measurement or quality score.

| Candidate | Public and maintenance signal at review | Architectural value | Decision |
|---|---|---|---|
| [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) | About 28,500 stars; v0.20.0 published 2026-08-11; active official releases | Turn-based runner, agent handoffs, lifecycle hooks, and tool events differ from LangGraph's explicit state graph | Selected |
| [CrewAI](https://github.com/crewAIInc/crewAI) | About 56,900 stars; 1.15.14 published 2026-08-08; active | Crews and flows offer real usage, but the flow surface is closer to the existing graph-shaped adapter and the integration boundary is broader | Not selected for this release line |
| [AutoGen](https://github.com/microsoft/autogen) | About 60,300 stars; Python 0.7.5 published 2025-09-30 | Its event-driven actor model would test a different architecture | Not selected because the official repository states that AutoGen is in maintenance mode and directs new users to Microsoft Agent Framework |

The selection does not claim that OpenAI Agents has the most users. It provides substantial public
use, a narrow maintained hook surface, and the strongest architectural contrast for the amount of
framework-specific code GraphABI must own.

The adapter relies on the SDK's documented
[run lifecycle hooks](https://openai.github.io/openai-agents-python/ref/lifecycle/) and
[`AgentHookContext.turn_input`](https://openai.github.io/openai-agents-python/ref/run_context/).

## Supported mapping

| SDK event or value | GraphABI trace record | Exact behavior |
|---|---|---|
| `on_agent_start` | `NodeExecution` start | Creates a run-unique occurrence from agent name and activation count. Records the SDK's prepared `turn_input`. |
| `on_llm_start` and `on_llm_end` | node output and metadata | Counts model calls and retains local model output items and response IDs. |
| `on_tool_start` and `on_tool_end` | `ToolActivity` | Preserves function-tool call ID, qualified name, arguments, result, and timing. |
| `on_handoff` | causal parent | Closes the source occurrence and makes it the target occurrence's causal parent. |
| declared `HandoffEdgeSpec` | `EdgeObservation` | Creates an edge only for the exact producer/consumer pair and records the resolver's JSON-object payload. |
| `on_agent_end` | final node output | Records the SDK final output without changing its meaning. |
| `RunResult.final_output` | `GraphRun.output` | Records the run's final local result. |

Repeated activation of one agent creates another occurrence and increments its attempt ordinal. A
handoff back to an earlier logical agent therefore remains distinct. Function-tool calls may run
in parallel because their SDK call IDs remain distinct inside the active agent occurrence.

## Instrument a handoff

```python
from graphabi.adapters.openai_agents import HandoffEdgeSpec, OpenAIAgentsAdapter


def handoff_payload(context, source, target):
    del source, target
    return context.context["handoff_payload"]


adapter = OpenAIAgentsAdapter(
    run_id="migration-001",
    graph_id="support_workflow",
    graph_version="2.0",
    context={"handoff_payload": {"authority_level": "recommendation"}},
    edges=(
        HandoffEdgeSpec(
            edge_id="researcher_to_publisher",
            producer="researcher",
            consumer="publisher",
            payload_resolver=handoff_payload,
        ),
    ),
)
bundle = adapter.invoke(starting_agent, {"input": "Prepare the recorded result."})
```

The payload resolver is application code because the generic SDK handoff hook exposes a control
transfer, not a universal domain payload. The resolver must return the exact observed payload that
the consumer relies on. Without a matching `HandoffEdgeSpec`, GraphABI records causal ancestry but
does not create an edge observation.

Use `invoke_async` inside an async application. The synchronous `invoke` method implements the
public framework-adapter protocol and uses the SDK's `Runner.run_sync`.

## Limits and data handling

- The adapter instruments ordinary `Agent` runs. Realtime agents, voice pipelines, sandbox agents,
  sessions, resumable interrupted runs, and streamed runner output are not covered by this first
  version.
- An agent handoff is sequential control transfer, not parallel fan-out. Parallel local tools stay
  activities within one node occurrence.
- An undeclared handoff is not an observed contract edge.
- Tool results do not become `SourceAccess`. Applications need instrumentation that actually
  observed a source open and support relationship.
- Prepared turn inputs, model output items, tool arguments, tool results, and resolver payloads are
  retained locally. Sanitize sensitive values before recording.
- Disabling SDK tracing prevents its exporter from making a hidden trace request. A model attached
  by the application may still make its own provider request; the adapter never creates or chooses
  a model.

Run the keyless example:

```bash
uv run python -m examples.openai_agents_adapter.example
```
