# Contract format 0.1

A GraphABI contract is versioned YAML describing a graph and the semantic assumptions that each
consumer makes about values crossing an incoming edge.

```yaml
version: "0.1"
graph: research_demo
nodes:
  - id: researcher
  - id: verifier
  - id: publisher
    terminal: true
    side_effecting: true
edges:
  - id: researcher_to_verifier
    producer: researcher
    consumer: verifier
    schema:
      model: ResearchResult
    invariants:
      - id: verified_requires_source
        evaluator: implication
        description: verified=true requires an opened source in this execution.
        severity: breaking
        when: {path: output.verified, equals: true}
        require: {path: metadata.opened_sources_count, greater_than: 0}
```

## Document fields

- `version` is currently exactly `"0.1"`.
- `graph` is a stable graph identifier.
- `nodes` contains unique `id` values and optional `terminal` / `side_effecting` booleans.
- `edges` contains a unique `id`, known `producer` and `consumer`, optional model reference, and at
  least one invariant.
- `schema.model` records the consumer's expected model name. v0.1 does not dynamically import the
  name; structural comparison receives concrete schemas from the integration boundary.

Node and edge references are validated together. Extra fields are rejected.

## Paths

Paths are dot-separated and start at one of:

- `input`: state observed at the consumer;
- `output`: producer payload carried across this edge;
- `metadata`: producer execution metadata;
- `tool_calls`: zero-based structured tool activities;
- `source_access`: zero-based source-access attempts;
- `observed_at`: edge timestamp.

Lists accept numeric components such as `source_access.0.opened`. Missing paths do not compare as
false: evaluators return `INSUFFICIENT_EVIDENCE` unless the operation is an explicit `exists` check.

## Implication comparisons

Both `when` and `require` use exactly one of:

- `equals`
- `not_equals`
- `greater_than`
- `greater_than_or_equal`
- `less_than`
- `exists`
- `non_empty`
- `contains`

When the antecedent is false, the implication passes. When it is true, the required comparison must
be provable.

## Evaluator families

### Provenance

`rule` is one of `opened_source`, `claim_support`, `accessed_citations`, or
`opened_supporting_source`. These inspect `SourceAccess` events. A string in `output.sources` is not
proof of access.

### Preservation and completeness

`set_preservation` requires `source_path` and `destination_path`; destination must be a superset.
`completeness` requires `destination_path`; the observed value must exist and be non-empty.

### Unit consistency

Provide `value_path`, `unit_path`, and `expected_unit`. Optional `representation_path` and
`expected_representation` distinguish fractions from percentages. v0.1 rejects silent unit changes.
With `allow_conversion: true`, a mismatch becomes `UNKNOWN`; GraphABI still does not claim the
conversion was correct.

### Authority

Provide `source_path` and `maximum_allowed`. The ordered scale is suggestion, recommendation/draft,
decision, authorized, published. Unknown labels remain `UNKNOWN`.

### Freshness

Provide `timestamp_path` and positive `max_age_seconds`. Timestamps must be ISO-8601. Missing
timestamps yield `INSUFFICIENT_EVIDENCE`.

## Severity and status

Contract severity is `warning` or `breaking`. Failed warning invariants produce `WARNING`; failed
breaking invariants produce `BREAKING`. `PASS`, `UNKNOWN`, and `INSUFFICIENT_EVIDENCE` do not erase
that declared severity.

## Errors

`graphabi check` reports the file, edge, invariant, invalid field, expected constraint, and a
suggested correction when possible. Use it before recording or comparing runs:

```bash
graphabi check examples/research_graph/contracts.yml
```

Unknown evaluator names remain schema-valid extension points, but the CLI returns `UNKNOWN` (exit
3) when it cannot execute one. Applications pass a custom registry to `compare_semantics`; use
`graphabi check --allow-unregistered contract.yml` only when schema-only validation is intentional.
