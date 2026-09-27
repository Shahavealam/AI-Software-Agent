"""Regression tests: JS/React projects must not fail on Python test mismatch.

Reproduces the reported failure — ``tests/test_generated.py`` doing
``from dashboard.components.ChartComponent import ChartComponent`` in a
pure-JS project (pytest rc=2 collection error ×3 → budget exhausted).
"""

from __future__ import annotations

from app.agents.developer import DeveloperAgent
from app.agents.execution import ExecutionAgent
from app.agents.qa import QAAgent, detect_project_language
from app.core.memory import MemoryManager
from app.core.state import AgentState

JS_PROJECT = {
    "dashboard/App.js": "import Dashboard from './components/Dashboard';\nexport default function App() { return Dashboard(); }\n",
    "dashboard/components/Dashboard.js": "export default function Dashboard() { return 'dash'; }\n",
    "dashboard/components/ChartComponent.js": "export default function ChartComponent() { return 'chart'; }\n",
    "dashboard/hooks/useDataFetch.js": "export default function useDataFetch() { return []; }\n",
    "dashboard/index.js": "import App from './App';\nconsole.log(App);\n",
}


def test_detect_language() -> None:
    assert detect_project_language(JS_PROJECT) == "javascript"
    assert detect_project_language({"calc.py": "x=1", "app.js": "x=1"}) == "python"  # tie → python
    assert detect_project_language({}) == "python"  # empty → python fallback
    assert detect_project_language({"tests/test_generated.py": "x", **JS_PROJECT}) == "javascript"  # stale suite ignored
    assert detect_project_language({"a.py": "x", "b.py": "y", "c.js": "z"}) == "python"


async def test_qa_routes_js_project_to_jest(tmp_cwd) -> None:
    state = AgentState(goal="build a dashboard")
    state.artifacts = dict(JS_PROJECT)
    state = await QAAgent(memory=MemoryManager()).run(state)
    assert "tests/dashboard.test.js" in state.artifacts
    assert "tests/test_generated.py" not in state.artifacts


async def test_qa_keeps_pytest_for_python(tmp_cwd) -> None:
    state = AgentState(goal="calculator")
    state.artifacts = {"calculator.py": "def add(a, b):\n    return a + b\n"}
    state = await QAAgent(memory=MemoryManager()).run(state)
    assert "tests/test_generated.py" in state.artifacts


async def test_js_project_with_stray_py_suite_passes() -> None:
    """Legacy artifact shape: pure-JS files + junk Python suite importing JS."""
    state = AgentState(goal="dashboard")
    state.artifacts = {
        **JS_PROJECT,
        "tests/test_generated.py": "from dashboard.components.ChartComponent import ChartComponent\n",
    }
    state = await ExecutionAgent(memory=MemoryManager()).run(state)
    summary = next(r for r in state.exec_reports if r.get("summary"))
    assert summary["ok"] is True, summary["stderr"]
    assert QAAgent().evaluate(state) is True


async def test_python_package_import_without_init() -> None:
    """Dotted package imports resolve via synthesised __init__.py."""
    state = AgentState(goal="pkg")
    state.artifacts = {
        "dashboard/components/chart.py": "class ChartComponent:\n    pass\n",
        "tests/test_chart.py": "from dashboard.components.chart import ChartComponent\ndef test_cls():\n    assert ChartComponent is not None\n",
    }
    state = await ExecutionAgent(memory=MemoryManager()).run(state)
    summary = next(r for r in state.exec_reports if r.get("summary"))
    assert summary["ok"] is True, summary["stderr"]


async def test_pytest_skipped_without_python_modules() -> None:
    state = AgentState(goal="js only")
    state.artifacts = {"app.js": "console.log('hi');\n"}
    state = await ExecutionAgent(memory=MemoryManager()).run(state)
    summary = next(r for r in state.exec_reports if r.get("summary"))
    assert summary["ok"] is True, summary["stderr"]


def test_developer_existing_files_block() -> None:
    state = AgentState(goal="demo")
    assert DeveloperAgent._existing_files_block(state) == ""
    state.artifacts = {"App.js": "x", "architect/plan.md": "plan"}
    block = DeveloperAgent._existing_files_block(state)
    assert "App.js" in block and "architect/plan.md" not in block
    assert "duplicates" in block
