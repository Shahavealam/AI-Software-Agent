"""Tiered memory engine + token-optimised epistemic summarisation.

Layers
------
* :class:`VolatileMemory`  — short-term, thread-safe in-memory buffer scoped to
  the active DAG execution loop.
* :class:`VectorMemory`    — long-term semantic cache (ChromaDB, with a pure
  in-process cosine fallback so tests/CI never need a server).
* :class:`EntityMemory`    — episodic key-value store for project metadata
  (branch, env vars, architecture decisions), persisted as JSON.
* :class:`SummaryMemory`   — moving-window / hierarchical summariser. When the
  rolling transcript nears ``summary_trigger_ratio`` (default 75%) of
  ``max_context_tokens`` it condenses history into an *Epistemic Summary
  Block* that preserves system state, variables and decisions.
* :class:`MemoryManager`   — facade wiring the four layers together.
"""

from __future__ import annotations

import asyncio
import json
import math
import re
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.config import get_settings, logger
from app.core.llm import LLMGateway

__all__ = [
    "EpistemicSummary",
    "VolatileMemory",
    "VectorMemory",
    "EntityMemory",
    "SummaryMemory",
    "MemoryManager",
]


# ── Epistemic summary block ──────────────────────────────────────────
@dataclass
class EpistemicSummary:
    """Structured condensation of history that survives context compaction."""

    decisions: list[str] = field(default_factory=list)
    system_state: dict[str, Any] = field(default_factory=dict)
    variables: dict[str, Any] = field(default_factory=dict)
    open_questions: list[str] = field(default_factory=list)
    narrative: str = ""
    created_at: float = field(default_factory=time.time)

    def render(self) -> str:
        lines = ["# Epistemic Summary Block"]
        if self.narrative:
            lines += ["", "## Narrative", self.narrative]
        if self.decisions:
            lines += ["", "## Architectural Decisions"] + [f"- {d}" for d in self.decisions]
        if self.system_state:
            lines += ["", "## System State"] + [f"- {k}: {v}" for k, v in self.system_state.items()]
        if self.variables:
            lines += ["", "## Variables"] + [f"- {k} = {v!r}" for k, v in self.variables.items()]
        if self.open_questions:
            lines += ["", "## Open Questions"] + [f"- {q}" for q in self.open_questions]
        return "\n".join(lines)


# ── Short-term volatile buffer ───────────────────────────────────────
class VolatileMemory:
    """Thread-safe volatile buffer for the active DAG loop."""

    def __init__(self, capacity: int = 200) -> None:
        self._buf: deque[dict[str, Any]] = deque(maxlen=capacity)
        self._lock = asyncio.Lock()

    async def push(self, role: str, content: str, meta: dict[str, Any] | None = None) -> None:
        async with self._lock:
            self._buf.append({"role": role, "content": content, "meta": meta or {}, "ts": time.time()})

    async def tail(self, n: int = 20) -> list[dict[str, Any]]:
        async with self._lock:
            return list(self._buf)[-n:]

    async def transcript(self) -> str:
        async with self._lock:
            return "\n".join(f"{m['role']}: {m['content']}" for m in self._buf)

    async def clear(self) -> None:
        async with self._lock:
            self._buf.clear()

    def __len__(self) -> int:
        return len(self._buf)


# ── Long-term semantic vector memory ─────────────────────────────────
def _bow_vector(text: str, dim: int = 256) -> list[float]:
    vec = [0.0] * dim
    for tok in re.findall(r"[a-z0-9_]+", text.lower()):
        vec[hash(tok) % dim] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


