"""Versioned report models and local renderers."""

from graphabi.reporting.models import CompatibilityReport
from graphabi.reporting.render import write_report

__all__ = ["CompatibilityReport", "write_report"]
