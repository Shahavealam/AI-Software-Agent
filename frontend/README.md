# 🤖 AI Software Engineer Agent — Frontend (Next.js + Material UI)

A modern **Next.js 14+ (App Router + TypeScript + Material UI / MUI)** frontend for the **AI Software Engineer Agent** backend.

It lets users submit natural-language software engineering goals, stream live agent output (tokens / state / result via SSE), inspect artifacts, execution reports, retries, and manage sessions — all connected to the FastAPI + LangGraph backend in `../app/`.

> **Backend:** `LangGraph + FastAPI + ChromaDB` — see [`../README.md`](../README.md)
> **Frontend (this folder):** `Next.js + TypeScript + Material UI (MUI v6) + Emotion` — talks to backend over HTTP/SSE.

---

## ✨ Features

- **Goal Runner UI** — submit goals like _"Build a FastAPI todo app with tests"_
- **Live Streaming** — renders `token` / `state` / `result` SSE events from `POST /v1/run` in real time
- **Agent Pipeline View** — Architect → Developer → QA → Writer status, feedback, retries
- **Artifacts Explorer** — view created/updated files, diffs, code blocks with syntax highlighting
- **Execution Reports** — sandbox runs, test results, lint output
- **Session Support** — `session_id` for persistent ChromaDB + entity memory per user/project
- **Health Indicator** — online/offline LLM mode via `GET /health`
- **Offline-Friendly** — works against backend offline/deterministic fallback mode (no OpenAI key needed)
- **MUI Theming** — `ThemeProvider + CssBaseline`, light/dark mode toggle, responsive `Grid` / `Stack` layout, `AppRouterCacheProvider` for Next.js App Router

---

## 🏗️ Architecture

```
┌──────────────────────┐      HTTP/SSE       ┌──────────────────────────────┐
│  Next.js Frontend    │ ──────────────────► │  FastAPI Backend (../app/)   │
│  (this folder)       │  POST /v1/run       │                              │
│                      │  GET  /health       │  MultiAgentOrchestrator      │
│  app/page.tsx        │ ◄────────────────── │  Architect → Dev → QA        │
│  components/Chat.tsx │  text/event-stream  │  + Memory (ChromaDB)         │
│  lib/api.ts          │  token/state/result │  + Sandbox + Self-correction │
└──────────────────────┘                     └──────────────────────────────┘
         │                                                     │
         │ NEXT_PUBLIC_API_URL=http://localhost:8000           │ PROJECT_ROOT=.
         └─────────────────────────────────────────────────────┘
```

**Backend contract (already implemented):**

| Endpoint | Method | Body | Response |
|---|---|---|---|
| `/health` | `GET` | — | `{ "status": "ok", "llm": "online" \| "offline" }` |
| `/v1/run` | `POST` | `{ "goal": string, "session_id": string }` | `text/event-stream` with `event: token/state/result` + `data: JSON` |

SSE event shapes:

```ts
// token — raw markdown chunk
{ "type": "token", "token": "Creating FastAPI..." }

// state — telemetry
{ "type": "state", "agent": "developer", "status": "running", "feedback": "..." }

// result — final AgentState
{ "type": "result", "state": { "artifacts": {...}, "exec_reports": [], "retries_used": 0, "error": null } }
```

---

## 📋 Prerequisites

- **Node.js 18.17+** or 20+ + `npm` / `pnpm` / `yarn`
- **Python 3.12+** for backend (see `../README.md`)
- Backend running locally (default `http://localhost:8000`)

Check versions:

```bash
node -v   # v20.x recommended
python3.12 --version
```

---

## 📦 Installation

### 1. Start the backend first

```bash
cd ..  # ai_software_agent/

# venv + deps
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # leave OPENAI_API_KEY empty for offline mode

# serve API on :8000
python -m app.main --serve --port 8000
# or
uvicorn app.main:app --port 8000 --reload

# verify
curl http://localhost:8000/health
# => {"status":"ok","llm":"offline"}
```

### 2. Scaffold / install frontend (Next.js + MUI)

