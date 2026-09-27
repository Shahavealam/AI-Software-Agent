"""Regression tests: prose/shell fences must never become executable .py files.

Reproduces the reported session failure — ``generated_1.py`` containing
"1. Navigate to the `dashboard/` directory:" plus a `test_stylesheets_existence`
asserting a .css file the sandbox never staged.
"""

from __future__ import annotations

from app.agents.developer import DeveloperAgent
from app.agents.execution import ExecutionAgent
from app.core.memory import MemoryManager
from app.core.state import AgentState

PROSE_BLOCK = (
    "```python\n"
    "1. Navigate to the `dashboard/` directory:\n"
    "2. Install necessary dependencies:\n"
    "3. Start the development server:\n"
    "```"
)


def test_numbered_instructions_become_txt_not_py() -> None:
    state = AgentState(goal="demo")
    DeveloperAgent._store_files(state, PROSE_BLOCK)
    assert "generated_0.txt" in state.artifacts
    assert not [k for k in state.artifacts if k.endswith(".py")]


def test_bulleted_prose_becomes_txt() -> None:
    state = AgentState(goal="demo")
    DeveloperAgent._store_files(
        state, "```python\n- `src/App.js`: Main application component.\n- `src/index.js`: Entry point.\n```"
    )
    assert not [k for k in state.artifacts if k.endswith(".py")]


def test_broken_real_code_stays_py() -> None:
    """A typo is code, not prose — keep .py so compile check flags it."""
    state = AgentState(goal="demo")
    DeveloperAgent._store_files(state, "```python:calc.py\ndef add(a b):\n    return a + b\n```")
    assert "calc.py" in state.artifacts


def test_valid_code_unaffected() -> None:
    state = AgentState(goal="demo")
    DeveloperAgent._store_files(state, "```python:calc.py\ndef add(a, b):\n    return a + b\n```")
    assert state.artifacts["calc.py"].startswith("def add")


def test_shell_narration_skipped() -> None:
    state = AgentState(goal="demo")
    DeveloperAgent._store_files(
        state,
        "```sh\nnpm install chart.js react-chartjs-2\n```\n"
        "```shell:frontend\nmkdir frontend\n```\n"
        "```shell\nmkdir x\n```\n",
    )
    assert state.artifacts == {}, sorted(state.artifacts)


def test_shell_with_real_filepath_kept() -> None:
    state = AgentState(goal="demo")
    DeveloperAgent._store_files(state, "```bash:deploy.sh\n#!/bin/bash\necho hi\n```")
    assert state.artifacts.get("deploy.sh", "").startswith("#!/bin/bash")


async def test_css_assets_staged_for_existence_tests() -> None:
    """os.path.isfile(.css) asserts pass — assets share the sandbox."""
    state = AgentState(goal="dashboard")
    state.artifacts = {
        "app.py": "def ok():\n    return True\n",
        "dashboard/src/styles/Dashboard.css": ".dash { color: red; }\n",
        "tests/test_assets.py": (
            "import os\nfrom app import ok\n"
            "def test_logic():\n    assert ok() is True\n"
            "def test_stylesheets_existence():\n"
            "    assert os.path.isfile('dashboard/src/styles/Dashboard.css')\n"
        ),
    }
    state = await ExecutionAgent(memory=MemoryManager()).run(state)
    summary = next(r for r in state.exec_reports if r.get("summary"))
    assert summary["ok"] is True, summary["stderr"]


async def test_missing_third_party_phased() -> None:
    """`import flask` fails with an explicit rewrite-using-stdlib signal."""
    state = AgentState(goal="api")
    state.artifacts = {
        "main.py": "from flask import Flask, jsonify\n\napp = Flask(__name__)\n",
    }
    state = await ExecutionAgent(memory=MemoryManager()).run(state)
    dep_reports = [r for r in state.exec_reports if r.get("phase") == "missing-dependency"]
    assert dep_reports, [ (r.get("target"), r.get("phase")) for r in state.exec_reports ]
    assert any("'flask'" in r.get("stderr", "") for r in dep_reports)
    assert "standard library" in dep_reports[0]["stderr"]
    summary = next(r for r in state.exec_reports if r.get("summary"))
    assert summary["ok"] is False


async def test_project_local_import_not_mislabeled() -> None:
    """`import dashboard.utils` with only dashboard/*.js staged is a plain
    import error, NOT a missing third-party package."""
    state = AgentState(goal="mixed")
    state.artifacts = {
        "app.py": "import dashboard.utils\nprint('hi')\n",
        "dashboard/utils.js": "export default {};\n",
    }
    state = await ExecutionAgent(memory=MemoryManager()).run(state)
    assert not [r for r in state.exec_reports if r.get("phase") == "missing-dependency"]


def test_file_list_narration_skipped() -> None:
    """A bare fence echoing an existing artifact path stores nothing."""
    state = AgentState(goal="demo")
    DeveloperAgent._store_files(state, "```javascript:dashboard/Dashboard.js\nx = 1\n```")
    assert "dashboard/Dashboard.js" in state.artifacts
    before = dict(state.artifacts)
    DeveloperAgent._store_files(state, "```\ndashboard/Dashboard.js\n```")
    assert state.artifacts == before


def test_stdlib_only_prompt() -> None:
    assert "standard library" in DeveloperAgent.system_prompt
    assert "flask" in DeveloperAgent.system_prompt.lower()
