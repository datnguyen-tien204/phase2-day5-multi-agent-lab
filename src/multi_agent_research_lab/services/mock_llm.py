"""Mock LLM client for demo/testing without a real API key.

Produces realistic, deterministic responses for the standard lab queries.
Swap for LLMClient when a real ANTHROPIC_API_KEY is available.
"""

from __future__ import annotations

import time

from multi_agent_research_lab.services.llm_client import LLMResponse

# ---------------------------------------------------------------------------
# Canned responses keyed by intent (detected from system prompt keywords)
# ---------------------------------------------------------------------------

_RESEARCHER_NOTES = """## Research Notes: GraphRAG State-of-the-Art

**Key Sub-topics Identified:**

### 1. What is GraphRAG?
GraphRAG (Graph Retrieval-Augmented Generation) is a Microsoft Research technique that augments
traditional RAG with knowledge graphs. Instead of raw vector search, it extracts entity-relation
graphs from source documents and uses community detection (Leiden algorithm) to build hierarchical
summaries [1][2].

### 2. Performance Benchmarks
- Beats naive RAG by +18% on multi-hop QA (HotpotQA benchmark) [2]
- Global query coverage improves by up to 40% vs vector-only retrieval [2]
- Trade-off: graph construction takes 3-5× longer than vector indexing [3]

### 3. Key Variants
- **LightRAG** [3]: Dual-level retrieval (local entity + global relationship). 4× lower
  latency than GraphRAG, comparable accuracy.
- **HippoRAG**: Hippocampal-inspired indexing, reduces hallucination on knowledge-intensive tasks.

### 4. Production Stacks
Common combinations: Neo4j (graph store) + LangChain/LlamaIndex + Weaviate/Pinecone [4].
Microsoft open-sourced GraphRAG under MIT license on GitHub (7k+ stars as of 2025) [1].

### 5. Limitations / Weak Evidence
- Most benchmarks are on English academic corpora — multilingual performance is under-studied.
- Community detection quality varies by domain (financial docs vs medical notes) — flagged as
  inconclusive from a single paper.

**Sources:**
[1] Microsoft Research GraphRAG Blog
[2] arXiv 2404.16130 — From Local to Global: A Graph RAG Approach
[3] arXiv 2410.05779 — LightRAG
[4] Neo4j Developer Blog — Production GraphRAG
[5] Towards Data Science — GraphRAG vs Traditional RAG
"""

_ANALYST_NOTES = """## Analysis: GraphRAG State-of-the-Art

## Key Claims

1. **GraphRAG outperforms vector RAG on multi-hop QA by ~18%** (HotpotQA)
   - Evidence Strength: **Strong** — published peer-reviewed result with public benchmark.

2. **Graph construction is 3-5× slower than vector indexing**
   - Evidence Strength: **Moderate** — reported in one comparative blog post, not replicated in
     peer review. Should be treated as indicative rather than definitive.

3. **LightRAG achieves comparable accuracy at 4× lower latency**
   - Evidence Strength: **Moderate** — early arXiv paper, awaiting peer review.

4. **Microsoft open-sourced GraphRAG (MIT license)**
   - Evidence Strength: **Strong** — verifiable from GitHub.

## Conflicting Viewpoints

- GraphRAG paper claims global query superiority; independent blog analyses (TDS) suggest
  the gap narrows significantly on shorter documents / focused corpora.
- LightRAG authors claim latency parity — Microsoft has not officially responded.

## Knowledge Gaps

- No rigorous multilingual or domain-specific benchmarks available.
- Production failure rates (graph corruption, community detection drift) are not documented.
- Cost comparison at scale (10M+ documents) is missing from literature.

## Actionable Insights

1. **Use GraphRAG for global/thematic queries** over large narrative corpora; use vector RAG
   for local, entity-specific lookups.
2. **Pilot LightRAG** if latency is critical and accuracy trade-off is acceptable.
3. **Budget for indexing time** — graph construction is expensive; plan for incremental updates.
"""

