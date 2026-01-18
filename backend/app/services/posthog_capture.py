"""
Minimal PostHog capture helper (backend).

Goals:
- Non-blocking: never slow down the user request path.
- Safe: failures are swallowed (metrics should not break product flows).
- Low-cardinality: callers should send only bounded properties.

Uses PostHog HTTP capture endpoint (works with project API key).
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        # Keep timeouts small; this must never block user flows.
        _client = httpx.AsyncClient(timeout=httpx.Timeout(2.0))
    return _client


async def close() -> None:
    """
    Close the shared httpx client.

    Call this during application shutdown (e.g., in FastAPI lifespan) to
    release connections cleanly.
    """
    global _client
    if _client is not None:
        try:
            await _client.aclose()
        except Exception as e:
            logger.debug("PostHog client close failed: %s", e)
        finally:
            _client = None


def _get_env() -> str:
    env = os.getenv("APP_ENV") or os.getenv("VITE_APP_ENV")
    if env:
        return env
    debug = os.getenv("DEBUG", "true").lower() in ("1", "true", "yes", "y")
    return "dev" if debug else "prod"


def _get_host() -> str:
    host = os.getenv("POSTHOG_HOST") or os.getenv("VITE_POSTHOG_HOST") or "https://us.i.posthog.com"
    return host.rstrip("/")


def _get_api_key() -> Optional[str]:
    # Accept either naming convention:
    # - POSTHOG_API_KEY (preferred)
    # - POSTHOG_PROJECT_API_KEY (common in PostHog UI / docs)
    # Also allow Vite vars for dev convenience.
    return (
        os.getenv("POSTHOG_API_KEY")
        or os.getenv("POSTHOG_PROJECT_API_KEY")
        or os.getenv("VITE_POSTHOG_KEY")
    )


async def capture(
    event: str,
    *,
    distinct_id: str = "backend",
    properties: Optional[Dict[str, Any]] = None,
) -> None:
    api_key = _get_api_key()
    if not api_key:
        return

    props = dict(properties or {})
    # Ensure environment is always available for filtering.
    props.setdefault("environment", _get_env())
    # Provide a server timestamp hint; PostHog will still use ingestion time.
    props.setdefault("server_time_ms", int(time.time() * 1000))

    payload = {
        "api_key": api_key,
        "event": event,
        "distinct_id": distinct_id,
        "properties": props,
    }

    try:
        client = _get_client()
        await client.post(f"{_get_host()}/capture/", json=payload)
    except Exception as e:
        # Never break product flows for telemetry.
        logger.debug("PostHog capture failed: %s", e)


def capture_background(
    event: str,
    *,
    distinct_id: str = "backend",
    properties: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Fire-and-forget capture.

    Safe to call from both sync and async contexts. If no loop is running, it's a no-op.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No event loop; don't block.
        return

    loop.create_task(capture(event, distinct_id=distinct_id, properties=properties))



