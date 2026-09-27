"""Architect & Code Analyzer: AST parsing, structural analysis, change plans."""

from __future__ import annotations

import ast
import os
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from app.agents.base import BaseAgent, EmitFn
from app.core.config import logger
from app.core.state import AgentName, AgentState


def analyse_python_source(source: str) -> dict[str, Any]:
    """Pure AST analysis — importable by tests and the agent alike."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return {"error": f"SyntaxError: {exc}", "imports": [], "classes": [], "functions": []}
    out: dict[str, Any] = {"imports": [], "classes": [], "functions": [], "docstring": ast.get_docstring(tree) or ""}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out["imports"].extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            out["imports"].append(node.module or "")
        elif isinstance(node, ast.ClassDef):
            out["classes"].append(node.name)
        elif isinstance(node, ast.FunctionDef):
            out["functions"].append(node.name)
    return out


class ArchitectAgent(BaseAgent):
    name = AgentName.ARCHITECT
    system_prompt = (
        "You are a principal software architect. Given a goal and repo analysis, "
        "produce a precise structural change plan: files to create/modify, "
        "interfaces, risks, and ordered steps. Be concrete and minimal."
    )

    async def run(self, state: AgentState, emit: EmitFn = None) -> AgentState:  # type: ignore[override]
        from app.agents.base import _noop_emit

        emit = emit or _noop_emit
        await self.tell(emit, "analysing", "Parsing repo structure (AST)", state.session_id)
        repo_map = self._scan_repo()
        patterns = await self.memory.recall(state.goal, k=3)
        plan = await self._gen(
            f"GOAL: {state.goal}\nREPO MAP (truncated): {str(repo_map)[:4000]}\n"
            f"RELEVANT PATTERNS: {str(patterns)[:2000]}\nReturn a numbered change plan."
        )
        state.artifacts["architect/plan.md"] = plan
        await self.memory.entities.update({"last_arch_plan": plan[:2000], "repo_files": len(repo_map)})
        await self.memory.remember_turn("Architect", plan[:2000])
        await self.tell(emit, "planned", f"Change plan ready ({len(repo_map)} files mapped)", state.session_id)
        return state

    async def stream(self, state: AgentState, emit: EmitFn = None) -> AsyncGenerator[str, None]:  # type: ignore[override]
        from app.agents.base import _noop_emit

        emit = emit or _noop_emit
        await self.tell(emit, "analysing", "Streaming architectural plan", state.session_id)
        repo_map = self._scan_repo()
        chunks: list[str] = []
        async for tok in self._gen_stream(f"GOAL: {state.goal}\nREPO FILES: {list(repo_map)[:50]}", emit, state.session_id):
            chunks.append(tok)
            yield tok
        state.artifacts["architect/plan.md"] = "".join(chunks)
        await self.tell(emit, "planned", "Plan streamed", state.session_id)

    def _scan_repo(self, root: str = ".", cap: int = 120) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in {".git", "__pycache__", ".venv", ".agent_backup", ".agent_chroma", "node_modules", "app"}]
            for fn in filenames:
                if not fn.endswith(".py") or len(out) >= cap:
                    continue
                p = Path(dirpath) / fn
                try:
                    out[str(p)] = analyse_python_source(p.read_text(encoding="utf-8", errors="ignore"))
                except Exception as exc:
                    logger.debug("scan skip %s: %s", p, exc)
        return out
