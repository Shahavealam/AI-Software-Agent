"""Tests for shared state contracts: DAG ordering, cycles, SSE framing."""

from __future__ import annotations

import json

import pytest

from app.core.state import AgentName, TaskNode, TaskStatus, TelemetryEvent, TokenEvent, WorkflowDAG


def _node(title: str, **kw) -> TaskNode:
    return TaskNode(title=title, owner=AgentName.DEVELOPER, **kw)


def test_topological_order_respects_dependencies() -> None:
    a = _node("a")
    b = _node("b", depends_on=[a.id])
    c = _node("c", depends_on=[b.id])
    dag = WorkflowDAG(goal="g", nodes=[c, a, b])  # shuffled input
    assert [n.title for n in dag.topological_order()] == ["a", "b", "c"]


def test_cycle_detection_raises() -> None:
    a = _node("a")
    b = _node("b", depends_on=[a.id])
    a.depends_on.append(b.id)
    with pytest.raises(ValueError, match="Cyclic"):
        WorkflowDAG(goal="g", nodes=[a, b]).topological_order()


def test_telemetry_event_sse_framing() -> None:
    evt = TelemetryEvent(agent="QA", status="running_tests", feedback="rerouting…", session_id="s1")
    frame = evt.sse()
    assert frame.startswith("event: state\ndata: ")
    payload = json.loads(frame.split("data: ", 1)[1])
    assert payload["agent"] == "QA" and payload["status"] == "running_tests"


def test_token_event_sse_framing() -> None:
    frame = TokenEvent(agent="Developer", token="def f():", session_id="s1").sse()
    assert frame.startswith("event: token\ndata: ")


def test_task_defaults() -> None:
    node = _node("x")
    assert node.status is TaskStatus.PENDING and node.attempts == 0
