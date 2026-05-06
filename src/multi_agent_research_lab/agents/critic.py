"""Critic agent — fact-checking, citation coverage, and quality gate."""

from __future__ import annotations

import logging

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.llm_client import LLMClient
from multi_agent_research_lab.utils.language import response_language_instruction

logger = logging.getLogger(__name__)

_SYSTEM = """You are a rigorous peer reviewer and fact-checker.

Given a final research answer and its source material, evaluate:

## Factual Accuracy
- Does each major claim appear in or follow logically from the sources?
- Flag any claims that seem hallucinated or unsupported.

## Citation Coverage
- Are all major claims backed by at least one citation?
- List any uncited claims.

## Clarity and Structure
- Is the answer well-structured and appropriate for the audience?
- Any confusing or ambiguous passages?

## Overall Quality Score
- Give an integer score 1-10 with justification.
- 9-10: Excellent, publish-ready. 7-8: Good, minor fixes. 5-6: Acceptable, notable gaps.
- Below 5: Needs significant revision.

## Recommended Revisions
- List up to 3 specific improvements (or "None needed" if score ≥ 8).

Format your response as structured markdown. Be fair but strict."""


class CriticAgent(BaseAgent):
    """Validates final answer: fact-check, citation coverage, quality score."""

    name = "critic"

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm = llm_client or LLMClient()

    def run(self, state: ResearchState) -> ResearchState:
        """Validate final_answer and populate `state.critique_notes`."""
        if not state.final_answer:
            logger.warning("Critic: no final_answer to review")
            state.critique_notes = "No final answer available for review."
            return state

        logger.info("Critic: reviewing final answer (%d words)", len(state.final_answer.split()))

        source_block = "\n".join(
            f"[{i+1}] {s.title}: {s.snippet[:200]}"
            for i, s in enumerate(state.sources)
        )

        user_prompt = (
            f"{response_language_instruction(state.request.query)}\n\n"
            f"Query: {state.request.query}\n\n"
            f"Final Answer to Review:\n{state.final_answer}\n\n"
            f"Source Material:\n{source_block or '(none)'}"
        )

        llm_node = state.add_visual_node(
            label="LLMClient.complete\nCritique answer",
            kind="tool",
            iteration=state.iteration,
            metadata={"agent": self.name, "model_task": "quality_gate"},
            parent_id=state.active_agent_node_id,
            edge_label="tool:llm.complete",
        )
        resp = self._llm.complete(_SYSTEM, user_prompt, temperature=0.1)
        state.critique_notes = resp.content
        state.add_token_usage("critic", resp.input_tokens, resp.output_tokens)

        quality_score = self._extract_score(resp.content)
        state.quality_score = quality_score
        state.add_visual_node(
            label=f"Critique\nScore: {quality_score if quality_score is not None else 'N/A'}/10",
            kind="artifact",
            iteration=state.iteration,
            metadata={"quality_score": quality_score},
            parent_id=llm_node,
            edge_label="output",
        )

        state.agent_results.append(
            AgentResult(
                agent=AgentName.CRITIC,
                content=resp.content,
                metadata={
                    "quality_score": quality_score,
                    "tokens_in": resp.input_tokens,
                    "tokens_out": resp.output_tokens,
                    "cost_usd": resp.cost_usd,
                },
            )
        )
        logger.info("Critic: quality_score=%s", quality_score)
        return state

    @staticmethod
    def _extract_score(critique: str) -> float | None:
        import re

        patterns = [r"score[:\s]+(\d+)", r"(\d+)\s*/\s*10", r"(\d+)\s*out of\s*10"]
        for pat in patterns:
            m = re.search(pat, critique, re.IGNORECASE)
            if m:
                val = int(m.group(1))
                return min(max(float(val), 0), 10)
        return None
