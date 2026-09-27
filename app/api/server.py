"""HTTP/SSE front-end for the multi-agent core.

Serve with::

    uvicorn app.api.server:app --port 8000
    # or
    python -m app.main --serve

``POST /v1/run`` streams ``text/event-stream`` frames — ``token`` (raw
markdown chunks), ``state`` (``TelemetryEvent`` dicts) and a final
``result`` carrying the full :class:`AgentState`.
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any

from app.core.config import get_settings

try:
    from fastapi import FastAPI
    from fastapi.responses import StreamingResponse
    from pydantic import BaseModel

    _FASTAPI_AVAILABLE = True
except Exception:  # FastAPI is an optional runtime dependency
    FastAPI = None  # type: ignore[assignment,misc]
    StreamingResponse = None  # type: ignore[assignment,misc]
    BaseModel = object  # type: ignore[assignment,misc]
    _FASTAPI_AVAILABLE = False


class RunRequest(BaseModel):  # type: ignore[valid-type,misc]
    """Request body for ``POST /v1/run``."""

    goal: str
    session_id: str = ""


def create_app() -> Any:
    """Build the FastAPI application (imports orchestrator lazily)."""
    if not _FASTAPI_AVAILABLE:
        raise RuntimeError("FastAPI is not installed. Install it with: pip install fastapi uvicorn sse-starlette")

    from app.main import arun_stream

    fast_app = FastAPI(title="AI Software Agent — multi-agent core", version="1.0.0")

    # CORS: frontend (Next.js on :3000) calls this API cross-origin.
    # Without this, browsers block GET /health responses and fail
    # POST /v1/run preflight (OPTIONS → 405), surfacing as "backend unreachable".
    from fastapi.middleware.cors import CORSMiddleware

    fast_app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3001",
        ],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @fast_app.get("/health")
    async def health() -> dict[str, str]:
        settings = get_settings()
        return {"status": "ok", "llm": "online" if settings.openai_api_key else "offline"}

    @fast_app.post("/v1/run")
    async def v1_run(req: RunRequest) -> Any:
        async def gen() -> AsyncGenerator[str, None]:
            async for evt in arun_stream(req.goal, req.session_id):
                kind = evt.get("type", "state")
                yield f"event: {kind}\ndata: {json.dumps(evt, default=str)}\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream")

    return fast_app


try:
    app = create_app()
except RuntimeError:
    app = None  # type: ignore[assignment]

__all__ = ["RunRequest", "app", "create_app"]
