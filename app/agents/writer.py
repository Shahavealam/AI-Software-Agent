"""Technical Writer: docs, inline comments, changelogs."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from app.agents.base import BaseAgent, EmitFn
from app.core.state import AgentName, AgentState


class WriterAgent(BaseAgent):
    name = AgentName.WRITER
    system_prompt = (
        "You are a senior technical writer. Produce README-grade documentation: "
        "overview, usage, API, examples, changelog. Clear, concise markdown."
    )

    async def run(self, state: AgentState, emit: EmitFn = None) -> AgentState:  # type: ignore[override]
        from app.agents.base import _noop_emit

        emit = emit or _noop_emit
        await self.tell(emit, "writing", "Generating documentation", state.session_id)
        files = list(state.artifacts)
        docs = await self._gen(f"GOAL: {state.goal}\nFILES: {files}\nWrite README.md + CHANGELOG entry.")
        state.docs["README.md"] = docs
        state.artifacts["docs/README.md"] = docs
        await self.memory.remember_turn("Writer", docs[:1500])
        await self.tell(emit, "documented", "Docs ready", state.session_id)
        return state

    async def stream(self, state: AgentState, emit: EmitFn = None) -> AsyncGenerator[str, None]:  # type: ignore[override]
        from app.agents.base import _noop_emit

        emit = emit or _noop_emit
        await self.tell(emit, "writing", "Streaming docs", state.session_id)
        chunks: list[str] = []
        async for tok in self._gen_stream(f"GOAL: {state.goal}\nFILES: {list(state.artifacts)}", emit, state.session_id):
            chunks.append(tok)
            yield tok
        state.docs["README.md"] = "".join(chunks)
        state.artifacts["docs/README.md"] = state.docs["README.md"]
        await self.tell(emit, "documented", "Docs streamed", state.session_id)
