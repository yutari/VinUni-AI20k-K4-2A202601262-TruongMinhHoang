"""Tracing hooks and observability configuration.

Supports LangSmith, Langfuse, and local structured span tracking.
"""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter
from typing import Any

from multi_agent_research_lab.core.config import Settings, get_settings


def configure_tracing(settings: Settings | None = None) -> None:
    """Configure environment variables for external tracing providers."""
    cfg = settings or get_settings()

    # Configure LangSmith if API key is provided
    if cfg.langsmith_api_key:
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_API_KEY"] = cfg.langsmith_api_key
        os.environ["LANGSMITH_PROJECT"] = cfg.langsmith_project
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_PROJECT"] = cfg.langsmith_project
        os.environ["LANGCHAIN_API_KEY"] = cfg.langsmith_api_key

    # Configure Langfuse if keys are provided
    if cfg.langfuse_public_key and cfg.langfuse_secret_key:
        os.environ["LANGFUSE_PUBLIC_KEY"] = cfg.langfuse_public_key
        os.environ["LANGFUSE_SECRET_KEY"] = cfg.langfuse_secret_key
        os.environ["LANGFUSE_HOST"] = cfg.langfuse_host


@contextmanager
def trace_span(name: str, attributes: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
    """Context manager for measuring execution spans with metadata."""
    started = perf_counter()
    span: dict[str, Any] = {
        "name": name,
        "attributes": attributes or {},
        "duration_seconds": None,
    }
    try:
        yield span
    finally:
        span["duration_seconds"] = perf_counter() - started
