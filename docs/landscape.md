# Landscape

Research date: 2026-07-31.

GraphABI explores edge-level, consumer-driven semantic compatibility
for agent graphs. Adjacent systems address schemas, final-output
evaluation, tracing, or general drift, but GraphABI focuses on explicit
meaning assumptions that downstream nodes rely upon.

This is a difference in focus, not a claim that semantic contracts are unprecedented.

## Schema validation

[JSON Schema](https://json-schema.org/overview/what-is-jsonschema) is a declarative language for
JSON structure and constraints, and validators decide whether instances conform. [Pydantic can
generate JSON Schema](https://pydantic.dev/docs/validation/latest/concepts/json_schema/) compliant
with JSON Schema 2020-12 and OpenAPI 3.1 from models. GraphABI runs these structural checks first;
its central demonstration begins where identical validated schemas stop distinguishing behavior.

## Consumer-driven contract testing

[Pact](https://docs.pact.io/) tests HTTP and message integration points from a shared consumer/
provider understanding. Its documentation emphasizes that consumers should contract only behavior
they use and describes Pact as “contract by example.” GraphABI borrows that consumer-driven stance
but applies contracts to in-process agent-graph edges and trace evidence such as source access,
freshness, units, entity preservation, and authority.

## Workflow tracing and agent observability

[OpenTelemetry tracing](https://opentelemetry.io/docs/specs/otel/trace/api/) represents an operation
as a root span and sub-spans. [Arize Phoenix](https://arize.com/docs/phoenix) provides OpenTelemetry-
based agent tracing, evaluation, prompt workflows, datasets, and experiments. [LangSmith
observability](https://docs.langchain.com/langsmith/observability-studio) supports inspecting and
debugging traces and turning trace examples into evaluation datasets.

These systems provide rich evidence and debugging workflows. GraphABI v0.1 stores a narrower local
trace model and asks a specific compatibility question: which producer-to-consumer meaning
assumption first broke, and what terminal paths are reachable from that edge? OpenTelemetry import
is a roadmap item, so GraphABI should complement rather than replace tracing systems.

## Agent and model evaluation

[Phoenix evaluations](https://arize.com/docs/phoenix/evaluation/llm-evals/evaluator-traces) support
deterministic code checks, human labels, and model judges for output quality. [MLflow's agent
evaluation](https://mlflow.org/docs/latest/genai/eval-monitor/) centers datasets, scorers, human
feedback, tracing, systematic evaluation, and production monitoring. GraphABI is not a general
quality-score framework: it evaluates explicit edge invariants and requires deterministic evidence
for the default workflow. A model judge is never its sole source of truth.

## Drift monitoring

[Evidently](https://docs.evidentlyai.com/metrics/explainer_drift) compares reference and current
value distributions with statistical drift methods. Distribution drift can reveal population-level
change without naming a violated consumer assumption; conversely, one critical provenance or
authority violation can break an edge without producing detectable distribution drift. The methods
are complementary.

## Model and prompt migration testing

Experiment systems in Phoenix, LangSmith, and MLflow compare versions over shared datasets and
scores. GraphABI can consume the same baseline/candidate idea, but reports contract location,
counterexample trace, repair boundary, and downstream topology instead of ranking overall quality.

## Positioning boundary

GraphABI should claim only this: for observed traces and explicit contracts, it can deterministically
identify contract violations, preserve uncertainty, and calculate graph impact. It should not claim
universal meaning, exhaustive behavioral equivalence, production observability, or superiority over
the adjacent categories above.
