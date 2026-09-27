"""Orchestrator: native async event-loop state-graph manager.

Topology
--------
ProductManager (DAG) → Architect → [Developer → QA → Execution]×N → Writer

The bracketed Developer/QA/Execution cycle is the agentic self-correction
loop: tracebacks flow back to the Developer with a retry budget
(``max_self_correction_retries``, default 3). Every transition emits a
``TelemetryEvent``; token production streams as raw markdown.

A LangGraph port would map 1:1 onto :meth:`MultiAgentOrchestrator.run_stream`
nodes; the native loop is kept dependency-light and fully typed.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from app.agents.architect import ArchitectAgent
from app.agents.base import EmitFn
from app.agents.developer import DeveloperAgent
from app.agents.execution import ExecutionAgent
from app.agents.product_manager import ProductManagerAgent
from app.agents.qa import QAAgent
from app.agents.writer import WriterAgent
from app.core.config import get_settings, logger
from app.core.memory import MemoryManager
from app.core.state import AgentName, AgentState, TaskStatus, TelemetryEvent, TokenEvent


class MultiAgentOrchestrator:
    """State-graph manager governing routing, propagation and loop checks."""

    def __init__(self, memory: MemoryManager | None = None, max_retries: int | None = None) -> None:
        self.memory = memory or MemoryManager()
        self.max_retries = max_retries if max_retries is not None else get_settings().max_self_correction_retries
        shared = self.memory
        self.router = ProductManagerAgent(memory=shared)
        self.architect = ArchitectAgent(memory=shared)
        self.developer = DeveloperAgent(memory=shared)
        self.qa = QAAgent(memory=shared)
        self.executor = ExecutionAgent(memory=shared)
        self.writer = WriterAgent(memory=shared)

    # -- public streaming API -----------------------------------------
    async def run_stream(self, goal: str, session_id: str = "") -> AsyncGenerator[dict[str, Any], None]:
        """Yield ``{'type': 'state'|'token'|'result', ...}`` event dicts.

        Consumed by SSE (``text/event-stream``), websockets, or the CLI.
        """
        state = AgentState(goal=goal, max_retries=self.max_retries)
        if session_id:
            state.session_id = session_id

        async def emit(d: dict[str, Any]) -> None:
            self._pending.append({"type": "state", **d})

        self._pending: list[dict[str, Any]] = []
        await self._emit_state(emit, AgentName.ORCHESTRATOR, "started", f"Goal received: {goal[:150]}", state)

        try:
            # 1. Route / plan
            async for chunk in self.router.stream(state, emit):
                yield {"type": "token", **TokenEvent(agent="ProductManager", token=chunk, session_id=state.session_id).model_dump()}
            async for evt in self._flush_states():
                yield evt
            if not state.dag or not state.dag.nodes:
                raise RuntimeError("Router produced an empty DAG")

            # 2. Architecture
            async for chunk in self.architect.stream(state, emit):
                yield {"type": "token", **TokenEvent(agent="Architect", token=chunk, session_id=state.session_id).model_dump()}
            async for evt in self._flush_states():
                yield evt

            # 3. Self-correction loop: Developer → QA → Execution (≤ budget)
            attempt = 0
            while True:
                attempt += 1
                await self._emit_state(emit, AgentName.ORCHESTRATOR, "iteration", f"Correction cycle {attempt}/{self.max_retries + 1}", state)
                async for evt in self._flush_states():
                    yield evt

                async for chunk in self.developer.stream(state, emit):
                    yield {"type": "token", **TokenEvent(agent="Developer", token=chunk, session_id=state.session_id).model_dump()}
                async for evt in self._flush_states():
                    yield evt

                state = await self.qa.run(state, emit)
                async for evt in self._flush_states():
                    yield evt

                state = await self.executor.run(state, emit)
                async for evt in self._flush_states():
                    yield evt

                ok = self.qa.evaluate(state)
                self._mark_tasks(state, ok)
                if ok:
                    await self._emit_state(emit, AgentName.ORCHESTRATOR, "verified", f"Tests/execution passed on attempt {attempt}", state)
                    async for evt in self._flush_states():
                        yield evt
                    break
                if attempt > self.max_retries:
                    state.error = f"Retry budget exhausted after {self.max_retries} corrections"
                    state.retries_used = self.max_retries
                    await self.memory.store_fix(state.goal, state.exec_reports[-1].get("stderr", "") if state.exec_reports else "unknown")
                    await self._emit_state(emit, AgentName.ORCHESTRATOR, "failed", state.error, state)
                    async for evt in self._flush_states():
                        yield evt
                    break
                await self._emit_state(
                    emit, AgentName.QA, "running_tests",
                    f"Test failed at attempt {attempt}. Rerouting traceback to Developer…",
                    state, {"stderr": (state.exec_reports[-1].get('stderr', '') if state.exec_reports else '')[:500]},
                )
                async for evt in self._flush_states():
                    yield evt
                state.retries_used = attempt
                # persist failure pattern for long-term recall
                if state.exec_reports:
                    await self.memory.store_fix(state.goal, state.exec_reports[-1].get("stderr", ""), {"attempt": attempt})

            # 4. Documentation (non-blocking for correctness)
            try:
                async for chunk in self.writer.stream(state, emit):
                    yield {"type": "token", **TokenEvent(agent="Writer", token=chunk, session_id=state.session_id).model_dump()}
                async for evt in self._flush_states():
                    yield evt
            except Exception as exc:
                logger.warning("writer step failed: %s", exc)

            state.done = state.error is None
            await self.memory.entities.update({"last_session": state.session_id, "last_goal": goal, "ok": state.done})
            yield {"type": "result", "state": state.model_dump()}
        except Exception as exc:
            logger.exception("orchestrator failure: %s", exc)
            state.error, state.done = str(exc), False
            yield {"type": "result", "state": state.model_dump()}

    # -- non-streaming convenience -------------------------------------
    async def run(self, goal: str, session_id: str = "") -> AgentState:
        final: AgentState | None = None
        async for evt in self.run_stream(goal, session_id):
            if evt.get("type") == "result":
                final = AgentState(**evt["state"])
        if final is None:
            raise RuntimeError("Orchestrator produced no result")
        return final

    # -- internals ------------------------------------------------------
    async def _flush_states(self) -> AsyncGenerator[dict[str, Any], None]:
        while self._pending:
            yield self._pending.pop(0)

    async def _emit_state(
        self, emit: EmitFn, agent: AgentName, status: str, feedback: str,
        state: AgentState, extra: dict[str, Any] | None = None,
    ) -> None:
        await emit(TelemetryEvent(agent=agent.value, status=status, feedback=feedback, session_id=state.session_id, extra=extra or {}).model_dump())

    @staticmethod
    def _mark_tasks(state: AgentState, ok: bool) -> None:
        if not state.dag:
            return
        for node in state.dag.nodes:
            if node.owner in (AgentName.DEVELOPER, AgentName.QA, AgentName.EXECUTION):
                node.status = TaskStatus.SUCCEEDED if ok else TaskStatus.NEEDS_FIX
                node.attempts += 1
