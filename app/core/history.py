"""Persistent conversation history: sessions + messages with MongoDB backend.

Why this module exists
-----------------------
The agent previously kept conversation state only in :class:`VolatileMemory`
(in-process, lost on restart) and a single global ``entities.json`` file.
There was no per-session history, no title/rename/delete, and no way to
resume a previous conversation ("further steps").

What this module provides
-------------------------
* :class:`ChatSession` / :class:`ChatMessage` — typed contracts shared by
  the orchestrator, the HTTP API and the frontend.
* :class:`BaseHistoryStore` — async CRUD contract:
  create / list / get / rename / delete sessions, append / list messages,
  and render prior turns as LLM context.
* :class:`FileHistoryStore` — JSON-file fallback (offline / CI safe).
  Used whenever ``MONGODB_URI`` is empty.
* :class:`MongoHistoryStore` — production backend over ``motor`` (async).
  Used whenever ``MONGODB_URI`` is set.
* :func:`get_history_store` — process-wide singleton factory.

MongoDB document shapes
-----------------------
``sessions`` collection::

    {"_id": "<session_id>", "title": "...", "created_at": float,
     "updated_at": float, "message_count": int,
     "last_preview": str, "metadata": {...}}

``messages`` collection::

    {"_id": "<msg_id>", "session_id": "...", "role": "user|assistant|system",
     "content": "...", "agent": "Developer|...", "kind": "goal|token|result|note",
     "created_at": float, "extra": {...}}

Indexes created on first connect: ``sessions(updated_at desc)``,
``messages(session_id, created_at)``.
"""

from __future__ import annotations

import abc
import asyncio
import json
import time
import uuid
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.config import get_settings, logger

ChatRole = Literal["user", "assistant", "system"]
MessageKind = Literal["goal", "token", "result", "note", "state"]

__all__ = [
    "ChatMessage",
    "ChatSession",
    "BaseHistoryStore",
    "FileHistoryStore",
    "MongoHistoryStore",
    "auto_title",
    "get_history_store",
    "reset_history_store",
]


def auto_title(goal: str, max_len: int = 60) -> str:
    """Derive a human-friendly session title from the first user goal."""
    first_line = (goal or "").strip().splitlines()[0].strip() if goal.strip() else "Untitled session"
    # strip common prefixes like "please", keep it readable
    title = " ".join(first_line.split())
    if len(title) > max_len:
        title = title[: max_len - 1].rstrip() + "…"
    return title or "Untitled session"


def _now() -> float:
    return time.time()


def _new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


class ChatSession(BaseModel):
    """One conversation thread (sidebar item in the frontend)."""

    id: str = Field(default_factory=lambda: _new_id("s-"))
    title: str = "Untitled session"
    created_at: float = Field(default_factory=_now)
    updated_at: float = Field(default_factory=_now)
    message_count: int = 0
    last_preview: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    """One persisted turn (user goal or assistant result)."""

    id: str = Field(default_factory=lambda: _new_id("m-"))
    session_id: str
    role: ChatRole = "user"
    content: str
    agent: str = ""
    kind: MessageKind = "note"
    created_at: float = Field(default_factory=_now)
    extra: dict[str, Any] = Field(default_factory=dict)


class BaseHistoryStore(abc.ABC):
    """Async CRUD contract for conversation history."""

    # -- sessions ----------------------------------------------------
    @abc.abstractmethod
    async def create_session(self, title: str = "", metadata: dict[str, Any] | None = None) -> ChatSession:
        ...

    @abc.abstractmethod
    async def list_sessions(self, limit: int = 50, offset: int = 0) -> list[ChatSession]:
        ...

    @abc.abstractmethod
    async def get_session(self, session_id: str) -> ChatSession | None:
        ...

    @abc.abstractmethod
    async def rename_session(self, session_id: str, title: str) -> ChatSession:
        ...

    @abc.abstractmethod
    async def delete_session(self, session_id: str) -> bool:
        ...

    @abc.abstractmethod
    async def ensure_session(self, session_id: str = "", title: str = "") -> ChatSession:
        """Return existing session or create one (used by orchestrator/SSE)."""

    # -- messages ----------------------------------------------------
    @abc.abstractmethod
    async def append_message(
        self,
        session_id: str,
        role: ChatRole,
        content: str,
        agent: str = "",
        kind: MessageKind = "note",
        extra: dict[str, Any] | None = None,
    ) -> ChatMessage:
        ...

    @abc.abstractmethod
    async def get_messages(self, session_id: str, limit: int = 100) -> list[ChatMessage]:
        ...

    # -- helpers ------------------------------------------------------
    async def get_context(self, session_id: str, limit: int = 20, max_chars: int = 6000) -> str:
        """Render the last N turns as compact LLM context (oldest → newest)."""
        msgs = await self.get_messages(session_id, limit=limit)
        lines: list[str] = []
        total = 0
        for m in msgs:
            line = f"{m.role.upper()} ({m.agent or m.kind}): {m.content}"
            if total + len(line) > max_chars:
                break
            lines.append(line[:2000])
            total += len(line)
        return "\n".join(lines)

    async def close(self) -> None:
        """Release backend resources (no-op for file store)."""


