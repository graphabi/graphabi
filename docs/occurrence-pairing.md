# Causal occurrence pairing for loops and fan-out

Status: implemented for trace schema 0.2.

## Why edge IDs are insufficient

An edge ID can be traversed more than once when a graph loops, retries work, fans out, or joins
parallel branches. Pairing the first baseline observation with the first candidate observation can
compare unrelated events. Wall-clock ordering is also unsafe because concurrent spans overlap and
clocks can skew.

GraphABI therefore records concrete node and edge occurrences. Occurrence IDs come from adapter
execution identity and counters, never payload hashes. Equal payloads may belong to different
events, and payload hashing could leak sensitive information.

## Pairing algorithm

For trace 0.2 comparisons GraphABI:

1. partitions observations by logical edge and selected run;
2. validates the occurrence DAG and all producer/consumer references;
3. recursively builds each execution's logical ancestry from node ID, incoming edge, branch ID,
   retry attempt, and sorted parent signatures;
4. builds an edge signature from the logical edge, branch, attempt, producer ancestry, and consumer
   ancestry;
5. pairs a baseline and candidate only when exactly one occurrence has that signature on each side;
6. evaluates every matched pair independently;
7. emits `BASELINE_ONLY` or `CANDIDATE_ONLY` insufficient evidence for unmatched signatures; and
8. emits `AMBIGUOUS` with the involved occurrence IDs when a signature is not unique.

The signature excludes occurrence IDs, timestamps, causal sequence numbers, graph versions, and
payload values. This lets equivalent causal work pair across runs even if a concurrent scheduler
chooses a different order.

## Loops and retries

Repeated logical nodes and edges have distinct occurrence IDs. Recursive ancestry distinguishes
bounded loop iterations. Retry attempts also carry an explicit positive `attempt`; failed attempts
remain in the trace and are not silently discarded. Every occurrence is evaluated under the same
edge contract unless the caller selects a narrower run before comparison.

## Fan-out, fan-in, and nested branches

Each fan-out child has its own occurrence and should carry the stable branch or map key exposed by
the framework. A fan-in execution lists every causal parent. Parent signatures are sorted, so
parallel completion order does not change pairing.

For a LangGraph fan-in that must wait for every parent, declare one list-parent edge such as
`graph.add_edge(["verifier_a", "verifier_b"], "join")`. Two separate calls such as
`graph.add_edge("verifier_a", "join")` and `graph.add_edge("verifier_b", "join")` are independent
triggers. With uneven branch depths, LangGraph can invoke the join before one declared parent has
run and invoke it again later. The recorder fails closed instead of fabricating that missing causal
parent.

If two siblings have identical ancestry, branch, and attempt, GraphABI cannot distinguish them
honestly. It reports `INSUFFICIENT_EVIDENCE` instead of falling back to timestamp proximity.

## Witnesses and impact

Findings and witnesses record baseline and candidate occurrence IDs, the pairing classification,
and a stable causal pairing key. A breaking trace 0.2 finding also follows the candidate occurrence
DAG from the direct consumer and records affected downstream occurrences. Logical topology impact
remains alongside it to describe potentially affected paths not exercised in that run.

## Trace 0.1 behavior

Trace 0.1 comparisons retain their one-observation-per-edge behavior. A simple cross-version
comparison is allowed only when both selected sides have at most one occurrence for the logical
edge. Repeated cross-version observations remain `AMBIGUOUS`. Use the explicit conservative
`upgrade_trace_bundle_v1` converter when the old trace contains sufficient singleton ancestry.
