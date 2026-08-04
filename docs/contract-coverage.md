# Contract coverage

GraphABI reports the proof surface of the compared traces alongside semantic findings. Coverage is
descriptive. It never turns an unobserved path into a pass.

The report exposes five ordered sets:

- `contracted_edges`: every edge named by the loaded consumer contract;
- `uncontracted_edges`: edge IDs observed in either selected run but absent from that contract;
- `observed_branches`: contracted edges observed in the selected candidate run;
- `unobserved_branches`: contracted edges absent from the selected candidate run;
- `insufficient_evidence_contracts`: invariant IDs that returned `INSUFFICIENT_EVIDENCE`.

The observed and unobserved branch sets form an exact, duplicate-free partition of contracted
edges. Uncontracted edges cannot appear in that partition. The report model rejects malformed
coverage instead of rendering contradictory totals.

`uncontracted_edges` can only list edges that were observed. GraphABI cannot infer an unobserved
edge that is absent from both the contract and trace. `observed_branches` is an edge-level measure
in trace schema 0.1 because repeated occurrences are not yet representable.

A useful automation policy can require all contracted branches to be observed and reject any
uncontracted observed edge. That policy remains separate from the semantic status. A fully observed
graph can still fail a contract, and a passing observed branch says nothing about unseen inputs.
