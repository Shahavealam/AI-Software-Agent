"""Execution & Runtime: sandboxed subprocess runner capturing stdout/stderr."""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path
from typing import Any

from app.agents.base import BaseAgent, EmitFn
from app.core.config import get_settings, logger
from app.core.state import AgentName, AgentState


async def run_python_snippet(code: str, timeout: float = 30.0) -> dict[str, Any]:
    """Execute a python snippet in a temp dir sandbox; return structured report."""
    with tempfile.TemporaryDirectory(prefix="agent_sbx_") as tmp:
        target = Path(tmp) / "snippet.py"
        target.write_text(code, encoding="utf-8")
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, str(target),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return {"ok": False, "returncode": -1, "stdout": "", "stderr": "TimeoutExpired", "timeout": True}
            rc = proc.returncode or 0
            return {
                "ok": rc == 0,
                "returncode": rc,
                "stdout": stdout.decode(errors="replace")[-8000:],
                "stderr": stderr.decode(errors="replace")[-8000:],
                "timeout": False,
            }
        except Exception as exc:
            logger.warning("sandbox error: %s", exc)
            return {"ok": False, "returncode": -1, "stdout": "", "stderr": str(exc)[:4000], "timeout": False}


class ExecutionAgent(BaseAgent):
    name = AgentName.EXECUTION
    system_prompt = "You are a sandbox runtime. You never write code; you only execute and report."

    async def run(self, state: AgentState, emit: EmitFn = None) -> AgentState:  # type: ignore[override]
        from app.agents.base import _noop_emit

        emit = emit or _noop_emit
        settings = get_settings()
        await self.tell(emit, "running", "Executing in sandbox", state.session_id)
        targets = [k for k in state.artifacts if k.endswith(".py") and not k.startswith(("architect/", "docs/"))]
        if not targets:
            report = {"ok": False, "returncode": -1, "stdout": "", "stderr": "No python artifacts to execute", "target": None}
            state.exec_reports.append(report)
            await self.tell(emit, "crashed", "Nothing to execute", state.session_id, report)
            return state
        # Execute each target sequentially; aggregate verdict
        for target in targets[:5]:
            code = state.artifacts[target][: settings.sandbox_max_bytes]
            report = await run_python_snippet(code, timeout=settings.sandbox_timeout_s)
            report["target"] = target
            state.exec_reports.append(report)
            verdict = "passed" if report["ok"] else "crashed"
            await self.tell(
                emit, verdict,
                f"{target}: rc={report['returncode']} " + (report["stderr"][-300:] if report["stderr"] else "OK"),
                state.session_id, {"target": target},
            )
            await self.memory.remember_turn("Execution", f"{target} rc={report['returncode']}")
        return state
