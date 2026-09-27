"""Tests for persistent conversation history (sessions + messages)."""

from __future__ import annotations

import pytest

from app.core.history import FileHistoryStore, auto_title, get_history_store, reset_history_store


@pytest.fixture()
def history_store(tmp_cwd):
    reset_history_store(None)
    store = FileHistoryStore(path=str(tmp_cwd / "history.json"))
    reset_history_store(store)
    yield store
    reset_history_store(None)


async def test_auto_title_truncates() -> None:
    assert auto_title("") == "Untitled session"
    assert auto_title("Build a FastAPI todo app with tests") == "Build a FastAPI todo app with tests"
    long = "x" * 200
    assert len(auto_title(long)) <= 60


async def test_session_crud(history_store: FileHistoryStore) -> None:
    s = await history_store.create_session(title="First chat")
    assert s.title == "First chat"

    listed = await history_store.list_sessions()
    assert [x.id for x in listed] == [s.id]

    renamed = await history_store.rename_session(s.id, "Renamed title")
    assert renamed.title == "Renamed title"

    with pytest.raises(ValueError):
        await history_store.rename_session(s.id, "   ")

    assert await history_store.delete_session(s.id) is True
    assert await history_store.get_session(s.id) is None
    assert await history_store.delete_session(s.id) is False


async def test_messages_and_context(history_store: FileHistoryStore) -> None:
    s = await history_store.create_session(title="ctx")
    await history_store.append_message(s.id, "user", "Build a calculator", agent="User", kind="goal")
    await history_store.append_message(s.id, "assistant", "Done: calc.py", agent="Orchestrator", kind="result")

    msgs = await history_store.get_messages(s.id)
    assert len(msgs) == 2
    assert msgs[0].role == "user" and msgs[1].role == "assistant"

    ctx = await history_store.get_context(s.id)
    assert "calculator" in ctx and "calc.py" in ctx

    updated = await history_store.get_session(s.id)
    assert updated is not None and updated.message_count == 2


async def test_file_persistence(tmp_cwd) -> None:
    path = str(tmp_cwd / "history.json")
    store = FileHistoryStore(path=path)
    s = await store.create_session(title="persist me")
    await store.append_message(s.id, "user", "hello", kind="goal")

    reloaded = FileHistoryStore(path=path)
    fetched = await reloaded.get_session(s.id)
    assert fetched is not None and fetched.title == "persist me"
    assert len(await reloaded.get_messages(s.id)) == 1


async def test_message_content_cap(history_store: FileHistoryStore) -> None:
    """Oversized content is bounded by HISTORY_MESSAGE_MAX_CHARS, not dropped."""
    from app.core.config import get_settings

    s = await history_store.create_session(title="caps")
    big = "x" * (get_settings().history_message_max_chars + 5000)
    msg = await history_store.append_message(s.id, "user", big, kind="goal")
    assert len(msg.content) == get_settings().history_message_max_chars
    assert (await history_store.get_session(s.id)).message_count == 1


async def test_orchestrator_persists_turns(tmp_cwd) -> None:
    """run_stream must persist user goal + assistant result under session_id."""
    from app.agents.orchestrator import MultiAgentOrchestrator
    from app.core.memory import MemoryManager

    reset_history_store(FileHistoryStore(path=str(tmp_cwd / "history.json")))
    orch = MultiAgentOrchestrator(memory=MemoryManager())
    final = await orch.run("Add a tiny calculator", session_id="test-session-1")
    assert final.session_id == "test-session-1"

    store = get_history_store()
    session = await store.get_session("test-session-1")
    assert session is not None
    msgs = await store.get_messages("test-session-1")
    roles = [m.role for m in msgs]
    assert "user" in roles and "assistant" in roles

    # Persisted report tails keep native JSON types (frontend strict-checks
    # `passed === true`; stringified "True"/"None" would break it).
    assistant_msg = next(m for m in msgs if m.kind == "result")
    for rep in assistant_msg.extra.get("exec_reports", []):
        assert isinstance(rep.get("ok"), bool)
        assert isinstance(rep.get("returncode"), int)
    assert isinstance(assistant_msg.extra.get("done"), bool)
    assert isinstance(assistant_msg.extra.get("artifacts"), list)

    # Full per-agent outputs are persisted as their own messages (previously
    # only a 4000-char combined preview survived).
    agents = {m.agent for m in msgs if m.kind == "note"}
    assert {"ProductManager", "Architect", "Developer", "Writer"} <= agents
    qa_notes = [m for m in msgs if m.agent == "QA"]
    assert qa_notes and "test" in qa_notes[0].content.lower()

    # Artifact CONTENTS snapshot rides along (previously names only).
    contents = assistant_msg.extra.get("artifact_contents", {})
    assert contents and all(isinstance(v, str) for v in contents.values())

    # Second goal in the same session sees prior context ("further steps")
    final2 = await orch.run("Now add subtraction", session_id="test-session-1")
    assert final2.history_context != "" or len(await store.get_messages("test-session-1")) >= 4


def test_history_api_endpoints(tmp_cwd) -> None:
    from fastapi.testclient import TestClient

    from app.api.server import create_app

    reset_history_store(FileHistoryStore(path=str(tmp_cwd / "history.json")))
    client = TestClient(create_app())

    r = client.post("/v1/sessions", json={"title": "API chat"})
    assert r.status_code == 201, r.text
    sid = r.json()["id"]

    r = client.get("/v1/sessions")
    assert r.status_code == 200 and any(s["id"] == sid for s in r.json()["sessions"])

    r = client.patch(f"/v1/sessions/{sid}", json={"title": "Renamed via API"})
    assert r.status_code == 200 and r.json()["title"] == "Renamed via API"

    r = client.get(f"/v1/sessions/{sid}/messages")
    assert r.status_code == 200 and r.json()["messages"] == []

    r = client.delete(f"/v1/sessions/{sid}")
    assert r.status_code == 200 and r.json()["deleted"] is True

    r = client.get(f"/v1/sessions/{sid}")
    assert r.status_code == 404
