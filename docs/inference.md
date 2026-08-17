# Conservative contract inference

`graphabi infer` reports candidate invariants observed in successful baseline traces. Every result
has status `SUGGESTED`, enforcement `NOT ENFORCED`, and the compatibility label
`SUGGESTED: NOT ENFORCED`. Inference never edits a contract or turns a correlation into a pass.

```bash
graphabi infer --database .graphabi/traces.db
graphabi infer --run baseline-001 --run baseline-002 --database .graphabi/traces.db
graphabi --json-output infer --database .graphabi/traces.db
```

With no `--run`, the command selects all successful baseline runs matching the graph ID, graph
version, and trace schema of the latest successful baseline. Repeat `--run` to select an explicit
set. Mixed graph identities, failed runs, candidate runs, and duplicate run IDs fail with an
actionable error instead of being combined.

## Suggestion evidence

Each suggestion contains:

- `observation_count`, partitioned exactly into supporting, counterexample, and insufficient
  evidence counts;
- `empirical_support_ratio`, calculated as support divided by support plus counterexamples;
- trace evidence references with run ID, edge ID, occurrence ID, outcome, and a bounded reason;
- a valid invariant YAML snippet; and
- the legacy `confidence` field, retained as an alias of `empirical_support_ratio` for alpha.1
  compatibility. It is not statistical confidence or a probability of semantic safety.

Insufficient evidence is excluded from the ratio and remains visible. It is never converted to
support. Failed graph runs are excluded from inference entirely.

## Observable candidate mappings

| Observation pattern | Suggested evaluator | Support | Counterexample | Insufficient evidence |
|---|---|---|---|---|
| `verified=true` and opened supporting source access | `provenance` | Opened source has `supports_claim=true` | No opened supporting source was recorded | Not applicable after the boolean antecedent is selected |
| `metadata.required_entities` to `output.entities` | `set_preservation` | Required set is preserved | Comparable set loses an entity | Either value is missing or not comparable as a set |
| `output.authority_level` | `authority` | Known level is at or below the observed ceiling | Known level exceeds the proposed ceiling | Missing or outside the maintained vocabulary |
| `metadata.*_unit` with a numeric output | `unit_consistency` | Unit matches the deterministic modal value | Unit differs from that value | Unit or finite magnitude is missing |
| `metadata.evidence_observed_at` | `freshness` | Parseable non-future timestamp is inside the observed envelope | Reserved for evidence outside a proposed fixed window | Missing, invalid, or future timestamp |

Authority and freshness ceilings are empirical envelopes derived from the selected traces. A unit
tie is resolved lexicographically so output remains deterministic. These mechanics make the
candidate reproducible; they do not make it a consumer requirement.

## Human review boundary

The YAML snippet contains only one candidate invariant. A reviewer must decide whether the
consumer actually relies on it, place it on the correct explicit contract edge, choose severity
and failure text, and run compatibility checks. `--output` writes only the suggestion document
shown by the CLI. GraphABI never copies it into `.graphabi/contracts.yml` or enables enforcement.

Run IDs and occurrence IDs are emitted as local evidence references. Arbitrary payload values are
not copied into evidence summaries, although a proposed expected unit or authority ceiling must
appear in its YAML. Review traces and generated suggestions before sharing them.
