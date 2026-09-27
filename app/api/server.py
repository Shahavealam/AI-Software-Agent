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
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import StreamingResponse
    from pydantic import BaseModel, Field

    _FASTAPI_AVAILABLE = True
except Exception:  # FastAPI is an optional runtime dependency
    FastAPI = None  # type: ignore[assignment,misc]
    HTTPException = Exception  # type: ignore[assignment,misc]
    StreamingResponse = None  # type: ignore[assignment,misc]
    BaseModel = object  # type: ignore[assignment,misc]
    Field = lambda *a, **k: ""  # type: ignore[assignment]
    _FASTAPI_AVAILABLE = False


class RunRequest(BaseModel):  # type: ignore[valid-type,misc]
    """Request body for ``POST /v1/run``."""

    goal: str
    # Reuse an existing session id to continue a conversation ("further
    # steps"). Empty => a new session is created (auto-titled from goal).
    session_id: str = ""


class CreateSessionRequest(BaseModel):  # type: ignore[valid-type,misc]
    title: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)  # type: ignore[valid-type]


class RenameSessionRequest(BaseModel):  # type: ignore[valid-type,misc]
    title: str


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

    # ── Conversation history (sessions + messages) ──────────────
    # Backed by MongoDB when MONGODB_URI is set, otherwise the JSON-file
    # fallback. Lets the frontend list / rename / delete chats and lets
    # follow-up goals continue the same session ("further steps").
    @fast_app.get("/v1/sessions")
    async def list_sessions(limit: int = 50, offset: int = 0) -> Any:
        from app.core.history import get_history_store

        store = get_history_store()
        sessions = await store.list_sessions(limit=min(limit, 200), offset=offset)
        return {"sessions": [s.model_dump() for s in sessions]}

    @fast_app.post("/v1/sessions", status_code=201)
    async def create_session(req: CreateSessionRequest) -> Any:
        from app.core.history import get_history_store

        store = get_history_store()
        session = await store.create_session(title=req.title or "Untitled session", metadata=req.metadata)
        return session.model_dump()

    @fast_app.get("/v1/sessions/{session_id}")
    async def get_session(session_id: str) -> Any:
        from app.core.history import get_history_store

        store = get_history_store()
        session = await store.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="unknown session")
        messages = await store.get_messages(session_id, limit=200)
        return {"session": session.model_dump(), "messages": [m.model_dump() for m in messages]}

    @fast_app.patch("/v1/sessions/{session_id}")
    async def rename_session(session_id: str, req: RenameSessionRequest) -> Any:
        from app.core.history import get_history_store

        store = get_history_store()
        try:
            session = await store.rename_session(session_id, req.title)
        except KeyError:
            raise HTTPException(status_code=404, detail="unknown session")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        return session.model_dump()

    @fast_app.delete("/v1/sessions/{session_id}")
    async def delete_session(session_id: str) -> Any:
        from app.core.history import get_history_store

        store = get_history_store()
        deleted = await store.delete_session(session_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="unknown session")
        return {"deleted": True, "session_id": session_id}

    @fast_app.get("/v1/sessions/{session_id}/messages")
    async def get_messages(session_id: str, limit: int = 100) -> Any:
        from app.core.history import get_history_store

        store = get_history_store()
        session = await store.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="unknown session")
        messages = await store.get_messages(session_id, limit=min(limit, 500))
        return {"session_id": session_id, "messages": [m.model_dump() for m in messages]}

    return fast_app


try:
    app = create_app()
except RuntimeError:
    app = None  # type: ignore[assignment]

__all__ = ["RunRequest", "CreateSessionRequest", "RenameSessionRequest", "app", "create_app"]
