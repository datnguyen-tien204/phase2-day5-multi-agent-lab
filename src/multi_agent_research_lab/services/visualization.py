"""Helpers for turning workflow state into frontend-friendly graph data."""

from __future__ import annotations

from typing import Any

from multi_agent_research_lab.core.state import ResearchState

_KIND_ROW = {
    "input": 0,
    "supervisor": 1,
    "agent": 2,
    "tool": 3,
    "artifact": 4,
    "terminal": 5,
}

_KIND_COLOR = {
    "input": "#e8f0fe",
    "supervisor": "#dbeafe",
    "agent": "#eff6ff",
    "tool": "#f0f9ff",
    "artifact": "#f8fbff",
    "terminal": "#d1fae5",
}


def build_visual_graph(state: ResearchState) -> dict[str, Any]:
    """Build a React Flow compatible graph payload."""
    nodes: list[dict[str, Any]] = []
    for node in sorted(state.visual_nodes, key=lambda item: (item.sequence, item.id)):
        row = _KIND_ROW.get(node.kind, 2)
        x = 80 + max(node.sequence - 1, 0) * 230
        y = 40 + row * 110
        nodes.append(
            {
                "id": node.id,
                "position": {"x": x, "y": y},
                "data": {
                    "label": node.label,
                    "kind": node.kind,
                    "iteration": node.iteration,
                    "metadata": node.metadata,
                    "status": node.status,
                },
                "style": {
                    "background": _KIND_COLOR.get(node.kind, "#ffffff"),
                    "border": "1px solid #2563eb",
                    "borderRadius": 16,
                    "color": "#1d4ed8",
                    "padding": 12,
                    "fontSize": 13,
                    "minWidth": 180,
                    "boxShadow": "0 10px 28px rgba(37, 99, 235, 0.10)",
                },
                "type": "default",
            }
        )

    edges = [
        {
            "id": edge.id,
            "source": edge.source,
            "target": edge.target,
            "label": edge.label,
            "animated": edge.kind != "flow",
            "style": {"stroke": "#3b82f6", "strokeWidth": 2},
            "labelStyle": {"fill": "#1d4ed8", "fontSize": 12},
        }
        for edge in state.visual_edges
    ]
    return {"nodes": nodes, "edges": edges}


def build_dashboard_payload(state: ResearchState) -> dict[str, Any]:
    """Return complete payload consumed by the React dashboard."""
    return {
        "query": state.request.query,
        "status": state.status,
        "route_history": state.route_history,
        "transitions": [t.model_dump() for t in state.transitions],
        "graph": build_visual_graph(state),
        "final_answer": state.final_answer,
        "planning_notes": state.planning_notes,
        "expanded_queries": state.expanded_queries,
        "research_notes": state.research_notes,
        "analysis_notes": state.analysis_notes,
        "critique_notes": state.critique_notes,
        "quality_score": state.quality_score,
        "summary": {
            "iterations": state.iteration,
            "sources": len(state.sources),
            "input_tokens": state.total_input_tokens,
            "output_tokens": state.total_output_tokens,
            "citation_coverage": state.citation_coverage(),
            "errors": state.errors,
        },
        "sources": [s.model_dump() for s in state.sources],
        "agent_results": [r.model_dump() for r in state.agent_results],
        "trace": state.trace,
        "visual_nodes": [n.model_dump() for n in state.visual_nodes],
        "visual_edges": [e.model_dump() for e in state.visual_edges],
    }
