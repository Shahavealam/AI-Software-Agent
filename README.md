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
- **Offline Mode**: Fully deterministic fallback when `OPENAI_API_KEY` is empty — no network calls, CI-safe

## 🗂️ Repository Map

```
Agents/
├── ai_software_agent/          # ← this README (Python backend)
│   ├── app/                    # NEW multi-agent core (recommended)
│   │   ├── main.py             # CLI + Python API (arun/arun_stream) + --serve
│   │   ├── agents/             # product_manager, architect, developer, qa, execution, writer, base, orchestrator
│   │   ├── core/               # config, llm, memory, state
│   │   └── api/server.py       # FastAPI app: GET /health, POST /v1/run (SSE) + CORS for :3000/:3001
│   ├── agent_core/             # LEGACY single-agent orchestrator (kept for compat)
│   ├── main.py                 # LEGACY single-agent CLI (list files | view | status | commit | help | exit)
│   ├── tools/                  # git / testing / validation helpers
│   ├── prompts/ templates/     # system + task prompts, code/file templates
│   ├── tests/                  # test_state, test_orchestrator, test_memory, test_agents
│   ├── frontend/README.md      # spec doc for the web UI (scaffold lives in ../ai_software_web)
│   └── .agent_state/ .agent_chroma/  # runtime data (entity JSON + chroma persist) — gitignored conceptually
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

### 4. Python API

```python
import asyncio
from app.main import arun, arun_stream

# One-shot
result = asyncio.run(arun("Add unit tests for app/core/memory.py"))
print(result.artifacts, result.exec_reports)

# Streaming
async def main():
    async for evt in arun_stream("Scaffold a blog API"):
        if evt["type"] == "token":
            print(evt["token"], end="")
        elif evt["type"] == "result":
            print("\nDone:", evt["state"]["artifacts"])

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

# Lint / format / type-check
ruff check .
black .
mypy app/
```

Current suite: `test_state`, `test_orchestrator`, `test_memory` (incl. Chroma keyword-arg round-trip), `test_agents` — all passing.

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
| `CHROMA` lock errors | Only one backend instance per `CHROMA_PERSIST_DIR`; or set `VECTOR_BACKEND=memory` in `.env`. |
| Stale root-owned pytest tmp (`/private/tmp/pytest-of-root ... not owned`) | Leftover from a sudo test run. `sudo rm -rf /private/tmp/pytest-of-root` and re-run `pytest` without sudo. |
| Port clash `:3000` / `:8000` | `npm run dev -- -p 3001` / `python -m app.main --serve --port 8001` + update `NEXT_PUBLIC_API_URL`. |

## 📄 License

MIT — see `pyproject.toml`. Frontend (`../ai_software_web`) shares the same licence.
