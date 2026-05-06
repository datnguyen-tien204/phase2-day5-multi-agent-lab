"""Small context-management layer.

AgenticAI uses multiple context-defense layers (truncate, microcompact, LLM
compact). This lab keeps it simple and deterministic: trim oversized text fields and
record compact boundaries in ResearchState for debugging.
"""

from __future__ import annotations

from multi_agent_research_lab.core.state import ResearchState


class ContextManager:
    """Deterministic context compaction for lab-scale state."""

    def __init__(self, max_chars: int = 8_000) -> None:
        self.max_chars = max_chars

    def compact(self, state: ResearchState) -> ResearchState:
        for field in ("research_notes", "analysis_notes", "critique_notes"):
            value = getattr(state, field)
            if isinstance(value, str) and len(value) > self.max_chars:
                compacted = self._middle_trim(value)
                setattr(state, field, compacted)
                state.add_compact_boundary(field, len(value), len(compacted))
        return state

    def compact_source_snippets(self, state: ResearchState, max_snippet_chars: int = 900) -> ResearchState:
        for source in state.sources:
            if len(source.snippet) > max_snippet_chars:
                source.snippet = source.snippet[: max_snippet_chars - 20].rstrip() + " ...[truncated]"
        return state

    def _middle_trim(self, text: str) -> str:
        keep = max(self.max_chars - 80, 100)
        head = keep // 2
        tail = keep - head
        return text[:head].rstrip() + "\n\n...[context compacted]...\n\n" + text[-tail:].lstrip()
