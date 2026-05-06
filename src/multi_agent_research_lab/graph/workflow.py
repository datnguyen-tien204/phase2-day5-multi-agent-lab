"""Multi-agent workflow — pure Python state-machine.

The required directory/module names are preserved. Internally the workflow follows a
small AgenticAI-style loop: Supervisor decides, a worker executes as an AgentTool,
context is compacted, then tool results feed back into Supervisor until done.
"""

from __future__ import annotations

import logging
import signal
import time
from collections.abc import Iterator
from contextlib import contextmanager

from multi_agent_research_lab.agents.analyst import AnalystAgent
from multi_agent_research_lab.agents.critic import CriticAgent
from multi_agent_research_lab.agents.planner import PlannerAgent
from multi_agent_research_lab.agents.researcher import ResearcherAgent
from multi_agent_research_lab.agents.supervisor import SupervisorAgent
from multi_agent_research_lab.agents.writer import WriterAgent
from multi_agent_research_lab.core.config import get_settings
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.observability.tracing import flush_langfuse, trace_span
from multi_agent_research_lab.services.agent_tool import AgentTool
from multi_agent_research_lab.services.context_manager import ContextManager
from multi_agent_research_lab.services.search_client import SearchClient

logger = logging.getLogger(__name__)


def _make_llm():
    """Return real LLMClient or MockLLMClient depending on available API key."""
    settings = get_settings()
    openai_key = settings.openai_api_key or ""
    anthropic_key = settings.anthropic_api_key or ""
    has_real_key = any(
        key and key not in ("sandbox", "your_key_here", "changeme")
        for key in (openai_key, anthropic_key)
    )
    if has_real_key:
        from multi_agent_research_lab.services.llm_client import LLMClient

        return LLMClient()

    logger.info("No real LLM API key found — using MockLLMClient for demo/CI")
    from multi_agent_research_lab.services.mock_llm import MockLLMClient

    return MockLLMClient(latency=0.05)


@contextmanager
def _timeout(seconds: int) -> Iterator[None]:
    """SIGALRM-based timeout (Unix only; no-op on Windows)."""

    def _handler(signum, frame):  # type: ignore[type-arg]
        raise TimeoutError(f"Workflow timed out after {seconds}s")

    old = signal.signal(signal.SIGALRM, _handler) if hasattr(signal, "SIGALRM") else None
    if hasattr(signal, "SIGALRM"):
        signal.alarm(seconds)
    try:
        yield
    finally:
        if hasattr(signal, "SIGALRM"):
            signal.alarm(0)
            if old is not None:
                signal.signal(signal.SIGALRM, old)


