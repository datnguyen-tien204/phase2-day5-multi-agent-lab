"""Analyst agent — turns research notes into structured insights."""

from __future__ import annotations

import logging

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.llm_client import LLMClient
from multi_agent_research_lab.utils.language import response_language_instruction

logger = logging.getLogger(__name__)

_SYSTEM = """You are a critical analyst. Given research notes, produce a structured analysis.

Your analysis MUST contain:
## Key Claims
- List the 3-5 strongest, most supported claims.

## Evidence Strength
- For each claim, rate evidence: Strong / Moderate / Weak and explain why.

## Conflicting Viewpoints
- Highlight any disagreements between sources.

## Knowledge Gaps
- What is NOT answered by the current research? What would require deeper investigation?

## Actionable Insights
- 2-3 concrete takeaways for the target audience.

Be concise (300-450 words). Be rigorous — flag weak evidence explicitly."""


class AnalystAgent(BaseAgent):
    """Turns research notes into structured insights."""

    name = "analyst"

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm = llm_client or LLMClient()

    def run(self, state: ResearchState) -> ResearchState:
        """Populate `state.analysis_notes`."""
        if not state.research_notes:
            logger.warning("Analyst: no research_notes available, skipping")
            state.analysis_notes = "No research notes available for analysis."
            return state

        logger.info("Analyst: analysing research notes (%d chars)", len(state.research_notes))

        user_prompt = (
            f"{response_language_instruction(state.request.query)}\n\n"
            f"Research Query: {state.request.query}\n"
            f"Audience: {state.request.audience}\n\n"
            f"Research Notes:\n{state.research_notes}"
        )

        llm_node = state.add_visual_node(
            label="LLMClient.complete\nAnalyse evidence",
            kind="tool",
            iteration=state.iteration,
            metadata={"agent": self.name, "model_task": "analysis"},
            parent_id=state.active_agent_node_id,
            edge_label="tool:llm.complete",
        )
        resp = self._llm.complete(_SYSTEM, user_prompt, temperature=0.1)
        state.analysis_notes = resp.content
        state.add_token_usage("analyst", resp.input_tokens, resp.output_tokens)
        state.add_visual_node(
            label="Analysis Notes",
            kind="artifact",
            iteration=state.iteration,
            metadata={"chars": len(resp.content)},
            parent_id=llm_node,
            edge_label="output",
        )

        state.agent_results.append(
            AgentResult(
                agent=AgentName.ANALYST,
                content=resp.content,
                metadata={
                    "tokens_in": resp.input_tokens,
                    "tokens_out": resp.output_tokens,
                    "cost_usd": resp.cost_usd,
                },
            )
        )
        logger.info("Analyst: done (%d tokens out)", resp.output_tokens)
        return state
