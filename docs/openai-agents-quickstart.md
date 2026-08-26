# OpenAI Agents SDK quick start

This tutorial uses the optional OpenAI Agents SDK adapter with deterministic local model responses.
It does not need an OpenAI API key and disables SDK trace export during the adapter run.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install "graphabi[openai-agents]==0.1.0a3"
graphabi doctor
```

Expected result: required checks pass, LangGraph adapter passes, and OpenAI Agents adapter reports
`PASS` for a supported `0.20.x` SDK.

## Run the keyless adapter fixture

```bash
python -m examples.openai_agents_adapter.example
```

Expected result:

```text
OpenAI Agents SDK adapter fixture
Run status: success
Node occurrences: 2
Handoff edges: 1
Network calls: 0
```

## Adapter setup

Handoffs become GraphABI edge observations only when your application declares the logical edge and
provides the exact payload the consumer relies on:

```python
from graphabi.adapters.openai_agents import HandoffEdgeSpec, OpenAIAgentsAdapter


def handoff_payload(context, source, target):
    del source, target
    return context.context["handoff_payload"]


adapter = OpenAIAgentsAdapter(
    run_id="baseline-001",
    graph_id="support_workflow",
    graph_version="1.0",
    variant="baseline",
    context={"handoff_payload": {"record_id": "fixture-001", "complete": True}},
    edges=(
        HandoffEdgeSpec(
            edge_id="researcher_to_publisher",
            producer="researcher",
            consumer="publisher",
            payload_resolver=handoff_payload,
        ),
    ),
)

bundle = adapter.invoke(starting_agent, {"input": "Inspect fixture-001 and publish it."})
```

## Capture baseline and candidate traces

This script uses the packaged keyless fixture, records a passing baseline handoff, then records a
candidate handoff whose payload is incomplete:

```bash
mkdir graphabi-openai-agents-start
cd graphabi-openai-agents-start
python - <<'PY'
from pathlib import Path

from examples.openai_agents_adapter.example import _handoff_payload, build_workflow
from graphabi.adapters.openai_agents import HandoffEdgeSpec, OpenAIAgentsAdapter
from graphabi.storage import SQLiteTraceStore

Path(".graphabi").mkdir(exist_ok=True)
store = SQLiteTraceStore(Path(".graphabi/traces.db"))

for run_id, variant, complete in [
    ("baseline-001", "baseline", True),
    ("candidate-001", "candidate", False),
]:
    starting_agent, context = build_workflow()
    context["handoff_payload"]["complete"] = complete
    adapter = OpenAIAgentsAdapter(
        run_id=run_id,
        graph_id="support_workflow",
        graph_version="1.0",
        variant=variant,
        context=context,
        edges=(
            HandoffEdgeSpec(
                edge_id="researcher_to_publisher",
                producer="researcher",
                consumer="publisher",
                payload_resolver=_handoff_payload,
            ),
        ),
    )
    bundle = adapter.invoke(starting_agent, {"input": "Inspect fixture-001 and publish it."})
    store.save_bundle(bundle)
    print(f"recorded {run_id}")
PY
```

## Minimal contract

Save this as `.graphabi/contracts.yml`:

```yaml
version: "0.2"
graph: support_workflow
nodes:
  - id: researcher
  - id: publisher
graph_edges:
  - id: researcher_to_publisher
    producer: researcher
    consumer: publisher
edges:
  - id: researcher_to_publisher
    producer: researcher
    consumer: publisher
    invariants:
      - id: handoff_payload_complete
        evaluator: implication
        description: Publishing requires a complete inspected record.
        severity: breaking
        when: {path: output.record_id, exists: true}
        require: {path: output.complete, equals: true}
```

## Compare

```bash
graphabi compare \
  --baseline-run baseline-001 \
  --candidate-run candidate-001 \
  --contract .graphabi/contracts.yml \
  --database .graphabi/traces.db \
  --allow-breaking
```

Expected result:

```text
Structural: PASS
Semantic: FAIL
First breaking edge: researcher_to_publisher
Observed contract coverage: 100.0%
Coverage is not correctness.
```

The same comparison returns `Semantic: PASS` if the candidate handoff payload keeps
`complete: true`.

## Limits

The adapter covers ordinary non-streamed `Agent` runs, local tools, and sequential handoffs for
OpenAI Agents SDK `>=0.20,<0.21`. Realtime, voice, sandbox, session-resume, and streamed-run
surfaces are not mapped. The adapter does not choose a model or make provider requests; any model
you attach can still make its own calls.
