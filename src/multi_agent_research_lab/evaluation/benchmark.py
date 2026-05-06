"""Benchmark: single-agent vs multi-agent with full metrics."""

from __future__ import annotations

import logging
from collections.abc import Callable
from time import perf_counter

from multi_agent_research_lab.core.schemas import BenchmarkMetrics
from multi_agent_research_lab.core.state import ResearchState

logger = logging.getLogger(__name__)

Runner = Callable[[str], ResearchState]

# Pricing (USD / 1M tokens) for Claude Sonnet 4
_INPUT_PRICE = 3.0
_OUTPUT_PRICE = 15.0


def _estimate_cost(state: ResearchState) -> float:
    """Sum token costs across all agents."""
    cost = (
        state.total_input_tokens * _INPUT_PRICE
        + state.total_output_tokens * _OUTPUT_PRICE
    ) / 1_000_000
    # Also check agent_results for individually tracked costs
    agent_cost = sum(
        r.metadata.get("cost_usd", 0) or 0
        for r in state.agent_results
    )
    return max(cost, agent_cost)


def _quality_score(state: ResearchState) -> float:
    """Extract quality score from critic if available, else heuristic."""
    for r in reversed(state.agent_results):
        if r.agent == "critic" and "quality_score" in r.metadata:
            val = r.metadata["quality_score"]
            if val is not None:
                return float(val)
    # Heuristic: penalise for errors, reward for completeness
    score = 5.0
    if state.final_answer:
        words = len(state.final_answer.split())
        score += min(2.0, words / 250)          # up to +2 for length
    if state.analysis_notes:
        score += 1.0                             # +1 for analysis present
    if state.sources:
        score += min(1.0, len(state.sources) / 5)  # up to +1 for sources
    score -= len(state.errors) * 0.5            # -0.5 per error
    return round(max(0.0, min(10.0, score)), 1)


def _agent_latency_breakdown(state: ResearchState) -> dict[str, float]:
    """Per-agent latency from trace events (seconds)."""
    breakdown: dict[str, float] = {}
    for event in state.trace:
        name = event.get("name", "")
        payload = event.get("payload", {})
        if name.startswith("agent:") or name.startswith("worker:"):
            agent = name.split(":")[-1]
            dur = payload.get("duration_seconds", 0) or 0
            breakdown[agent] = breakdown.get(agent, 0) + dur
    return breakdown


def run_benchmark(
    run_name: str,
    query: str,
    runner: Runner,
) -> tuple[ResearchState, BenchmarkMetrics]:
    """Measure latency, cost, quality, citation coverage, and error rate."""
    logger.info("Benchmark START — '%s'", run_name)
    started = perf_counter()
    try:
        state = runner(query)
        failed = 0
    except Exception as exc:
        logger.error("Runner failed: %s", exc)
        from multi_agent_research_lab.core.schemas import ResearchQuery
        state = ResearchState(request=ResearchQuery(query=query))
        state.errors.append(str(exc))
        failed = 1

    latency = perf_counter() - started

    metrics = BenchmarkMetrics(
        run_name=run_name,
        latency_seconds=round(latency, 3),
        estimated_cost_usd=round(_estimate_cost(state), 6),
        quality_score=_quality_score(state),
        input_tokens=state.total_input_tokens,
        output_tokens=state.total_output_tokens,
        citation_coverage=round(state.citation_coverage(), 3),
        failure_rate=float(failed),
        agent_breakdown=_agent_latency_breakdown(state),
        notes=f"routes={state.route_history} errors={state.errors}",
    )
    logger.info(
        "Benchmark END — lat=%.2fs cost=$%.5f quality=%.1f",
        metrics.latency_seconds,
        metrics.estimated_cost_usd or 0,
        metrics.quality_score or 0,
    )
    return state, metrics
