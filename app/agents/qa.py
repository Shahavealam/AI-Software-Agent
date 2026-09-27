"""QA & Testing: formulates pytest/jest suites, evaluates against requirements."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from app.agents.base import BaseAgent, EmitFn
from app.core.state import AgentName, AgentState

_JS_EXTS = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")


def detect_project_language(artifacts: dict[str, str]) -> str:
    """Return ``"python"`` or ``"javascript"`` for the implementation files.

    Counts non-test, non-doc source files by extension. Python wins ties
    (backwards compatible) and empty projects default to ``"python"`` so a
    stray Python suite is never generated for a JS project by accident.
    """
    py, js = 0, 0
    for path in artifacts:
        lowered = path.lower()
        if lowered.startswith(("architect/", "docs/")):
            continue
        if lowered.endswith(".py") and not _is_test_artifact(lowered):
            py += 1
        elif lowered.endswith(_JS_EXTS):
            js += 1
    if js > py:
        return "javascript"
    return "python"


def _is_test_artifact(lowered: str) -> bool:
    base = lowered.rsplit("/", 1)[-1]
    return (
        (base.startswith("test_") and base.endswith(".py"))
        or base.endswith("_test.py")
        or (lowered.startswith("tests/") and base.endswith(".py"))
        or base.endswith(".test.js")
    )


class QAAgent(BaseAgent):
    name = AgentName.QA
    system_prompt = (
        "You are a rigorous QA engineer. Write a test suite matching the "
        "project's language: pytest (test_*.py) for Python, Jest "
        "(*.test.js) for JavaScript/TypeScript. "
        "Rules: output ONE fenced code block; deterministic asserts only, "
        "no network, no input(). Then append a PASS/FAIL rubric outside the fence."
    )

    async def run(self, state: AgentState, emit: EmitFn = None) -> AgentState:  # type: ignore[override]
        from app.agents.base import _noop_emit

        emit = emit or _noop_emit
        await self.tell(emit, "testing", "Formulating test suite", state.session_id)
        impl = {k: v for k, v in state.artifacts.items() if not k.startswith(("architect/", "docs/"))}
        feedback = self._latest_feedback(state)
        history_block = f"\nHISTORY:\n{state.history_context[:2000]}" if state.history_context else ""
        language = detect_project_language(impl)
        if language == "javascript":
            suite_path = "tests/dashboard.test.js"
            kind_instruction = (
                "Write Jest tests now (ONE fenced javascript block). Import components "
                "via relative paths, e.g. `import Chart from '../dashboard/components/ChartComponent';`. "
                "Do NOT write Python; this is a JavaScript project."
            )
        else:
            suite_path = "tests/test_generated.py"
            kind_instruction = (
                "Write pytest tests now (ONE fenced python block). Import the implementation with "
                "`import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))` "
                "or plain top-level imports (tests run with the project root on sys.path). "
                "Do NOT write JavaScript; this is a Python project."
            )
        prompt = (
            f"GOAL: {state.goal}{history_block}\nPROJECT LANGUAGE: {language}\n"
            f"IMPLEMENTATION FILES: {list(impl)}\n"
            + "\n".join(f"--- {k} ---\n{v[:3000]}" for k, v in list(impl.items())[:4])
            + (f"\nPREVIOUS FAILURE (fix the suite/code mismatch):\n{feedback[:2500]}" if feedback else "")
            + f"\n{kind_instruction}"
            + "\nOnly assert files listed in IMPLEMENTATION FILES above, using their exact relative paths — never invent paths."
        )
        suite = await self._gen(prompt)
        state.artifacts[suite_path] = self._strip_fences(suite)
        state.test_reports.append({"suite": suite_path, "passed": None, "details": "awaiting execution"})
        await self.memory.remember_turn("QA", suite[:2000])
        await self.tell(emit, "tests_ready", f"Test suite formulated ({suite_path}), routing to Execution", state.session_id)
        return state

    async def stream(self, state: AgentState, emit: EmitFn = None) -> AsyncGenerator[str, None]:  # type: ignore[override]
        from app.agents.base import _noop_emit

        emit = emit or _noop_emit
        await self.tell(emit, "testing", "Streaming test suite", state.session_id)
        impl = {k: v for k, v in state.artifacts.items() if not k.startswith(("architect/", "docs/"))}
        language = detect_project_language(impl)
        suite_path = "tests/dashboard.test.js" if language == "javascript" else "tests/test_generated.py"
        chunks: list[str] = []
        async for tok in self._gen_stream(f"GOAL: {state.goal}\nLANGUAGE: {language}\nFILES: {list(impl)}", emit, state.session_id):
            chunks.append(tok)
            yield tok
        state.artifacts[suite_path] = self._strip_fences("".join(chunks))
        await self.tell(emit, "tests_ready", f"Tests streamed ({suite_path})", state.session_id)

    def evaluate(self, state: AgentState) -> bool:
        """Return True if the latest execution verdict indicates success.

        Prefers the aggregate ``{"summary": True}`` report appended by
        :class:`ExecutionAgent` (whole-iteration verdict); falls back to the
        last per-file report for backwards compatibility.
        """
        if not state.exec_reports:
            return False
        summary = next((r for r in reversed(state.exec_reports) if r.get("summary")), None)
        last = summary if summary is not None else state.exec_reports[-1]
        passed = bool(last.get("ok")) and last.get("returncode", 1) == 0
        details = (last.get("stdout", "") + "\n" + last.get("stderr", ""))[:4000]
        if state.test_reports:
            state.test_reports[-1].update({"passed": passed, "details": details})
        else:
            state.test_reports.append({"suite": "tests/test_generated.py", "passed": passed, "details": details})
        return passed

    @staticmethod
    def _latest_feedback(state: AgentState) -> str:
        if state.exec_reports:
            last = state.exec_reports[-1]
            if not last.get("ok"):
                return f"TARGET {last.get('target')}: {last.get('stderr', '')}\n{last.get('stdout', '')}"
        return ""

    @staticmethod
    def _strip_fences(text: str) -> str:
        """Extract python code from fenced blocks (all edge cases).

        Handles: multiple blocks (joined), `````python`` / `````py`` /
        `````python3`` / `````plaintext`` info strings, missing language,
        ``\\r\\n`` line endings, and unfenced output (returned as-is).
        Prefers the largest python-looking block when several exist.
        """
        import re

        normalised = text.replace("\r\n", "\n").replace("\r", "\n")
        blocks = re.findall(r"```[^\n`]*\n(.*?)```", normalised, re.DOTALL)
        if not blocks:
            return normalised.strip()
        cleaned = [b.strip() for b in blocks if b.strip()]
        if not cleaned:
            return normalised.strip()
        if len(cleaned) == 1:
            return cleaned[0]
        # Multiple blocks: prefer python-looking content (def/class/import),
        # else join all so multi-file suites are not silently truncated.
        scored = sorted(
            cleaned,
            key=lambda b: sum(1 for kw in ("def test_", "import ", "def ", "class ", "assert ") if kw in b),
            reverse=True,
        )
        if sum(1 for b in cleaned if "def test_" in b or "import " in b) >= 2:
            return "\n\n".join(cleaned)
        return scored[0]
