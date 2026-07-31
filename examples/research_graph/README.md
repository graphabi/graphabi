# Research graph example

This deterministic LangGraph demonstrates a schema-compatible semantic regression across:

```text
researcher → verifier → decision_maker → publisher
```

- `models.py` defines the exact shared Pydantic schemas.
- `baseline.py` opens and checks a local source.
- `candidate.py` is an **intentionally broken demo fixture** that records failed source access while
  returning schema-valid `verified=true`.
- `graph.py` builds both real LangGraph executions through the adapter.
- `contracts.yml` states the verifier's consumer-driven assumptions.
- `fixtures/` contains synthetic public evidence only.

Run the supported orchestration from the repository root:

```bash
make demo
```

Do not copy `candidate.py` behavior into production code.
