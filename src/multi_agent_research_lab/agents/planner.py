"""Planner agent — decomposes the user query before research."""

from __future__ import annotations

import json
import logging

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.llm_client import LLMClient
from multi_agent_research_lab.utils.language import response_language_instruction

logger = logging.getLogger(__name__)

_SYSTEM = """You are a focused research planner.

Given a user query, expand it into a better research plan before source search.
Return ONLY valid JSON:
{
  "intent": "what the user really wants answered",
  "scope": "what is in scope and what is out of scope",
  "key_aspects": ["3 to 6 aspects that must be covered"],
  "planning_notes": "concise plan focused on the user's actual question",
  "expanded_queries": ["3 to 5 concrete web search queries"]
}

Rules:
- Stay centered on the user's actual question; do not broaden into unrelated topics.
- If the query asks for comparison, include comparison queries.
- If the query asks for latest/current information, include freshness terms.
- If the query is Vietnamese, expanded queries can mix Vietnamese and English terms for better retrieval.
- Cover definitions, evidence, limitations, comparisons, and practical implications only when relevant.
- Keep expanded queries concise and search-engine friendly."""


class PlannerAgent(BaseAgent):
    """Creates expanded research queries from the original user prompt."""

    name = "planner"

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm = llm_client or LLMClient()

    def run(self, state: ResearchState) -> ResearchState:
        if state.expanded_queries:
            return state

        prompt = (
            f"{response_language_instruction(state.request.query)}\n\n"
            f"User query: {state.request.query}\n"
            f"Audience: {state.request.audience}\n"
            f"Max sources: {state.request.max_sources}"
        )
        llm_node = state.add_visual_node(
            label="Planner Agent\nExpand query",
            kind="agent",
            iteration=0,
            metadata={"agent": self.name, "description": "Decompose and broaden the user query."},
            parent_id=state.current_visual_node_id,
            edge_label="plan",
        )
        state.active_agent_node_id = llm_node
        tool_node = state.add_visual_node(
            label="LLMClient.complete\nPlan research",
            kind="tool",
            iteration=0,
            metadata={"agent": self.name, "model_task": "query_planning"},
            parent_id=llm_node,
            edge_label="tool:llm.complete",
        )
        try:
            resp = self._llm.complete(_SYSTEM, prompt, temperature=0.1)
            content = resp.content.strip()
            if content.startswith("```"):
                content = content.strip("`")
                content = content.removeprefix("json").strip()
            data = json.loads(content)
            queries = data.get("expanded_queries", [])
            notes = data.get("planning_notes", "")
            intent = str(data.get("intent", "")).strip()
            scope = str(data.get("scope", "")).strip()
            aspects = data.get("key_aspects", [])
            if not isinstance(queries, list):
                queries = []
            if not isinstance(aspects, list):
                aspects = []
            state.expanded_queries = [
                str(query).strip() for query in queries if str(query).strip()
            ][:5]
            aspect_block = "\n".join(f"- {aspect}" for aspect in aspects if str(aspect).strip())
            state.planning_notes = "\n".join(
                part
                for part in (
                    f"Intent: {intent}" if intent else "",
                    f"Scope: {scope}" if scope else "",
                    "Key aspects:\n" + aspect_block if aspect_block else "",
                    str(notes).strip(),
                )
                if part
            ) or "Query expanded for focused research."
            state.add_token_usage("planner", resp.input_tokens, resp.output_tokens)
        except Exception as exc:
            logger.warning("Planner failed, falling back to original query: %s", exc)
            state.expanded_queries = [state.request.query]
            state.planning_notes = "Planner fallback: use original query."

        state.add_visual_node(
            label=f"Expanded Queries\n{len(state.expanded_queries)} queries",
            kind="artifact",
            iteration=0,
            metadata={"queries": state.expanded_queries, "planning_notes": state.planning_notes},
            parent_id=tool_node,
            edge_label="output",
        )
        state.current_visual_node_id = llm_node
        return state
