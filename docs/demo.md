# Deterministic research demo

The mandatory example is a linear LangGraph:

```text
researcher → verifier → decision_maker → publisher
```

`publisher` is terminal and side-effecting in the contract. The nodes call no hosted model and no
external service.

## Baseline execution

The baseline researcher opens `fixtures/helios-study.txt`, extracts a claim that appears verbatim,
hashes the source content, records the successful file tool call and source-access event, checks
support, and then sets `verified=true` and evidential confidence. It includes both entities required
by the verifier.

## Candidate execution

`candidate.py` is prominently labeled as an intentionally broken demonstration fixture. It attempts
to open a missing local file and records the failure, but returns `verified=true`, high writing-
quality confidence, the unaccessed citation, and one missing entity. It constructs the same
`ResearchResult` Pydantic model as the baseline.

## What `graphabi demo` does

1. Clears `.graphabi/demo/` and `.graphabi/reports/latest/`.
2. Runs baseline as `baseline-001` and candidate as `candidate-003`.
3. Validates both objects with Pydantic and the same generated JSON Schema.
4. Converts adapter-captured executions to versioned traces.
5. Saves SQLite, JSON, and JSONL trace data.
6. Reloads both runs from SQLite and proves the recorded baseline passes enforced contracts.
7. Evaluates the recorded candidate and identifies `researcher_to_verifier` first.
8. Computes the path through `verifier`, `decision_maker`, and `publisher`.
9. Generates machine JSON and offline HTML from one report model.

Run:

```bash
make demo
graphabi report --open
```

Without `--allow-breaking`, `graphabi demo` exits `2` because the candidate is incompatible. Exit
code `0` is reserved for a compatible result or an explicitly accepted demonstration break.

The demo asserts a narrow claim: identical schemas can conceal a violated, explicit consumer
assumption, and trace evidence can expose one concrete counterexample. It does not establish
general semantic understanding.
