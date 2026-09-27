# 🤖 AI Software Engineer Agent

An intelligent, event-driven multi-agent system that automates software engineering tasks through natural language interaction.

Built on **LangGraph + FastAPI + ChromaDB**, with streaming CLI, HTTP/SSE API, offline fallback mode (no API key required), and a **Next.js + Material UI frontend** (`../ai_software_web`).

## 🚀 Features

- **Code Generation**: Create new files, classes, and functions
- **Code Analysis**: Understand existing code structure
- **Refactoring**: Improve code quality and maintainability
- **Bug Fixing**: Identify and fix issues (sandbox-verified)
- **Testing**: Generate and run unit tests
- **Documentation**: Auto-generate technical documentation
- **Git Integration**: Version control operations (`tools/git_tools.py`)
- **Multi-language Support**: Python, JavaScript, HTML, JSON, Markdown
- **Multi-Agent Orchestration**: ProductManager (DAG) → Architect → [Developer → QA → Execution]×N → Writer, with self-correction loop (retry budget, default 3)
- **Streaming Interfaces**: CLI tokens + SSE (`token` / `state` / `result` events) + Next.js web UI
- **Persistent Memory**: ChromaDB vector store + JSON entity store + epistemic summarisation
- **Conversation History**: per-session chat threads (title / rename / delete) backed by MongoDB with JSON-file fallback; follow-up goals reuse `session_id` for "further steps"
- **Offline Mode**: Fully deterministic fallback when `OPENAI_API_KEY` is empty — no network calls, CI-safe

## 🗂️ Repository Map

```
Agents/
├── ai_software_agent/          # ← this README (Python backend)
│   ├── app/                    # NEW multi-agent core (recommended)
│   │   ├── main.py             # CLI + Python API (arun/arun_stream) + --serve
│   │   ├── agents/             # product_manager, architect, developer, qa, execution, writer, base, orchestrator
│   │   ├── core/               # config, llm, memory, state, history (sessions+messages)
│   │   └── api/server.py       # FastAPI app: GET /health, POST /v1/run (SSE) + /v1/sessions CRUD + CORS for :3000/:3001
│   ├── agent_core/             # LEGACY single-agent orchestrator (kept for compat)
│   ├── main.py                 # LEGACY single-agent CLI (list files | view | status | commit | help | exit)
│   ├── tools/                  # git / testing / validation helpers
│   ├── prompts/ templates/     # system + task prompts, code/file templates
│   ├── tests/                  # test_state, test_orchestrator, test_memory, test_agents, test_history
│   ├── frontend/README.md      # spec doc for the web UI (scaffold lives in ../ai_software_web)
│   └── .agent_state/ .agent_chroma/  # runtime data (entity JSON + history JSON + chroma persist) — gitignored conceptually
└── ai_software_web/            # Next.js 14 + MUI v6 frontend (see its own README)
    ├── src/app/                # layout (AppBar+health), page (runner), api/run (CORS proxy)
    ├── src/components/         # GoalForm, StreamView, PipelineView, ArtifactsView, HealthBadge
    ├── src/lib/api.ts          # getHealth + streamRun (fetch-based SSE, POST)
    └── src/store/              # zustand agent store
```

> **Pipeline (actual, `app/agents/orchestrator.py`)**: `ProductManager (DAG) → Architect → [Developer → QA → Execution]×N → Writer`. The bracketed loop replays tracebacks to the Developer until tests pass or `MAX_SELF_CORRECTION_RETRIES` is exhausted. Every transition emits a `state` event; LLM output streams as `token` events; the run ends with a `result` event carrying the full `AgentState` (artifacts, exec_reports, retries_used, error).

## 📋 Prerequisites

