"""Regression tests for the "streamed code but run failed" family of bugs.

Covers: shared-sandbox multi-file imports, guarded CLIs, syntax-error
attribution, summary-based QA verdicts, fence-parser edge cases.
"""

from __future__ import annotations

from app.agents.developer import DeveloperAgent
from app.agents.execution import ExecutionAgent, is_test_path, sanitise_relpath
from app.agents.qa import QAAgent
from app.core.memory import MemoryManager
from app.core.state import AgentState


def _agent() -> ExecutionAgent:
    return ExecutionAgent(memory=MemoryManager())


async def test_multifile_import_project_passes() -> None:
    """The calculator case: test imports sibling module — must pass."""
    state = AgentState(goal="calculator")
    state.artifacts = {
        "calculator.py": "def add(a, b):\n    return a + b\n",
        "tests/test_calculator.py": (
            "from calculator import add\n"
            "def test_add():\n    assert add(1, 2) == 3\n"
        ),
    }
    state = await _agent().run(state)
    summary = next(r for r in state.exec_reports if r.get("summary"))
    assert summary["ok"] is True, summary["stderr"]
    assert QAAgent().evaluate(state) is True


async def test_guarded_cli_does_not_fail_build() -> None:
    """argparse behind __main__ guard must import cleanly (old code ran it bare → exit 2)."""
    state = AgentState(goal="cli")
    state.artifacts = {
        "cli.py": (
            "import argparse\n"
            "def build_parser():\n    p = argparse.ArgumentParser()\n    p.add_argument('x')\n    return p\n"
            "def main():\n    args = build_parser().parse_args()\n    print(args.x)\n"
            "if __name__ == '__main__':\n    main()\n"
        ),
    }
    state = await _agent().run(state)
    summary = next(r for r in state.exec_reports if r.get("summary"))
    assert summary["ok"] is True, summary["stderr"]


async def test_syntax_error_attributed_to_file() -> None:
    state = AgentState(goal="broken")
    state.artifacts = {"bad.py": "def broken(:\n"}
    state = await _agent().run(state)
    summary = next(r for r in state.exec_reports if r.get("summary"))
    assert summary["ok"] is False
    assert "bad.py" in summary["stderr"]
    assert QAAgent().evaluate(state) is False


async def test_broken_import_surfaces_module() -> None:
    state = AgentState(goal="bad import")
    state.artifacts = {"app.py": "from nosuchmod_xyz import thing\nprint(thing)\n"}
    state = await _agent().run(state)
    summary = next(r for r in state.exec_reports if r.get("summary"))
    assert summary["ok"] is False
    assert "app.py" in summary["stderr"]


def test_evaluate_prefers_summary_over_last_file() -> None:
    agent = QAAgent()
    # last per-file report ok, but aggregate summary failed → must be False
    state = AgentState(goal="g", exec_reports=[
        {"ok": True, "returncode": 0, "stdout": "ok", "stderr": "", "target": "a.py"},
        {"ok": False, "returncode": 1, "stdout": "", "stderr": "pytest failed", "target": None, "summary": True},
    ])
    assert agent.evaluate(state) is False
    # and vice versa
    state2 = AgentState(goal="g", exec_reports=[
        {"ok": False, "returncode": 1, "stdout": "", "stderr": "x", "target": "a.py"},
        {"ok": True, "returncode": 0, "stdout": "all green", "stderr": "", "target": None, "summary": True},
    ])
    assert agent.evaluate(state2) is True


def test_is_test_path_edge_cases() -> None:
    assert is_test_path("tests/test_generated.py")
    assert is_test_path("test_foo.py")
    assert is_test_path("foo_test.py")
    assert is_test_path("tests/sub/test_x.py")
    assert not is_test_path("calculator.py")
    assert not is_test_path("cli.py")
    assert not is_test_path("contest.py")  # must not match test_ prefix logic wrongly
    assert not is_test_path("latest.py")


def test_sanitise_relpath_blocks_traversal() -> None:
    assert sanitise_relpath("../../etc/passwd") == "etc/passwd"
    assert sanitise_relpath("/abs/path.py") == "abs/path.py"
    assert sanitise_relpath("./a/b.py") == "a/b.py"
    assert sanitise_relpath("") is None


def test_developer_fence_variants() -> None:
    cases = [
        ("```python:calculator.py\ndef add(a, b):\n    return a + b\n```", "calculator.py"),
        ("```python calculator.py\nCODE\n```", "calculator.py"),
        ("```calculator.py\nCODE\n```", "calculator.py"),
        ("```python\nCODE\n```", "generated_0.py"),
        ("```py:tests/test_a.py\nCODE\n```", "tests/test_a.py"),
        ("```c++:main.cpp\nCODE\n```", "main.cpp"),
        ("```python:\"my dir/app.py\"\nCODE\n```", "my dir/app.py"),
        ("```python:../../evil.py\nCODE\n```", "evil.py"),
    ]
    for text, expected in cases:
        state = AgentState(goal="demo")
        DeveloperAgent._store_files(state, text.replace("CODE", "x = 1"))
        assert expected in state.artifacts, f"{text!r} → {sorted(state.artifacts)}"

    # CRLF + duplicate path (last wins)
    state = AgentState(goal="demo")
    DeveloperAgent._store_files(
        state, "```python:a.py\r\nv = 1\r\n```\n```python:a.py\nv = 2\n```"
    )
    assert state.artifacts["a.py"] == "v = 2"


def test_qa_strip_fences_edge_cases() -> None:
    # multiple blocks joined (suite split across blocks)
    multi = "```python\nimport os\n```\nnotes\n```python\ndef test_a():\n    assert True\n```"
    out = QAAgent._strip_fences(multi)
    assert "import os" in out and "def test_a" in out
    # single block preferred content kept
    single = "rubric\n```python\ndef test_x():\n    assert 1 == 1\n```\nPASS"
    assert "def test_x" in QAAgent._strip_fences(single)
    # unfenced passes through
    assert QAAgent._strip_fences("def test_y():\n    assert True") .startswith("def test_y")
    # CRLF handled
    assert "def test_z" in QAAgent._strip_fences("```python\r\ndef test_z():\r\n    assert True\r\n```")
