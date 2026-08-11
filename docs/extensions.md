# Extension tutorial

## Add an evaluator without editing the engine

Implement the public protocol and register an instance:

```python
from graphabi.contracts.evaluators import EvaluationResult, EvaluatorRegistry, default_registry
from graphabi.contracts.models import Invariant
from graphabi.models.traces import EdgeObservation


class PrefixEvaluator:
    name = "prefix"

    def evaluate(
        self,
        invariant: Invariant,
        candidate: EdgeObservation,
        baseline: EdgeObservation | None = None,
    ) -> EvaluationResult:
        del baseline
        value = candidate.output.get("claim")
        if not isinstance(value, str):
            return EvaluationResult(
                status="INSUFFICIENT_EVIDENCE",
                reason="output.claim is missing",
                expectation=invariant.description,
                relevant_paths=("output.claim",),
            )
        return EvaluationResult(
            status="PASS" if value.startswith("FACT:") else "BREAKING",
            reason="claim prefix evaluated deterministically",
            expectation=invariant.description,
            observed=value,
            relevant_paths=("output.claim",),
        )


registry = default_registry()
registry.register(PrefixEvaluator())
```

Pass `registry=registry` to `compare_semantics`. Contract YAML may use `evaluator: prefix` because
unknown evaluator names are schema-valid extension points. Include unit tests for pass, failure,
missing evidence, non-mutation, and stable output. Use the evaluator proposal issue template before
adding a built-in family.

## Add a framework adapter

An adapter's output contract is `TraceBundle`, not a framework callback object:

```python
from typing import Any
from graphabi.models.traces import TraceBundle


class MyFrameworkAdapter:
    framework_name = "my-framework"

    def invoke(self, graph: Any, input_data: dict[str, Any]) -> TraceBundle:
        # Instrument the real invocation and construct validated GraphRun,
        # NodeExecution, and EdgeObservation records.
        ...
```

Keep implementation below `src/graphabi/adapters/my_framework/`. Record installed versions with
`importlib.metadata.version`; do not leak framework types into models, comparison, contracts,
storage, inference, or reporting. Integration tests must run the real supported API and prove that
reports derive from the captured invocation.

`LangGraphRecorder` implements this protocol directly: configure instrumented nodes and then call
`recorder.invoke(compiled_graph, input_data)`. Protocol conformance is runtime-tested so the public
example and interface cannot drift independently.

`OpenAIAgentsAdapter` also implements the protocol for synchronous SDK runs and provides
`invoke_async` for async applications. It records agent and tool lifecycle hooks. A handoff creates
an edge only when a `HandoffEdgeSpec` supplies the logical edge identity and an application-owned
payload resolver. See the [adapter guide](openai-agents-adapter.md).

Framework adapters should emit trace 0.2. Every node invocation needs a run-unique occurrence ID,
topological causal sequence, retry attempt, stable branch key when available, and all causal parent
occurrence IDs. Every edge crossing references its concrete producer and consumer occurrences.
Do not derive identity from timestamps or payload hashes.

`LangGraphRecorder.instrument` accepts `parent_node` for one logical parent, `parent_nodes` for
distinct fan-in parents, callable `branch_id` and `attempt` resolvers, and a `parent_occurrences`
resolver for joins or loops that require explicit occurrence selection. The resolver can use
`recorder.occurrence_ids(node_id, branch_id=...)` to select completed work. If the framework cannot
distinguish otherwise identical siblings, preserve that ambiguity so comparison returns
`INSUFFICIENT_EVIDENCE`.

## Add storage or rendering

Implement `TraceStore` for persistence. A renderer consumes `CompatibilityReport` and a validated
`Contract`. Neither extension should call evaluators or change finding status.
