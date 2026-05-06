"""Command-line entrypoint for the Multi-Agent Research Lab."""

from __future__ import annotations

import json
from typing import Annotated

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from multi_agent_research_lab.core.config import get_settings
from multi_agent_research_lab.core.schemas import ResearchQuery
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.evaluation.benchmark import run_benchmark
from multi_agent_research_lab.evaluation.report import render_markdown_report
from multi_agent_research_lab.graph.workflow import MultiAgentWorkflow, _make_llm
from multi_agent_research_lab.observability.logging import configure_logging
from multi_agent_research_lab.observability.tracing import TraceExporter
from multi_agent_research_lab.services.storage import LocalArtifactStore
from multi_agent_research_lab.services.visualization import build_dashboard_payload

app = typer.Typer(help="Multi-Agent Research Lab CLI", rich_markup_mode="rich")
console = Console()


def _init() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)


# ── Baseline ──────────────────────────────────────────────────────────────────

@app.command()
def baseline(
    query: Annotated[str, typer.Option("--query", "-q", help="Research query")],
    save: Annotated[bool, typer.Option("--save", help="Save output to reports/")] = False,
) -> None:
    """Run real single-agent baseline (one LLM call, no orchestration)."""
    _init()

    system = (
        "You are an expert research assistant. Answer the query thoroughly in ~500 words. "
        "Include key facts, cite relevant concepts, and structure with markdown headers."
    )

    console.print(Panel.fit("[bold cyan]Single-Agent Baseline[/]", subtitle=f"[dim]{query[:70]}[/]"))

    llm = _make_llm()
    with console.status("[bold]Calling LLM…"):
        resp = llm.complete(system, query, temperature=0.3)

    state = ResearchState(request=ResearchQuery(query=query))
    state.final_answer = resp.content
    state.add_token_usage("baseline", resp.input_tokens, resp.output_tokens)

    console.print(Markdown(resp.content))
    _print_stats(resp.input_tokens, resp.output_tokens, resp.cost_usd, resp.latency_seconds)

    if save:
        store = LocalArtifactStore()
        p = store.write_text("baseline_answer.md", resp.content)
        console.print(f"\n[dim]Saved → {p}[/]")


# ── Multi-agent ───────────────────────────────────────────────────────────────

@app.command("multi-agent")
def multi_agent(
    query: Annotated[str, typer.Option("--query", "-q", help="Research query")],
    save: Annotated[bool, typer.Option("--save", help="Save outputs to reports/")] = False,
    trace: Annotated[bool, typer.Option("--trace", help="Print trace summary")] = False,
) -> None:
    """Run the full multi-agent workflow (Supervisor → Researcher → Analyst → Writer → Critic)."""
    _init()

    console.print(Panel.fit("[bold green]Multi-Agent Workflow[/]", subtitle=f"[dim]{query[:70]}[/]"))

    state = ResearchState(request=ResearchQuery(query=query))
    workflow = MultiAgentWorkflow()

    with console.status("[bold]Running multi-agent pipeline…"):
        result = workflow.run(state)

    # Print route
    console.print(f"\n[bold]Route taken:[/] {' → '.join(result.route_history)}")
    console.print(f"[bold]Iterations:[/] {result.iteration}")

    if result.errors:
        console.print(f"[yellow]Errors:[/] {result.errors}")

    # Print final answer
    if result.final_answer:
        console.print("\n")
        console.print(Panel(Markdown(result.final_answer), title="[bold green]Final Answer[/]"))
    else:
        console.print("[red]No final answer produced.[/]")

    # Print token summary
    _print_stats(result.total_input_tokens, result.total_output_tokens, latency_seconds=None)

    # Critic score
    for r in result.agent_results:
        if r.agent == "critic" and r.metadata.get("quality_score"):
            console.print(f"\n[bold]Quality Score (Critic):[/] {r.metadata['quality_score']}/10")

    if trace:
        console.print(Markdown(TraceExporter.summary(result)))

    if save:
        store = LocalArtifactStore()
        if result.final_answer:
            p = store.write_text("multi_agent_answer.md", result.final_answer)
            console.print(f"[dim]Answer → {p}[/]")
        tp = store.write_text("trace.json", TraceExporter.to_json(result))
        console.print(f"[dim]Trace → {tp}[/]")


# ── Benchmark ─────────────────────────────────────────────────────────────────