# ── File-backed fallback (offline / tests) ───────────────────────────
class FileHistoryStore(BaseHistoryStore):
    """JSON-file history store: ``{sessions: {...}, messages: {...}}``.

    The whole file is loaded once and written atomically (tmp + rename)
    on every mutation. Good enough for single-process dev/CI use.
    """

    def __init__(self, path: str | None = None) -> None:
        self.path = Path(path or get_settings().history_store_path)
        self._lock = asyncio.Lock()
        self._sessions: dict[str, ChatSession] = {}
        self._messages: dict[str, list[ChatMessage]] = {}
        self._load()

    # -- persistence --------------------------------------------------
    def _load(self) -> None:
        try:
            if self.path.exists():
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                for sid, s in (raw.get("sessions") or {}).items():
                    try:
                        self._sessions[sid] = ChatSession(**s)
                    except Exception:
                        continue
                for sid, msgs in (raw.get("messages") or {}).items():
                    parsed: list[ChatMessage] = []
                    for m in msgs or []:
                        try:
                            parsed.append(ChatMessage(**m))
                        except Exception:
                            continue
                    self._messages[sid] = sorted(parsed, key=lambda m: m.created_at)
        except Exception as exc:
            logger.warning("history file load failed (%s)", exc)

    async def _persist(self) -> None:
        def _write() -> None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "sessions": {sid: s.model_dump() for sid, s in self._sessions.items()},
                "messages": {sid: [m.model_dump() for m in msgs] for sid, msgs in self._messages.items()},
            }
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
            tmp.replace(self.path)

        await asyncio.to_thread(_write)

    # -- sessions ------------------------------------------------------
    async def create_session(self, title: str = "", metadata: dict[str, Any] | None = None) -> ChatSession:
        session = ChatSession(title=title or "Untitled session", metadata=metadata or {})
        async with self._lock:
            self._sessions[session.id] = session
            self._messages.setdefault(session.id, [])
        await self._persist()
        return session

    async def list_sessions(self, limit: int = 50, offset: int = 0) -> list[ChatSession]:
        async with self._lock:
            ordered = sorted(self._sessions.values(), key=lambda s: s.updated_at, reverse=True)
        return ordered[offset : offset + limit]

    async def get_session(self, session_id: str) -> ChatSession | None:
        async with self._lock:
            return self._sessions.get(session_id)

    async def rename_session(self, session_id: str, title: str) -> ChatSession:
        title = title.strip()
        if not title:
            raise ValueError("title must not be empty")
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError(f"unknown session: {session_id}")
            session.title = title[:200]
            session.updated_at = _now()
        await self._persist()
        return session

    async def delete_session(self, session_id: str) -> bool:
        async with self._lock:
            existed = session_id in self._sessions
            self._sessions.pop(session_id, None)
            self._messages.pop(session_id, None)
        if existed:
            await self._persist()
        return existed

    async def ensure_session(self, session_id: str = "", title: str = "") -> ChatSession:
        if session_id:
            existing = await self.get_session(session_id)
            if existing is not None:
                return existing
            session = ChatSession(id=session_id, title=title or "Untitled session")
            async with self._lock:
                self._sessions[session.id] = session
                self._messages.setdefault(session.id, [])
            await self._persist()
            return session
        return await self.create_session(title=title or "Untitled session")

    # -- messages -------------------------------------------------------
    async def append_message(
        self,
        session_id: str,
        role: ChatRole,
        content: str,
        agent: str = "",
        kind: MessageKind = "note",
        extra: dict[str, Any] | None = None,
    ) -> ChatMessage:
        content = content or ""
        max_msgs = get_settings().history_max_messages
        msg_cap = get_settings().history_message_max_chars
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                session = ChatSession(id=session_id, title=auto_title(content))
                self._sessions[session.id] = session
                self._messages.setdefault(session.id, [])
            msg = ChatMessage(session_id=session.id, role=role, content=content[:msg_cap], agent=agent, kind=kind, extra=extra or {})
            buf = self._messages.setdefault(session.id, [])
            buf.append(msg)
            # cap per-session buffer (oldest dropped)
            if len(buf) > max_msgs:
                del buf[: len(buf) - max_msgs]
            session.message_count = len(buf)
            session.updated_at = msg.created_at
            session.last_preview = content[:200].replace("\n", " ")
            if session.title.strip().lower() in ("", "untitled session", "new chat") and role == "user" and content.strip():
                session.title = auto_title(content)
        await self._persist()
        return msg

    async def get_messages(self, session_id: str, limit: int = 100) -> list[ChatMessage]:
        async with self._lock:
            return list(self._messages.get(session_id, [])[-limit:])


