# 5-minute quick start

This path uses the published alpha package and the deterministic demo. It needs Python 3.12 or
3.13. It does not need an API key, Docker, a cloud account, Ollama, or a hosted model.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install graphabi==0.1.0a3
graphabi doctor
```

Expected result: required checks pass. Optional checks can be `INFO`; that is not a failed install.

You can also run the demo without keeping an environment:

```bash
uvx --from graphabi==0.1.0a3 graphabi demo --allow-breaking
```

## Run the proof

```bash
graphabi demo --allow-breaking
```

Expected result:

```text
Structural compatibility: PASS
Semantic compatibility: FAIL
First breaking edge:
researcher -> verifier
```

The demo intentionally compares two schema-compatible LangGraph executions. The candidate returns
the same Pydantic shape as the baseline, but violates the verifier's explicit contract:
`verified=true` requires an opened supporting source. `--allow-breaking` keeps the command exit code
at `0` so the example is easy to run interactively.

Open the report path printed by the command:

```bash
graphabi report
graphabi report --open
```

The HTML report is self-contained and local. It shows the first breaking edge, the exact witness,
downstream affected nodes, and coverage. Coverage tells you which declared edges were observed and
contracted; it is not correctness.

## Initialize your project

From a new or existing project directory:

```bash
graphabi init
graphabi doctor
graphabi check .graphabi/contracts.yml
```

The generated contract is only a placeholder. Replace its graph, node, edge, and invariant names
with consumer requirements you are willing to enforce.

Next, choose a supported integration:

- [LangGraph quick start](langgraph-quickstart.md)
- [OpenAI Agents SDK quick start](openai-agents-quickstart.md)

Read [UNKNOWN](unknown.md) before wiring the result into CI.
