# Design Document — Multi-Agent Research System

## Problem

Xây dựng một **research assistant** có thể nhận câu hỏi phức tạp, tìm kiếm tài liệu liên quan,
phân tích bằng chứng, tổng hợp câu trả lời có citation, và tự kiểm tra chất lượng — tất cả
trong một pipeline có thể audit và đo lường.

## Why Multi-Agent?

Single agent không thể đồng thời tối ưu cho:
- **Breadth** (tìm nhiều nguồn) AND **depth** (phân tích kỹ từng nguồn)
- **Research rigor** (citation đầy đủ) AND **writing quality** (mạch lạc, đúng audience)
- **Generation** AND **verification** (fact-check chính output của mình)

Chia ra 4 specialist agents cho phép mỗi agent có **system prompt, temperature, và output format
riêng**, tối ưu hoá từng bước mà không compromise.

## Agent Roles

| Agent | Responsibility | Input | Output | Failure mode |
|---|---|---|---|---|
| **Supervisor** | Routing decisions + guardrails | Full ResearchState | Next route (str) | LLM ambiguous → deterministic fallback |
| **Researcher** | Source search + research notes | query, max_sources | sources[], research_notes | No KB match → LLM synthesis fallback |
| **Analyst** | Evidence strength + gaps | research_notes | analysis_notes | Missing notes → skip with warning |
| **Writer** | Synthesise final answer | notes + analysis + sources | final_answer (markdown) | Partial state → best-effort write |
| **Critic** | Fact-check + quality score | final_answer + sources | critique_notes, score 1-10 | Always optional pass |

## Shared State

| Field | Type | Purpose |
|---|---|---|
| `request` | ResearchQuery | Original query, max_sources, audience |
| `iteration` | int | Guards max_iterations |
| `route_history` | list[str] | Full audit trail of routing decisions |
| `sources` | list[SourceDocument] | Deduplicated cited sources |
| `research_notes` | str | Researcher's structured notes |
| `analysis_notes` | str | Analyst's evidence assessment |
| `final_answer` | str | Writer's synthesised response |
| `critique_notes` | str | Critic's fact-check + score |
| `token_usage` | list[TokenUsage] | Per-agent token + cost tracking |
| `trace` | list[dict] | Span events (name, duration, attributes) |
| `errors` | list[str] | Accumulated error messages |
| `status` | str | running / done / failed |

## Routing Policy

```
START ──▶ Supervisor
  research_notes missing?   ──▶ researcher
  analysis_notes missing?   ──▶ analyst
  final_answer missing?     ──▶ writer
  critique_notes missing?   ──▶ critic
  else                      ──▶ done

GUARDRAILS (checked before routing):
  iteration >= max_iterations  ──▶ done (forced)
  len(errors) >= 3             ──▶ done (emergency exit)
```

## Guardrails

| Guardrail | Mechanism | Config |
|---|---|---|
| Max iterations | `iteration >= max_iterations` → force done | `MAX_ITERATIONS=6` |
| Timeout | SIGALRM (Unix) → TimeoutError | `TIMEOUT_SECONDS=120` |
| LLM retry | `tenacity` 3× exp back-off | hardcoded in `LLMClient` |
| Worker retry | `_safe_run()` 2 attempts + 1s sleep | workflow loop |
| Error accumulation | `len(errors) >= 3` → supervisor exits | hardcoded |
| Partial-state rescue | Writer triggered on timeout if notes exist | workflow handler |
| Output validation | Pydantic schemas at every boundary | `core/schemas.py` |

## Benchmark Plan

**Queries tested:**
1. `Research GraphRAG state-of-the-art and write a 500-word summary`
2. `Compare single-agent and multi-agent workflows for customer support`
3. `Summarize production guardrails for LLM agents`

**Metrics:**

| Metric | How measured |
|---|---|
| Latency | `perf_counter()` wall-clock in `run_benchmark()` |
| Cost | Token count × price per 1M tokens |
| Quality | Critic score (1-10) + heuristic fallback |
| Citation coverage | Fraction of sources cited in `final_answer` |
| Failure rate | Exceptions caught / total runs |

**Expected outcomes:**
- Multi-agent: +2-3 quality points, 4-6× latency/cost overhead
- Citation coverage: 0% single → ~80-100% multi
- Failure rate: <5% with retry + fallback in place
