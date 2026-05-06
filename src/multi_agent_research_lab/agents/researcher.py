"""Researcher agent — collects sources and distils research notes."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.config import get_settings
from multi_agent_research_lab.core.schemas import AgentName, AgentResult, SourceDocument
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.llm_client import LLMClient
from multi_agent_research_lab.services.permission import PermissionDecision, PermissionPolicy
from multi_agent_research_lab.services.search_client import SearchClient
from multi_agent_research_lab.utils.language import response_language_instruction

logger = logging.getLogger(__name__)

_SYSTEM = """You are an expert research assistant. Given a research query and a set of source
documents, produce clear, factual research notes.

Rules:
- Summarise the most important facts from the sources.
- Cite each source by its index number [1], [2], etc.
- Identify 3-5 key sub-topics or themes.
- Note any conflicting or uncertain information.
- Keep total length to 400-600 words.
- Do NOT produce a final essay — produce structured notes."""


class ResearcherAgent(BaseAgent):
    """Collects sources and creates concise research notes.

    Search is treated as a read-only/network action. When enabled, a small fan-out
    runs query variants concurrently, mirroring AgenticAI's concurrency-safe
    partitioning without changing the required project structure.
    """

    name = "researcher"

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        search_client: SearchClient | None = None,
    ) -> None:
        self._llm = llm_client or LLMClient()
        self._search = search_client or SearchClient(llm_client=self._llm)
        self._settings = get_settings()
        self._permissions = PermissionPolicy()

    def run(self, state: ResearchState) -> ResearchState:
        """Populate `state.sources` and `state.research_notes`."""
        q = state.request
        logger.info("Researcher: searching for '%s'", q.query[:60])

        check = self._permissions.check(f"search network: {q.query}")
        if check.decision != PermissionDecision.ALLOW:
            state.errors.append(f"Research search blocked: {check.reason}")
            state.research_notes = "Search was blocked by permission policy."
            return state

        sources = self._collect_sources(state, q.query, q.max_sources)
        state.sources.extend(sources)
        state.sources = self._dedupe_sources(state.sources)[: q.max_sources]

        source_block = "\n\n".join(
            f"[{i+1}] **{s.title}**\n"
            f"URL: {s.url or 'N/A'}\n"
            f"Snippet and fetched context:\n{s.snippet}"
            for i, s in enumerate(state.sources)
        )
        user_prompt = f"Query: {q.query}\n\nAudience: {q.audience}\n\nSources:\n{source_block}"
        user_prompt = f"{response_language_instruction(q.query)}\n\n{user_prompt}"

        llm_node = state.add_visual_node(
            label="LLMClient.complete\nSynthesize research notes",
            kind="tool",
            iteration=state.iteration,
            metadata={"agent": self.name, "model_task": "research_synthesis"},
            parent_id=state.active_agent_node_id,
            edge_label="tool:llm.complete",
        )
        resp = self._llm.complete(_SYSTEM, user_prompt, temperature=0.2)
        state.research_notes = resp.content
        state.add_token_usage("researcher", resp.input_tokens, resp.output_tokens)
        state.add_visual_node(
            label="Research Notes",
            kind="artifact",
            iteration=state.iteration,
            metadata={"chars": len(resp.content), "sources_found": len(state.sources)},
            parent_id=llm_node,
            edge_label="output",
        )

        state.agent_results.append(
            AgentResult(
                agent=AgentName.RESEARCHER,
                content=resp.content,
                metadata={
                    "sources_found": len(state.sources),
                    "tokens_in": resp.input_tokens,
                    "tokens_out": resp.output_tokens,
                    "cost_usd": resp.cost_usd,
                    "parallel_research": self._settings.enable_parallel_research,
                },
            )
        )
        logger.info("Researcher: done (%d sources, %d tokens)", len(state.sources), resp.output_tokens)
        return state

    def _collect_sources(self, state: ResearchState, query: str, max_sources: int) -> list[SourceDocument]:
        if not self._settings.enable_parallel_research or max_sources <= 2:
            return self._run_search_tool(state, query, max_sources)

        queries = state.expanded_queries or [
            query,
            f"{query} evidence benchmarks limitations",
            f"{query} production best practices",
        ]
        queries = [q for q in queries if q][:5]
        per_query = max(2, max_sources // 2)
        results: list[SourceDocument] = []
        with ThreadPoolExecutor(max_workers=min(3, len(queries))) as pool:
            future_map = {pool.submit(self._search.search, subquery, per_query): subquery for subquery in queries}
            for future in as_completed(future_map):
                subquery = future_map[future]
                try:
                    docs = future.result()
                    tool_node = state.add_visual_node(
                        label=f"SearchClient.search\n{subquery[:60]}",
                        kind="tool",
                        iteration=state.iteration,
                        metadata={
                            "agent": self.name,
                            "query": subquery,
                            "max_results": per_query,
                            "mode": "parallel",
                        },
                        parent_id=state.active_agent_node_id,
                        edge_label="tool:search",
                    )
                    state.add_visual_node(
                        label=f"Search Results\n{len(docs)} sources",
                        kind="artifact",
                        iteration=state.iteration,
                        metadata={"query": subquery, "count": len(docs)},
                        parent_id=tool_node,
                        edge_label="returns",
                    )
                    results.extend(docs)
                except Exception as exc:  # keep research resilient; SearchClient has fallback paths.
                    logger.warning("Research subquery failed: %s", exc)
        return self._dedupe_sources(results)[:max_sources]

    def _run_search_tool(self, state: ResearchState, query: str, max_results: int) -> list[SourceDocument]:
        """Record search as a tool call for visualisation, then execute it."""
        tool_node = state.add_visual_node(
            label=f"SearchClient.search\n{query[:60]}",
            kind="tool",
            iteration=state.iteration,
            metadata={"agent": self.name, "query": query, "max_results": max_results, "mode": "serial"},
            parent_id=state.active_agent_node_id,
            edge_label="tool:search",
        )
        docs = self._search.search(query, max_results=max_results)
        state.add_visual_node(
            label=f"Search Results\n{len(docs)} sources",
            kind="artifact",
            iteration=state.iteration,
            metadata={"query": query, "count": len(docs)},
            parent_id=tool_node,
            edge_label="returns",
        )
        return docs

    @staticmethod
    def _dedupe_sources(sources: list[SourceDocument]) -> list[SourceDocument]:
        seen: set[str] = set()
        unique: list[SourceDocument] = []
        for source in sources:
            key = source.url or source.title
            if key not in seen:
                seen.add(key)
                unique.append(source)
        return unique
