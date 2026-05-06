"""Writer agent — produces final answer from research and analysis notes."""

from __future__ import annotations

import logging

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.llm_client import LLMClient
from multi_agent_research_lab.utils.language import response_language_instruction

logger = logging.getLogger(__name__)

_SYSTEM = """You are a skilled technical writer. Synthesise research notes and analysis into
a polished, well-structured response.

Requirements:
- Write clearly for the specified audience.
- Open with a 1-2 sentence executive summary.
- Structure with markdown headers (##).
- Cite sources inline using [Title](URL) format when URLs are available, else [Title].
- End with a "## References" section listing all sources used.
- Target ~500 words (can be longer for complex topics, shorter for simple ones).
- No fluff, no filler — every sentence must add value.
- If analysis identified weak evidence, mention it honestly."""


class WriterAgent(BaseAgent):
    """Produces final answer from research and analysis notes."""

    name = "writer"

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm = llm_client or LLMClient()

    def run(self, state: ResearchState) -> ResearchState:
        """Populate `state.final_answer`."""
        logger.info("Writer: synthesising final answer")

        source_list = "\n".join(
            f"[{i+1}] {s.title} — {s.url or 'no URL'}"
            for i, s in enumerate(state.sources)
        )

        revision_block = (
            f"\n\nPrior Critique / Revision Request:\n{state.revision_feedback}"
            if state.revision_feedback
            else ""
        )
        user_prompt = (
            f"{response_language_instruction(state.request.query)}\n\n"
            f"Query: {state.request.query}\n"
            f"Audience: {state.request.audience}\n\n"
            f"Research Notes:\n{state.research_notes or '(none)'}\n\n"
            f"Analysis:\n{state.analysis_notes or '(none)'}\n\n"
            f"Available Sources:\n{source_list or '(none)'}"
            f"{revision_block}"
        )

        llm_node = state.add_visual_node(
            label="LLMClient.complete\nWrite final answer",
            kind="tool",
            iteration=state.iteration,
            metadata={"agent": self.name, "model_task": "final_answer"},
            parent_id=state.active_agent_node_id,
            edge_label="tool:llm.complete",
        )
        resp = self._llm.complete(_SYSTEM, user_prompt, temperature=0.4)
        state.final_answer = resp.content
        state.revision_feedback = None
        state.add_token_usage("writer", resp.input_tokens, resp.output_tokens)
        state.add_visual_node(
            label="Final Answer",
            kind="artifact",
            iteration=state.iteration,
            metadata={"words": len(resp.content.split())},
            parent_id=llm_node,
            edge_label="output",
        )

        state.agent_results.append(
            AgentResult(
                agent=AgentName.WRITER,
                content=resp.content,
                metadata={
                    "tokens_in": resp.input_tokens,
                    "tokens_out": resp.output_tokens,
                    "cost_usd": resp.cost_usd,
                    "word_count": len(resp.content.split()),
                },
            )
        )
        logger.info("Writer: done (%d words)", len(resp.content.split()))
        return state