@app.command()
def benchmark(
    query: Annotated[str, typer.Option("--query", "-q", help="Research query")] = (
        "Research GraphRAG state-of-the-art and write a 500-word summary"
    ),
    save: Annotated[bool, typer.Option("--save", help="Save report to reports/")] = True,
) -> None:
    """Benchmark single-agent vs multi-agent and produce a comparison report."""
    _init()
    console.print(Panel.fit("[bold magenta]Benchmark Mode[/]", subtitle=f"[dim]{query[:70]}[/]"))

    llm = _make_llm()

    # ── Single-agent runner ────────────────────────────────────────────────────
    def single_runner(q: str) -> ResearchState:
        system = (
            "You are an expert research assistant. Answer the query thoroughly in ~500 words. "
            "Include key facts, cite relevant concepts, and use markdown headers."
        )
        resp = llm.complete(system, q, temperature=0.3)
        s = ResearchState(request=ResearchQuery(query=q))
        s.final_answer = resp.content
        s.add_token_usage("baseline", resp.input_tokens, resp.output_tokens)
        return s

    # ── Multi-agent runner ─────────────────────────────────────────────────────
    def multi_runner(q: str) -> ResearchState:
        s = ResearchState(request=ResearchQuery(query=q))
        return MultiAgentWorkflow().run(s)

    # Run both
    with console.status("[bold cyan]Running single-agent baseline…"):
        single_state, single_metrics = run_benchmark("single-agent", query, single_runner)

    with console.status("[bold green]Running multi-agent workflow…"):
        multi_state, multi_metrics = run_benchmark("multi-agent", query, multi_runner)

    # Rich table
    table = Table(title="Benchmark Results", show_lines=True)
    table.add_column("Metric", style="bold")
    table.add_column("Single-Agent", justify="right")
    table.add_column("Multi-Agent", justify="right")

    def fmt(val: object, unit: str = "") -> str:
        return f"{val}{unit}" if val is not None else "—"

    table.add_row("Latency (s)", fmt(f"{single_metrics.latency_seconds:.2f}"), fmt(f"{multi_metrics.latency_seconds:.2f}"))
    table.add_row("Cost (USD)", fmt(f"${single_metrics.estimated_cost_usd:.5f}"), fmt(f"${multi_metrics.estimated_cost_usd:.5f}"))
    table.add_row("Quality /10", fmt(single_metrics.quality_score), fmt(multi_metrics.quality_score))
    table.add_row("Citation %", fmt(f"{(single_metrics.citation_coverage or 0)*100:.0f}%"), fmt(f"{(multi_metrics.citation_coverage or 0)*100:.0f}%"))
    table.add_row("Tokens In", fmt(f"{single_metrics.input_tokens:,}"), fmt(f"{multi_metrics.input_tokens:,}"))
    table.add_row("Tokens Out", fmt(f"{single_metrics.output_tokens:,}"), fmt(f"{multi_metrics.output_tokens:,}"))
    table.add_row("Errors", fmt(len(single_state.errors)), fmt(len(multi_state.errors)))

    console.print(table)

    # Render markdown report
    report = render_markdown_report([single_metrics, multi_metrics], query=query)

    if save:
        store = LocalArtifactStore()
        rp = store.write_text("benchmark_report.md", report)
        te = store.write_text("trace_multi.json", TraceExporter.to_json(multi_state))
        console.print(f"\n[bold]Report saved:[/] {rp}")
        console.print(f"[bold]Trace saved:[/] {te}")
    else:
        console.print(Markdown(report))


# ── Visualisation / Dashboard ────────────────────────────────────────────────

@app.command("visualize")
def visualize(
    query: Annotated[str, typer.Option("--query", "-q", help="Research query")],
    save: Annotated[bool, typer.Option("--save", help="Save dashboard payload to reports/")] = True,
) -> None:
    """Run the workflow and export frontend-ready graph data."""
    _init()
    console.print(Panel.fit("[bold blue]Workflow Visualizer[/]", subtitle=f"[dim]{query[:70]}[/]"))
    state = ResearchState(request=ResearchQuery(query=query))
    result = MultiAgentWorkflow().run(state)
    payload = build_dashboard_payload(result)
    console.print(f"[bold]Route:[/] {' → '.join(result.route_history)}")
    console.print(f"[bold]Graph nodes:[/] {len(payload['graph']['nodes'])}  [bold]edges:[/] {len(payload['graph']['edges'])}")
    if save:
        store = LocalArtifactStore()
        p = store.write_text("dashboard_latest.json", json.dumps(payload, indent=2))
        console.print(f"[dim]Dashboard payload → {p}[/]")
    if result.final_answer:
        console.print(Panel(Markdown(result.final_answer[:1200] + ("..." if len(result.final_answer) > 1200 else "")), title="[bold blue]Answer Preview[/]"))


