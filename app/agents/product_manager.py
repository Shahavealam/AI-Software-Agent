"""Product Manager / Router: intent parsing → dependency mapping → DAG build."""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from app.agents.base import BaseAgent, EmitFn
from app.core.config import logger
from app.core.state import AgentName, AgentState, TaskNode, TaskStatus, WorkflowDAG

_FALLBACK_HINTS: tuple[tuple[str, AgentName, str], ...] = (
    ("test", AgentName.QA, "test"),
    ("doc", AgentName.WRITER, "docs"),
    ("analys", AgentName.ARCHITECT, "analysis"),
    ("refactor", AgentName.ARCHITECT, "analysis"),
    ("architect", AgentName.ARCHITECT, "analysis"),
    ("structur", AgentName.ARCHITECT, "analysis"),
    ("run", AgentName.EXECUTION, "execution"),
    ("execut", AgentName.EXECUTION, "execution"),
)


class ProductManagerAgent(BaseAgent):
    name = AgentName.PRODUCT_MANAGER
    system_prompt = (
        "You are a principal product manager and task router. Decompose software "
        "requests into a minimal DAG of tasks with owners, kinds and dependencies. "
        "Reply ONLY with JSON: {\"tasks\": [{\"title\": str, \"owner\": str, "
        "\"kind\": str, \"depends_on_idx\": [int]}]}."
    )

    async def run(self, state: AgentState, emit: EmitFn = None) -> AgentState:  # type: ignore[override]
        from app.agents.base import _noop_emit

        emit = emit or _noop_emit
        await self.tell(emit, "routing", f"Parsing intent: {state.goal[:120]}", state.session_id)
        try:
            dag = await self._build_dag(state.goal, state.history_context)
        except Exception as exc:
            logger.warning("router LLM path failed (%s); heuristic fallback", exc)
            dag = self._heuristic_dag(state.goal)
        state.dag = dag
        for node in dag.nodes:
            node.status = TaskStatus.PLANNED
        await self.memory.entities.update({"last_goal": state.goal, "dag_size": len(dag.nodes)})
        await self.tell(
            emit, "planned", f"DAG built with {len(dag.nodes)} tasks",
            state.session_id, {"tasks": [n.title for n in dag.nodes]},
        )
        return state

    # -- LLM path -----------------------------------------------------
    async def _build_dag(self, goal: str, history_context: str = "") -> WorkflowDAG:
        history_block = f"\nSESSION HISTORY (prior turns, continue from these):\n{history_context[:3000]}" if history_context else ""
        raw = await self._gen(f"User goal: {goal}{history_block}\nOwners: Architect, Developer, QA, Execution, Writer.")
        data = self._extract_json(raw)
        tasks = data.get("tasks") if isinstance(data, dict) else None
        if not tasks:
            return self._heuristic_dag(goal)
        nodes: list[TaskNode] = [
            TaskNode(id=uuid.uuid4().hex[:8], title=f"task-{i}", owner=AgentName.DEVELOPER)
            for i in range(len(tasks))
        ]
        allowed = {a.value for a in AgentName}
        for i, t in enumerate(tasks):
            owner_raw = str(t.get("owner", "Developer"))
            owner = AgentName(owner_raw) if owner_raw in allowed else AgentName.DEVELOPER
            nodes[i].title = str(t.get("title", f"task-{i}"))[:200]
            nodes[i].owner = owner
            kind = str(t.get("kind", "code"))
            nodes[i].kind = kind if kind in ("analysis", "code", "test", "execution", "docs", "plan") else "code"  # type: ignore[assignment]
            for dep_idx in t.get("depends_on_idx", []) or []:
                if isinstance(dep_idx, int) and 0 <= dep_idx < len(nodes) and dep_idx != i:
                    nodes[i].depends_on.append(nodes[dep_idx].id)
        dag = WorkflowDAG(goal=goal, nodes=nodes)
        dag.topological_order()  # validates acyclicity
        return dag

    @staticmethod
    def _extract_json(raw: str) -> Any:
        m = re.search(r"```(?:json)?\s*(.*?)\s*```", raw, re.DOTALL | re.IGNORECASE)
        candidate = m.group(1) if m else raw
        try:
            return json.loads(candidate)
        except Exception:
            start, end = candidate.find("{"), candidate.rfind("}")
            if 0 <= start < end:
                try:
                    return json.loads(candidate[start : end + 1])
                except Exception:
                    return {}
            return {}

    # -- deterministic fallback ---------------------------------------
    def _heuristic_dag(self, goal: str) -> WorkflowDAG:
        lowered = goal.lower()
        nodes: list[TaskNode] = []
        nodes.append(TaskNode(title="Analyse request & repo structure", owner=AgentName.ARCHITECT, kind="analysis"))
        code = TaskNode(title=f"Implement: {goal[:100]}", owner=AgentName.DEVELOPER, kind="code", depends_on=[nodes[0].id])
        nodes.append(code)
        nodes.append(TaskNode(title="Generate pytest suite", owner=AgentName.QA, kind="test", depends_on=[code.id]))
        nodes.append(TaskNode(title="Execute & capture results", owner=AgentName.EXECUTION, kind="execution", depends_on=[nodes[-1].id]))
        if any(k in lowered for k, _, _ in _FALLBACK_HINTS if "doc" in k):
            nodes.append(TaskNode(title="Write documentation & changelog", owner=AgentName.WRITER, kind="docs", depends_on=[code.id]))
        return WorkflowDAG(goal=goal, nodes=nodes)
