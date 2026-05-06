"""Agent-as-tool registry.

Keeps Supervisor/Workflow decoupled from concrete worker implementations while
preserving the assignment's required agent modules.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from multi_agent_research_lab.core.state import ResearchState


@dataclass(frozen=True)
class AgentTool:
    name: str
    description: str
    run: Callable[[ResearchState], ResearchState]
    is_concurrency_safe: bool = False

    def execute(self, state: ResearchState) -> ResearchState:
        return self.run(state)
