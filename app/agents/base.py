"""Abstract base class for all deep agents.

Contract
--------
* Every agent is async-first and streams **two** channels:
  1. ``stream`` — raw markdown/token chunks (``AsyncGenerator[str, None]``)
     for real-time code / prose production.
  2. ``run``    — full result + telemetry side-channel via the supplied
     ``emit`` callback (``TelemetryEvent`` dicts → SSE ``state`` events).
* Agents never call each other directly; the orchestrator propagates
  :class:`AgentState`. This keeps the topology decoupled and event-driven.
"""

from __future__ import annotations

import abc
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Any

from app.core.config import logger
from app.core.llm import LLMGateway
from app.core.memory import MemoryManager
from app.core.state import AgentName, AgentState, TelemetryEvent

EmitFn = Callable[[dict[str, Any]], Awaitable[None]]


async def _noop_emit(_: dict[str, Any]) -> None:
    return None


class BaseAgent(abc.ABC):
    """Async/streaming ABC every specialist extends."""

    name: AgentName
    system_prompt: str = "You are a helpful engineering agent."

    def __init__(
        self,
        memory: MemoryManager | None = None,
        llm: LLMGateway | None = None,
    ) -> None:
        self.memory = memory or MemoryManager()
        self.llm = llm or LLMGateway()
        self.logger = logger.bind if hasattr(logger, "bind") else None  # structlog compat

    # -- telemetry helper -------------------------------------------
    async def tell(
        self,
        emit: EmitFn,
        status: str,
        feedback: str = "",
        session_id: str = "",
        extra: dict[str, Any] | None = None,
    ) -> None:
        event = TelemetryEvent(
            agent=self.name.value,
            status=status,
            feedback=feedback,
            session_id=session_id,
            extra=extra or {},
        )
        try:
            await emit(event.model_dump())
        except Exception as exc:
            logger.warning("%s telemetry emit failed: %s", self.name.value, exc)

    # -- core contract -----------------------------------------------
    @abc.abstractmethod
    async def run(self, state: AgentState, emit: EmitFn = _noop_emit) -> AgentState:
        """Execute one graph step; return the (mutated) state."""

    async def stream(
        self, state: AgentState, emit: EmitFn = _noop_emit
    ) -> AsyncGenerator[str, None]:
        """Default streaming: run once, then yield a compact digest.

        Code-heavy agents override this to yield live LLM tokens.
        """
        before = time.time()
        await self.tell(emit, "started", f"{self.name.value} started", state.session_id)
        updated = await self.run(state, emit)
        await self.tell(
            emit, "completed", f"{self.name.value} done in {time.time() - before:.1f}s",
            updated.session_id,
        )
        yield f"\n\n> [{self.name.value}] step complete.\n"

    # -- shared helpers ----------------------------------------------
    async def _gen(self, user_prompt: str, session_id: str = "") -> str:
        await self.memory.remember_turn(self.name.value, user_prompt[:2000])
        await self.memory.compact_if_needed()
        return await self.llm.chat(self.system_prompt, user_prompt)

    async def _gen_stream(
        self, user_prompt: str, emit: EmitFn, session_id: str = ""
    ) -> AsyncGenerator[str, None]:
        await self.memory.remember_turn(self.name.value, user_prompt[:2000])
        await self.memory.compact_if_needed()
        async for token in self.llm.stream(self.system_prompt, user_prompt):
            yield token
