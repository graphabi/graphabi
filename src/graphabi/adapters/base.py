"""Public framework adapter protocol."""

from __future__ import annotations

from typing import Any, Protocol

from graphabi.models.traces import TraceBundle


class FrameworkAdapter(Protocol):
    """Minimal boundary required for framework instrumentation."""

    framework_name: str

    def invoke(self, graph: Any, input_data: dict[str, Any]) -> TraceBundle:
        """Invoke an instrumented graph and return framework-neutral traces."""
        ...
