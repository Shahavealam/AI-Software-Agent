"""LLM gateway: single async entry-point with token counting + offline fallback.

All agents call :meth:`LLMGateway.chat` / :meth:`LLMGateway.stream` so model,
retry, and telemetry policy live in exactly one place.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any

from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential

from app.core.config import get_settings, logger

try:  # optional heavy deps
    import tiktoken as _tiktoken
except Exception:  # pragma: no cover
    _tiktoken = None  # type: ignore[assignment]


def _message_classes() -> tuple[type, type]:
    """HumanMessage/SystemMessage — langchain_core>=0.3, fallback to legacy."""
    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        return HumanMessage, SystemMessage
    except ImportError:  # pragma: no cover - legacy langchain<0.2
        from langchain.schema import HumanMessage, SystemMessage  # type: ignore[no-redef]

        return HumanMessage, SystemMessage


class LLMGateway:
    """Thin async wrapper over ChatOpenAI with graceful offline mode."""

    def __init__(self, model: str | None = None) -> None:
        self.settings = get_settings()
        self.model = model or self.settings.openai_model
        self._llm: Any | None = None
        self._init_llm()

    # -- setup ------------------------------------------------------
    def _init_llm(self) -> None:
        if not self.settings.openai_api_key:
            logger.warning("OPENAI_API_KEY missing — LLMGateway in offline mode")
            return
        try:
            from langchain_openai import ChatOpenAI

            self._llm = ChatOpenAI(model=self.model, api_key=self.settings.openai_api_key)
            logger.info("LLMGateway connected model=%s", self.model)
        except Exception as exc:  # pragma: no cover
            logger.warning("LLMGateway init failed (%s) — offline mode", exc)
            self._llm = None

    @property
    def online(self) -> bool:
        return self._llm is not None

    # -- tokens ------------------------------------------------------
    def count_tokens(self, text: str) -> int:
        if _tiktoken is not None:
            try:
                enc = _tiktoken.encoding_for_model(self.model)
            except Exception:
                enc = _tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        return max(1, len(text) // 4)  # rough fallback

    # -- chat ---------------------------------------------------------
    async def chat(self, system: str, user: str) -> str:
        """Single non-streaming completion (retried, thread-safe)."""
        if self._llm is None:
            return self._offline_reply(system, user)
        HumanMessage, SystemMessage = _message_classes()

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8), reraise=True
        ):
            with attempt:
                resp = await asyncio.to_thread(
                    self._llm.invoke, [SystemMessage(content=system), HumanMessage(content=user)]
                )
                content = getattr(resp, "content", "")
                return content if isinstance(content, str) else str(content)
        raise RuntimeError("unreachable")  # pragma: no cover

    async def stream(self, system: str, user: str) -> AsyncGenerator[str, None]:
        """Stream raw markdown/token chunks; offline mode yields one chunk."""
        if self._llm is None:
            yield self._offline_reply(system, user)
            return
        try:
            HumanMessage, SystemMessage = _message_classes()

            chunks = self._llm.stream(
                [SystemMessage(content=system), HumanMessage(content=user)]
            )
            for chunk in chunks:  # sync iterator -> pump in thread
                content = getattr(chunk, "content", "")
                if content:
                    yield str(content)
                await asyncio.sleep(0)
        except Exception as exc:
            logger.warning("stream fallback: %s", exc)
            yield await self.chat(system, user)

    @staticmethod
    def _offline_reply(system: str, user: str) -> str:
        preview = (user[:400] + "…") if len(user) > 400 else user
        return (
            "[offline-mode] No OPENAI_API_KEY configured.\n"
            f"system: {system[:200]}\nrequest: {preview}\n"
            "Set OPENAI_API_KEY to enable live generation."
        )