- **Python 3.12+** (see `.python-version`)
- `pip` >= 23, or [`uv`](https://docs.astral.sh/uv/) (recommended)
- **Node.js 18.17+** (20.x recommended) — only for the web frontend
- Optional: OpenAI API key for online LLM mode. Without a key the agent runs in offline/deterministic fallback mode.

## 📦 Installation

```bash
# 1. Clone the repository
git clone <repository-url>
cd ai_software_agent

# 2. Create and activate a virtual environment
python3.12 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install dependencies (pick one)
pip install -r requirements.txt  # full install incl. dev tools
# or minimal / editable install:
pip install -e .
pip install -e ".[dev]"          # + pytest, ruff, mypy, black
# or with uv:
uv sync

# 4. Set up environment variables
cp .env.example .env
# Edit .env and add your key (leave empty for offline mode):
# OPENAI_API_KEY=sk-...
```

### ⚙️ Configuration (`.env`)

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | _(empty)_ | Empty = offline mode, set = online LLM mode |
| `OPENAI_MODEL` | `gpt-4o-mini` | Chat/completion model |
| `OPENAI_EMBED_MODEL` | `text-embedding-3-small` | Embeddings model |
| `MAX_CONTEXT_TOKENS` | `128000` | Transcript budget before summariser compacts |
| `SUMMARY_TRIGGER_RATIO` | `0.75` | Compact when usage ≥ ratio × budget |
| `VECTOR_BACKEND` | `chroma` | `chroma` or `memory` (in-process fallback) |
| `CHROMA_PERSIST_DIR` | `.agent_chroma` | Vector store persist path |
| `ENTITY_STORE_PATH` | `.agent_state/entities.json` | Entity memory path |
| `MONGODB_URI` | _(empty)_ | Empty = JSON-file history fallback; set e.g. `mongodb://localhost:27017` for MongoDB history |
| `MONGODB_DB` | `ai_agent` | MongoDB database for history |
| `MONGODB_SESSIONS_COLLECTION` | `sessions` | Sessions collection name |
| `MONGODB_MESSAGES_COLLECTION` | `messages` | Messages collection name |
| `HISTORY_STORE_PATH` | `.agent_state/history.json` | File fallback path when `MONGODB_URI` is empty |
| `HISTORY_MAX_MESSAGES` | `200` | Max messages kept per session (oldest dropped) |
| `HISTORY_MESSAGE_MAX_CHARS` | `65536` | Hard cap per persisted message (both backends) |
| `HISTORY_SUMMARY_MAX_CHARS` | `20000` | Cap for the orchestrator result summary |
| `HISTORY_STREAM_PREVIEW_MAX_CHARS` | `12000` | Streamed-output preview inside the summary |
| `HISTORY_REPORT_FIELD_MAX_CHARS` | `4000` | Per-field cap for persisted exec/test reports |
| `HISTORY_SAVE_AGENT_TURNS` | `true` | Persist each agent's full output as its own message |
| `HISTORY_AGENT_TURN_MAX_CHARS` | `12000` | Cap per persisted agent-turn message |
| `HISTORY_ARTIFACT_FILE_MAX_CHARS` | `20000` | Per-file cap for the artifact-contents snapshot |
| `HISTORY_ARTIFACTS_TOTAL_MAX_CHARS` | `200000` | Total cap for the artifact-contents snapshot |
| `PROJECT_ROOT` | `.` | Working directory for agent file ops |
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `MAX_SELF_CORRECTION_RETRIES` | `3` | Self-correction loop retries (0–10) |
| `SANDBOX_TIMEOUT_S` | `30` | Code execution timeout (s) |
| `SANDBOX_MAX_BYTES` | `64000` | Max captured sandbox output (bytes) |

## ▶️ Running the Project

### 1. Multi-agent CLI (recommended, `app/` core)

```bash
# Single goal (streaming output)
python -m app.main "Build a FastAPI todo app with tests"

# Interactive REPL
python -m app.main

# Via installed entry point (after pip install -e .)
ai-agent "Refactor agent_core/ to async with retries"
ai-agent   # interactive mode
```

### 2. Legacy single-agent CLI (`main.py`)

```bash
python main.py
# Commands inside the CLI:
#   list files | view <filename> | status | commit | help | exit
```

### 3. HTTP / SSE API server (backend for the web UI)

```bash
# Option A — via CLI flag
python -m app.main --serve --port 8000

# Option B — via uvicorn (same app)
uvicorn app.main:app --port 8000 --reload
# or directly:
uvicorn app.api.server:app --port 8000 --reload
```

CORS is pre-configured for `http://localhost:3000`, `127.0.0.1:3000`, `:3001` variants, so the Next.js dev server can call the API cross-origin. For other origins (e.g. Vercel preview), extend `allow_origins` in `app/api/server.py` or use the frontend's `/api` proxy route.

Endpoints:

```bash
# Health check (shows online/offline LLM status)
curl http://localhost:8000/health
# => {"status":"ok","llm":"offline"}

# Stream an agent run (SSE: token / state / result events)
# Omit session_id => new auto-titled session; reuse it for follow-up "further steps"
curl -N -X POST http://localhost:8000/v1/run \
  -H "Content-Type: application/json" \
  -d '{"goal": "Create a Python CLI calculator with tests", "session_id": "demo"}'
```

Event shapes:

```jsonc
// token — raw markdown chunk
{ "type": "token", "agent": "Developer", "token": "Creating FastAPI...", "session_id": "demo" }
// state — TelemetryEvent
{ "type": "state", "agent": "developer", "status": "running", "feedback": "..." }
// result — final AgentState
{ "type": "result", "state": { "artifacts": {...}, "exec_reports": [], "retries_used": 0, "error": null } }
```

### 3b. Conversation history (sessions + messages)

Every `POST /v1/run` persists under `session_id` (auto-created + auto-titled from the goal when omitted): the user goal, **each agent's full streamed output** as its own message (`ProductManager`/`Architect`/`Developer`/`Writer` as `note`, QA suite included), and a final `result` message carrying the summary, wider report tails (last 5 exec / 3 test reports) and a bounded **artifact-contents snapshot** (previously only file names were kept). Prior turns are injected into `state.history_context` so ProductManager/Architect/Developer continue the same thread. Backend: MongoDB when `MONGODB_URI` is set, otherwise `.agent_state/history.json` (offline/CI safe). Volume is controlled by the `HISTORY_*_CHARS` settings above (MongoDB documents cap at 16MB); LLM context stays capped separately via `MAX_CONTEXT_TOKENS`.

```bash
# List sessions (newest first)
curl "http://localhost:8000/v1/sessions?limit=50&offset=0"

# Create a session explicitly
curl -X POST http://localhost:8000/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{"title": "My calculator thread"}'
# => {"id": "s-...", "title": "My calculator thread", ...} (201)

# Get session + its messages
curl http://localhost:8000/v1/sessions/<id>

# Rename title
curl -X PATCH http://localhost:8000/v1/sessions/<id> \
  -H "Content-Type: application/json" \
  -d '{"title": "Calculator v2"}'

# List messages only
curl "http://localhost:8000/v1/sessions/<id>/messages?limit=100"

# Delete session + its messages
curl -X DELETE http://localhost:8000/v1/sessions/<id>
```

MongoDB document shapes (`sessions` / `messages` collections, `motor` async driver):

```jsonc
// sessions: {"_id": "<session_id>", "title": "...", "created_at": 0.0,
//            "updated_at": 0.0, "message_count": 2, "last_preview": "...", "metadata": {}}
// messages: {"_id": "<msg_id>", "session_id": "...", "role": "user|assistant|system",
//            "content": "...", "agent": "Developer", "kind": "goal|result|note", "created_at": 0.0, "extra": {}}
```

### 4. Python API

```python
import asyncio
from app.main import arun, arun_stream

# One-shot (pass session_id to continue a thread)
result = asyncio.run(arun("Add unit tests for app/core/memory.py", session_id="my-thread"))
print(result.session_id, result.history_context[:200], result.artifacts)

# Streaming
async def main():
    async for evt in arun_stream("Scaffold a blog API", session_id="my-thread"):
        if evt["type"] == "token":
            print(evt["token"], end="")
        elif evt["type"] == "result":
            print("\nDone:", evt["state"]["artifacts"])

asyncio.run(main())
```

History from Python (same store the API uses):

```python
import asyncio
from app.core.history import get_history_store

async def main():
    store = get_history_store()
    print(await store.list_sessions())
    await store.rename_session("<id>", "New title")
    print(await store.get_messages("<id>"))

asyncio.run(main())
```

### 5. Web frontend (Next.js + MUI, `../ai_software_web`)

```bash
# Terminal 1 — backend (from this folder)
python -m app.main --serve --port 8000

# Terminal 2 — frontend
cd ../ai_software_web
npm install
cp .env.example .env.local   # NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev                  # => http://localhost:3000
```

The UI sends `{ goal, session_id }` to `POST /v1/run` via `fetch` streaming (EventSource can't POST), renders tokens as markdown, pipeline steps (PM → Architect → Dev → QA → Writer), artifacts with tabs, and a health chip from `GET /health`. Full details in `../ai_software_web/README.md` (and the spec copy at `frontend/README.md`).

## 🧪 Testing & Linting

```bash
# Run all tests
pytest -v

# Focused runs
pytest tests/test_memory.py -v
pytest tests/test_orchestrator.py -v
pytest tests/test_history.py -v

# Lint / format / type-check
ruff check .
black .
mypy app/
```

Current suite: `test_state`, `test_orchestrator`, `test_memory` (incl. Chroma keyword-arg round-trip), `test_agents`, `test_history` (session CRUD, persistence, orchestrator turn capture, API endpoints) — all passing (26 tests).

## 🛠️ Troubleshooting

| Symptom | Cause / Fix |
|---|---|
| `PermissionError: [Errno 13] ... '.agent_state/entities.json'` | Runtime dirs created by a prior `sudo`/root run and owned by `root`. Fix ownership (run as root once): `chown -R $(id -un):staff .agent_state .agent_chroma` (or the whole repo). Then re-run **without** `sudo`. Verify: `touch .agent_state/.write_test` as your normal user. |
| `chroma add failed (Expected embeddings to be a list of floats ...)` | **Fixed in `app/core/memory.py`** — Chroma's `add(ids, embeddings, metadatas, documents)` / `query(query_embeddings, query_texts, ...)` were called positionally, so text landed in `embeddings`. Now called with keywords (`ids/documents/metadatas`, `query_texts/n_results`) + metadata sanitised to Chroma scalar types. If you still see it, pull the latest `memory.py`. Workaround: `VECTOR_BACKEND=memory`. |
| `chroma query failed (...)` then silent fallback | Same positional-arg bug as above (fixed). Check logs with `LOG_LEVEL=DEBUG`. |
| Frontend `Maximum update depth exceeded` | A component calls `setState` during render (e.g. `setState` directly in body, or `useEffect` without dep array that writes to the `zustand` store each render). Fix: move the update into an event handler or `useEffect(..., [stableDeps])`, and subscribe with selectors (`useAgentStore(s => s.output)`) instead of the whole store. The shipped `GoalForm/StreamView/PipelineView` follow this pattern. |
| Frontend shows `backend unreachable` / CORS error on `:3000` | Backend not running, wrong `NEXT_PUBLIC_API_URL` (no trailing `/`), or origin not in `allow_origins`. Start backend (`python -m app.main --serve --port 8000`), or set `NEXT_PUBLIC_API_URL=/api` to use the Next.js proxy route (`src/app/api/run`). |
| `GET /.well-known/appspecific/com.chrome.devtools.json 404` | Harmless Chrome DevTools probe during `next dev` — not an app error. Ignore, or silence by adding a `public/.well-known/...` stub. |
| `health: offline` | Normal without `OPENAI_API_KEY`. Set the key in `.env` for online LLM mode. |
| History empty after restart | Expected before this change; now sessions persist in MongoDB (`MONGODB_URI` set) or `.agent_state/history.json` (fallback). Check the file exists and is writable; same `PermissionError` ownership fix as `entities.json` applies. |
| `motor is not installed` | Install history backend dep: `pip install motor` (or `pip install -r requirements.txt`). File fallback is used only when `MONGODB_URI` is empty. |
| `PATCH /v1/sessions/<id>` → 404 | Unknown/expired `session_id` (deleted or different `HISTORY_STORE_PATH` / Mongo DB). List via `GET /v1/sessions` to confirm. |
| `PATCH /v1/sessions/<id>` → 422 | Empty title — titles must be non-empty (max 200 chars). |
| `ModuleNotFoundError: No module named 'flask'` (or requests/numpy/…) in exec reports | The sandbox has only the stdlib + already-installed packages — third-party deps can't be pip-installed there. The Developer is instructed stdlib-only, and the failure carries a `missing-dependency` rewrite hint so the retry loop drops the dependency instead of repeating the error. |
| `CHROMA` lock errors | Only one backend instance per `CHROMA_PERSIST_DIR`; or set `VECTOR_BACKEND=memory` in `.env`. |
| Stale root-owned pytest tmp (`/private/tmp/pytest-of-root ... not owned`) | Leftover from a sudo test run. `sudo rm -rf /private/tmp/pytest-of-root` and re-run `pytest` without sudo. |
| Port clash `:3000` / `:8000` | `npm run dev -- -p 3001` / `python -m app.main --serve --port 8001` + update `NEXT_PUBLIC_API_URL`. |

## 📄 License

MIT — see `pyproject.toml`. Frontend (`../ai_software_web`) shares the same licence.
