# Causal occurrence pairing for loops and fan-out

Status: design only. Trace schema 0.1 still permits one observation per edge and run.

## Problem

An edge ID is not enough when a graph revisits a node, fans out work, retries a tool, or joins
parallel branches. Pairing the first baseline observation with the first candidate observation can
compare unrelated causal events and produce a false verdict. Ordering by wall-clock time is also
unsafe because concurrent spans can overlap and clocks can skew.

## Proposed identity

The next trace schema should give every node execution an `occurrence_id` unique within the run.
Every edge crossing should carry:

- its own `occurrence_id`;
- `producer_occurrence_id` and `consumer_occurrence_id`;
- zero or more `causal_parent_ids` for joins;
- a stable branch or map key when the framework provides one;
- an attempt number for retries;
- the existing logical node and edge IDs.

IDs must come from adapter-observed execution identity, not payload hashes. Equal payloads can belong
to different causal events, and hashing them can leak sensitive data.

## Pairing algorithm

1. Partition observations by logical graph, edge, and selected run.
2. Build a directed acyclic occurrence graph from producer, consumer, and causal parent IDs. A
   logical graph may contain loops while one completed run's occurrence graph remains acyclic.
3. Pair baseline and candidate occurrences first by stable branch key and retry attempt when both
   adapters recorded them.
4. Within that partition, compare causal ancestry signatures made from logical node and edge IDs,
   not timestamps or values.
5. If exactly one pairing remains, evaluate the edge contract for that pair.
6. If zero or multiple pairings remain, return `INSUFFICIENT_EVIDENCE` with the ambiguous occurrence
   IDs. Never choose the nearest timestamp as a hidden fallback.

## Fan-out and joins

Each mapped child gets a distinct occurrence. A join records every causal parent instead of
selecting one. Coverage reports observed and unobserved occurrence partitions in addition to
logical branches. Impact analysis starts at the breaking consumer occurrence and follows occurrence
edges, while the report may collapse them to logical nodes for a readable summary.

## Retries

Retries are separate occurrences with a shared logical operation ID and increasing attempt number.
Policy must say whether compatibility is evaluated per attempt, on the terminal successful attempt,
or on the retry sequence. GraphABI should not silently discard failed attempts.

## Schema and compatibility plan

- Introduce a new trace schema version rather than adding ambiguous optional identity to 0.1.
- Keep a strict 0.1 reader that rejects duplicate edge observations as it does today.
- Provide an explicit 0.1-to-next converter only for runs where every logical edge occurred once.
- Version coverage and report models with the trace change.
- Require property tests for permutation stability, ambiguous joins, nested loops, retries, fan-out,
  missing parents, and disconnected occurrences.

Implementation should wait until at least two real adapters can supply these identities without
guessing. Until then, GraphABI states the limitation and rejects ambiguous duplicates.
