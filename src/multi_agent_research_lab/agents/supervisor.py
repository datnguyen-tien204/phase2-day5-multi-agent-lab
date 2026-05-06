"""Supervisor / router — decides which worker runs next and when to stop."""

from __future__ import annotations

import logging

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.config import get_settings
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.llm_client import LLMClient

logger = logging.getLogger(__name__)

_SYSTEM = """You are the Supervisor of a multi-agent research pipeline.
Decide the next step based on the current state.

Available routes:
- "researcher" — collect sources and produce research notes
- "analyst"    — analyse research notes for key claims, evidence strength, gaps
- "writer"     — synthesise final answer from notes + analysis or revise from critique
- "critic"     — fact-check and quality-score the final answer
- "done"       — workflow is complete

Respond with ONLY one word: researcher | analyst | writer | critic | done"""


class SupervisorAgent(BaseAgent):
    """Decides which worker should run next and when to stop.

    The deterministic route is intentionally preferred. This follows the lab's open
    requirement while making CI stable and mirroring AgenticAI's explicit state-machine
    idea: every route has a reason, not just a next node.
    """

    name = "supervisor"

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm = llm_client or LLMClient()
        self._settings = get_settings()

    def run(self, state: ResearchState) -> ResearchState:
        """Update `state.route_history` with the next route."""
        if state.iteration >= self._settings.max_iterations:
            logger.warning("Supervisor: max_iterations reached (%d)", state.iteration)
            state.errors.append(f"Max iterations ({self._settings.max_iterations}) reached")
            state.record_route("done", reason="max_iter_stop")
            return state

        if len(state.errors) >= 3:
            logger.error("Supervisor: too many errors (%d), stopping", len(state.errors))
            state.record_route("done", reason="error_fallback", metadata={"errors": state.errors})
            return state

        route, reason = self._deterministic_route_with_reason(state)
        if route is None:
            route = self._llm_route(state)
            reason = "llm_route"

        logger.info("Supervisor → %s (reason=%s, iter=%d)", route, reason, state.iteration)
        state.record_route(route, reason=reason)

        state.agent_results.append(
            AgentResult(
                agent=AgentName.SUPERVISOR,
                content=route,
                metadata={"iteration": state.iteration, "reason": reason, "errors": len(state.errors)},
            )
        )
        return state

    def _deterministic_route(self, state: ResearchState) -> str | None:
        """Backward-compatible helper used by the provided tests."""
        route, _reason = self._deterministic_route_with_reason(state)
        return route

    def _deterministic_route_with_reason(self, state: ResearchState) -> tuple[str | None, str]:
        """Return a route/reason without calling the LLM when the path is obvious."""
        if not state.research_notes:
            return "researcher", "missing_research"
        if not state.analysis_notes:
            return "analyst", "missing_analysis"
        if not state.final_answer:
            return "writer", "missing_final_answer"

        if state.critique_notes and state.quality_score is not None:
            needs_revision = state.quality_score < self._settings.quality_threshold
            can_revise = state.revision_rounds < self._settings.max_revision_rounds
            if needs_revision and can_revise:
                state.mark_revision_needed(state.critique_notes, state.quality_score)
                return "writer", "quality_revision"

        if not state.critique_notes:
            return "critic", "needs_quality_gate"
        return "done", "completed"

    def _llm_route(self, state: ResearchState) -> str:
        """Ask the LLM when the state is ambiguous."""
        user_prompt = (
            f"Query: {state.request.query}\n"
            f"Iteration: {state.iteration}\n"
            f"research_notes present: {bool(state.research_notes)}\n"
            f"analysis_notes present: {bool(state.analysis_notes)}\n"
            f"final_answer present: {bool(state.final_answer)}\n"
            f"critique_notes present: {bool(state.critique_notes)}\n"
            f"quality_score: {state.quality_score}\n"
            f"revision_rounds: {state.revision_rounds}\n"
            f"errors so far: {state.errors}\n"
            f"route_history: {state.route_history}"
        )
        resp = self._llm.complete(_SYSTEM, user_prompt, temperature=0.0)
        state.add_token_usage("supervisor", resp.input_tokens, resp.output_tokens)
        route = resp.content.strip().lower().split()[0]
        valid = {"researcher", "analyst", "writer", "critic", "done"}
        return route if route in valid else "done"
