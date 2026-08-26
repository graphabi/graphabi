# Draft: Hacker News Show HN

Title:

```text
Show HN: GraphABI, trace-observable semantic contracts for agent graphs
```

Post:

```text
GraphABI is an alpha Python tool for testing explicit, trace-observable semantic contracts across
changes to agent systems.

It records baseline and candidate graph executions, evaluates YAML contracts on graph edges, and
shows the first breaking edge plus downstream impact. The current demo is deterministic: the
candidate keeps the same Pydantic schema but returns verified=true without an opened supporting
source, so structural compatibility passes while semantic compatibility fails.

Install:

pip install graphabi==0.1.0a3
graphabi demo --allow-breaking

Supported adapters today are LangGraph and OpenAI Agents SDK. It is not a semantic oracle, not a
hosted observability backend, and not evidence of broad adoption. UNKNOWN is a first-class result
when the trace or contract lacks enough evidence to justify PASS or FAIL.

Repo: https://github.com/graphabi/graphabi
PyPI: https://pypi.org/project/graphabi/0.1.0a3/
```
