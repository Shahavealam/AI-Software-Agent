"""Software Developer: writes modular clean code. Never executes it."""

from __future__ import annotations

import re
from collections.abc import AsyncGenerator

from app.agents.base import BaseAgent, EmitFn
from app.core.state import AgentName, AgentState


class DeveloperAgent(BaseAgent):
    name = AgentName.DEVELOPER
    system_prompt = (
        "You are a senior software developer. Write modular, clean, fully "
        "type-hinted code (Python/JS/HTML). Output ONLY fenced code blocks, "
        "one per file: ```<lang>:<path>\\n<code>```. No execution, no tests."
    )

    async def run(self, state: AgentState, emit: EmitFn = None) -> AgentState:  # type: ignore[override]
        from app.agents.base import _noop_emit

        emit = emit or _noop_emit
        await self.tell(emit, "coding", "Writing modular code", state.session_id)
        plan = state.artifacts.get("architect/plan.md", "")
        feedback = self._latest_feedback(state)
        patterns = await self.memory.recall(state.goal, k=3)
        prompt = (
            f"GOAL: {state.goal}\nPLAN: {plan[:4000]}\n"
            f"PATTERNS: {str(patterns)[:1500]}\nFEEDBACK: {feedback[:3000]}\n"
            "Write the implementation now."
        )
        full = "".join([c async for c in self._gen_stream(prompt, emit, state.session_id)])
        self._store_files(state, full)
        await self.memory.remember_turn("Developer", full[:2000])
        await self.tell(emit, "coded", f"Wrote {len([k for k in state.artifacts if not k.startswith('architect/')])} file(s)", state.session_id)
        return state

    async def stream(self, state: AgentState, emit: EmitFn = None) -> AsyncGenerator[str, None]:  # type: ignore[override]
        from app.agents.base import _noop_emit

        emit = emit or _noop_emit
        await self.tell(emit, "coding", "Streaming code tokens", state.session_id)
        plan = state.artifacts.get("architect/plan.md", "")
        feedback = self._latest_feedback(state)
        chunks: list[str] = []
        async for tok in self._gen_stream(f"GOAL: {state.goal}\nPLAN: {plan[:4000]}\nFEEDBACK: {feedback[:3000]}", emit, state.session_id):
            chunks.append(tok)
            yield tok  # raw markdown token streaming
        self._store_files(state, "".join(chunks))
        await self.tell(emit, "coded", "Code stream complete", state.session_id)

    # -- helpers -------------------------------------------------------
    @staticmethod
    def _latest_feedback(state: AgentState) -> str:
        if state.exec_reports:
            last = state.exec_reports[-1]
            if not last.get("ok"):
                return f"TRACEBACK:\n{last.get('stderr', '')}\nSTDOUT:\n{last.get('stdout', '')}"
        if state.test_reports:
            last = state.test_reports[-1]
            if not last.get("passed"):
                return f"TEST FAILURES:\n{last.get('details', '')}"
        return ""

    @staticmethod
    def _store_files(state: AgentState, text: str) -> None:
        pattern = re.compile(r"```(?:(\w+):)?([^\n`]+)?\n(.*?)```", re.DOTALL)
        n = 0
        for m in pattern.finditer(text):
            path = (m.group(2) or "").strip() or f"generated_{n}.py"
            code = m.group(3).strip()
            if code:
                state.artifacts[path] = code
                n += 1
        if n == 0 and text.strip():
            state.artifacts["solution.py"] = text.strip()
