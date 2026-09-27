"""Shared event / state contracts for the reactive agent topology.

The orchestrator and every worker speak these typed models — both through
the in-process async-generator bus and over SSE (``text/event-stream``).
"""

from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentName(str, Enum):
    ORCHESTRATOR = "Orchestrator"
    PRODUCT_MANAGER = "ProductManager"
    ARCHITECT = "Architect"
    DEVELOPER = "Developer"
    QA = "QA"
    EXECUTION = "Execution"
    WRITER = "Writer"


class TaskStatus(str, Enum):
    PENDING = "pending"
    PLANNED = "planned"
    RUNNING = "running"
    NEEDS_FIX = "needs_fix"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class TaskNode(BaseModel):
    """One unit of work inside the engineering DAG."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    title: str
    owner: AgentName
    kind: Literal["analysis", "code", "test", "execution", "docs", "plan"] = "code"
    payload: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    attempts: int = 0
    error: str | None = None


class WorkflowDAG(BaseModel):
    """Directed acyclic graph of :class:`TaskNode` produced by the router."""

    goal: str
    nodes: list[TaskNode] = Field(default_factory=list)

    def topological_order(self) -> list[TaskNode]:
        order: list[TaskNode] = []
        visited: dict[str, int] = {}  # 0=unseen 1=in-stack 2=done
        index = {n.id: n for n in self.nodes}

        def dfs(node: TaskNode) -> None:
            state = visited.get(node.id, 0)
            if state == 1:
                raise ValueError(f"Cyclic dependency detected at task {node.id}")
            if state == 2:
                return
            visited[node.id] = 1
            for dep in node.depends_on:
                if dep in index:
                    dfs(index[dep])
            visited[node.id] = 2
            order.append(node)

        for node in self.nodes:
            dfs(node)
        return order


class AgentState(BaseModel):
    """Mutable blackboard propagated through the graph execution."""

    session_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    goal: str = ""
    history_context: str = ""  # prior turns for this session (from HistoryStore)
    dag: WorkflowDAG | None = None
    artifacts: dict[str, str] = Field(default_factory=dict)  # path -> content
    test_reports: list[dict[str, Any]] = Field(default_factory=list)
    exec_reports: list[dict[str, Any]] = Field(default_factory=list)
    docs: dict[str, str] = Field(default_factory=dict)
    retries_used: int = 0
    max_retries: int = 3
    done: bool = False
    error: str | None = None


class TelemetryEvent(BaseModel):
    """State-change notification streamed to clients."""

    agent: str
    status: str
    feedback: str = ""
    ts: float = Field(default_factory=time.time)
    session_id: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)

    def sse(self) -> str:
        return f"event: state\ndata: {self.model_dump_json()}\n\n"


class TokenEvent(BaseModel):
    """Raw token chunk streamed during generation."""

    agent: str
    token: str
    ts: float = Field(default_factory=time.time)
    session_id: str = ""

    def sse(self) -> str:
        return f"event: token\ndata: {self.model_dump_json()}\n\n"
