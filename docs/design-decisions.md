# Design decisions

## Consumer-driven edges

Contracts belong to edges and describe consumer reliance. Producer-owned declarations tend to
repeat intended behavior; the compatibility question is whether every downstream consumer can
still safely interpret the new behavior.

## Deterministic built-ins before model judges

The v0.1 claim needs reproducible evidence. Built-in evaluators therefore compare explicit values,
events, units, authority labels, and timestamps. A future model-backed evaluator may return a
conservative status, but it will not replace deterministic evidence or be the default source of
truth.

## Explicit uncertainty

Missing evidence is not false and is never success. `UNKNOWN` means GraphABI lacks an evaluator or
cannot interpret the observed value. `INSUFFICIENT_EVIDENCE` means required observation data is
absent. Reports preserve both.

## JSON-in-SQLite persistence

SQLite tables index runs and edge observations while keeping each versioned Pydantic record as
lossless JSON. This makes the first store inspectable and transactional without coupling core models
to an ORM. Query optimization and remote stores are deferred.

## Adapter wrappers

LangGraph nodes are wrapped at graph construction. Business nodes do not receive a database handle
and do not write persistence records. This is a small, stable integration surface compatible with
the current `StateGraph.add_node`, `compile`, and `invoke` APIs.

## No global evaluator registry

`default_registry()` returns a fresh registry. Tests and applications can add or replace evaluators
without process-global mutation, import ordering, or hidden plugin discovery.

## Report model before HTML

JSON and HTML derive from `CompatibilityReport`. The renderer cannot invent findings. Inline SVG,
CSS, and minimal HTML disclosure elements keep the report offline and remove a frontend toolchain.
Report models mask common secret shapes before serialization, and Jinja autoescaping is forced for
the `.j2` template rather than inferred from its filename.

## Conservative unit policy

Different units can sometimes convert correctly, but unit labels alone cannot prove the magnitude
was transformed. v0.1 fails mismatches by default; explicitly allowed conversion remains `UNKNOWN`
until a future conversion policy can verify both unit and magnitude.

## Standard-library SQLite

SQLAlchemy would add capabilities unused by v0.1. The store protocol leaves room for a future
backend without imposing the dependency today.

## Python packaging

The intentionally broken graph stays in top-level `examples`, separate from the `graphabi` package.
It is included in distributions solely so the installed `graphabi demo` entry point remains usable.
