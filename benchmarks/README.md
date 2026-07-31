# Benchmarks

Run `make benchmark` to generate ignored `latest.json` and `latest.md` measurements for the
current machine. Results cover trace loading, contract evaluation, impact analysis, and report
generation for deterministic linear graphs of approximately 10, 100, and 1,000 nodes.

Synthetic fixture construction is timed and reported separately so setup cost is visible rather
than silently excluded from the published local result.

These are transparent local measurements, not general scalability claims.
