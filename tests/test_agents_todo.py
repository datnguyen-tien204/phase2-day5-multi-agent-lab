"""Tests for all agents — now fully implemented, no more StudentTodoError."""

import pytest

from multi_agent_research_lab.agents import (
    AnalystAgent, CriticAgent, ResearcherAgent, SupervisorAgent, WriterAgent
)
from multi_agent_research_lab.core.schemas import ResearchQuery
from multi_agent_research_lab.core.state import ResearchState


def _make_state(query: str = "Explain multi-agent systems") -> ResearchState:
    return ResearchState(request=ResearchQuery(query=query))


# ── Supervisor ────────────────────────────────────────────────────────────────

def test_supervisor_routes_to_researcher_when_no_notes() -> None:
    """Supervisor should deterministically pick researcher first."""
    state = _make_state()
    # Patch LLM to avoid real API call
    sup = SupervisorAgent.__new__(SupervisorAgent)
    route = sup._deterministic_route(state)
    assert route == "researcher"


def test_supervisor_routes_to_analyst_after_research() -> None:
    state = _make_state()
    state.research_notes = "Some notes"
    sup = SupervisorAgent.__new__(SupervisorAgent)
    route = sup._deterministic_route(state)
    assert route == "analyst"


def test_supervisor_routes_to_writer_after_analysis() -> None:
    state = _make_state()
    state.research_notes = "Some notes"
    state.analysis_notes = "Some analysis"
    sup = SupervisorAgent.__new__(SupervisorAgent)
    route = sup._deterministic_route(state)
    assert route == "writer"


def test_supervisor_routes_to_critic_after_writer() -> None:
    state = _make_state()
    state.research_notes = "Some notes"
    state.analysis_notes = "Some analysis"
    state.final_answer = "Final answer"
    sup = SupervisorAgent.__new__(SupervisorAgent)
    route = sup._deterministic_route(state)
    assert route == "critic"


def test_supervisor_routes_done_when_complete() -> None:
    state = _make_state()
    state.research_notes = "notes"
    state.analysis_notes = "analysis"
    state.final_answer = "answer"
    state.critique_notes = "critique"
    sup = SupervisorAgent.__new__(SupervisorAgent)
    route = sup._deterministic_route(state)
    assert route == "done"


# ── Critic score extraction ───────────────────────────────────────────────────

def test_critic_score_extraction() -> None:
    critic = CriticAgent.__new__(CriticAgent)
    assert critic._extract_score("Overall Quality Score: 8/10") == 8.0
    assert critic._extract_score("score: 7") == 7.0
    assert critic._extract_score("9 out of 10") == 9.0
    assert critic._extract_score("no score here") is None


# ── State helpers ─────────────────────────────────────────────────────────────

def test_state_token_totals() -> None:
    state = _make_state()
    state.add_token_usage("researcher", 100, 200)
    state.add_token_usage("analyst", 150, 50)
    assert state.total_input_tokens == 250
    assert state.total_output_tokens == 250


def test_state_citation_coverage_empty() -> None:
    state = _make_state()
    assert state.citation_coverage() == 0.0
