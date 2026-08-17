"""Framework adapter interfaces."""

from graphabi.adapters.base import FrameworkAdapter
from graphabi.adapters.detection import ADAPTER_PROJECT_HINTS, AdapterProjectHint
from graphabi.adapters.otel import (
    TELEMETRY_MAPPING_PROFILE,
    TelemetryImportDiagnostic,
    TelemetryImportResult,
    import_otlp_json,
    load_otlp_json,
)

MAINTAINED_FRAMEWORK_ADAPTERS = tuple(hint.adapter for hint in ADAPTER_PROJECT_HINTS)

__all__ = [
    "ADAPTER_PROJECT_HINTS",
    "MAINTAINED_FRAMEWORK_ADAPTERS",
    "TELEMETRY_MAPPING_PROFILE",
    "AdapterProjectHint",
    "FrameworkAdapter",
    "TelemetryImportDiagnostic",
    "TelemetryImportResult",
    "import_otlp_json",
    "load_otlp_json",
]
