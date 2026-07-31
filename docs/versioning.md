# Versioning policy

GraphABI uses Semantic Versioning for the Python package.

- Patch releases fix behavior without intentionally changing public APIs or versioned schemas.
- Minor releases may add backward-compatible fields, evaluators, commands, and adapters.
- Major releases may remove or change public behavior after migration documentation.

Contract, trace, and report documents carry their own schema version. Readers reject unsupported
versions. A package release may support multiple document versions during migration. Adding an
optional field is normally compatible; changing meaning, required fields, status interpretation, or
serialized types requires a new document version.

The `0.x` package line is alpha: APIs may evolve, but maintainers still document public changes,
include migrations where practical, and never silently reinterpret `UNKNOWN` as `PASS`.
