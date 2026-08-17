# Project initialization

`graphabi init [DIRECTORY]` creates explicit local onboarding files under `.graphabi/`:

| File | Purpose |
|---|---|
| `config.yml` | Detected adapter hints, local paths, and non-enforcement policy |
| `contracts.yml` | Valid placeholder contract that requires human replacement and review |
| `README.md` | Trace-recording guidance and exact next commands |
| `.gitignore` | Excludes runtime databases, traces, imports, reports, and suggestions |

The command does not create a database, run a graph, make network calls, discover topology, infer
contracts, or enable enforcement. Existing generated files cause an actionable error. `--force`
replaces only the four starter files and leaves other `.graphabi/` content untouched.

## Context detection

Detection is limited to declared dependencies in root `pyproject.toml` and `requirements*.txt`
files. It recognizes the maintained `langgraph` and `openai-agents` distributions, including
PEP 503-equivalent hyphen, underscore, and dot spellings. It also reads PEP 621 dependency lists,
dependency groups, and Poetry dependency tables.

Detection does not inspect imports or execute project code. A detected dependency is advisory: it
does not prove the framework is used. No dependency match produces a framework-independent
`TraceBundle` and local OTLP/JSON guidance instead of guessing.

## Generated contract policy

The starter contract is marked `EXAMPLE_NOT_ENFORCED` in config and comments. Replace every graph,
node, edge, and invariant placeholder with reviewed consumer requirements. GraphABI uses the file
only when it is passed explicitly to a command such as:

```bash
graphabi check .graphabi/contracts.yml
graphabi compare \
  --baseline-run BASELINE_RUN_ID \
  --candidate-run CANDIDATE_RUN_ID \
  --contract .graphabi/contracts.yml \
  --database .graphabi/traces.db
```

`graphabi infer` continues to emit only `SUGGESTED: NOT ENFORCED` candidates and never modifies the
starter contract.
