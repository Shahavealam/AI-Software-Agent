"""Execution & Runtime: sandboxed subprocess runner capturing stdout/stderr.

Strategy (why not "run every .py file"?)
----------------------------------------
Naively executing each ``*.py`` artifact with ``python file.py`` fails
*correct* projects:

* multi-file imports (``from calculator import add``) break when each file
  is copied to its own isolated temp dir;
* CLI entry points (``argparse`` / ``sys.argv``) exit with code 2 when run
  with no arguments;
* interactive scripts (``input()``) crash with ``EOFError``;
* pytest suites executed as plain scripts do nothing (exit 0 without
  running a single test) or fail on missing fixtures.

Instead :class:`ExecutionAgent` materialises **all** artifacts (code plus
assets such as ``.css``/``.json``) into **one** shared sandbox directory
(preserving relative paths such as ``tests/`` or ``models/``) and then:

1. if Python test files exist **and** Python modules exist,
   runs ``python -m pytest -q`` inside the sandbox and reports pass/fail
   (a stray Python suite in a pure-JS project is skipped, not failed);
2. ``py_compile``-checks every Python module (catches ``SyntaxError`` with
   the exact file/line), synthesising missing ``__init__.py`` so dotted
   package imports resolve;
3. import smoke-checks each non-test Python module with the sandbox root
   on ``sys.path`` (catches ``ModuleNotFoundError`` / ``ImportError``
   across files without executing ``argparse``/``input()`` at top level —
   well-structured CLIs guard those behind ``if __name__ == "__main__"``);
4. ``node --check``-validates plain JavaScript files when ``node`` exists
   (JSX/TSX and missing-node degrade to presence checks, never failures).

A final aggregate ``{"summary": True, "ok": bool, ...}`` report is appended
so :meth:`QAAgent.evaluate` can judge the whole iteration instead of an
arbitrary last file. Per-file reports keep ``target`` set for debugging.
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

from app.agents.base import BaseAgent, EmitFn
from app.core.config import get_settings, logger
from app.core.state import AgentName, AgentState


async def run_python_snippet(code: str, timeout: float = 30.0) -> dict[str, Any]:
    """Execute a python snippet in a temp dir sandbox; return structured report."""
    with tempfile.TemporaryDirectory(prefix="agent_sbx_") as tmp:
        target = Path(tmp) / "snippet.py"
        target.write_text(code, encoding="utf-8")
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, str(target),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return {"ok": False, "returncode": -1, "stdout": "", "stderr": "TimeoutExpired", "timeout": True}
            rc = proc.returncode or 0
            return {
                "ok": rc == 0,
                "returncode": rc,
                "stdout": stdout.decode(errors="replace")[-8000:],
                "stderr": stderr.decode(errors="replace")[-8000:],
                "timeout": False,
            }
        except Exception as exc:
            logger.warning("sandbox error: %s", exc)
            return {"ok": False, "returncode": -1, "stdout": "", "stderr": str(exc)[:4000], "timeout": False}


# ── helpers ------------------------------------------------------------
def is_test_path(path: str) -> bool:
    """True for pytest-style files: ``test_*.py``, ``*_test.py``, under ``tests/``."""
    posix = path.replace("\\", "/").lower()
    base = posix.rsplit("/", 1)[-1]
    return (
        base.startswith("test_") and base.endswith(".py")
    ) or (
        base.endswith("_test.py")
    ) or (
        posix.startswith("tests/") and base.endswith(".py")
    )


def sanitise_relpath(path: str) -> str | None:
    """Clean an artifact path for sandbox materialisation; None => skip."""
    cleaned = path.replace("\\", "/").strip().lstrip("./")
    parts = [p for p in PurePosixPath(cleaned).parts if p not in ("", ".", "..")]
    if not parts:
        return None
    safe = "/".join(parts)
    if safe.startswith("/") or ".." in parts:
        return None
    return safe


async def _run_subprocess(
    *argv: str, cwd: str, timeout: float,
) -> tuple[int, str, str, bool]:
    """Run argv, capture output; returns (rc, stdout, stderr, timed_out)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv, cwd=cwd,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            await proc.wait()
            return -1, "", "TimeoutExpired", True
        return proc.returncode or 0, out.decode(errors="replace"), err.decode(errors="replace"), False
    except Exception as exc:
        return -1, "", str(exc)[:2000], False


