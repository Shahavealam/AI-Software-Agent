"""Shared fixtures: isolate filesystem side-effects per test."""

from __future__ import annotations

import pytest


@pytest.fixture()
def tmp_cwd(tmp_path, monkeypatch):
    """Run the test with CWD in a temp dir (entity store, chroma dir)."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture(autouse=True)
def force_offline(monkeypatch):
    """Force offline LLM mode so tests are deterministic and cost-free.

    Live connectivity is verified separately (manual smoke test), never
    implicitly by the suite — even when a real OPENAI_API_KEY is present.
    """
    from app.core import config

    monkeypatch.setenv("OPENAI_API_KEY", "")
    config.get_settings.cache_clear()
    yield
    config.get_settings.cache_clear()
