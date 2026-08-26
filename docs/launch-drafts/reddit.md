# Draft: Reddit

```text
I am looking for feedback on GraphABI alpha.3, a Python tool for trace-observable semantic
contracts in agent graphs.

What it does:
- records baseline and candidate executions
- checks explicit YAML contracts on graph edges
- reports the first breaking edge, witness, and downstream impact
- keeps UNKNOWN separate from PASS when evidence is missing

Install:

pip install graphabi==0.1.0a3
graphabi demo --allow-breaking

The deterministic demo needs no API key, Docker, cloud account, or Ollama. LangGraph and OpenAI
Agents SDK are the maintained adapters today.

It is not a semantic oracle, not a hosted observability platform, and not claiming real-world
adoption yet. I am trying to learn where the first-user path is unclear.

Repo: https://github.com/graphabi/graphabi
PyPI: https://pypi.org/project/graphabi/0.1.0a3/
```
