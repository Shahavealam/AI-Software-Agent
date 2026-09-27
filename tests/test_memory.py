"""Tests for the tiered memory engine (all backends offline-safe)."""

from __future__ import annotations

from app.core.memory import EntityMemory, MemoryManager, VectorMemory, VolatileMemory


async def test_volatile_memory_roundtrip() -> None:
    mem = VolatileMemory(capacity=10)
    await mem.push("user", "hello")
    await mem.push("Developer", "code")
    tail = await mem.tail(1)
    assert tail[0]["content"] == "code"
    assert "user: hello" in await mem.transcript()
    assert len(mem) == 2
    await mem.clear()
    assert len(mem) == 0


async def test_vector_memory_fallback_recall(tmp_cwd) -> None:
    mem = VectorMemory(persist_dir=str(tmp_cwd / "chroma"))
    await mem.add("pytest fix: wrap parser in try/except ValueError", {"kind": "bugfix"})
    await mem.add("react button component with useState hook", {"kind": "pattern"})
    hits = await mem.query("pytest ValueError parser", k=1)
    assert hits and "try/except" in hits[0]["text"]
    patterns = await mem.recall_patterns("python", "pytest parser", k=1)
    assert patterns and "try/except" in patterns[0]


async def test_entity_memory_persists(tmp_path) -> None:
    path = str(tmp_path / "entities.json")
    mem = EntityMemory(path=path)
    await mem.set("branch", "main")
    await mem.update({"env": "test", "retries": 3})
    assert await mem.get("branch") == "main"
    assert await mem.get("missing", "dflt") == "dflt"
    snap = await mem.snapshot()
    assert snap["env"] == "test"
    # reload from disk
    assert await EntityMemory(path=path).get("branch") == "main"


async def test_summary_trigger_and_compaction(tmp_cwd) -> None:
    mm = MemoryManager()
    # tiny window forces the 75%-style trigger without a huge fixture
    mm.summariser.settings.max_context_tokens = 200
    try:
        big = "decision: use pytest for all suites\n" + ("lorem ipsum dolor " * 200)
        assert mm.summariser.should_summarise(big)
        assert not mm.summariser.should_summarise("tiny")
        compacted = await mm.summariser.maybe_compact(big, {"branch": "main"})
        assert "Epistemic Summary Block" in compacted
        assert "pytest" in compacted  # decision preserved
        assert mm.llm.count_tokens(compacted) < mm.llm.count_tokens(big)
    finally:
        mm.summariser.settings.max_context_tokens = 128_000


async def test_memory_manager_facade(tmp_cwd) -> None:
    mm = MemoryManager()
    await mm.remember_turn("user", "prefer type-hinted python")
    doc_id = await mm.store_fix("boom", "guard clause")
    assert doc_id
    assert await mm.recall("guard clause")
    compacted = await mm.compact_if_needed({"goal": "demo"})
    assert "user: prefer type-hinted python" in compacted