# ── MongoDB backend ──────────────────────────────────────────────────
class MongoHistoryStore(BaseHistoryStore):
    """Production history store over MongoDB (``motor`` async driver)."""

    def __init__(
        self,
        uri: str | None = None,
        db_name: str | None = None,
        sessions_collection: str | None = None,
        messages_collection: str | None = None,
    ) -> None:
        settings = get_settings()
        self._uri = uri or settings.mongodb_uri
        if not self._uri:
            raise ValueError("MONGODB_URI is empty — cannot create MongoHistoryStore")
        try:
            from motor.motor_asyncio import AsyncIOMotorClient
        except ImportError as exc:
            raise RuntimeError("motor is not installed. Install it with: pip install motor") from exc
        self._client = AsyncIOMotorClient(self._uri)
        db = self._client[db_name or settings.mongodb_db]
        self._sessions = db[sessions_collection or settings.mongodb_sessions_collection]
        self._messages = db[messages_collection or settings.mongodb_messages_collection]
        self._indexes_ready = False
        self._lock = asyncio.Lock()

    async def _ensure_indexes(self) -> None:
        if self._indexes_ready:
            return
        async with self._lock:
            if self._indexes_ready:
                return
            await self._sessions.create_index("updated_at")
            await self._messages.create_index([("session_id", 1), ("created_at", 1)])
            self._indexes_ready = True

    @staticmethod
    def _session_from_doc(doc: dict[str, Any]) -> ChatSession:
        doc = dict(doc)
        if "_id" in doc:
            doc["id"] = doc.pop("_id")
        return ChatSession(**{k: v for k, v in doc.items() if k in ChatSession.model_fields})

    @staticmethod
    def _message_from_doc(doc: dict[str, Any]) -> ChatMessage:
        doc = dict(doc)
        if "_id" in doc:
            doc["id"] = doc.pop("_id")
        return ChatMessage(**{k: v for k, v in doc.items() if k in ChatMessage.model_fields})

    # -- sessions ------------------------------------------------------
    async def create_session(self, title: str = "", metadata: dict[str, Any] | None = None) -> ChatSession:
        await self._ensure_indexes()
        session = ChatSession(title=title or "Untitled session", metadata=metadata or {})
        doc = session.model_dump()
        doc["_id"] = doc.pop("id")
        await self._sessions.insert_one(doc)
        return session

    async def list_sessions(self, limit: int = 50, offset: int = 0) -> list[ChatSession]:
        await self._ensure_indexes()
        cursor = self._sessions.find({}).sort("updated_at", -1).skip(offset).limit(limit)
        return [self._session_from_doc(d) async for d in cursor]

    async def get_session(self, session_id: str) -> ChatSession | None:
        await self._ensure_indexes()
        doc = await self._sessions.find_one({"_id": session_id})
        return self._session_from_doc(doc) if doc else None

    async def rename_session(self, session_id: str, title: str) -> ChatSession:
        from pymongo import ReturnDocument

        title = title.strip()
        if not title:
            raise ValueError("title must not be empty")
        await self._ensure_indexes()
        res = await self._sessions.find_one_and_update(
            {"_id": session_id}, {"$set": {"title": title[:200], "updated_at": _now()}},
            return_document=ReturnDocument.AFTER,
        )
        if res is None:
            raise KeyError(f"unknown session: {session_id}")
        return self._session_from_doc(res)

    async def delete_session(self, session_id: str) -> bool:
        await self._ensure_indexes()
        res = await self._sessions.delete_one({"_id": session_id})
        await self._messages.delete_many({"session_id": session_id})
        return res.deleted_count > 0

    async def ensure_session(self, session_id: str = "", title: str = "") -> ChatSession:
        await self._ensure_indexes()
        if session_id:
            existing = await self.get_session(session_id)
            if existing is not None:
                return existing
            session = ChatSession(id=session_id, title=title or "Untitled session")
            doc = session.model_dump()
            doc["_id"] = doc.pop("id")
            await self._sessions.insert_one(doc)
            return session
        return await self.create_session(title=title or "Untitled session")

    # -- messages -------------------------------------------------------
    async def append_message(
        self,
        session_id: str,
        role: ChatRole,
        content: str,
        agent: str = "",
        kind: MessageKind = "note",
        extra: dict[str, Any] | None = None,
    ) -> ChatMessage:
        await self._ensure_indexes()
        content = content or ""
        msg_cap = get_settings().history_message_max_chars
        session = await self.get_session(session_id)
        if session is None:
            session = await self.ensure_session(session_id, title=auto_title(content))
        msg = ChatMessage(session_id=session.id, role=role, content=content[:msg_cap], agent=agent, kind=kind, extra=extra or {})
        doc = msg.model_dump()
        doc["_id"] = doc.pop("id")
        await self._messages.insert_one(doc)
        count = await self._messages.count_documents({"session_id": session.id})
        update: dict[str, Any] = {
            "updated_at": msg.created_at,
            "message_count": count,
            "last_preview": content[:200].replace("\n", " "),
        }
        if session.title.strip().lower() in ("", "untitled session", "new chat") and role == "user" and content.strip():
            update["title"] = auto_title(content)
        await self._sessions.update_one({"_id": session.id}, {"$set": update})
        # cap per-session buffer
        max_msgs = get_settings().history_max_messages
        if count > max_msgs:
            oldest = self._messages.find({"session_id": session.id}).sort("created_at", 1).limit(count - max_msgs)
            ids = [d["_id"] async for d in oldest]
            if ids:
                await self._messages.delete_many({"_id": {"$in": ids}})
        return msg

    async def get_messages(self, session_id: str, limit: int = 100) -> list[ChatMessage]:
        await self._ensure_indexes()
        # Newest-first with a DB-side limit, then restore chronological order —
        # avoids loading the whole thread when it grows large.
        cursor = self._messages.find({"session_id": session_id}).sort("created_at", -1).limit(limit)
        docs = [d async for d in cursor]
        return [self._message_from_doc(d) for d in reversed(docs)]

    async def close(self) -> None:
        self._client.close()


# ── Singleton factory ────────────────────────────────────────────────
_history_store: BaseHistoryStore | None = None


def get_history_store() -> BaseHistoryStore:
    """Return the process-wide history store.

    MongoDB when ``MONGODB_URI`` is set, otherwise the JSON-file fallback
    (offline/CI safe). Override the backend in tests via
    :func:`reset_history_store` or by clearing ``MONGODB_URI``.
    """
    global _history_store
    if _history_store is None:
        settings = get_settings()
        if settings.mongodb_uri:
            try:
                _history_store = MongoHistoryStore()
                logger.info("HistoryStore: mongodb backend db=%s", settings.mongodb_db)
            except Exception as exc:
                logger.warning("HistoryStore mongo unavailable (%s) — file fallback", exc)
                _history_store = FileHistoryStore()
        else:
            _history_store = FileHistoryStore()
    return _history_store


def reset_history_store(store: BaseHistoryStore | None = None) -> None:
    """Reset the singleton (tests / backend switching)."""
    global _history_store
    _history_store = store