If `frontend/` is empty (docs-only), scaffold **without Tailwind** (MUI handles styling):

```bash
cd frontend/

npx create-next-app@latest . --typescript --eslint --app --src-dir --import-alias "@/*"
# answers: ✔ src/ ✔ App Router ✔ NO Tailwind (we use MUI)

# Core MUI stack (MUI v6 + Emotion for Next.js App Router)
npm install @mui/material @mui/icons-material @emotion/react @emotion/styled @emotion/cache
npm install @mui/lab  # optional: LoadingButton, Timeline, etc.

# SSE + state + markdown
npm install eventsource-parser zustand react-markdown remark-gfm
```

If `package.json` already exists:

```bash
cd frontend/
npm install
```

> **Framework:** [Material UI (MUI)](https://mui.com/material-ui/) — React UI library implementing Material Design. We use `ThemeProvider`, `CssBaseline`, `AppBar`, `Container`, `Card`, `TextField`, `Button`, `Chip`, `LinearProgress`, `Drawer`, `Snackbar`, etc. Styling via `sx` prop + Emotion (no Tailwind needed).

### 3. Configure environment

```bash
cp .env.example .env.local
```

`.env.local`:

```env
# Backend base URL (no trailing slash)
NEXT_PUBLIC_API_URL=http://localhost:8000

# Optional: default session id prefix
NEXT_PUBLIC_DEFAULT_SESSION=demo
```

> In production (Vercel etc.) set `NEXT_PUBLIC_API_URL` to your deployed FastAPI URL and enable CORS on backend.

### 4. Run frontend

```bash
npm run dev
# => http://localhost:3000
```

Open **http://localhost:3000**, type a goal, watch streaming output.

---

## 🔌 Backend Connection Guide

### Health check

```ts
// lib/api.ts
export async function getHealth(base = process.env.NEXT_PUBLIC_API_URL!) {
  const res = await fetch(`${base}/health`, { cache: "no-store" });
  if (!res.ok) throw new Error(`health failed: ${res.status}`);
  return res.json() as Promise<{ status: string; llm: "online" | "offline" }>;
}
```

### Streaming a task (SSE via fetch)

Backend uses `POST /v1/run` with SSE — `EventSource` won't work (POST). Use `fetch` + reader:

```ts
// lib/api.ts
export type AgentEvent =
  | { type: "token"; token: string }
  | { type: "state"; agent: string; status: string; feedback: string }
  | { type: "result"; state: any };

export async function* streamRun(
  goal: string,
  session_id = "demo",
  base = process.env.NEXT_PUBLIC_API_URL!
): AsyncGenerator<AgentEvent> {
  const res = await fetch(`${base}/v1/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({ goal, session_id }),
  });
  if (!res.ok || !res.body) throw new Error(`run failed: ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });

    // SSE frames: "event: <kind>\ndata: <json>\n\n"
    let idx: number;
    while ((idx = buf.indexOf("\n\n")) !== -1) {
      const frame = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      const mEvent = frame.match(/^event:\s*(.+)$/m);
      const mData = frame.match(/^data:\s*(.+)$/ms);
      if (mData) {
        try {
          const data = JSON.parse(mData[1]);
          yield { type: mEvent?.[1] ?? data.type, ...data } as AgentEvent;
        } catch { /* keep-alive / partial */ }
      }
    }
  }
}
```

### Minimal React + MUI usage

```tsx
// components/Runner.tsx
"use client";
import { useState } from "react";
import { Box, TextField, Button, Card, CardContent, Typography, LinearProgress, Chip } from "@mui/material";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import { streamRun } from "@/lib/api";

export default function Runner() {
  const [goal, setGoal] = useState("Create a Python CLI calculator with tests");
  const [output, setOutput] = useState("");
  const [running, setRunning] = useState(false);

  async function run() {
    setOutput(""); setRunning(true);
    try {
      for await (const evt of streamRun(goal, "demo")) {
        if (evt.type === "token") setOutput((o) => o + (evt as any).token);
        if (evt.type === "state") console.log(`[${(evt as any).agent}]`, (evt as any).feedback);
        if (evt.type === "result") console.log("artifacts:", (evt as any).state.artifacts);
      }
    } finally { setRunning(false); }
  }

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
      <TextField
        label="Engineering goal"
        multiline rows={3} fullWidth
        value={goal} onChange={(e) => setGoal(e.target.value)}
      />
      <Box>
        <Button variant="contained" startIcon={<PlayArrowIcon />} onClick={run} disabled={running}>
          {running ? "Running…" : "Run Agent"}
        </Button>
        {running && <LinearProgress sx={{ mt: 2 }} />}
      </Box>
      <Card variant="outlined">
        <CardContent>
          <Typography variant="overline">Live output</Typography>
          <Typography variant="body2" sx={{ whiteSpace: "pre-wrap" }}>{output}</Typography>
        </CardContent>
      </Card>
    </Box>
  );
}
```

### MUI Theme + Next.js App Router setup (required)

```ts
// src/theme.ts
import { createTheme } from "@mui/material/styles";

export const theme = createTheme({
  palette: { mode: "dark", primary: { main: "#7c4dff" }, secondary: { main: "#00e5ff" } },
  typography: { fontFamily: "Inter, Roboto, sans-serif" },
});
```

```tsx
// src/components/ThemeRegistry.tsx
"use client";
import { AppRouterCacheProvider } from "@mui/material-nextjs/v14-appRouter";
import { ThemeProvider, CssBaseline } from "@mui/material";
import { theme } from "@/theme";

export default function ThemeRegistry({ children }: { children: React.ReactNode }) {
  return (
    <AppRouterCacheProvider>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </ThemeProvider>
    </AppRouterCacheProvider>
  );
}
```

```tsx
// src/app/layout.tsx
import ThemeRegistry from "@/components/ThemeRegistry";
import { AppBar, Toolbar, Typography, Container } from "@mui/material";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <ThemeRegistry>
          <AppBar position="static">
            <Toolbar><Typography variant="h6">🤖 AI Software Engineer Agent</Typography></Toolbar>
          </AppBar>
          <Container maxWidth="lg" sx={{ py: 4 }}>{children}</Container>
        </ThemeRegistry>
      </body>
    </html>
  );
}
```

> Install the Next.js MUI integration: `npm install @mui/material-nextjs` (for `AppRouterCacheProvider`).

### cURL equivalent (debug backend directly)

```bash
curl -N -X POST http://localhost:8000/v1/run \
  -H "Content-Type: application/json" \
  -d '{"goal": "Create a Python CLI calculator with tests", "session_id": "demo"}'
```

---

## 📁 Recommended Project Structure (Next.js + MUI)

```
frontend/
├── README.md               # this file
├── .env.example            # NEXT_PUBLIC_API_URL template
├── .env.local              # local override (gitignored)
├── next.config.mjs
├── tsconfig.json
├── package.json            # @mui/material, @emotion/*, @mui/icons-material
├── src/
│   ├── theme.ts            # MUI createTheme (palette, dark mode)
│   ├── app/
│   │   ├── layout.tsx      # ThemeRegistry + AppBar + Container
│   │   ├── page.tsx        # main goal runner page (MUI Grid/Stack)
│   │   └── api/run/route.ts# optional proxy to backend (avoids CORS)
│   ├── components/
│   │   ├── ThemeRegistry.tsx # AppRouterCacheProvider + ThemeProvider + CssBaseline
│   │   ├── GoalForm.tsx    # MUI TextField + Button + LoadingButton
│   │   ├── StreamView.tsx  # MUI Card + live markdown tokens
│   │   ├── PipelineView.tsx# MUI Stepper / Timeline + Chip status
│   │   ├── ArtifactsView.tsx# MUI Drawer / Tabs / List + exec_reports
│   │   └── HealthBadge.tsx # MUI Chip (online=success, offline=warning)
│   ├── lib/
│   │   ├── api.ts          # getHealth + streamRun (above)
│   │   └── types.ts        # AgentEvent, AgentState types
│   └── store/
│       └── useAgentStore.ts# zustand store (optional)
└── public/
```

Key MUI components used:

| UI area | MUI components |
|---|---|
| Layout | `AppBar`, `Toolbar`, `Container`, `Box`, `Grid`, `Stack` |
| Form | `TextField`, `Button` / `LoadingButton` (`@mui/lab`), `Select`, `Chip` |
| Streaming | `Card`, `CardContent`, `Typography`, `LinearProgress`, `Skeleton` |
| Pipeline | `Stepper`, `StepLabel`, `Timeline`, `Chip`, `Alert` |
| Artifacts | `Tabs`, `List`, `Drawer`, `Code` in `Paper`, `Snackbar` for errors |
| Theming | `ThemeProvider`, `CssBaseline`, `useColorScheme` / `IconButton` + `Brightness4/7` for dark toggle |

**Next.js proxy (optional, fixes CORS in dev/prod):**

```ts
// src/app/api/run/route.ts
export async function POST(req: Request) {
  const body = await req.json();
  const upstream = await fetch(`${process.env.BACKEND_URL!}/v1/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return new Response(upstream.body, {
    headers: { "Content-Type": "text/event-stream" },
  });
}
```

If you use the proxy, set `NEXT_PUBLIC_API_URL=/api` — no CORS config needed.

---

## 🧪 Tasks You Can Perform From UI

| Goal example | What backend does |
|---|---|
| `Build a FastAPI todo app with tests` | Architect plans → Developer scaffolds → QA runs `pytest` → Writer docs |
| `Refactor agent_core/ to async with retries` | Analysis + refactor + exec report |
| `Add unit tests for app/core/memory.py` | Generates `tests/test_*.py`, runs sandbox |
| `Fix bug in <file> where ...` | Reads file via `PROJECT_ROOT`, patches, verifies |
| `Document app/agents/orchestrator.py` | Generates markdown docs |

All tasks stream identically — UI just sends different `goal` strings.

---

## ⚙️ Scripts

```bash
npm run dev    # dev server :3000
npm run build  # production build
npm run start  # serve production build
npm run lint   # eslint
```

Backend scripts (from repo root):

```bash
python -m app.main "Build a FastAPI todo app with tests"  # CLI streaming
python -m app.main --serve --port 8000                    # API server
pytest -v                                                 # backend tests
```

---

## 🚀 Deployment

**Frontend (Vercel):**

1. Push `frontend/` to git.
2. Import in Vercel → Root Directory = `frontend`.
3. Env: `NEXT_PUBLIC_API_URL=https://<your-backend>.up.railway.app` (or `/api` if proxied).
4. Deploy.

