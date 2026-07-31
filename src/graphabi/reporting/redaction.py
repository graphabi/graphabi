"""Best-effort masking for values that must not enter compatibility reports."""

from __future__ import annotations

import re
from typing import Any

from graphabi.models.traces import RedactedValue

_SENSITIVE_KEYS = {
    "access_key",
    "api_key",
    "authorization",
    "client_secret",
    "credential",
    "credentials",
    "password",
    "private_key",
    "secret",
    "token",
}
_SENSITIVE_SUFFIXES = ("_api_key", "_credential", "_password", "_secret", "_token")
_SECRET_PATTERNS = (
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"(?i)\b(?:sk|rk|pk)-[a-z0-9_-]{16,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{16,}\b"),
    re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/-]{12,}=*"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)


def _sensitive_key(key: object) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "_", str(key).lower()).strip("_")
    return normalized in _SENSITIVE_KEYS or normalized.endswith(_SENSITIVE_SUFFIXES)


def _secret_string(value: str) -> bool:
    return any(pattern.search(value) for pattern in _SECRET_PATTERNS)


def redact_sensitive(value: Any) -> Any:
    """Recursively mask common credential keys and unmistakable token formats."""
    if isinstance(value, dict):
        return {
            key: (
                RedactedValue(reason="sensitive value masked").model_dump(mode="json")
                if _sensitive_key(key)
                else redact_sensitive(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, tuple):
        return tuple(redact_sensitive(item) for item in value)
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, str) and _secret_string(value):
        return "[REDACTED]"
    return value
