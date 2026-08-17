# Security policy

## Supported versions

Only the latest tagged v0.1 alpha is supported with security fixes.

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability or accidental secret exposure. Use
GitHub's **Security → Report a vulnerability** flow; private vulnerability reporting is enabled for
this repository. The maintainer should acknowledge a report within seven days and provide a status
update within fourteen days.

Include affected version, reproduction steps, impact, and any proposed mitigation. Do not include
real customer data, credentials, or third-party personal data.

## Security boundaries

GraphABI reads local contracts, traces, SQLite databases, and report files. The default demo makes
no network calls. HTML strings are escaped and reports mask common credential keys, token formats,
and local absolute paths, but masking is not general DLP: reports, raw exports, and databases must
still be reviewed before publication. The local report server binds to `127.0.0.1` by default and
is not hardened for untrusted multi-user access.

Dependencies are locked by `uv.lock`; release workflows build but do not publish automatically.
