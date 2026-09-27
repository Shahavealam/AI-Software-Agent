"""End-to-end orchestrator test (offline mode: deterministic fallbacks)."""

from __future__ import annotations

from app.agents.orchestrator import MultiAgentOrchestrator
from app.core.memory import MemoryManager


async def test_run_stream_event_contract(tmp_cwd) -> None:
    orch = MultiAgentOrchestrator(memory=MemoryManager(), max_retries=1)
    events = [e async for e in orch.run_stream("write a python add(a, b) function")]

    kinds = {e["type"] for e in events}
    assert kinds >= {"state", "token", "result"}

    states = [e for e in events if e["type"] == "state"]
    agents = {e["agent"] for e in states}
    assert {"Orchestrator", "Developer", "Execution", "QA"} <= agents

    result = next(e for e in events if e["type"] == "result")
    st = result["state"]
    assert st["dag"] and len(st["dag"]["nodes"]) >= 3
    assert st["artifacts"] and st["exec_reports"]
    # offline placeholders cannot pass: budget must be respected exactly
    assert st["retries_used"] == 1
    assert st["error"] and "budget" in st["error"].lower()
    assert st["done"] is False


async def test_run_convenience_returns_state(tmp_cwd) -> None:
    orch = MultiAgentOrchestrator(memory=MemoryManager(), max_retries=0)
    state = await orch.run("write a python add(a, b) function")
    assert state.dag is not None and state.retries_used == 0
    assert len(state.exec_reports) >= 1


async def test_self_correction_reroutes_traceback(tmp_cwd) -> None:
    orch = MultiAgentOrchestrator(memory=MemoryManager(), max_retries=2)
    events = [e async for e in orch.run_stream("write a python add(a, b) function")]
    feedback = " ".join(e.get("feedback", "") for e in events if e["type"] == "state")
    assert "Rerouting traceback to Developer" in feedback
