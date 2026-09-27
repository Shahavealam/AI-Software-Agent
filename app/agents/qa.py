"""QA & Testing: formulates pytest/jest suites, evaluates against requirements."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from app.agents.base import BaseAgent, EmitFn
from app.core.state import AgentName, AgentState


class QAAgent(BaseAgent):
    name = AgentName.QA
    system_prompt = (
        "You are a rigorous QA engineer. Given a goal and implementation, write "
        "a pytest suite (test_*.py) covering happy paths, edges and failures. "
        "Output ONLY fenced code blocks. Then append a PASS/FAIL rubric."
    )

    async def run(self, state: AgentState, emit: EmitFn = None) -> AgentState:  # type: ignore[override]
        from app.agents.base import _noop_emit

        emit = emit or _noop_emit
        await self.tell(emit, "testing", "Formulating test suite", state.session_id)
        impl = {k: v for k, v in state.artifacts.items() if not k.startswith(("architect/", "docs/"))}
        prompt = f"GOAL: {state.goal}\nIMPLEMENTATION FILES: {list(impl)}\n" + "\n".join(
            f"--- {k} ---\n{v[:3000]}" for k, v in list(impl.items())[:4]
        )
        suite = await self._gen(prompt + "\nWrite pytest tests now.")
        state.artifacts["tests/test_generated.py"] = self._strip_fences(suite)
        state.test_reports.append({"suite": "tests/test_generated.py", "passed": None, "details": "awaiting execution"})
        await self.memory.remember_turn("QA", suite[:2000])
        await self.tell(emit, "tests_ready", "Test suite formulated, routing to Execution", state.session_id)
        return state

    async def stream(self, state: AgentState, emit: EmitFn = None) -> AsyncGenerator[str, None]:  # type: ignore[override]
        from app.agents.base import _noop_emit

        emit = emit or _noop_emit
        await self.tell(emit, "testing", "Streaming test suite", state.session_id)
        impl = {k: v for k, v in state.artifacts.items() if not k.startswith(("architect/", "docs/"))}
        chunks: list[str] = []
        async for tok in self._gen_stream(f"GOAL: {state.goal}\nFILES: {list(impl)}", emit, state.session_id):
            chunks.append(tok)
            yield tok
        state.artifacts["tests/test_generated.py"] = self._strip_fences("".join(chunks))
        await self.tell(emit, "tests_ready", "Tests streamed", state.session_id)

    def evaluate(self, state: AgentState) -> bool:
        """Return True if latest exec report indicates success."""
        if not state.exec_reports:
            return False
        last = state.exec_reports[-1]
        passed = bool(last.get("ok")) and last.get("returncode", 1) == 0
        details = (last.get("stdout", "") + last.get("stderr", ""))[:4000]
        if state.test_reports:
            state.test_reports[-1].update({"passed": passed, "details": details})
        else:
            state.test_reports.append({"suite": "tests/test_generated.py", "passed": passed, "details": details})
        return passed

    @staticmethod
    def _strip_fences(text: str) -> str:
        import re

        m = re.search(r"```(?:\w+)?\n(.*?)```", text, re.DOTALL)
        return m.group(1).strip() if m else text.strip()