@app.command("serve-api")
def serve_api(
    host: Annotated[str, typer.Option("--host", help="Bind host")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", help="Bind port")] = 8000,
) -> None:
    """Serve the FastAPI backend used by the React dashboard."""
    _init()
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover
        raise typer.BadParameter("uvicorn is not installed. Install the api extra first.") from exc

    console.print(f"[bold blue]Starting dashboard API[/] at http://{host}:{port}")
    uvicorn.run("multi_agent_research_lab.api.app:app", host=host, port=port, reload=False)


# ── Design doc ────────────────────────────────────────────────────────────────

@app.command("design-doc")
def design_doc(
    save: Annotated[bool, typer.Option("--save", help="Save to reports/")] = True,
) -> None:
    """Generate the filled design document."""
    _init()
    content = _build_design_doc()
    console.print(Markdown(content))
    if save:
        store = LocalArtifactStore()
        p = store.write_text("design_doc.md", content)
        console.print(f"\n[dim]Saved → {p}[/]")


def _build_design_doc() -> str:
    return """# Design Document — Multi-Agent Research System

## Problem

Build a research assistant that handles complex, multi-step research queries:
(1) searches and gathers sources, (2) critically analyses evidence, (3) synthesises a
polished response, and (4) fact-checks quality — all in an auditable, cost-tracked pipeline.

## Why multi-agent?

A single prompt cannot simultaneously optimise for breadth of search, critical rigour,
writing quality, AND fact-checking — each role demands different system prompts,
temperature settings, and output formats. Multi-agent separates these concerns cleanly.

## Agent Roles

| Agent | Responsibility | Input | Output | Failure mode |
|---|---|---|---|---|
| Supervisor | Route decisions, guardrails | Full state | Next route | LLM ambiguity → deterministic fallback |
| Researcher | Source retrieval + notes | Query | sources, research_notes | No results → LLM synthesises |
| Analyst | Evidence analysis | research_notes | analysis_notes | Missing notes → warning + skip |
| Writer | Final synthesis | notes + analysis | final_answer | Partial state → best-effort write |
| Critic | Fact-check + quality score | final_answer + sources | critique_notes, score | N/A (optional pass) |

## Shared State

| Field | Type | Purpose |
|---|---|---|
| request | ResearchQuery | Original query + constraints |
| iteration | int | Guards max_iterations |
| route_history | list[str] | Full audit trail |
| sources | list[SourceDocument] | Cited material |
| research_notes | str | Researcher output |
| analysis_notes | str | Analyst output |
| final_answer | str | Writer output |
| critique_notes | str | Critic output |
| token_usage | list[TokenUsage] | Per-agent cost tracking |
| trace | list[dict] | Span events for observability |
| errors | list[str] | Error accumulation |

## Routing Policy

```
START → supervisor
  researcher_notes missing?  → researcher
  analysis_notes missing?    → analyst
  final_answer missing?      → writer
  critique missing?          → critic
  else                       → done
GUARDRAILS: max_iterations=6, timeout=120s, errors≥3 → done
```

## Guardrails

- **Max iterations:** 6 (configurable via MAX_ITERATIONS env)
- **Timeout:** 120s SIGALRM (configurable via TIMEOUT_SECONDS env)
- **Retry:** tenacity 3× with exponential back-off in LLMClient
- **Fallback:** writer runs on partial state if timeout hit
- **Validation:** Pydantic schemas at every boundary
- **Error accumulation:** ≥3 errors → supervisor exits early

## Benchmark Plan

Queries: GraphRAG summary, single vs multi-agent comparison, LLM guardrails
Metrics: latency (s), cost (USD), quality (0–10 critic score), citation %, error rate
Expected: multi-agent +2-3 quality points, 3-5× latency/cost overhead
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _print_stats(
    input_tokens: int = 0,
    output_tokens: int = 0,
    cost_usd: float | None = None,
    latency_seconds: float | None = None,
) -> None:
    parts = [f"[dim]Tokens: {input_tokens:,} in / {output_tokens:,} out[/]"]
    if cost_usd is not None:
        parts.append(f"[dim]Cost: ${cost_usd:.5f}[/]")
    if latency_seconds is not None:
        parts.append(f"[dim]Latency: {latency_seconds:.2f}s[/]")
    console.print("  ".join(parts))


if __name__ == "__main__":
    app()
