"""Tracing hooks with JSON export support.

Improvements vs skeleton:
- Span nesting (parent_span tracking)
- Auto-attach to ResearchState.trace
- JSON-serialisable export
- Wall-clock timestamps
"""

from __future__ import annotations

import datetime
import json
import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from time import perf_counter
from typing import Any

logger = logging.getLogger(__name__)


def _langfuse_client():
    """Return Langfuse client if configured; otherwise None."""
    try:
        from multi_agent_research_lab.core.config import get_settings

        settings = get_settings()
        if settings.langfuse_public_key and not os.getenv("LANGFUSE_PUBLIC_KEY"):
            os.environ["LANGFUSE_PUBLIC_KEY"] = settings.langfuse_public_key
        if settings.langfuse_secret_key and not os.getenv("LANGFUSE_SECRET_KEY"):
            os.environ["LANGFUSE_SECRET_KEY"] = settings.langfuse_secret_key
        if settings.langfuse_base_url and not os.getenv("LANGFUSE_HOST"):
            os.environ["LANGFUSE_HOST"] = settings.langfuse_base_url
        if not settings.langfuse_public_key or not settings.langfuse_secret_key:
            return None
        from langfuse import get_client

        return get_client()
    except Exception as exc:  # pragma: no cover - optional dependency/provider
        logger.debug("Langfuse unavailable: %s", exc)
        return None


def flush_langfuse() -> None:
    """Flush queued Langfuse events when configured."""
    client = _langfuse_client()
    if client is not None:
        try:
            client.flush()
        except Exception as exc:  # pragma: no cover
            logger.debug("Langfuse flush failed: %s", exc)


@contextmanager
def trace_span(
    name: str,
    attributes: dict[str, Any] | None = None,
    state: Any = None,          # ResearchState | None
) -> Iterator[dict[str, Any]]:
    """Minimal span context used by every agent.

    If `state` is provided, the finished span is appended to state.trace automatically.
    """
    started = perf_counter()
    ts = datetime.datetime.utcnow().isoformat()
    span: dict[str, Any] = {
        "name": name,
        "started_at": ts,
        "attributes": attributes or {},
        "duration_seconds": None,
        "error": None,
    }
    client = _langfuse_client()
    langfuse_cm = None
    try:
        if client is not None:
            langfuse_cm = client.start_as_current_span(
                name=name,
                input=attributes or {},
                metadata={
                    "agent": (attributes or {}).get("agent"),
                    "iteration": getattr(state, "iteration", None),
                    "route_history": getattr(state, "route_history", None),
                },
            )
            langfuse_cm.__enter__()
            if state is not None:
                client.update_current_trace(
                    name=f"multi-agent: {state.request.query[:80]}",
                    session_id="multi-agent-research-lab",
                    user_id="2A202600217",
                    input=state.request.query,
                    tags=["vinuni", "multi-agent", "research-lab"],
                    metadata={"audience": state.request.audience},
                )
        yield span
    except Exception as exc:
        span["error"] = str(exc)
        if client is not None:
            try:
                client.update_current_span(level="ERROR", status_message=str(exc))
            except Exception:
                pass
        raise
    finally:
        span["duration_seconds"] = round(perf_counter() - started, 4)
        if client is not None:
            try:
                client.update_current_span(
                    output={"duration_seconds": span["duration_seconds"], "error": span["error"]},
                    metadata=span["attributes"],
                )
            except Exception:
                pass
        if langfuse_cm is not None:
            try:
                langfuse_cm.__exit__(None, None, None)
            except Exception as exc:
                logger.debug("Langfuse span close failed: %s", exc)
        logger.debug("SPAN[%s] %.3fs %s", name, span["duration_seconds"], attributes)
        if state is not None:
            state.add_trace_event(name, span)


class TraceExporter:
    """Export collected trace events to JSON for offline analysis."""

    @staticmethod
    def to_json(state: Any, pretty: bool = True) -> str:
        """Serialise state.trace to JSON string."""
        indent = 2 if pretty else None
        return json.dumps(state.trace, indent=indent, default=str)

    @staticmethod
    def save(state: Any, path: Path) -> None:
        """Write trace JSON to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(TraceExporter.to_json(state), encoding="utf-8")
        logger.info("Trace saved → %s (%d events)", path, len(state.trace))

    @staticmethod
    def summary(state: Any) -> str:
        """Return a human-readable one-liner per span."""
        lines = ["=== Trace Summary ==="]
        for event in state.trace:
            p = event.get("payload", {})
            dur = p.get("duration_seconds", "?")
            err = f" ❌ {p.get('error')}" if p.get("error") else ""
            lines.append(f"  [{p.get('started_at','')[:19]}] {event['name']:30s}  {dur}s{err}")
        return "\n".join(lines)