**Backend (Railway / Render / Fly / Docker):**

```bash
# example Dockerfile CMD
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

> If frontend and backend are on different origins, add CORS on backend:
> ```python
> from fastapi.middleware.cors import CORSMiddleware
> app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "https://<vercel-app>.vercel.app"], allow_methods=["*"], allow_headers=["*"])
> ```

---

## 🛠️ Troubleshooting

| Symptom | Cause / Fix |
|---|---|
| `Failed to fetch /v1/run` | Backend not running → `python -m app.main --serve --port 8000`; check `NEXT_PUBLIC_API_URL` has no trailing `/` |
| CORS error in browser | Add `CORSMiddleware` on backend or use Next.js `/api` proxy route above |
| Empty stream / hangs | Backend in offline mode without key still streams — wait 5–10s; check backend logs `LOG_LEVEL=DEBUG` |
| `health: offline` | Normal without `OPENAI_API_KEY`. Set key in `../.env` for online LLM mode |
| `CHROMA` lock errors | Only one backend instance per `CHROMA_PERSIST_DIR`; or set `VECTOR_BACKEND=memory` in `../.env` |
| Port clash `:3000` / `:8000` | `npm run dev -- -p 3001` / `python -m app.main --serve --port 8001` + update `NEXT_PUBLIC_API_URL` |

---

## 📄 License

MIT — same as backend. See [`../pyproject.toml`](../pyproject.toml).