class VectorMemory:
    """Semantic cache: ChromaDB when available, else in-memory cosine store.

    Stores bug fixes, design preferences and reusable code patterns.
    """

    def __init__(self, collection: str = "agent_memory", persist_dir: str | None = None) -> None:
        self.settings = get_settings()
        self._lock = asyncio.Lock()
        self._fallback: list[dict[str, Any]] = []  # {text, meta, vec}
        self._chroma: Any | None = None
        self._collection: Any | None = None
        if self.settings.vector_backend == "chroma":
            try:
                import chromadb

                client = chromadb.PersistentClient(path=persist_dir or self.settings.chroma_persist_dir)
                self._chroma = client
                self._collection = client.get_or_create_collection(collection)
                logger.info("VectorMemory: chroma backend ready")
            except Exception as exc:
                logger.warning("VectorMemory chroma unavailable (%s) — memory fallback", exc)

    async def add(self, text: str, meta: dict[str, Any] | None = None) -> str:
        doc_id = f"m-{int(time.time() * 1000)}-{len(self._fallback)}"
        meta = meta or {}
        async with self._lock:
            if self._collection is not None:
                try:
                    # NOTE: chroma's Collection.add signature is
                    # add(ids, embeddings=None, metadatas=None, documents=None, ...),
                    # so positional args would send `text` as embeddings.
                    # Always use keywords.
                    safe_meta = {k: (v if isinstance(v, (str, int, float, bool)) or v is None else str(v)) for k, v in meta.items()}
                    await asyncio.to_thread(
                        self._collection.add,
                        ids=[doc_id],
                        documents=[text],
                        metadatas=[safe_meta],
                    )
                    return doc_id
                except Exception as exc:
                    logger.warning("chroma add failed (%s); using fallback", exc)
                    self._collection = None
            self._fallback.append({"id": doc_id, "text": text, "meta": meta, "vec": _bow_vector(text)})
        return doc_id

    async def query(self, text: str, k: int = 5) -> list[dict[str, Any]]:
        async with self._lock:
            if self._collection is not None:
                try:
                    # NOTE: Collection.query signature is
                    # query(query_embeddings=None, query_texts=None, ..., n_results=10),
                    # so positional args would send `text` as embeddings.
                    res: dict[str, Any] = await asyncio.to_thread(
                        self._collection.query, query_texts=[text], n_results=k
                    )
                    docs = (res.get("documents") or [[]])[0]
                    metas = (res.get("metadatas") or [[]])[0]
                    ids = (res.get("ids") or [[]])[0]
                    return [{"id": i, "text": d, "meta": m} for i, d, m in zip(ids, docs, metas)]
                except Exception as exc:
                    logger.warning("chroma query failed (%s); using fallback", exc)
                    self._collection = None
            qv = _bow_vector(text)
            ranked = sorted(self._fallback, key=lambda d: _cosine(qv, d["vec"]), reverse=True)
            return [{"id": d["id"], "text": d["text"], "meta": d["meta"]} for d in ranked[:k]]

    async def recall_patterns(self, language: str, task: str, k: int = 3) -> list[str]:
        hits = await self.query(f"{language} {task}", k=k)
        return [h["text"] for h in hits]


# ── Episodic / entity store ──────────────────────────────────────────
class EntityMemory:
    """Persistent key-value manager for project metadata."""

    def __init__(self, path: str | None = None) -> None:
        self.path = Path(path or get_settings().entity_store_path)
        self._lock = asyncio.Lock()
        self._data: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        try:
            if self.path.exists():
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("EntityMemory load failed (%s)", exc)
            self._data = {}

    async def _persist(self) -> None:
        def _write() -> None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self._data, indent=2, default=str), encoding="utf-8")

        await asyncio.to_thread(_write)

    async def set(self, key: str, value: Any) -> None:
        async with self._lock:
            self._data[key] = value
        await self._persist()

    async def get(self, key: str, default: Any = None) -> Any:
        async with self._lock:
            return self._data.get(key, default)

    async def update(self, mapping: dict[str, Any]) -> None:
        async with self._lock:
            self._data.update(mapping)
        await self._persist()

    async def snapshot(self) -> dict[str, Any]:
        async with self._lock:
            return dict(self._data)


