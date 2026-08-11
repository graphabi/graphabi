# Contract coverage

GraphABI reports the proof surface of the selected candidate trace alongside semantic findings.
Coverage is descriptive. It never turns an unobserved path into a pass and never establishes
semantic correctness.

## Denominator

Contract format 0.2 declares all known topology under `graph_edges`; contracted edges remain under
`edges`. The total graph-edge count comes from that inventory. Edge and node identities observed in
either selected run but missing from the declaration are retained, reported as unexpected, and make
`graph_inventory_complete` false rather than being discarded.

A version 0.1 contract remains loadable. Its contracted edges and observed trace edges form the
best available inventory, but the report marks that inventory incomplete because it cannot discover
an edge absent from both the contract and traces.

## JSON fields

`contract_coverage` exposes ordered identity sets plus a numeric `summary`:

- `graph_nodes` and `graph_edges`: the inventory used for totals;
- `contracted_edges` and `uncontracted_edges`: an exact partition of graph edges;
- `observed_edges` and `unobserved_edges`: an exact partition using the candidate run;
- `contracted_and_observed`, `contracted_but_unobserved`, and
  `observed_but_uncontracted`: exact intersections and differences;
- `insufficient_evidence_branches`: contracted edge IDs with at least one
  `INSUFFICIENT_EVIDENCE` finding;
- `unexpected_observed_edges`: candidate observations absent from the declaration or whose
  endpoints conflict with it;
- `insufficient_evidence_contracts`: individual invariant IDs with insufficient evidence;
- `graph_inventory_complete`: whether a 0.2 declaration matches all selected observations.

`observed_branches` and `unobserved_branches` remain serialized as report 0.1 compatibility aliases
for `contracted_and_observed` and `contracted_but_unobserved`.

The percentage is:

```text
contracted and observed edges / total graph edges * 100
```

It is rounded to one decimal place. For 31 graph edges with 17 both contracted and observed, the
reported value is 54.8%. A fully observed graph can still fail a contract; a passing observed edge
says nothing about unseen inputs. `summary.coverage_is_correctness` is always `false`.

Coverage totals remain logical-edge metrics. Trace schema 0.2 evaluates every causally paired edge
occurrence independently and records occurrence IDs in findings and witnesses; it does not inflate
the graph-edge denominator for loops or retries. See [occurrence pairing](occurrence-pairing.md).
