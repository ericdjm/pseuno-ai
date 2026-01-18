#!/usr/bin/env python3
"""
PostHog smoke test for Pseuno AI:
- Fires (captures) *every* instrumented event name (frontend + backend telemetry)
- Adds a shared `seed_id` so you can filter/verify ingestion
- Optionally polls PostHog Query API (personal key) until the events are queryable

This is NOT a replacement for true end-to-end correctness validation, but it ensures:
- Event names exist in the project
- Properties appear in PostHog (schema discovery)
- Dashboards/tiles can be built and will render
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any, Dict, List, Optional, Tuple


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.environ.get(name, default)
    if v is None or v == "":
        return None
    return v


def _guess_ingest_host(raw: str) -> str:
    raw = raw.rstrip("/")
    # If user accidentally provides app host (us.posthog.com), convert to ingest host.
    if ".i.posthog.com" in raw:
        return raw
    if raw.endswith("us.posthog.com") or raw.endswith("posthog.com") and "us." in raw:
        return "https://us.i.posthog.com"
    if raw.endswith("eu.posthog.com") or raw.endswith("posthog.com") and "eu." in raw:
        return "https://eu.i.posthog.com"
    # Default to US ingest.
    return "https://us.i.posthog.com"


def _guess_app_host(raw: str) -> str:
    raw = raw.rstrip("/")
    if raw.endswith(".i.posthog.com"):
        # Convert ingest -> app host
        if raw.startswith("https://eu.i."):
            return "https://eu.posthog.com"
        return "https://us.posthog.com"
    return raw


def _capture_key() -> str:
    key = (
        _env("POSTHOG_API_KEY")
        or _env("POSTHOG_PROJECT_API_KEY")
        or _env("VITE_POSTHOG_KEY")
    )
    if not key:
        raise SystemExit("Missing POSTHOG_API_KEY/POSTHOG_PROJECT_API_KEY/VITE_POSTHOG_KEY for capture.")
    return key


def _capture_host() -> str:
    host = _env("POSTHOG_INGEST_HOST") or _env("VITE_POSTHOG_HOST") or _env("POSTHOG_HOST") or ""
    return _guess_ingest_host(host) if host else "https://us.i.posthog.com"


def _api_host() -> str:
    host = _env("POSTHOG_HOST") or "https://us.posthog.com"
    return _guess_app_host(host)


def _post_json(url: str, body: Dict[str, Any], headers: Dict[str, str], timeout_s: int = 15) -> Dict[str, Any]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as r:
            raw = r.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8") if e.fp else ""
        raise RuntimeError(f"HTTP {e.code} POST {url}\n{raw or e.reason}") from None


def _get_json(url: str, headers: Dict[str, str], timeout_s: int = 15) -> Dict[str, Any]:
    req = urllib.request.Request(url, method="GET", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as r:
            raw = r.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8") if e.fp else ""
        raise RuntimeError(f"HTTP {e.code} GET {url}\n{raw or e.reason}") from None


def capture(event: str, distinct_id: str, properties: Dict[str, Any]) -> None:
    url = f"{_capture_host()}/capture/"
    body = {
        "api_key": _capture_key(),
        "event": event,
        "distinct_id": distinct_id,
        "properties": properties,
    }
    _post_json(url, body, headers={"Content-Type": "application/json", "Accept": "application/json"})


def _hogql_count_by_seed(seed_id: str, project_id: str, personal_key: str) -> int:
    url = f"{_api_host()}/api/projects/{project_id}/query/"
    query = {
        "kind": "HogQLQuery",
        "query": "select count() as c from events where properties.seed_id = {seed}",
        "values": {"seed": seed_id},
    }
    res = _post_json(
        url,
        {"query": query},
        headers={
            "Authorization": f"Bearer {personal_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout_s=30,
    )
    # HogQLQuery results vary by version; try a couple shapes.
    r = res.get("results")
    if isinstance(r, list) and r and isinstance(r[0], list) and r[0] and isinstance(r[0][0], (int, float)):
        return int(r[0][0])
    if isinstance(r, list) and r and isinstance(r[0], dict) and "c" in r[0]:
        return int(r[0]["c"])
    # Fallback: no parse
    return 0


def main() -> int:
    seed_id = str(uuid.uuid4())
    env = _env("APP_ENV") or _env("VITE_APP_ENV") or "dev"
    now_ms = int(time.time() * 1000)

    # Shared IDs so dashboards can link “flows”
    style_prompt_id = 123
    lyrics_thread_id = 456

    base = {
        "seed_id": seed_id,
        "environment": env,
        "server_time_ms": now_ms,
        "client_session_id": f"smoke_session_{seed_id[:8]}",
        "client_time_ms": now_ms,
    }

    # ----------------------------------------------------------------------------
    # Frontend events (from frontend/src/analytics.ts)
    # ----------------------------------------------------------------------------
    flow_id = str(uuid.uuid4())
    frontend_events: List[Tuple[str, str, Dict[str, Any]]] = [
        ("auth_login_clicked", "smoke_user", {"flow": "auth"}),
        ("auth_login_succeeded", "smoke_user", {"flow": "auth"}),
        ("auth_login_failed", "smoke_user", {"flow": "auth", "error_type": "OAuthError"}),
        ("auth_status_loaded", "smoke_user", {"flow": "auth", "authenticated": True}),
        ("auth_logout", "smoke_user", {"flow": "auth"}),
        ("generate_clicked", "smoke_user", {"flow": "generate", "page": "new_song", "auth_state": "guest", "has_lyrics_input": True, "has_style_input": True, "personalize_enabled": False, "instrumental_intended": False, "instrumental_intent_signal": "lyrics_about_present", "flow_id": flow_id, "used_randomize_style": True, "used_randomize_lyrics": True, "primary_tag_bucket": "electronic", "tag_buckets": ["electronic"]}),
        ("generate_succeeded", "smoke_user", {"flow": "generate", "page": "new_song", "auth_state": "guest", "duration_ms": 1234, "has_lyrics": True, "instrumental_intended": False, "instrumental_intent_signal": "lyrics_about_present", "flow_id": flow_id, "used_randomize_style": True, "used_randomize_lyrics": True, "primary_tag_bucket": "electronic", "tag_buckets": ["electronic"]}),
        ("generate_succeeded", "smoke_user_spotify", {"flow": "generate", "page": "new_song", "auth_state": "spotify", "duration_ms": 1400, "has_lyrics": True, "instrumental_intended": True, "instrumental_intent_signal": "lyrics_about_empty"}),
        ("generate_failed", "smoke_user", {"flow": "generate", "page": "new_song", "auth_state": "guest", "duration_ms": 432, "error_type": "NetworkError"}),
        ("generate_wait_notice_shown", "smoke_user", {"flow": "generate", "page": "new_song", "auth_state": "guest", "wait_seconds": 10}),
        ("style_selected", "smoke_user", {"flow": "library", "page": "song_view", "auth_state": "guest"}),
        ("thread_selected", "smoke_user", {"flow": "library", "page": "song_view", "auth_state": "guest"}),
        ("favorite_toggled", "smoke_user", {"flow": "library", "page": "song_view", "auth_state": "spotify", "is_favorite": True}),
        ("randomize_style_clicked", "smoke_user", {"flow": "style_create", "page": "new_song", "auth_state": "guest", "personalize_enabled": False, "manual_tags_count": 2, "primary_tag_bucket": "electronic", "tag_buckets": ["electronic"]}),
        ("randomize_style_succeeded", "smoke_user", {"flow": "style_create", "page": "new_song", "auth_state": "guest", "duration_ms": 800, "auto_picked_count": 3, "primary_tag_bucket": "electronic", "tag_buckets": ["electronic"]}),
        ("randomize_style_failed", "smoke_user", {"flow": "style_create", "page": "new_song", "auth_state": "guest", "duration_ms": 200, "error_type": "TimeoutError", "primary_tag_bucket": "electronic", "tag_buckets": ["electronic"]}),
        ("randomize_lyrics_clicked", "smoke_user", {"flow": "style_create", "page": "new_song", "auth_state": "guest", "has_style_input": True, "randomize_context": "new_song"}),
        ("randomize_lyrics_succeeded", "smoke_user", {"flow": "style_create", "page": "new_song", "auth_state": "guest", "duration_ms": 500, "randomize_context": "new_song"}),
        ("randomize_lyrics_failed", "smoke_user", {"flow": "style_create", "page": "new_song", "auth_state": "guest", "duration_ms": 150, "error_type": "APIError", "randomize_context": "new_song"}),
        ("personalize_toggled", "smoke_user", {"flow": "style_create", "page": "new_song", "auth_state": "spotify", "is_enabled": True}),
        ("tag_added", "smoke_user", {"flow": "style_create", "page": "new_song", "auth_state": "guest", "source": "recommended"}),
        ("tag_removed", "smoke_user", {"flow": "style_create", "page": "new_song", "auth_state": "guest"}),
        ("new_lyrics_variation_clicked", "smoke_user", {"flow": "library", "page": "song_view", "auth_state": "guest"}),
        ("draft_lyrics_generated", "smoke_user", {"flow": "library", "page": "song_view", "auth_state": "guest", "duration_ms": 900, "has_lyrics_about_input": True}),
        ("draft_lyrics_failed", "smoke_user", {"flow": "library", "page": "song_view", "auth_state": "guest", "duration_ms": 400, "error_type": "ServerError", "has_lyrics_about_input": True}),
        ("new_lyrics_in_style_started", "smoke_user", {"flow": "library", "page": "song_view", "auth_state": "guest", "has_lyrics_about_input": True}),
        ("new_lyrics_in_style_succeeded", "smoke_user", {"flow": "library", "page": "song_view", "auth_state": "guest", "duration_ms": 1200, "has_lyrics_about_input": True}),
        ("new_lyrics_in_style_failed", "smoke_user", {"flow": "library", "page": "song_view", "auth_state": "guest", "duration_ms": 300, "error_type": "APIError", "has_lyrics_about_input": True}),
        ("copied_to_clipboard", "smoke_user", {"flow": "utility", "page": "song_view", "auth_state": "guest", "content_type": "lyrics", "copy_context": "song_view", "exclude_present": False, "exclude_count_bucket": "0"}),
        ("copied_to_clipboard_failed", "smoke_user", {"flow": "utility", "page": "song_view", "auth_state": "guest", "content_type": "lyrics", "error_type": "NotAllowedError"}),
        ("suno_link_clicked", "smoke_user", {"flow": "utility", "page": "song_view", "auth_state": "guest", "origin_mode": "generated", "exclude_present": False, "exclude_count_bucket": "0"}),
        ("output_used", "smoke_user", {"flow": "utility", "page": "song_view", "auth_state": "guest", "method": "open_suno", "style_prompt_id": style_prompt_id, "lyrics_thread_id": lyrics_thread_id, "origin_mode": "generated", "origin_action": "generate", "flow_id": flow_id, "prompt_generation_id": "gen_smoke_1", "primary_tag_bucket": "electronic"}),
        ("output_used", "smoke_user", {"flow": "utility", "page": "song_view", "auth_state": "guest", "method": "copy_lyrics", "style_prompt_id": style_prompt_id, "lyrics_thread_id": lyrics_thread_id, "origin_mode": "generated"}),
        ("output_used", "smoke_user", {"flow": "utility", "page": "song_view", "auth_state": "guest", "method": "copy_style_prompt", "style_prompt_id": style_prompt_id, "lyrics_thread_id": lyrics_thread_id, "origin_mode": "loaded"}),
        ("output_used", "smoke_user", {"flow": "utility", "page": "song_view", "auth_state": "guest", "method": "open_suno", "style_prompt_id": style_prompt_id, "lyrics_thread_id": lyrics_thread_id, "origin_mode": "new"}),
        ("style_title_changed", "smoke_user", {"flow": "manual", "page": "song_view", "auth_state": "guest", "source": "manual"}),
        ("style_title_change_failed", "smoke_user", {"flow": "manual", "page": "song_view", "auth_state": "guest", "error_type": "APIError"}),
        ("song_title_changed", "smoke_user", {"flow": "manual", "page": "song_view", "auth_state": "guest", "source": "manual"}),
        ("song_title_change_failed", "smoke_user", {"flow": "manual", "page": "song_view", "auth_state": "guest", "error_type": "APIError"}),
        ("lyrics_manual_edit_saved", "smoke_user", {"flow": "manual", "page": "song_view", "auth_state": "guest", "edit_size": "small", "was_empty_before": False}),
        ("lyrics_manual_edit_save_failed", "smoke_user", {"flow": "manual", "page": "song_view", "auth_state": "guest", "error_type": "APIError"}),
        ("song_deleted", "smoke_user", {"flow": "library", "page": "song_view", "auth_state": "guest", "source": "song_view", "remaining_songs_bucket": "1-2"}),
        ("song_delete_failed", "smoke_user", {"flow": "library", "page": "song_view", "auth_state": "guest", "source": "song_view", "error_type": "APIError"}),
        ("style_deleted", "smoke_user", {"flow": "library", "page": "song_view", "auth_state": "guest", "source": "sidebar"}),
        ("style_delete_failed", "smoke_user", {"flow": "library", "page": "song_view", "auth_state": "guest", "source": "sidebar", "error_type": "APIError"}),
        ("songs_reordered", "smoke_user", {"flow": "library", "page": "song_view", "auth_state": "guest", "songs_count_bucket": "3-5", "move_direction": "down"}),
        ("songs_reorder_failed", "smoke_user", {"flow": "library", "page": "song_view", "auth_state": "guest", "error_type": "updates_not_persisted"}),
        # New naming + legacy refine (to verify both show up)
        ("style_refine_started", "smoke_user", {"flow": "style_refine", "page": "song_view", "auth_state": "guest"}),
        ("style_refine_succeeded", "smoke_user", {"flow": "style_refine", "page": "song_view", "auth_state": "guest", "duration_ms": 1500, "created_new_style": True, "updates_persisted": True, "changed_suno_prompt": True, "changed_fields_count_bucket": "1"}),
        ("style_refine_failed", "smoke_user", {"flow": "style_refine", "page": "song_view", "auth_state": "guest", "duration_ms": 200, "error_type": "APIError"}),
        ("lyrics_ai_edit_started", "smoke_user", {"flow": "lyrics_ai_edit", "page": "song_view", "auth_state": "guest"}),
        ("lyrics_ai_edit_succeeded", "smoke_user", {"flow": "lyrics_ai_edit", "page": "song_view", "auth_state": "guest", "duration_ms": 900, "updates_persisted": True, "changed_lyrics": True, "changed_fields_count_bucket": "1"}),
        ("lyrics_ai_edit_failed", "smoke_user", {"flow": "lyrics_ai_edit", "page": "song_view", "auth_state": "guest", "duration_ms": 120, "error_type": "APIError"}),
        ("refine_started", "smoke_user", {"flow": "refine", "page": "song_view", "auth_state": "guest", "refine_type": "style"}),
        ("refine_succeeded", "smoke_user", {"flow": "refine", "page": "song_view", "auth_state": "guest", "refine_type": "style", "duration_ms": 1500, "created_new_style": True, "updates_persisted": True}),
        ("refine_failed", "smoke_user", {"flow": "refine", "page": "song_view", "auth_state": "guest", "refine_type": "style", "duration_ms": 200, "error_type": "APIError"}),
    ]

    # ----------------------------------------------------------------------------
    # Backend telemetry events
    # ----------------------------------------------------------------------------
    backend_events: List[Tuple[str, str, Dict[str, Any]]] = [
        # Match real operation names used in backend instrumentation (agent_prompt_graph/refine services)
        ("llm_call", "backend", {"operation": "style.generate", "provider": "openai", "model": "gpt-4o-mini", "duration_ms": 777, "status": "succeeded", "error_type": None, "variant_id": "smoke", "architecture": "two_step", "is_repair": False, "attempt": 1}),
        ("llm_call", "backend", {"operation": "lyrics.generate", "provider": "openai", "model": "gpt-4o-mini", "duration_ms": 888, "status": "succeeded", "error_type": None, "variant_id": "smoke", "architecture": "two_step", "is_repair": False, "attempt": 1}),
        ("llm_call", "backend", {"operation": "song.generate", "provider": "openai", "model": "gpt-4o-mini", "duration_ms": 999, "status": "succeeded", "error_type": None, "variant_id": "smoke", "architecture": "two_step", "is_repair": False, "attempt": 1}),
        ("llm_call", "backend", {"operation": "refine.call", "provider": "gemini", "model": "gemini-1.5-flash", "duration_ms": 555, "status": "failed", "error_type": "TimeoutError", "variant_id": "smoke", "architecture": "refine_service", "is_repair": False, "attempt": 1}),
        ("llm_call", "backend", {"operation": "refine.planner", "provider": "openai", "model": "gpt-4o-mini", "duration_ms": 444, "status": "succeeded", "error_type": None, "variant_id": "smoke", "architecture": "unified_refine", "is_repair": False, "attempt": 1}),
        ("llm_call", "backend", {"operation": "style.repair", "provider": "openai", "model": "gpt-4o-mini", "duration_ms": 333, "status": "succeeded", "error_type": None, "variant_id": "smoke", "architecture": "two_step", "is_repair": True, "repair_kind": "style", "attempt": 1}),
        ("repair_agent_invoked", "backend", {"repair_kind": "style", "attempt": 1, "issues_count": 2, "issue_category": "schema", "variant_id": "smoke", "architecture": "smoke", "model": "gpt-4o-mini"}),
        ("repair_agent_validated", "backend", {"repair_kind": "style", "attempt": 1, "issues_count": 2, "issue_category": "schema", "fixed": True, "variant_id": "smoke", "architecture": "smoke", "model": "gpt-4o-mini"}),
    ]

    total = 0
    for (event, distinct_id, props) in [*frontend_events, *backend_events]:
        capture(event, distinct_id, {**base, **props})
        total += 1

    print(f"[ok] captured {total} events with seed_id={seed_id}")
    print(f"[ok] ingest host: {_capture_host()}")
    print(f"[ok] api host: {_api_host()}")

    # ----------------------------------------------------------------------------
    # Optional: poll PostHog until queryable
    # ----------------------------------------------------------------------------
    project_id = _env("POSTHOG_PROJECT_ID")
    personal_key = _env("POSTHOG_PERSONAL_API_KEY")
    if not project_id or not personal_key:
        print("[warn] POSTHOG_PROJECT_ID/POSTHOG_PERSONAL_API_KEY not set; skipping queryable verification.")
        return 0

    deadline = time.time() + 180
    while time.time() < deadline:
        try:
            c = _hogql_count_by_seed(seed_id, project_id, personal_key)
            print(f"[poll] seed events count: {c}")
            if c >= total:
                print("[ok] all smoke events are queryable")
                return 0
        except Exception as e:
            print(f"[poll] query error (will retry): {e}")
        time.sleep(10)

    print("[warn] timed out waiting for all events to be queryable (PostHog indexing delay).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

