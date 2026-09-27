"""Tests for specialist agents: AST analysis, sandbox, router, QA verdicts."""

from __future__ import annotations

from app.agents.architect import analyse_python_source
from app.agents.developer import DeveloperAgent
from app.agents.execution import run_python_snippet
from app.agents.product_manager import ProductManagerAgent
from app.agents.qa import QAAgent
from app.core.memory import MemoryManager
from app.core.state import AgentState


def test_ast_analysis() -> None:
    out = analyse_python_source("import os\nclass A:\n def f(self) -> int:\n  return 1\n")
    assert out["classes"] == ["A"] and out["functions"] == ["f"] and "os" in out["imports"]


def test_ast_syntax_error_reported() -> None:
    out = analyse_python_source("def broken(:\n")
    assert "error" in out


async def test_sandbox_success_and_crash() -> None:
    ok = await run_python_snippet("print('hi')")
    assert ok["ok"] and ok["returncode"] == 0 and "hi" in ok["stdout"]
    bad = await run_python_snippet("raise ValueError('boom')")
    assert not bad["ok"] and bad["returncode"] != 0 and "boom" in bad["stderr"]


async def test_router_builds_valid_dag(tmp_cwd) -> None:
    mm = MemoryManager()
    agent = ProductManagerAgent(memory=mm)
    state = AgentState(goal="add a typed python calculator with tests")
    state = await agent.run(state)
    assert state.dag is not None and len(state.dag.nodes) >= 3
    state.dag.topological_order()  # raises on cycles
    owners = {n.owner for n in state.dag.nodes}
    assert len(owners) >= 2  # routed across specialists


def test_developer_stores_fenced_files() -> None:
    state = AgentState(goal="demo")
    DeveloperAgent._store_files(state, "```python:calc.py\ndef add(a, b):\n return a + b\n```")
    assert "calc.py" in state.artifacts and "def add" in state.artifacts["calc.py"]


def test_developer_fallback_single_file() -> None:
    state = AgentState(goal="demo")
    DeveloperAgent._store_files(state, "plain code without fences")
    assert state.artifacts["solution.py"].startswith("plain code")


def test_qa_evaluate_verdicts() -> None:
    agent = QAAgent()
    passing = AgentState(goal="g", exec_reports=[{"ok": True, "returncode": 0, "stdout": "ok", "stderr": ""}])
    assert agent.evaluate(passing) is True
    assert passing.test_reports[-1]["passed"] is True
    failing = AgentState(goal="g", exec_reports=[{"ok": False, "returncode": 1, "stdout": "", "stderr": "boom"}])
    assert agent.evaluate(failing) is False
    assert agent.evaluate(AgentState(goal="g")) is False