def _module_name(relpath: str) -> str:
    stem = relpath.replace("\\", "/")
    if stem.endswith(".py"):
        stem = stem[: -len(".py")]
    return stem.replace("/", ".").replace("-", "_")


def _missing_third_party(stderr: str, materialised: list[str]) -> str:
    """Extract a missing third-party package name from an import traceback.

    Returns ``""`` when the failure is NOT a missing external dependency —
    i.e. stdlib modules (always present), project-local modules, or
    directory prefixes of staged files (e.g. ``dashboard`` when only
    ``dashboard/*.js`` exists). Anything else (``flask``, ``requests``…)
    cannot be pip-installed into the sandbox, so the verdict carries an
    explicit rewrite-using-stdlib signal instead of a bare traceback.
    """
    import re

    m = re.search(r"No module named '([\w.]+)'", stderr)
    if not m:
        return ""
    top = m.group(1).split(".")[0]
    if top in getattr(sys, "stdlib_module_names", set()):
        return ""
    for p in materialised:
        first = p.replace("\\", "/").split("/")[0]
        stem = first[:-len(".py")] if first.endswith(".py") else first
        if top == first or top == stem.replace("-", "_"):
            return ""  # project-local (or its asset dir) — genuine import bug
    return top


_JS_EXTS = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")

_JSX_HINT = (
    "react", "jsx", "React.createElement", "ReactDOM", "useState", "useEffect",
    "from 'react'", 'from "react"', "require('react')", 'require("react")',
)


def _looks_like_jsx(source: str) -> bool:
    """Heuristic: JSX/TSX cannot be validated with ``node --check``."""
    import re

    if re.search(r"<[A-Z][A-Za-z0-9]*(?:\s|>|/>)", source):
        return True
    return any(hint in source for hint in _JSX_HINT)


def _node_available() -> bool:
    import shutil

    return shutil.which("node") is not None


