# Draft: LangGraph Community

```text
I published GraphABI alpha.3 and would value feedback from LangGraph users.

GraphABI instruments LangGraph executions, records baseline and candidate traces, evaluates
explicit semantic contracts on graph edges, and reports the first breaking edge plus downstream
impact.

The deterministic demo uses a small LangGraph where the candidate preserves the Pydantic schema but
violates the verifier's evidence contract:

pip install graphabi==0.1.0a3
graphabi demo --allow-breaking

LangGraph quick start:
https://github.com/graphabi/graphabi/blob/main/docs/langgraph-quickstart.md

Boundaries: no automatic topology discovery, no universal semantic understanding, and UNKNOWN is a
first-class unresolved result when evidence is insufficient.
```
