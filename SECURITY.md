# Security policy

## Supported versions

Only the latest tagged v0.1 alpha is supported with security fixes.

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability or accidental secret exposure. Before the
public repository is created, contact the repository owner privately. After creation, enable GitHub
Private Vulnerability Reporting and use the repository's **Security → Report a vulnerability**
flow. The maintainer should acknowledge a report within seven days and provide a status update
within fourteen days.

Include affected version, reproduction steps, impact, and any proposed mitigation. Do not include
real customer data, credentials, or third-party personal data.

## Security boundaries

GraphABI reads local contracts, traces, SQLite databases, and report files. The default demo makes
no network calls. HTML reports may contain local trace payloads and should not be published without
review. The local report server binds to `127.0.0.1` by default and is not hardened for untrusted
multi-user access.

Dependencies are locked by `uv.lock`; release workflows build but do not publish automatically.
