# LangGraph quick start

This tutorial uses the published PyPI package and the packaged deterministic LangGraph example. It
does not need a model provider or network access after installation.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install graphabi==0.1.0a3
graphabi doctor
```

`doctor` should report the LangGraph adapter as `PASS` because LangGraph is part of the base alpha
install.

## Capture baseline and candidate traces

Create a clean directory and record the packaged LangGraph example into SQLite:

```bash
mkdir graphabi-langgraph-start
cd graphabi-langgraph-start
python - <<'PY'
from pathlib import Path

from examples.research_graph.graph import run_graph
from graphabi.storage import SQLiteTraceStore

Path(".graphabi").mkdir(exist_ok=True)
store = SQLiteTraceStore(Path(".graphabi/traces.db"))

for variant, run_id in [("baseline", "baseline-001"), ("candidate", "candidate-003")]:
    bundle, _ = run_graph(variant, run_id)
    store.save_bundle(bundle)
    print(f"recorded {run_id}")
PY
```

Locate the packaged contract:

```bash
CONTRACT=$(python - <<'PY'
from pathlib import Path
import examples.research_graph as example

print(Path(example.__file__).with_name("contracts.yml"))
PY
)
```

## Compare

```bash
graphabi compare \
  --baseline-run baseline-001 \
  --candidate-run candidate-003 \
  --contract "$CONTRACT" \
  --database .graphabi/traces.db \
  --allow-breaking
```

Expected result:

```text
Structural: PASS
Semantic: FAIL
First breaking edge: researcher_to_verifier
Observed contract coverage: 100.0%
Coverage is not correctness.
```

## Adapter setup for your graph

Wrap each node with `LangGraphRecorder.instrument`, then invoke the compiled graph through the
recorder:

```python
from graphabi.adapters.langgraph import EdgeSpec, LangGraphRecorder

recorder = LangGraphRecorder(
    run_id="baseline-001",
    graph_id="my_graph",
    graph_version="1.0",
    variant="baseline",
    edges=(EdgeSpec("producer_to_consumer", "producer", "consumer", "result"),),
)

builder.add_node("producer", recorder.instrument("producer", producer_node))
builder.add_node(
    "consumer",
    recorder.instrument(
        "consumer",
        consumer_node,
        parent_node="producer",
        incoming_edge="producer_to_consumer",
    ),
)

bundle = recorder.invoke(compiled_graph, {"input": "example"})
```

Persist the returned `TraceBundle` with `SQLiteTraceStore.save_bundle` or export it with
`graphabi.traces.export_json` and import it with `graphabi record`.

## Minimal contract

```yaml
version: "0.2"
graph: my_graph
nodes:
  - id: producer
  - id: consumer
graph_edges:
  - id: producer_to_consumer
    producer: producer
    consumer: consumer
edges:
  - id: producer_to_consumer
    producer: producer
    consumer: consumer
    invariants:
      - id: result_value_required
        evaluator: completeness
        description: The consumer requires a non-empty result value.
        severity: breaking
        destination_path: output.value
```

## Limits

GraphABI does not discover LangGraph topology automatically. You must declare logical edges and
record the payload field crossing each edge. Repeated, parallel, or fan-in executions need explicit
parent or branch identity when the framework cannot distinguish occurrences on its own.