class MultiAgentWorkflow:
    """Builds and runs the multi-agent research pipeline."""

    def __init__(self) -> None:
        self._settings = get_settings()
        llm = _make_llm()
        search = SearchClient(llm_client=llm)

        self._supervisor = SupervisorAgent(llm_client=llm)
        self._planner = PlannerAgent(llm_client=llm)
        researcher = ResearcherAgent(llm_client=llm, search_client=search)
        analyst = AnalystAgent(llm_client=llm)
        writer = WriterAgent(llm_client=llm)
        critic = CriticAgent(llm_client=llm)

        self._workers: dict[str, AgentTool] = {
            "researcher": AgentTool(
                name="researcher",
                description="Collect read-only sources and produce research notes.",
                run=researcher.execute,
                is_concurrency_safe=True,
            ),
            "analyst": AgentTool(
                name="analyst",
                description="Analyse evidence and produce structured insights.",
                run=analyst.execute,
            ),
            "writer": AgentTool(
                name="writer",
                description="Write or revise the final answer.",
                run=writer.execute,
            ),
            "critic": AgentTool(
                name="critic",
                description="Quality gate and fact-check final answer.",
                run=critic.execute,
            ),
        }
        self._context = ContextManager(max_chars=self._settings.max_context_chars)

    def build(self) -> dict[str, object]:
        """Return graph description dict."""
        return {
            "nodes": list(self._workers.keys()) + ["supervisor"],
            "edges": {
                "supervisor": list(self._workers.keys()) + ["done"],
                **{k: ["supervisor"] for k in self._workers},
            },
        }

    def run(self, state: ResearchState) -> ResearchState:
        """Execute the state-machine loop and return final state."""
        logger.info("Workflow START — query='%s'", state.request.query[:60])
        self._bootstrap_visualisation(state)
        try:
            with _timeout(self._settings.timeout_seconds):
                state = self._planner.execute(state)
                state = self._loop(state)
        except TimeoutError as exc:
            logger.error("Workflow TIMEOUT: %s", exc)
            state.errors.append(str(exc))
            state.status = "failed"
            if not state.final_answer and state.research_notes:
                state = self._safe_run("writer", state)
        except Exception as exc:
            logger.error("Workflow ERROR: %s", exc)
            state.errors.append(str(exc))
            state.status = "failed"

        state.status = "done" if state.final_answer else "failed"
        self._finalise_visualisation(state)
        logger.info(
            "Workflow END status=%s routes=%s in=%d out=%d",
            state.status,
            state.route_history,
            state.total_input_tokens,
            state.total_output_tokens,
        )
        flush_langfuse()
        return state

    def _bootstrap_visualisation(self, state: ResearchState) -> None:
        if state.visual_nodes:
            return
        prompt_node = state.add_visual_node(
            label=f"User Prompt\n{state.request.query[:90]}",
            kind="input",
            iteration=0,
            metadata={"audience": state.request.audience},
            node_id="user-prompt",
        )
        state.current_visual_node_id = prompt_node

    def _finalise_visualisation(self, state: ResearchState) -> None:
        if any(node.id == "workflow-terminal" for node in state.visual_nodes):
            return
        label = "Workflow Done" if state.status == "done" else "Workflow Failed"
        terminal = state.add_visual_node(
            label=label,
            kind="terminal",
            iteration=state.iteration,
            metadata={"errors": state.errors, "status": state.status},
            node_id="workflow-terminal",
            parent_id=state.current_visual_node_id,
            edge_label="complete",
            status=state.status,
        )
        state.current_visual_node_id = terminal

    def _loop(self, state: ResearchState) -> ResearchState:
        max_iter = self._settings.max_iterations
        while state.iteration < max_iter:
            state = self._context.compact_source_snippets(self._context.compact(state))
            with trace_span("supervisor:decide", state=state):
                state = self._supervisor.execute(state)

            route = state.route_history[-1] if state.route_history else "done"
            transition = state.transitions[-1] if state.transitions else None
            supervisor_node = state.add_visual_node(
                label=f"Supervisor\nIteration {state.iteration}",
                kind="supervisor",
                iteration=state.iteration,
                metadata={
                    "route": route,
                    "reason": transition.reason if transition else None,
                    "history": list(state.route_history),
                },
                parent_id=state.current_visual_node_id,
                edge_label="decide",
            )
            state.current_visual_node_id = supervisor_node

            if route == "done":
                break

            state = self._safe_run(route, state, parent_node_id=supervisor_node)
            state = self._context.compact_source_snippets(self._context.compact(state))
        else:
            state.errors.append(f"Max iterations ({max_iter}) reached")
            state.record_route("done", reason="max_iter_stop")
        return state

    def _safe_run(self, agent_name: str, state: ResearchState, parent_node_id: str | None = None) -> ResearchState:
        """Run a worker with retry-once on transient errors."""
        worker = self._workers.get(agent_name)
        if worker is None:
            state.errors.append(f"Unknown agent: {agent_name}")
            return state

        worker_node = state.add_visual_node(
            label=f"{agent_name.title()} Agent",
            kind="agent",
            iteration=state.iteration,
            metadata={"description": worker.description, "agent": agent_name},
            parent_id=parent_node_id or state.current_visual_node_id,
            edge_label=agent_name,
        )
        state.active_agent_node_id = worker_node
        state.current_visual_node_id = worker_node

        for attempt in range(1, 3):
            try:
                with trace_span(f"worker:{agent_name}", state=state) as span:
                    span["attributes"]["attempt"] = attempt
                    span["attributes"]["agent_tool"] = worker.description
                    updated = worker.execute(state)
                    updated.current_visual_node_id = worker_node
                    updated.active_agent_node_id = worker_node
                    return updated
            except Exception as exc:
                logger.warning("Agent '%s' attempt %d failed: %s", agent_name, attempt, exc)
                if attempt == 2:
                    state.errors.append(f"{agent_name} failed after 2 attempts: {exc}")
                else:
                    time.sleep(1)
        return state