_FINAL_ANSWER = """## GraphRAG: State-of-the-Art Summary

GraphRAG (Graph Retrieval-Augmented Generation) represents a significant evolution in
retrieval-augmented generation, addressing a key weakness of traditional vector search:
the inability to answer *global*, thematic questions that require synthesising information
across an entire corpus.

## What Is GraphRAG?

Introduced by [Microsoft Research](https://www.microsoft.com/en-us/research/blog/graphrag-unlocking-llm-discovery-on-narrative-private-data/),
GraphRAG builds a **knowledge graph** of entities and relationships extracted from source
documents using an LLM. It then applies **community detection** (the Leiden algorithm) to
group related nodes into hierarchical clusters, generating multi-level summaries that capture
both local details and global themes.

## Performance Highlights

According to the [original paper (arXiv 2404.16130)](https://arxiv.org/abs/2404.16130),
GraphRAG improves multi-hop QA on HotpotQA by approximately **18%** over BM25 + vector
hybrid baselines, and global query coverage by up to **40%**. These gains are most pronounced
on long, narrative-rich corpora (annual reports, novels, medical records).

The trade-off is indexing cost: graph construction typically takes **3-5× longer** than
standard vector indexing, making real-time or frequent-update pipelines challenging.

## Key Variants

| System | Strength | Latency vs GraphRAG |
|---|---|---|
| GraphRAG (Microsoft) | Best global QA | Baseline |
| [LightRAG](https://arxiv.org/abs/2410.05779) | Dual-level retrieval | ~4× faster |
| HippoRAG | Reduced hallucination | Similar |

**[LightRAG](https://arxiv.org/abs/2410.05779)** is particularly noteworthy: it introduces
dual-level retrieval combining local entity lookup and global relationship traversal, matching
GraphRAG's accuracy at a fraction of the latency cost.

## Production Considerations

For production deployments, [Neo4j's developer blog](https://neo4j.com/developer-blog/graphrag-langchain)
recommends pairing GraphRAG with Neo4j as the graph store, LangChain for orchestration, and
a separate vector store (Weaviate or Pinecone) for hybrid retrieval.

Microsoft's GraphRAG is open-sourced under the MIT license on GitHub (7,000+ stars).

## When to Use GraphRAG

- ✅ Large, narrative corpora requiring cross-document synthesis
- ✅ Thematic or global queries ("What are the main risks in these contracts?")
- ✅ Applications where citation quality matters
- ❌ Real-time indexing requirements (too slow to rebuild graph)
- ❌ Simple, keyword-based lookups (vector search is sufficient and cheaper)

## References

1. [GraphRAG: Unlocking LLM discovery on narrative private data](https://www.microsoft.com/en-us/research/blog/graphrag-unlocking-llm-discovery-on-narrative-private-data/) — Microsoft Research
2. [From Local to Global: A Graph RAG Approach (arXiv 2404.16130)](https://arxiv.org/abs/2404.16130)
3. [LightRAG (arXiv 2410.05779)](https://arxiv.org/abs/2410.05779)
4. [Production GraphRAG with Neo4j](https://neo4j.com/developer-blog/graphrag-langchain)
5. [GraphRAG vs Traditional RAG](https://towardsdatascience.com/graphrag-vs-traditional-rag)
"""

_CRITIQUE = """## Critic Review

## Factual Accuracy

All major claims in the final answer are traceable to the provided sources:
- The 18% improvement figure appears in arXiv 2404.16130 ✅
- The 3-5× indexing overhead is cited from the comparative blog source ✅
- LightRAG 4× latency claim comes from arXiv 2410.05779 ✅
- One uncited claim: "7,000+ GitHub stars" — verifiable but not in provided sources ⚠️

## Citation Coverage

5 out of 5 sources are referenced in the final answer (100% citation coverage). ✅
All major claims carry at least one inline citation.

## Clarity and Structure

- The table comparing GraphRAG variants is an excellent addition for technical learners. ✅
- "When to Use" section with ✅/❌ is highly scannable. ✅
- The executive summary is concise and accurate.

## Overall Quality Score

**Score: 9/10**

This is a publication-ready summary for technical learners. The only deduction is for the
unverified GitHub stars count and the lack of discussion of multilingual limitations
(flagged as a knowledge gap in analysis but not surfaced in final answer).

## Recommended Revisions

1. Add a caveat about limited multilingual benchmarks.
2. Verify/update the GitHub stars count or remove it.
3. Consider adding a cost estimate per 1M tokens for production planning.
"""

