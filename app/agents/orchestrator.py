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
from app.core.history import auto_title, get_history_store
from app.core.memory import MemoryManager
from app.core.state import AgentName, AgentState, TaskStatus, TelemetryEvent, TokenEvent


def _artifact_snapshot(artifacts: dict[str, str], settings: Any) -> dict[str, str]:
    """Bounded snapshot of artifact CONTENTS for history (names alone lose the code).

    Per-file and total caps keep MongoDB documents small; larger files are
    cut with an explicit marker instead of silently dropping content.
    """
    out: dict[str, str] = {}
    total = 0
    for path in sorted(artifacts):
        content = artifacts[path] or ""
        if len(content) > settings.history_artifact_file_max_chars:
            content = content[: settings.history_artifact_file_max_chars] + "\n…[truncated]"
        if total + len(content) > settings.history_artifacts_total_max_chars:
            break
        out[path] = content
        total += len(content)
    return out


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

        Side-effects on the persistent :class:`HistoryStore`:
        * ensures a session exists (auto-title from the goal),
        * appends the user goal as a ``user`` message,
        * loads prior turns into ``state.history_context`` so downstream
          agents can continue "further steps" in the same session,
        * appends one ``assistant`` message per agent stage (full outputs,
          not just previews) plus a final ``result`` message carrying the
          summary, report tails and an artifact-contents snapshot.
        """
        settings = get_settings()
        history = get_history_store()
        try:
            session = await history.ensure_session(session_id or "", title=auto_title(goal))
            session_id = session.id
        except Exception as exc:
            logger.warning("history ensure_session failed (%s); continuing without persistence", exc)
            history = None  # type: ignore[assignment]

        state = AgentState(goal=goal, max_retries=self.max_retries)
        state.session_id = session_id

        assistant_chunks: list[str] = []
        agent_chunks: dict[str, list[str]] = {}

        def _record(agent_name: str, chunk: str) -> None:
            assistant_chunks.append(chunk)
            agent_chunks.setdefault(agent_name, []).append(chunk)

        async def _persist_agent_turn(agent_name: str) -> None:
            """Persist one agent's full streamed output as its own message.

            Previously only a 4000-char preview of ALL agents combined
            survived — the per-agent content was lost from the DB.
            """
            if history is None or not settings.history_save_agent_turns:
                return
            # Pop (not peek) so retry-loop re-runs persist only the new
            # attempt instead of re-saving all previous attempts each time.
            text = "".join(agent_chunks.pop(agent_name, [])).strip()
            if not text:
                return
            try:
                await history.append_message(
                    session_id, "assistant", text[: settings.history_agent_turn_max_chars],
                    agent=agent_name, kind="note",
                )
            except Exception as exc:
                logger.warning("history persist %s turn failed (%s)", agent_name, exc)

        async def _persist_qa_suite() -> None:
            """QA runs non-streaming — snapshot the generated suite file."""
            if history is None or not settings.history_save_agent_turns:
                return
            try:
                suite_path = state.test_reports[-1].get("suite") if state.test_reports else ""
                content = state.artifacts.get(suite_path, "") if suite_path else ""
                if not content.strip():
                    return
                await history.append_message(
                    session_id, "assistant", content[: settings.history_agent_turn_max_chars],
                    agent=AgentName.QA.value, kind="note",
                    extra={"suite": suite_path},
                )
            except Exception as exc:
                logger.warning("history persist QA suite failed (%s)", exc)

        async def _persist_user_turn() -> None:
            if history is None:
                return
            try:
                await history.append_message(session_id, "user", goal, agent="User", kind="goal")
                ctx = await history.get_context(session_id, limit=20, max_chars=6000)
                # Exclude the just-appended goal itself from the context window
                # when it is the only message (avoids echoing goal back).
                state.history_context = ctx
                if ctx:
                    await self.memory.remember_turn("History", f"session {session_id} prior turns:\n{ctx[:4000]}")
            except Exception as exc:
                logger.warning("history persist user turn failed (%s)", exc)

        async def _persist_assistant_turn(final_state: AgentState) -> None:
            if history is None:
                return
            try:
                files = sorted(final_state.artifacts)
                field_cap = settings.history_report_field_max_chars
                last_err = ""
                for rep in reversed(final_state.exec_reports[-5:]):
                    if not rep.get("ok") and rep.get("stderr"):
                        last_err = f"[{rep.get('target') or rep.get('phase') or 'exec'}] {rep['stderr'][-field_cap:]}"
                        break
                def _trimmed(report: dict[str, Any]) -> dict[str, Any]:
                    # Truncate long strings but keep native JSON types (bool /
                    # None / numbers / lists) intact — the frontend does
                    # strict checks like `passed === true`.
                    return {
                        k: (v[:field_cap] if isinstance(v, str) and len(v) > field_cap else v)
                        for k, v in report.items()
                    }

                exec_tail = [_trimmed(rep) for rep in final_state.exec_reports[-5:]]
                test_tail = [_trimmed(rep) for rep in final_state.test_reports[-3:]]
                preview_cap = settings.history_stream_preview_max_chars
                if final_state.error:
                    summary = f"Run failed: {final_state.error}"
                    if last_err:
                        summary += f"\nLast error:\n{last_err[:preview_cap]}"
                    summary += f"\nFiles kept: {', '.join(files) if files else 'none'}"
                else:
                    streamed = "".join(assistant_chunks).strip()
                    summary = f"Goal: {goal}\nFiles: {', '.join(files) if files else 'none'}\n"
                    if streamed:
                        summary += f"Output:\n{streamed[:preview_cap]}"
                    else:
                        docs = final_state.docs
                        if docs:
                            first = next(iter(docs.values()))[:preview_cap]
                            summary += f"Docs preview:\n{first}"
                await history.append_message(
                    session_id, "assistant", summary[: settings.history_summary_max_chars],
                    agent="Orchestrator", kind="result",
                    extra={"done": final_state.done, "error": final_state.error or "",
                           "artifacts": files, "retries_used": final_state.retries_used,
                           "artifact_contents": _artifact_snapshot(final_state.artifacts, settings),
                           "exec_reports": exec_tail, "test_reports": test_tail},
                )
            except Exception as exc:
                logger.warning("history persist assistant turn failed (%s)", exc)

        await _persist_user_turn()

        async def emit(d: dict[str, Any]) -> None:
            self._pending.append({"type": "state", **d})

        self._pending: list[dict[str, Any]] = []
        await self._emit_state(emit, AgentName.ORCHESTRATOR, "started", f"Goal received: {goal[:150]}", state)

        try:
            # 1. Route / plan
            async for chunk in self.router.stream(state, emit):
                _record("ProductManager", chunk)
                yield {"type": "token", **TokenEvent(agent="ProductManager", token=chunk, session_id=state.session_id).model_dump()}
            await _persist_agent_turn("ProductManager")
            async for evt in self._flush_states():
                yield evt
            if not state.dag or not state.dag.nodes:
                raise RuntimeError("Router produced an empty DAG")

            # 2. Architecture
            async for chunk in self.architect.stream(state, emit):
                _record("Architect", chunk)
                yield {"type": "token", **TokenEvent(agent="Architect", token=chunk, session_id=state.session_id).model_dump()}
            await _persist_agent_turn("Architect")
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
                    _record("Developer", chunk)
                    yield {"type": "token", **TokenEvent(agent="Developer", token=chunk, session_id=state.session_id).model_dump()}
                await _persist_agent_turn("Developer")
                async for evt in self._flush_states():
                    yield evt

                state = await self.qa.run(state, emit)
                await _persist_qa_suite()
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
                    _record("Writer", chunk)
                    yield {"type": "token", **TokenEvent(agent="Writer", token=chunk, session_id=state.session_id).model_dump()}
                await _persist_agent_turn("Writer")
                async for evt in self._flush_states():
                    yield evt
            except Exception as exc:
                logger.warning("writer step failed: %s", exc)

            state.done = state.error is None
            await self.memory.entities.update({"last_session": state.session_id, "last_goal": goal, "ok": state.done})
            await _persist_assistant_turn(state)
            yield {"type": "result", "state": state.model_dump()}
        except Exception as exc:
            logger.exception("orchestrator failure: %s", exc)
            state.error, state.done = str(exc), False
            await _persist_assistant_turn(state)
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
