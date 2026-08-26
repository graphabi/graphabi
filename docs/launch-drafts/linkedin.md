# Draft: LinkedIn

```text
I published GraphABI alpha.3 to PyPI.

GraphABI tests explicit, trace-observable semantic contracts across changes to agent systems. It
records baseline and candidate executions, checks YAML contracts on graph edges, and reports the
first breaking edge plus downstream impact.

The current deterministic demo shows a schema-compatible regression: both versions satisfy the same
Pydantic model, but the candidate returns verified=true without opening supporting evidence.

Install:

pip install graphabi==0.1.0a3
graphabi demo --allow-breaking

Supported adapters today: LangGraph and OpenAI Agents SDK. This is alpha software, local-first, and
does not claim automatic semantic understanding or external adoption.

https://github.com/graphabi/graphabi
https://pypi.org/project/graphabi/0.1.0a3/
```
