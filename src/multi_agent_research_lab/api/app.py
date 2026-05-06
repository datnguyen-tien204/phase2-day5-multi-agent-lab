"""FastAPI app for the React visual dashboard."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from pydantic import BaseModel, Field

from multi_agent_research_lab.core.schemas import ResearchQuery
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.graph.workflow import MultiAgentWorkflow
from multi_agent_research_lab.services.storage import LocalArtifactStore
from multi_agent_research_lab.services.visualization import build_dashboard_payload

try:  # Optional dependency; keeps CI imports safe when FastAPI is not installed.
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import StreamingResponse
except Exception as exc:  # pragma: no cover
    raise RuntimeError(
        "FastAPI is not installed. Install optional API dependencies to run the dashboard."
    ) from exc


class RunRequest(BaseModel):
    prompt: str = Field(..., min_length=5)
    audience: str = Field(default="technical learners")
    max_sources: int = Field(default=5, ge=1, le=20)


app = FastAPI(title="Multi-Agent Research Lab Dashboard API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/sample")
def sample() -> dict:
    sample_path = Path("reports") / "dashboard_latest.json"
    if sample_path.exists():
        return json.loads(sample_path.read_text(encoding="utf-8"))
    state = ResearchState(
        request=ResearchQuery(
            query="Research GraphRAG state-of-the-art and write a 500-word summary",
            audience="technical learners",
        )
    )
    result = MultiAgentWorkflow().run(state)
    payload = build_dashboard_payload(result)
    sample_path.parent.mkdir(parents=True, exist_ok=True)
    sample_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


@app.post("/api/run")
def run_workflow(req: RunRequest) -> dict:
    state = ResearchState(
        request=ResearchQuery(query=req.prompt, audience=req.audience, max_sources=req.max_sources)
    )
    result = MultiAgentWorkflow().run(state)
    payload = build_dashboard_payload(result)
    store = LocalArtifactStore()
    graph_json = json.dumps(payload, indent=2)
    store.write_text("dashboard_latest.json", graph_json)
    return payload


@app.post("/api/run-stream")
def run_workflow_stream(req: RunRequest) -> StreamingResponse:
    """Stream graph snapshots while the workflow is running."""

    def _events():
        state = ResearchState(
            request=ResearchQuery(query=req.prompt, audience=req.audience, max_sources=req.max_sources)
        )
        result_box: dict[str, ResearchState | None] = {"state": None}
        error_box: dict[str, BaseException | None] = {"error": None}

        def _run() -> None:
            try:
                result_box["state"] = MultiAgentWorkflow().run(state)
            except BaseException as exc:  # pragma: no cover - streamed to caller
                error_box["error"] = exc

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

        last_signature: tuple[int, int, int, str] | None = None
        while thread.is_alive():
            signature = (
                len(state.visual_nodes),
                len(state.visual_edges),
                len(state.route_history),
                state.status,
            )
            if signature != last_signature:
                payload = build_dashboard_payload(state)
                yield f"event: update\ndata: {json.dumps(payload)}\n\n"
                last_signature = signature
            time.sleep(0.15)

        thread.join()
        if error_box["error"] is not None:
            payload = {"status": "failed", "error": str(error_box["error"])}
            yield f"event: error\ndata: {json.dumps(payload)}\n\n"
            return

        final_state = result_box["state"] or state
        payload = build_dashboard_payload(final_state)
        store = LocalArtifactStore()
        store.write_text("dashboard_latest.json", json.dumps(payload, indent=2))
        yield f"event: final\ndata: {json.dumps(payload)}\n\n"

    return StreamingResponse(_events(), media_type="text/event-stream")
