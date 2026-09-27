"""Entrypoint: initialises the multi-agent core, exposes async streaming loop.

Three interfaces over the same :class:`MultiAgentOrchestrator`:

* Python API  — :func:`arun_stream` / :func:`arun`
* CLI         — ``python -m app.main "goal"`` or ``ai-agent "goal"``
* HTTP/SSE    — ``uvicorn app.main:app`` → ``POST /v1/run`` (SSE
  ``text/event-stream`` with ``token`` / ``state`` / ``result`` events)
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import AsyncGenerator
from typing import Any

from app.agents.orchestrator import MultiAgentOrchestrator
from app.core.config import configure_logging
from app.core.memory import MemoryManager
from app.core.state import AgentState

logger = configure_logging()

_orchestrator: MultiAgentOrchestrator | None = None


def get_orchestrator() -> MultiAgentOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = MultiAgentOrchestrator(memory=MemoryManager())
    return _orchestrator


# ── Python API ────────────────────────────────────────────────────────
async def arun_stream(goal: str, session_id: str = "") -> AsyncGenerator[dict[str, Any], None]:
    async for evt in get_orchestrator().run_stream(goal, session_id):
        yield evt


async def arun(goal: str, session_id: str = "") -> AgentState:
    return await get_orchestrator().run(goal, session_id)


# ── FastAPI / SSE (canonical implementation lives in app.api.server) ──
try:
    from app.api.server import app
except Exception:
    app = None  # type: ignore[assignment]  # FastAPI not installed


# ── CLI ───────────────────────────────────────────────────────────────
async def _cli_stream(goal: str) -> int:
    print(f"\033[36m▶ goal:\033[0m {goal}\n")
    async for evt in arun_stream(goal):
        t = evt.get("type")
        if t == "token":
            sys.stdout.write(evt.get("token", ""))
            sys.stdout.flush()
        elif t == "state":
            print(f"\n\033[33m[{evt.get('agent')}/{evt.get('status')}]\033[0m {evt.get('feedback', '')}")
        elif t == "result":
            st = evt["state"]
            print("\n\033[32m✔ done\033[0m" if not st.get("error") else f"\n\033[31m✘ {st.get('error')}\033[0m")
            print(f"artifacts: {sorted(st.get('artifacts', {}))}")
            print(f"retries_used: {st.get('retries_used')} exec_reports: {len(st.get('exec_reports', []))}")
    return 0


def cli_main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Multi-agent software engineering core")
    p.add_argument("goal", nargs="*", help="Engineering goal, or omit for interactive mode")
    p.add_argument("--serve", action="store_true", help="Run SSE server (uvicorn)")
    p.add_argument("--port", type=int, default=8000)
    args = p.parse_args(argv)
    if args.serve:
        import uvicorn

        uvicorn.run("app.main:app", host="0.0.0.0", port=args.port, reload=False)
        return 0
    if args.goal:
        return asyncio.run(_cli_stream(" ".join(args.goal)))
    # interactive REPL
    print("\033[36mAI Software Agent — multi-agent core (type 'exit' to quit)\033[0m")
    while True:
        try:
            goal = input("\n\033[32mgoal>\033[0m ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nbye.")
            return 0
        if goal.lower() in {"exit", "quit"}:
            print("bye.")
            return 0
        if goal:
            asyncio.run(_cli_stream(goal))
    return 0


if __name__ == "__main__":
    raise SystemExit(cli_main())
