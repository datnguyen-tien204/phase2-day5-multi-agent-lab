from multi_agent_research_lab.core.schemas import ResearchQuery
from multi_agent_research_lab.core.state import ResearchState


def test_state_records_route_and_trace() -> None:
    state = ResearchState(request=ResearchQuery(query="Explain multi-agent systems"))
    state.record_route("researcher")
    state.add_trace_event("route", {"next": "researcher"})
    assert state.iteration == 1
    assert state.route_history == ["researcher"]
    assert state.trace[0]["name"] == "route"


def test_state_token_accumulation() -> None:
    state = ResearchState(request=ResearchQuery(query="Test query"))
    state.add_token_usage("researcher", 500, 200)
    state.add_token_usage("analyst", 300, 100)
    assert state.total_input_tokens == 800
    assert state.total_output_tokens == 300


def test_state_citation_coverage() -> None:
    from multi_agent_research_lab.core.schemas import SourceDocument
    state = ResearchState(request=ResearchQuery(query="Test query"))
    state.sources = [
        SourceDocument(title="GraphRAG Paper", url="https://arxiv.org/abs/2404.16130", snippet="..."),
        SourceDocument(title="LangGraph Docs", url="https://langchain.com", snippet="..."),
    ]
    state.final_answer = "See [GraphRAG Paper](https://arxiv.org/abs/2404.16130) for details."
    cov = state.citation_coverage()
    assert 0 <= cov <= 1
