"""Conservative dependency hints for maintained framework adapters."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AdapterProjectHint:
    """Manifest dependency and recording guidance for one maintained adapter."""

    adapter: str
    distributions: tuple[str, ...]
    recording_guidance: str
    documentation: str


ADAPTER_PROJECT_HINTS = (
    AdapterProjectHint(
        adapter="langgraph",
        distributions=("langgraph",),
        recording_guidance=(
            "Wrap declared nodes with LangGraphRecorder and explicit EdgeSpec definitions, then "
            "export the returned TraceBundle."
        ),
        documentation="https://github.com/graphabi/graphabi/blob/main/docs/extensions.md",
    ),
    AdapterProjectHint(
        adapter="openai-agents",
        distributions=("openai-agents",),
        recording_guidance=(
            "Run through OpenAIAgentsAdapter and declare HandoffEdgeSpec payload resolvers for "
            "handoffs that represent contract edges."
        ),
        documentation=(
            "https://github.com/graphabi/graphabi/blob/main/docs/openai-agents-adapter.md"
        ),
    ),
)

__all__ = ["ADAPTER_PROJECT_HINTS", "AdapterProjectHint"]