class ExecutionAgent(BaseAgent):
    name = AgentName.EXECUTION
    system_prompt = "You are a sandbox runtime. You never write code; you only execute and report."

    async def run(self, state: AgentState, emit: EmitFn = None) -> AgentState:  # type: ignore[override]
        from app.agents.base import _noop_emit

        emit = emit or _noop_emit
        settings = get_settings()
        await self.tell(emit, "running", "Executing in sandbox", state.session_id)

        py_files = {
            k: v for k, v in state.artifacts.items()
            if k.endswith(".py") and not k.startswith(("architect/", "docs/"))
        }
        js_files = {
            k: v for k, v in state.artifacts.items()
            if k.lower().endswith(_JS_EXTS) and not k.startswith(("architect/", "docs/"))
        }
        if not py_files and not js_files:
            report = {"ok": False, "returncode": -1, "stdout": "", "stderr": "No python or javascript artifacts to execute", "target": None}
            state.exec_reports.append(report)
            await self.tell(emit, "crashed", "Nothing to execute", state.session_id, report)
            return state

        timeout = settings.sandbox_timeout_s
        max_bytes = settings.sandbox_max_bytes

        with tempfile.TemporaryDirectory(prefix="agent_sbx_") as tmp:
            # Materialise EVERY artifact (code + assets like .css/.json/.md),
            # preserving package layout so cross-file imports AND file-existence
            # asserts (os.path.isfile) resolve. Only .py/.js are validated;
            # the rest are staged context. Capped to bound sandbox time.
            stageable = {
                k: v for k, v in state.artifacts.items()
                if not k.startswith(("architect/", "docs/"))
            }
            materialised: list[str] = []
            staged: dict[str, str] = {}
            for raw_path, content in list(stageable.items())[:60]:
                rel = sanitise_relpath(raw_path)
                if not rel:
                    continue
                dest = Path(tmp) / rel
                try:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_text(content[:max_bytes], encoding="utf-8")
                    materialised.append(rel)
                    staged[rel] = content
                except Exception as exc:
                    logger.warning("sandbox materialise skip %s: %s", raw_path, exc)
            if not materialised:
                report = {"ok": False, "returncode": -1, "stdout": "", "stderr": "No materialisable python artifacts", "target": None}
                state.exec_reports.append(report)
                await self.tell(emit, "crashed", "Nothing materialised", state.session_id, report)
                return state

            # Synthesise empty __init__.py so dotted imports across package
            # dirs (e.g. `from dashboard.components.x import Y`) resolve even
            # when the LLM omits the boilerplate files.
            pkg_dirs = {str(Path(p).parent) for p in materialised if p.endswith(".py")}
            for d in sorted(pkg_dirs):
                if d in (".", ""):
                    continue
                init = Path(tmp) / d / "__init__.py"
                try:
                    if not init.exists():
                        init.write_text("", encoding="utf-8")
                except Exception as exc:
                    logger.warning("sandbox __init__ skip %s: %s", d, exc)

            test_files = [p for p in materialised if is_test_path(p)]
            py_test_files = [p for p in test_files if p.endswith(".py")]
            py_modules = [p for p in materialised if p.endswith(".py") and not is_test_path(p)]
            js_targets = [p for p in materialised if p.lower().endswith(_JS_EXTS)]
            failures: list[str] = []

            # 1. pytest — only when Python tests CAN be meaningful, i.e. real
            # Python modules exist. A stray test_generated.py importing JS
            # modules (language mismatch from an older QA) is skipped instead
            # of failing the whole iteration with a collection error.
            if py_test_files and not py_modules:
                report = {
                    "ok": True, "returncode": 0,
                    "stdout": "pytest skipped: no python modules in a javascript project",
                    "stderr": "", "target": "pytest (skipped)", "timeout": False, "skipped": True,
                }
                state.exec_reports.append(report)
                await self.tell(emit, "passed", "pytest skipped (no python modules)", state.session_id, {"target": "pytest"})
            elif py_test_files:
                rc, out, err, timed_out = await _run_subprocess(
                    sys.executable, "-m", "pytest", "-q", *sorted(py_test_files),
                    cwd=tmp, timeout=max(timeout, 60.0),
                )
                if "No module named pytest" in err:
                    # Fallback: run each test file directly; imports still
                    # resolve because the sandbox root is shared.
                    fallback_ok = True
                    fb_out, fb_err = [], []
                    for tf in sorted(py_test_files):
                        rc1, out1, err1, to1 = await _run_subprocess(
                            sys.executable, tf, cwd=tmp, timeout=timeout,
                        )
                        fb_out.append(f"## {tf} rc={rc1}\n{out1[-2000:]}")
                        fb_err.append(f"## {tf}\n{err1[-2000:]}")
                        fallback_ok = fallback_ok and rc1 == 0 and not to1
                    report = {
                        "ok": fallback_ok, "returncode": 0 if fallback_ok else 1,
                        "stdout": "\n".join(fb_out)[-8000:], "stderr": "\n".join(fb_err)[-8000:],
                        "target": "pytest (direct fallback)", "timeout": False,
                    }
                else:
                    report = {
                        "ok": rc == 0 and not timed_out, "returncode": rc,
                        "stdout": out[-8000:], "stderr": err[-8000:],
                        "target": "pytest", "timeout": timed_out,
                    }
                state.exec_reports.append(report)
                await self.tell(
                    emit, "passed" if report["ok"] else "crashed",
                    f"pytest: rc={rc} " + ((err[-300:] or out[-300:] or "OK").replace("\n", " ")),
                    state.session_id, {"target": "pytest"},
                )
                if not report["ok"]:
                    failures.append(f"pytest rc={rc}: {(err or out)[-500:]}")

            # 2. compile + import check for every non-test PYTHON module --
            # (JS targets are validated in stage 3, never py_compiled.)
            for rel in sorted(py_modules)[:20]:
                # 2a. syntax check (exact file/line on SyntaxError)
                rc, out, err, timed_out = await _run_subprocess(
                    sys.executable, "-m", "py_compile", rel, cwd=tmp, timeout=timeout,
                )
                if rc != 0 or timed_out:
                    report = {
                        "ok": False, "returncode": rc, "stdout": out[-4000:],
                        "stderr": (err or "TimeoutExpired")[-4000:],
                        "target": rel, "timeout": timed_out, "phase": "compile",
                    }
                    state.exec_reports.append(report)
                    await self.tell(emit, "crashed", f"{rel}: compile failed", state.session_id, {"target": rel})
                    failures.append(f"{rel} compile: {err[-300:]}")
                    continue
                # 2b. import smoke check (no argv/input execution; top-level
                # guarded CLIs import cleanly, broken imports surface here)
                mod = _module_name(rel)
                check = (
                    "import sys; sys.path.insert(0, '.'); "
                    f"__import__({mod!r}); print('import-ok')"
                )
                rc, out, err, timed_out = await _run_subprocess(
                    sys.executable, "-c", check, cwd=tmp, timeout=timeout,
                )
                ok = rc == 0 and "import-ok" in out and not timed_out
                phase = "import"
                missing = "" if ok else _missing_third_party(err, materialised)
                if missing:
                    phase = "missing-dependency"
                    err = (
                        f"{err[-2000:]}\nHINT: third-party package '{missing}' is not "
                        "installed in the sandbox and cannot be pip-installed — rewrite "
                        "using only the Python standard library."
                    )
                report = {
                    "ok": ok, "returncode": rc, "stdout": out[-4000:],
                    "stderr": err[-4000:], "target": rel, "timeout": timed_out, "phase": phase,
                }
                state.exec_reports.append(report)
                await self.tell(
                    emit, "passed" if ok else "crashed",
                    f"{rel}: {'import-ok' if ok else 'rc=' + str(rc) + ' ' + err[-300:].replace(chr(10), ' ')}",
                    state.session_id, {"target": rel},
                )
                if not ok:
                    failures.append(f"{rel} {phase} rc={rc}: {err[-300:]}")
                await self.memory.remember_turn("Execution", f"{rel} rc={rc}")

            # 2b. javascript validation via node --check (best-effort) -----
            # JSX/TSX cannot be parsed by node; those are presence-checked
            # only. Missing `node` degrades to presence-checks as well —
            # never a failure: we cannot prove JS wrong from here.
            node_ok = _node_available()
            for rel in sorted(js_targets)[:20]:
                src = staged.get(rel, "")
                if _looks_like_jsx(src):
                    report = {
                        "ok": True, "returncode": 0, "stdout": "jsx/tsx: syntax check skipped (needs bundler)",
                        "stderr": "", "target": rel, "timeout": False, "phase": "jsx-skip",
                    }
                elif not node_ok:
                    report = {
                        "ok": True, "returncode": 0, "stdout": "node unavailable: presence check only",
                        "stderr": "", "target": rel, "timeout": False, "phase": "js-presence",
                    }
                else:
                    rc, out, err, timed_out = await _run_subprocess(
                        "node", "--check", rel, cwd=tmp, timeout=timeout,
                    )
                    ok = rc == 0 and not timed_out
                    report = {
                        "ok": ok, "returncode": rc, "stdout": out[-4000:],
                        "stderr": (err or "TimeoutExpired")[-4000:] if not ok else "",
                        "target": rel, "timeout": timed_out, "phase": "node-check",
                    }
                    if not ok:
                        failures.append(f"{rel} node --check rc={rc}: {err[-300:]}")
                state.exec_reports.append(report)
                await self.tell(
                    emit, "passed" if report["ok"] else "crashed",
                    f"{rel}: {report.get('phase')} {'ok' if report['ok'] else 'FAILED'}",
                    state.session_id, {"target": rel},
                )

            # 3. aggregate summary — the single verdict QA evaluates -----
            passed = not failures
            summary = {
                "ok": passed, "returncode": 0 if passed else 1,
                "stdout": f"checked {len(materialised)} file(s); pytest={'yes' if py_test_files else 'no'}; js={'yes' if js_targets else 'no'}",
                "stderr": "" if passed else "; ".join(failures)[:4000],
                "target": None, "summary": True,
                "targets": sorted(materialised),
            }
            state.exec_reports.append(summary)
            await self.tell(
                emit, "passed" if passed else "crashed",
                f"Summary: {'all green' if passed else summary['stderr'][:300]}",
                state.session_id, {"failures": len(failures)},
            )
        return state
