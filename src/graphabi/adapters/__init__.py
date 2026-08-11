"""Framework adapter interfaces."""

from graphabi.adapters.base import FrameworkAdapter
from graphabi.adapters.otel import (
    TELEMETRY_MAPPING_PROFILE,
    TelemetryImportDiagnostic,
    TelemetryImportResult,
    import_otlp_json,
    load_otlp_json,
)

MAINTAINED_FRAMEWORK_ADAPTERS = ("langgraph", "openai-agents")

__all__ = [
    "MAINTAINED_FRAMEWORK_ADAPTERS",
    "TELEMETRY_MAPPING_PROFILE",
    "FrameworkAdapter",
    "TelemetryImportDiagnostic",
    "TelemetryImportResult",
    "import_otlp_json",
    "load_otlp_json",
]
