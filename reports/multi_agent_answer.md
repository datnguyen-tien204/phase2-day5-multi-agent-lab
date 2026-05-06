## GraphRAG: State-of-the-Art Summary

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
