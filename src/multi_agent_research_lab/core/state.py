"""Shared state for the multi-agent workflow.

Single source of truth passed through every agent. Extend when adding new agents.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from multi_agent_research_lab.core.schemas import AgentResult, ResearchQuery, SourceDocument


class TokenUsage(BaseModel):
    """Per-agent token accounting."""

    agent: str
    input_tokens: int = 0
    output_tokens: int = 0


class Transition(BaseModel):
    """Auditable state-machine transition."""

    from_route: str | None = None
    to_route: str
    reason: str
    iteration: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class VisualNode(BaseModel):
    """Graph node used by the frontend visualiser."""

    id: str
    label: str
    kind: str
    iteration: int = 0
    sequence: int = 0
    status: str = "completed"
    metadata: dict[str, Any] = Field(default_factory=dict)


class VisualEdge(BaseModel):
    """Graph edge used by the frontend visualiser."""

    id: str
    source: str
    target: str
    label: str | None = None
    kind: str = "flow"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResearchState(BaseModel):
    """Single source of truth passed through the workflow."""

    request: ResearchQuery
    iteration: int = 0
    route_history: list[str] = Field(default_factory=list)

    # Agent outputs
    planning_notes: str | None = None
    expanded_queries: list[str] = Field(default_factory=list)
    sources: list[SourceDocument] = Field(default_factory=list)
    research_notes: str | None = None
    analysis_notes: str | None = None
    critique_notes: str | None = None
    final_answer: str | None = None

    # AgenticAI-inspired additions: explicit loop transitions and quality gate state.
    transitions: list[Transition] = Field(default_factory=list)
    quality_score: float | None = Field(default=None, ge=0, le=10)
    revision_rounds: int = 0
    revision_feedback: str | None = None
    compact_boundaries: list[dict[str, Any]] = Field(default_factory=list)

    # Visualisation / observability
    agent_results: list[AgentResult] = Field(default_factory=list)
    trace: list[dict[str, Any]] = Field(default_factory=list)
    token_usage: list[TokenUsage] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    visual_nodes: list[VisualNode] = Field(default_factory=list)
    visual_edges: list[VisualEdge] = Field(default_factory=list)
    visual_sequence: int = 0
    current_visual_node_id: str | None = None
    active_agent_node_id: str | None = None

    # Status
    status: str = "running"  # running | done | failed

    # ── helpers ────────────────────────────────────────────────
    def record_route(
        self,
        route: str,
        reason: str = "next_turn",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        previous = self.route_history[-1] if self.route_history else None
        self.route_history.append(route)
        self.iteration += 1
        self.transitions.append(
            Transition(
                from_route=previous,
                to_route=route,
                reason=reason,
                iteration=self.iteration,
                metadata=metadata or {},
            )
        )

    def add_trace_event(self, name: str, payload: dict[str, Any]) -> None:
        self.trace.append({"name": name, "payload": payload})

    def add_token_usage(self, agent: str, input_tokens: int, output_tokens: int) -> None:
        self.token_usage.append(
            TokenUsage(agent=agent, input_tokens=input_tokens, output_tokens=output_tokens)
        )

    def mark_revision_needed(self, feedback: str, score: float | None = None) -> None:
        self.revision_rounds += 1
        self.revision_feedback = feedback
        self.quality_score = score
        # Clear critique so Supervisor can send writer output back through Critic.
        self.critique_notes = None

    def add_compact_boundary(self, field: str, before_chars: int, after_chars: int) -> None:
        self.compact_boundaries.append(
            {"field": field, "before_chars": before_chars, "after_chars": after_chars}
        )

    def next_visual_id(self, prefix: str) -> str:
        """Return a unique graph node/edge id."""
        self.visual_sequence += 1
        safe = prefix.replace(':', '-').replace(' ', '-')
        return f"{safe}-{self.visual_sequence}"

    def add_visual_node(
        self,
        label: str,
        kind: str,
        iteration: int | None = None,
        metadata: dict[str, Any] | None = None,
        node_id: str | None = None,
        parent_id: str | None = None,
        edge_label: str | None = None,
        status: str = "completed",
    ) -> str:
        """Append a graph node and optionally connect it to a parent."""
        resolved_id = node_id or self.next_visual_id(kind)
        seq = self.visual_sequence
        self.visual_nodes.append(
            VisualNode(
                id=resolved_id,
                label=label,
                kind=kind,
                iteration=iteration or self.iteration,
                sequence=seq,
                status=status,
                metadata=metadata or {},
            )
        )
        if parent_id:
            self.add_visual_edge(parent_id, resolved_id, label=edge_label)
        self.current_visual_node_id = resolved_id
        return resolved_id

    def add_visual_edge(
        self,
        source: str,
        target: str,
        label: str | None = None,
        kind: str = "flow",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        edge_id = self.next_visual_id("edge")
        self.visual_edges.append(
            VisualEdge(
                id=edge_id,
                source=source,
                target=target,
                label=label,
                kind=kind,
                metadata=metadata or {},
            )
        )
        return edge_id

    @property
    def total_input_tokens(self) -> int:
        return sum(u.input_tokens for u in self.token_usage)

    @property
    def total_output_tokens(self) -> int:
        return sum(u.output_tokens for u in self.token_usage)

    def citation_coverage(self) -> float:
        """Fraction of sources that appear to be cited in the final answer."""
        if not self.final_answer or not self.sources:
            return 0.0
        cited = sum(
            1
            for src in self.sources
            if (src.url and src.url in self.final_answer)
            or src.title.lower()[:20] in self.final_answer.lower()
        )
        return cited / len(self.sources)
