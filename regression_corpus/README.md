# Semantic regression corpus

This directory contains a small, deterministic GraphABI regression corpus. It is not an industry
benchmark and has not been externally validated. Its purpose is to prevent known semantic and
causal regressions in GraphABI itself and to provide inspectable examples for contract authors.

Every case has:

- a recorded baseline trace bundle
- a recorded candidate trace bundle
- an explicit consumer contract
- an expected trace-derived finding set
- a concise rationale in `manifest.yml`

The ten cases cover provenance, set preservation, units, authority, freshness, repeated loop-edge
occurrences, parallel fan-out, model migration, prompt migration, and tool migration. All values
are synthetic local fixtures. No API key or network access is used.

Run the corpus:

```bash
make corpus
```

Machine-readable output is available with:

```bash
uv run python scripts/run_regression_corpus.py --json
```

The runner loads each checked-in contract and both trace bundles, verifies the baseline against
itself, and invokes the normal semantic comparison engine for the candidate. Expected findings are
assertions only; they are never substituted for engine output.

Regenerate fixtures after an intentional definition change, then review the complete trace and
contract diff:

```bash
uv run python scripts/generate_regression_corpus.py
uv run python scripts/generate_regression_corpus.py --check
```

The corpus schema is version `0.1`. It is repository test data, not a versioned GraphABI public
interchange format.
