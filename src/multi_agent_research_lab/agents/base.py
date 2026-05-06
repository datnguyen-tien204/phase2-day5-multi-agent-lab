"""Base agent contract."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.observability.tracing import trace_span


class BaseAgent(ABC):
    """Minimal interface every agent must implement.

    Improvements vs skeleton:
    - Auto trace_span wrapping via `execute()`
    - Structured logging
    - Token usage forwarded to state
    """

    name: str
    logger: logging.Logger

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls.logger = logging.getLogger(f"agents.{getattr(cls, 'name', cls.__name__)}")

    @abstractmethod
    def run(self, state: ResearchState) -> ResearchState:
        """Read and update shared state, then return it."""

    def execute(self, state: ResearchState) -> ResearchState:
        """Public entry-point: wraps run() with tracing and error handling."""
        with trace_span(
            f"agent:{self.name}",
            attributes={"iteration": state.iteration, "agent": self.name},
            state=state,
        ) as span:
            try:
                updated = self.run(state)
                span["attributes"]["status"] = "ok"
                return updated
            except Exception as exc:
                span["attributes"]["status"] = "error"
                state.errors.append(f"{self.name}: {exc}")
                raise
