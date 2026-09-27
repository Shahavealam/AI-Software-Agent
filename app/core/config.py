"""Centralised, typed configuration + structured logging.

All knobs are env-overridable via ``pydantic-settings`` so the system runs
in offline/CI mode without secrets and lights up fully with an API key.
"""

from __future__ import annotations

import logging
import sys
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven settings (prefix-free, explicit field names)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str = Field(default="", description="OpenAI API key; empty => offline mode")
    openai_model: str = Field(default="gpt-4o-mini")
    openai_embed_model: str = Field(default="text-embedding-3-small")
    max_context_tokens: int = Field(default=128_000, gt=1024)
    summary_trigger_ratio: float = Field(default=0.75, gt=0.0, lt=1.0)
    max_self_correction_retries: int = Field(default=3, ge=0, le=10)
    sandbox_timeout_s: float = Field(default=30.0, gt=0)
    sandbox_max_bytes: int = Field(default=64_000, gt=1024)
    vector_backend: Literal["chroma", "memory"] = Field(default="chroma")
    chroma_persist_dir: str = Field(default=".agent_chroma")
    entity_store_path: str = Field(default=".agent_state/entities.json")
    # ── Conversation history ──────────────────────────────────────
    # Empty MONGODB_URI => file-backed fallback at HISTORY_STORE_PATH
    # (works offline / in CI). Set MONGODB_URI to persist in MongoDB.
    mongodb_uri: str = Field(default="", description="MongoDB connection string; empty => file/memory fallback")
    mongodb_db: str = Field(default="ai_agent")
    mongodb_sessions_collection: str = Field(default="sessions")
    mongodb_messages_collection: str = Field(default="messages")
    history_store_path: str = Field(default=".agent_state/history.json")
    history_max_messages: int = Field(default=200, gt=1)
    # ── History content volume (MongoDB documents cap at 16MB — these keep
    # persisted turns full but bounded; LLM context stays capped separately
    # via MAX_CONTEXT_TOKENS / get_context max_chars) ──────────────────
    history_message_max_chars: int = Field(default=65536, gt=1024, description="Hard cap per persisted message content")
    history_summary_max_chars: int = Field(default=20000, gt=1024, description="Cap for the orchestrator result summary")
    history_stream_preview_max_chars: int = Field(default=12000, gt=1024, description="Streamed-output preview inside the summary")
    history_report_field_max_chars: int = Field(default=4000, gt=256, description="Per-field cap for persisted exec/test reports")
    history_save_agent_turns: bool = Field(default=True, description="Persist each agent's full output as its own message")
    history_agent_turn_max_chars: int = Field(default=12000, gt=1024, description="Cap per persisted agent-turn message")
    history_artifact_file_max_chars: int = Field(default=20000, gt=1024, description="Per-file cap for artifact contents snapshot")
    history_artifacts_total_max_chars: int = Field(default=200000, gt=1024, description="Total cap for artifact contents snapshot")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    project_root: str = Field(default=".")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def project_root() -> Path:
    return Path(get_settings().project_root).resolve()


def configure_logging(level: str | None = None) -> logging.Logger:
    """Configure stdlib logging once; return root agent logger."""
    lvl = (level or get_settings().log_level).upper()
    logger = logging.getLogger("agent")
    if logger.handlers:
        logger.setLevel(lvl)
        return logger
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(lvl)
    logger.propagate = False
    # Quiet noisy deps
    for noisy in ("httpx", "chromadb", "openai", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    return logger


logger = configure_logging()
