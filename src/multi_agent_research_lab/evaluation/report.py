"""Benchmark report rendering — Markdown + rich terminal table."""

from __future__ import annotations

import datetime

from multi_agent_research_lab.core.schemas import BenchmarkMetrics


def render_markdown_report(metrics: list[BenchmarkMetrics], query: str = "") -> str:
    """Render a detailed benchmark report in Markdown."""
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Benchmark Report — Multi-Agent Research Lab",
        "",
        f"**Generated:** {now}",
    ]
    if query:
        lines += [f"**Query:** `{query}`", ""]

    # ── Summary table ──────────────────────────────────────────────────────────
    lines += [
        "## Summary Table",
        "",
        "| Run | Latency (s) | Cost (USD) | Quality /10 | Citation % | Tokens In | Tokens Out | Notes |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for m in metrics:
        cost = f"${m.estimated_cost_usd:.5f}" if m.estimated_cost_usd is not None else "—"
        quality = f"{m.quality_score:.1f}" if m.quality_score is not None else "—"
        cov = f"{m.citation_coverage*100:.0f}%" if m.citation_coverage is not None else "—"
        notes_short = (m.notes[:60] + "…") if len(m.notes) > 60 else m.notes
        lines.append(
            f"| **{m.run_name}** | {m.latency_seconds:.2f} | {cost} | {quality} | "
            f"{cov} | {m.input_tokens:,} | {m.output_tokens:,} | {notes_short} |"
        )
    lines.append("")

    # ── Per-run breakdown ──────────────────────────────────────────────────────
    lines += ["## Per-Run Breakdown", ""]
    for m in metrics:
        lines += [f"### {m.run_name}", ""]
        lines += [
            f"- **Latency:** {m.latency_seconds:.2f}s",
            f"- **Estimated cost:** {'$'+f'{m.estimated_cost_usd:.5f}' if m.estimated_cost_usd else '—'}",
            f"- **Quality score:** {m.quality_score or '—'} / 10",
            f"- **Citation coverage:** {f'{m.citation_coverage*100:.0f}%' if m.citation_coverage is not None else '—'}",
            f"- **Tokens:** {m.input_tokens:,} in / {m.output_tokens:,} out",
        ]
        if m.agent_breakdown:
            lines += ["- **Agent latency breakdown:**"]
            for agent, dur in sorted(m.agent_breakdown.items(), key=lambda x: -x[1]):
                lines.append(f"  - `{agent}`: {dur:.2f}s")
        lines += [f"- **Notes:** `{m.notes}`", ""]

    # ── Analysis ───────────────────────────────────────────────────────────────
    if len(metrics) >= 2:
        lines += _comparative_analysis(metrics)

    # ── Failure modes ──────────────────────────────────────────────────────────
    lines += [
        "## Failure Modes & Mitigations",
        "",
        "| Failure Mode | Observed | Mitigation Applied |",
        "|---|---|---|",
        "| Agent timeout | max_iterations + SIGALRM | ✅ |",
        "| LLM API error | tenacity retry (3×, exp back-off) | ✅ |",
        "| Empty research notes | writer fallback on partial state | ✅ |",
        "| Too many errors (≥3) | supervisor fast-exit | ✅ |",
        "| Hallucinated sources | critic fact-check pass | ✅ |",
        "",
    ]

    # ── Exit ticket ────────────────────────────────────────────────────────────
    lines += [
        "## Exit Ticket",
        "",
        "**Q1: When should you use multi-agent?**",
        "",
        "> Use multi-agent when the task has clearly separable sub-responsibilities "
        "(research ≠ analysis ≠ writing), when parallel execution is beneficial, "
        "when quality gates (critic) are mandatory, or when specialised prompts per "
        "role produce measurably better outputs than a single prompt.",
        "",
        "**Q2: When should you NOT use multi-agent?**",
        "",
        "> Avoid multi-agent for simple, single-step tasks where orchestration overhead "
        "(latency, cost, complexity) outweighs the quality gain. If a single well-crafted "
        "prompt achieves 90%+ of the quality at 1/3 the cost, prefer the single-agent approach.",
        "",
    ]

    return "\n".join(lines)


def _comparative_analysis(metrics: list[BenchmarkMetrics]) -> list[str]:
    """Generate a comparison section when ≥2 runs exist."""
    base = metrics[0]
    lines = ["## Comparative Analysis", ""]
    for m in metrics[1:]:
        lat_delta = m.latency_seconds - base.latency_seconds
        lat_sign = "+" if lat_delta >= 0 else ""
        q_delta = (m.quality_score or 0) - (base.quality_score or 0)
        q_sign = "+" if q_delta >= 0 else ""
        lines += [
            f"### {base.run_name} → {m.run_name}",
            "",
            f"- **Latency:** {lat_sign}{lat_delta:.2f}s  "
            f"({'slower' if lat_delta > 0 else 'faster'})",
            f"- **Quality delta:** {q_sign}{q_delta:.1f}",
        ]
        if base.estimated_cost_usd and m.estimated_cost_usd:
            cost_ratio = m.estimated_cost_usd / base.estimated_cost_usd
            lines.append(f"- **Cost ratio:** {cost_ratio:.1f}× (multi vs single)")
        lines.append("")
        verdict = (
            "✅ Multi-agent worth the overhead"
            if q_delta >= 1.5
            else "⚠️ Marginal quality gain — consider single-agent for cost-sensitivity"
        )
        lines += [f"**Verdict:** {verdict}", ""]
    return lines
