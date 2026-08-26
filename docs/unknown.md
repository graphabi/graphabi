# Understanding UNKNOWN

`UNKNOWN` does not mean GraphABI is broken. It means GraphABI does not have enough trustworthy,
trace-observable evidence to justify either `PASS` or `FAIL`.

GraphABI keeps uncertainty separate from success because a silent pass is more dangerous than an
honest non-answer. Automation should treat `UNKNOWN` and `INSUFFICIENT_EVIDENCE` as unresolved
outcomes, not compatibility approvals.

## Concrete example

This authority invariant is incomplete:

```yaml
invariants:
  - id: authority_does_not_escalate
    evaluator: authority
    description: The producer must not escalate approval authority.
    severity: breaking
    source_path: output.authority_level
    maximum_allowed: reviewer
```

It names `reviewer`, but does not define what order `reviewer` belongs to. GraphABI will not guess
whether `reviewer` is higher or lower than `approver`, `publisher`, or a domain-specific label.
The result is `UNKNOWN`.

Make the assumption explicit:

```yaml
invariants:
  - id: authority_does_not_escalate
    evaluator: authority
    description: The producer must not escalate approval authority.
    severity: breaking
    source_path: output.authority_level
    maximum_allowed: reviewer
    authority_order: [draft, reviewer, approver]
```

Now GraphABI can compare labels in this contract-local order. If the trace records
`output.authority_level: approver`, the invariant can fail. If it records `draft`, it can pass. If
the trace omits `output.authority_level`, the result remains evidence-limited.

## UNKNOWN versus INSUFFICIENT_EVIDENCE

`UNKNOWN` usually means GraphABI lacks a rule, mapping, vocabulary, or evaluator needed to interpret
the observation. `INSUFFICIENT_EVIDENCE` usually means the rule is known, but the trace does not
contain the required path or occurrence evidence.

Both are deliberate non-pass results.
