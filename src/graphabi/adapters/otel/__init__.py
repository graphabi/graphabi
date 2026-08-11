"""Local OTLP/JSON import using the narrow GraphABI telemetry profile."""

from graphabi.adapters.otel.importer import (
    TELEMETRY_MAPPING_PROFILE,
    TelemetryImportDiagnostic,
    TelemetryImportResult,
    import_otlp_json,
    load_otlp_json,
)

__all__ = [
    "TELEMETRY_MAPPING_PROFILE",
    "TelemetryImportDiagnostic",
    "TelemetryImportResult",
    "import_otlp_json",
    "load_otlp_json",
]
