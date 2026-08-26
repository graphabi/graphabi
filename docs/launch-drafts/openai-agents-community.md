# Draft: OpenAI Agents SDK Community

```text
I published GraphABI alpha.3 with an optional OpenAI Agents SDK adapter and would value feedback
from SDK users.

GraphABI records agent activations, tools, and declared handoff payloads, then evaluates explicit
trace-observable contracts across baseline and candidate runs.

Keyless fixture:

pip install "graphabi[openai-agents]==0.1.0a3"
python -m examples.openai_agents_adapter.example

Quick start:
https://github.com/graphabi/graphabi/blob/main/docs/openai-agents-quickstart.md

Boundaries: only OpenAI Agents SDK >=0.20,<0.21 is supported today; handoffs become contract edges
only when the app supplies a HandoffEdgeSpec payload resolver. This is not automatic semantic
understanding.
```