# ── Hierarchical summariser ──────────────────────────────────────────
class SummaryMemory:
    """Moving-window compactor producing :class:`EpistemicSummary` blocks.

    Trigger: ``used_tokens >= trigger_ratio * max_context_tokens``.
    Uses the LLM when online, otherwise a deterministic extractive fallback
    so the pipeline never stalls.
    """

    def __init__(self, llm: LLMGateway | None = None) -> None:
        self.settings = get_settings()
        self.llm = llm or LLMGateway()
        self.history: list[EpistemicSummary] = []

    @property
    def threshold(self) -> int:
        return int(self.settings.max_context_tokens * self.settings.summary_trigger_ratio)

    def should_summarise(self, transcript: str) -> bool:
        return self.llm.count_tokens(transcript) >= self.threshold

    async def maybe_compact(self, transcript: str, context: dict[str, Any] | None = None) -> str:
        """Return (possibly compacted) transcript with summary block prepended."""
        if not self.should_summarise(transcript):
            return transcript
        summary = await self.summarise(transcript, context or {})
        self.history.append(summary)
        # keep the freshest ~25% window + the structured block
        tail_budget = self.settings.max_context_tokens // 4
        words = transcript.split()
        tail = " ".join(words[-tail_budget // 4 :])
        compacted = summary.render() + "\n\n# Live Window (post-compaction)\n" + tail
        logger.info("SummaryMemory compacted %d -> %d tokens", self.llm.count_tokens(transcript), self.llm.count_tokens(compacted))
        return compacted

    async def summarise(self, transcript: str, context: dict[str, Any]) -> EpistemicSummary:
        if self.llm.online:
            prompt = (
                "Condense the engineering transcript into: decisions, system_state, "
                "variables, open_questions, narrative (2-4 sentences). "
                f"Extra context: {json.dumps(context, default=str)[:2000]}\n\n{transcript[-12000:]}"
            )
            try:
                raw = await self.llm.chat("You are a precise engineering archivist.", prompt)
                return EpistemicSummary(narrative=raw, system_state=dict(context))
            except Exception as exc:
                logger.warning("LLM summarise failed (%s); extractive fallback", exc)
        return self._extractive(transcript, context)

    def _extractive(self, transcript: str, context: dict[str, Any]) -> EpistemicSummary:
        decisions = [ln.strip() for ln in transcript.splitlines() if re.match(r"\s*(decision|decided|chose|adr)[:\-]", ln, re.I)][:10]
        variables = {k: v for k, v in (context or {}).items() if isinstance(v, (str, int, float, bool))}
        freq = Counter(re.findall(r"[A-Za-z][A-Za-z0-9_]{3,}", transcript))
        narrative = "Topical focus: " + ", ".join(w for w, _ in freq.most_common(8)) + "."
        return EpistemicSummary(decisions=decisions, system_state=dict(context or {}), variables=variables, narrative=narrative)


# ── Facade ───────────────────────────────────────────────────────────
class MemoryManager:
    """Single handle composing the memory stack used by agents/orchestrator."""

    def __init__(self) -> None:
        self.llm = LLMGateway()
        self.short: VolatileMemory = VolatileMemory()
        self.long: VectorMemory = VectorMemory()
        self.entities: EntityMemory = EntityMemory()
        self.summariser: SummaryMemory = SummaryMemory(self.llm)

    async def remember_turn(self, role: str, content: str) -> None:
        await self.short.push(role, content)

    async def compact_if_needed(self, extra_context: dict[str, Any] | None = None) -> str:
        transcript = await self.short.transcript()
        if self.summariser.should_summarise(transcript):
            compacted = await self.summariser.maybe_compact(transcript, extra_context or {})
            await self.short.clear()
            await self.short.push("system", compacted)
            return compacted
        return transcript

    async def store_fix(self, title: str, fix: str, meta: dict[str, Any] | None = None) -> str:
        return await self.long.add(f"{title}\n{fix}", {"kind": "bugfix", **(meta or {})})

    async def recall(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        return await self.long.query(query, k=k)
