"""Software Developer: writes modular clean code. Never executes it."""

from __future__ import annotations

import ast
import re
from collections.abc import AsyncGenerator

from app.agents.base import BaseAgent, EmitFn
from app.core.state import AgentName, AgentState


class DeveloperAgent(BaseAgent):
    name = AgentName.DEVELOPER
    system_prompt = (
        "You are a senior software developer. Write modular, clean, fully "
        "type-hinted code (Python/JS/HTML). Output one fenced code block per file: "
        "```<lang>:<path>\\n<code>``` e.g. ```python:calculator.py\\n...```. "
        "Rules: guard CLI/IO behind `if __name__ == \"__main__\":` so modules stay "
        "import-safe; keep imports top-level and cross-file names consistent; "
        "Python MUST use ONLY the standard library — never import flask, django, "
        "fastapi, requests, numpy, pandas or any third-party package (they are "
        "not installed in the sandbox; a web API uses stdlib http.server/wsgiref); "
        "NEVER put numbered instructions, explanations or shell commands inside "
        "a code fence — prose goes outside fences, terminal commands as plain "
        "text, never as files; no execution, no tests."
    )

    async def run(self, state: AgentState, emit: EmitFn = None) -> AgentState:  # type: ignore[override]
        from app.agents.base import _noop_emit

        emit = emit or _noop_emit
        await self.tell(emit, "coding", "Writing modular code", state.session_id)
        plan = state.artifacts.get("architect/plan.md", "")
        feedback = self._latest_feedback(state)
        patterns = await self.memory.recall(state.goal, k=3)
        history_block = f"\nHISTORY:\n{state.history_context[:3000]}" if state.history_context else ""
        existing_block = self._existing_files_block(state)
        prompt = (
            f"GOAL: {state.goal}{history_block}\nPLAN: {plan[:4000]}\n"
            f"PATTERNS: {str(patterns)[:1500]}\nFEEDBACK: {feedback[:3000]}\n"
            f"{existing_block}"
            "Write the implementation now."
        )
        full = "".join([c async for c in self._gen_stream(prompt, emit, state.session_id)])
        self._store_files(state, full)
        await self.memory.remember_turn("Developer", full[:2000])
        await self.tell(emit, "coded", f"Wrote {len([k for k in state.artifacts if not k.startswith('architect/')])} file(s)", state.session_id)
        return state

    async def stream(self, state: AgentState, emit: EmitFn = None) -> AsyncGenerator[str, None]:  # type: ignore[override]
        from app.agents.base import _noop_emit

        emit = emit or _noop_emit
        await self.tell(emit, "coding", "Streaming code tokens", state.session_id)
        plan = state.artifacts.get("architect/plan.md", "")
        feedback = self._latest_feedback(state)
        history_block = f"\nHISTORY:\n{state.history_context[:3000]}" if state.history_context else ""
        existing_block = self._existing_files_block(state)
        chunks: list[str] = []
        async for tok in self._gen_stream(f"GOAL: {state.goal}{history_block}\nPLAN: {plan[:4000]}\nFEEDBACK: {feedback[:3000]}\n{existing_block}", emit, state.session_id):
            chunks.append(tok)
            yield tok  # raw markdown token streaming
        self._store_files(state, "".join(chunks))
        await self.tell(emit, "coded", "Code stream complete", state.session_id)

    # -- helpers -------------------------------------------------------
    @staticmethod
    def _existing_files_block(state: AgentState) -> str:
        """List current artifact paths so retries reuse them.

        Without this the model invents new paths each attempt (``App.js``,
        then ``dashboard/App.js``), leaving stale duplicates behind.
        """
        files = sorted(
            k for k in state.artifacts
            if not k.startswith(("architect/", "docs/"))
        )[:30]
        if not files:
            return ""
        return (
            "EXISTING FILES (reuse these exact paths — update in place, "
            "do NOT create renamed/prefixed duplicates):\n"
            + "\n".join(f"- {f}" for f in files) + "\n"
        )

    @staticmethod
    def _latest_feedback(state: AgentState) -> str:
        if state.exec_reports:
            last = state.exec_reports[-1]
            if not last.get("ok"):
                return f"TRACEBACK:\n{last.get('stderr', '')}\nSTDOUT:\n{last.get('stdout', '')}"
        if state.test_reports:
            last = state.test_reports[-1]
            if not last.get("passed"):
                return f"TEST FAILURES:\n{last.get('details', '')}"
        return ""

    _LANGS = frozenset({
        "python", "py", "python3", "javascript", "js", "typescript", "ts", "tsx",
        "html", "css", "json", "yaml", "yml", "markdown", "md", "plaintext", "text",
        "bash", "sh", "shell", "zsh", "console", "terminal", "cmd", "powershell",
        "shellsession", "c", "cpp", "c++", "c#", "java", "go", "rust",
    })

    # Fence languages that denote terminal sessions, not files. A block in
    # one of these WITHOUT an explicit file path (```sh / ```shell:dirname)
    # is narration ("run npm install") and must be skipped, not stored.
    _SHELL_LANGS = frozenset({
        "shell", "bash", "sh", "zsh", "console", "terminal", "cmd",
        "powershell", "shellsession",
    })

    @staticmethod
    def _looks_like_prose(code: str) -> bool:
        """Heuristic: English instructions vs real (possibly broken) code.

        Only used when ``ast.parse`` already failed, to decide whether a
        ``python``-labelled block is narration ("1. Navigate to …") that must
        not become a ``generated_N.py`` time-bomb, or genuine code with a
        typo that must stay ``.py`` so the compile check + retry loop fix it.
        Conservative: requires clear prose dominance.
        """
        prose, code_score = 0, 0
        for line in code.splitlines():
            s = line.strip()
            if not s:
                continue
            if re.match(r"^(\d+[.)]|[-*])\s+\S", s):
                prose += 2  # numbered / bulleted instruction step
            elif re.match(r"^(Here|This|The|Sure|Below|Note|First|Next|Then|Finally|Step)\b", s, re.IGNORECASE):
                prose += 1
            if "`" in s:
                prose += 1  # backtick narration (python code never uses `)
            if re.search(r"\b(def |class |import |from |return |if __name__|print\(|assert )", s):
                code_score += 2
            if re.search(r"[=(){}\[\]]", s):
                code_score += 1
        return prose >= 2 and prose > code_score

    @classmethod
    def _split_info(cls, info: str) -> tuple[str, str]:
        """Split a fence info string into (language, path)."""
        info = info.strip().strip("`").strip()
        if not info:
            return "", ""
        if ":" in info:
            lang_part, _, path_part = info.partition(":")
            lang_part, path_part = lang_part.strip(), path_part.strip()
            if lang_part.lower() in cls._LANGS and path_part:
                return lang_part, path_part
            if path_part and ("/" in path_part or "." in path_part):
                return lang_part, path_part
            return lang_part, ""
        tokens = info.split()
        if len(tokens) >= 2 and tokens[0].lower() in cls._LANGS:
            return tokens[0], " ".join(tokens[1:])
        if len(tokens) == 1:
            tok = tokens[0]
            if tok.lower() in cls._LANGS or tok.lower() in {"plain", "code"}:
                return tok, ""
            return "", tok  # bare path, no language
        return "", info  # path containing spaces, no language

    @staticmethod
    def _sanitise_path(path: str) -> str:
        cleaned = path.replace("\\", "/").strip().strip("\"'").lstrip("./")
        parts = [p for p in cleaned.split("/") if p not in ("", ".", "..")]
        return "/".join(parts)

    @staticmethod
    def _ext_for(lang: str) -> str:
        return {
            "python": "py", "py": "py", "python3": "py",
            "javascript": "js", "js": "js", "typescript": "ts", "ts": "ts", "tsx": "tsx",
            "html": "html", "css": "css", "json": "json", "yaml": "yaml", "yml": "yml",
            "markdown": "md", "md": "md",
        }.get(lang.lower(), "py" if not lang else "txt")

    @classmethod
    def _store_files(cls, state: AgentState, text: str) -> None:
        """Store every fenced block as an artifact (all edge cases).

        Handles: `````python:path`` / `````python path`` / bare `````path`` /
        language-only fences (auto-named ``generated_N.<ext>``), ``c++``/``c#``
        info strings, CRLF, quoted/spaced paths, ``..`` traversal (collapsed),
        and duplicate paths (last block wins). Defensive filters:

        * shell-session fences without a file path (`````sh`` /
          `````shell:dirname``) are terminal narration, skipped entirely;
        * a ``python``-labelled block that fails ``ast.parse`` AND reads as
          English instructions is stored as ``.txt`` (never executed),
          while genuine code with a typo stays ``.py`` so the compile check
          flags it and the retry loop fixes it.

        Falls back to ``solution.py`` only when no fence exists at all.
        """
        normalised = text.replace("\r\n", "\n").replace("\r", "\n")
        pattern = re.compile(r"```([^`\n]*)\n(.*?)```", re.DOTALL)
        matches = list(pattern.finditer(normalised))
        n = 0
        for m in matches:
            lang, path = cls._split_info(m.group(1) or "")
            code = m.group(2).strip()
            if not code:
                continue
            lowered_lang = lang.lower()
            if path:
                path = cls._sanitise_path(path)
            if not path:
                if lowered_lang in cls._SHELL_LANGS:
                    continue  # terminal narration, not a file
                path = f"generated_{n}.{cls._ext_for(lang)}"
            elif lowered_lang in cls._SHELL_LANGS and "." not in path.rsplit("/", 1)[-1]:
                # Extensionless shell target: a real file (Dockerfile, Makefile)
                # is kept, but a bare directory ("frontend") is cd narration.
                if re.match(r"^\s*(cd|mkdir|npx|npm|pip|uv|ls|echo|export|chmod|curl|git)\b", code):
                    continue
            if path.endswith(".py"):
                try:
                    ast.parse(code)
                except SyntaxError:
                    if cls._looks_like_prose(code):
                        path = path[: -len(".py")] + ".txt"
            if path.startswith("generated_") and code.strip() in state.artifacts:
                # File-list narration ("dashboard/Dashboard.js" as a bare fence)
                # duplicating an existing artifact — not a new file.
                continue
            state.artifacts[path] = code
            n += 1
        if not matches and normalised.strip():
            # No fences at all: strip prose, keep code-looking lines so we
            # never persist pure English as solution.py. (When fences exist
            # but every block was skipped/empty, store nothing — never dump
            # raw fences as code.)
            lines = normalised.strip().splitlines()
            code_lines = [ln for ln in lines if ln.strip() and not re.match(r"^\s*(Here|This|The|Sure|Below|Note:)", ln)]
            state.artifacts["solution.py"] = "\n".join(code_lines).strip() or normalised.strip()
