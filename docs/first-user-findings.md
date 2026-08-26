# First-user onboarding findings

Date: 2026-08-26

Starting point:

```bash
python -m pip install graphabi==0.1.0a3
```

## Clean-room result

- Install from PyPI succeeded on Python 3.12 and 3.13.
- `graphabi doctor` passed required runtime checks and made optional OpenAI Agents support visible.
- `graphabi demo --allow-breaking` produced the expected schema `PASS`, semantic `FAIL`, first
  breaking edge, witness, downstream impact, and report paths.
- `uvx --from graphabi==0.1.0a3 graphabi demo --allow-breaking` worked from a temporary directory.
- `graphabi init` created conservative starter state without guessing topology or enabling
  enforcement.
- `graphabi check .graphabi/contracts.yml` validated the starter contract.
- The packaged LangGraph example can record baseline and candidate traces from a PyPI install and
  compare them with the packaged contract.
- The packaged OpenAI Agents fixture works only with the `openai-agents` extra, as intended.

## Hidden knowledge found

- The README still led with GitHub and local-wheel installation after PyPI publication.
- The first run path did not have a single short tutorial that started from PyPI install.
- Framework onboarding was split between example READMEs and adapter docs, and did not show the
  full trace capture to comparison path for new users.
- `UNKNOWN` was accurate in several docs, but there was no single short explanation with a concrete
  contract example.
- The generated `.graphabi/README.md` did not point users to `doctor` as the first debugging tool
  or to the maintained onboarding docs.
- `doctor` reported useful checks, but did not explicitly group required runtime checks, optional
  adapters, local project state, trace-store checks, contract checks, and report artifacts.

## Changes made from this review

- Added the PyPI-based [5-minute quick start](quickstart.md).
- Added [LangGraph](langgraph-quickstart.md) and
  [OpenAI Agents SDK](openai-agents-quickstart.md) quick starts.
- Added [UNKNOWN](unknown.md) education.
- Updated `README.md` install commands to use `graphabi==0.1.0a3` explicitly.
- Updated `graphabi init` generated guidance and `graphabi doctor` categories.
- Added `HUMAN_TEST.md`, launch drafts, and a human-only adoption ledger.
