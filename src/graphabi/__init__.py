"""GraphABI public package."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("graphabi")
except PackageNotFoundError:  # pragma: no cover - source tree without installation
    __version__ = "0.1.0a3"

__all__ = ["__version__"]
