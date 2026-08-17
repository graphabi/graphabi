# Alpha 3 hostile validation

Status: external validation in progress. This document records controlled local experiments against public repositories. It is not an adoption claim and it does not describe upstream defects.

## Baseline

The experiments used GraphABI alpha.2 at commit `0bccea59e5c4a53df6db69ea1a099f93ea118f43`. The released source was not modified during integration. The local baseline was 194 passing tests with 91.37% coverage on Python 3.12.13, plus a clean package build and isolated doctor/demo checks.

## Targets

Four integrations succeeded: `langchain-ai/retrieval-agent-template` at `99f9121722743a4524fd9f65f3ffb151a2724587`, `langchain-ai/deepagents` at `f0446c8c8aecff243545fe0c551a6539ccf482a2`, `langchain-ai/open-swe` at `331ea489f609aec360e8575b7fef26d92faf9709`, and `openai/openai-agents-python` at `d40f5d9832c657d64ef1bd858fd0a977eec6262e`. AutoGen at `027ecf0a379bcc1d09956d46d12d44a3ad9cee14` passed its practical core and agentchat tests but was not integrated because optional dependency collection was not reproducible without a large matrix.

The reproducible commands, patches, logs, and classifications live in the separate `graphabi-lab` directory. External source is not vendored into GraphABI.

## Results

Ten controlled mutations were attempted. Five were detected as semantic `FAIL` findings with the expected first edge. Two entity-preservation mutations were detected as warning-level findings. Two authority mutations returned `UNKNOWN`. One empty-query mutation raised an upstream `IndexError` before a semantic comparison.

The positive cases show that alpha.2 can expose some schema-compatible semantic regressions in real framework code. The unresolved authority cases are equally important: alpha.2 did not turn an authority change into a false `PASS`, but it also did not produce a breaking finding. All successful reports had complete observed contract coverage, confirming that coverage is not correctness.

No external false positive was observed in this small, contract-selected sample. No pre-existing upstream bug was reported. External adoption, users, contributors, endorsements, and maintainer feedback remain zero because no outreach was performed.

## Strongest hostile criticisms

1. A contract can be a manually curated restatement of the mutation. The current cases reduce this risk by grounding contracts in packet fields and downstream code, but the sample does not establish independence.
2. The detected breaks are obvious once the contract is written. GraphABI has not yet shown that it finds a regression ordinary tests and schema validation would reliably miss across a broad corpus.
3. `WARNING` and `UNKNOWN` results limit immediate operational value. The authority cases were honest uncertainty, but they were not actionable breaking findings.
4. Instrumentation defines the available evidence. Missing metadata can make a semantic question unanswerable, and alpha.2 does not always distinguish that from a weak evaluator.
5. The current integrations use deterministic local model controls. They validate framework wiring and semantic comparison, not model behavior in production.
6. The OpenAI Agents SDK checkout reports version 0.21.1 while alpha.2 documented a `<0.21` bound. The adapter worked locally, but support boundaries need an explicit compatibility policy.

## Evidence-driven Alpha 3 work

Do not release Alpha 3 from this document alone. The justified candidates are: improve preservation evaluators so defensible entity invariants produce evidence-backed findings; make authority evidence explicit enough to separate `UNKNOWN` from a detected break; and clarify adapter version bounds. Each requires a generalized regression fixture before implementation.

No feature change was made solely to improve this campaign's score. Alpha 3 has no tag, release, or publication target yet.

## Reproduction and limitations

The complete matrix, setup friction, target selection, and exact commands are in `~/Developer/graphabi-lab`. Results are local controlled mutations, not organic upstream bugs. The campaign has not established external adoption, industry benchmark status, or universal telemetry compatibility.