_BASELINE_ANSWER = """## GraphRAG: A Comprehensive Overview

GraphRAG (Graph Retrieval-Augmented Generation) is Microsoft Research's extension of standard
RAG that replaces pure vector similarity search with a knowledge-graph-powered retrieval
system.

## Core Mechanism

Instead of chunking documents and indexing embeddings, GraphRAG:
1. Extracts entities (people, concepts, places) and their relationships using an LLM.
2. Builds a knowledge graph from these extractions.
3. Applies the Leiden community detection algorithm to cluster related entities.
4. Generates hierarchical summaries at each community level.
5. Uses these summaries to answer both local (entity-specific) and global (thematic) queries.

## Key Advantages

- **Global query answering**: Unlike vector RAG, GraphRAG can synthesise information across
  an entire corpus to answer questions like "What are the main themes in this document set?"
- **Improved multi-hop reasoning**: By traversing graph edges, it handles questions requiring
  information from multiple documents.
- **Better citation quality**: Entity-level grounding produces more precise source attribution.

## Performance

Published results show ~18% improvement on HotpotQA multi-hop benchmark. Global query
coverage improves by up to 40% vs vector-only RAG.

## Trade-offs

GraphRAG is significantly more expensive to index (3-5× slower) and more complex to operate.
For simple, focused queries, traditional vector RAG remains the better choice.

## Key Variants

- **LightRAG**: Dual-level retrieval at 4× lower latency.
- **HippoRAG**: Hippocampal-inspired approach reducing hallucinations.

GraphRAG is open source (MIT license) and available on GitHub.
"""

# Simple supervisor routing response
_SUPERVISOR_RESPONSES = {
    "researcher": "researcher",
    "analyst": "analyst",
    "writer": "writer",
    "critic": "critic",
    "done": "done",
}


class MockLLMClient:
    """Deterministic mock LLM for demo and integration testing.

    Token counts are estimated at ~1 token per 4 chars (rough heuristic).
    """

    def __init__(self, latency: float = 0.05) -> None:
        self._latency = latency  # simulated per-call latency (seconds)
        self.calls: list[dict] = []

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
    ) -> LLMResponse:
        time.sleep(self._latency)

        content = self._pick_response(system_prompt, user_prompt)
        in_tok = max(1, len(system_prompt + user_prompt) // 4)
        out_tok = max(1, len(content) // 4)
        cost = (in_tok * 3.0 + out_tok * 15.0) / 1_000_000

        self.calls.append({"system": system_prompt[:60], "user": user_prompt[:60]})

        return LLMResponse(
            content=content,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=cost,
            model="mock-claude",
            latency_seconds=self._latency,
        )

    def _pick_response(self, system: str, user: str) -> str:
        s = system.lower()
        u = user.lower()
        if "supervisor" in s or "route" in s:
            if "research_notes present: false" in u:
                return "researcher"
            if "analysis_notes present: false" in u:
                return "analyst"
            if "final_answer present: false" in u:
                return "writer"
            if "critique_notes present: false" in u:
                return "critic"
            return "done"
        if "research assistant" in s and "research notes" in s:
            return _RESEARCHER_NOTES
        if "critical analyst" in s:
            return _ANALYST_NOTES
        if "technical writer" in s:
            return _FINAL_ANSWER
        if "peer reviewer" in s or "fact-check" in s:
            return _CRITIQUE
        if "research assistant" in s:
            return _BASELINE_ANSWER
        if "search engine" in s:
            import json
            return json.dumps([
                {"title": "GraphRAG Paper", "url": "https://arxiv.org/abs/2404.16130",
                 "snippet": "Microsoft GraphRAG introduces knowledge-graph-powered retrieval."},
            ])
        return f"Mock response for: {user[:80]}"
