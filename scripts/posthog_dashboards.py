#!/usr/bin/env python3
"""
PostHog dashboard/insight automation for Pseuno AI.
Uses PostHog's REST API to:
- Create (or find) dashboards
- Create (or find) insights with `query` payloads
- Attach insights to dashboards
- Validate queries by calling `/api/projects/{project_id}/query/`

Auth: Personal API key (Bearer token) via env var POSTHOG_PERSONAL_API_KEY.

Notes:
- This script intentionally uses only the Python standard library.
- Do NOT commit personal API keys. Use env vars when running.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import http.client
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple


_DASHBOARD_TILES_SUPPORTED: Optional[bool] = None


def _env(name: str, default: Optional[str] = None) -> str:
    v = os.environ.get(name, default)
    if v is None or v == "":
        raise SystemExit(f"Missing required env var: {name}")
    return v


@dataclass(frozen=True)
class PostHogConfig:
    host: str
    project_id: str
    personal_api_key: str


def _cfg() -> PostHogConfig:
    host = os.environ.get("POSTHOG_HOST", "https://us.posthog.com").rstrip("/")
    return PostHogConfig(
        host=host,
        project_id=_env("POSTHOG_PROJECT_ID"),
        personal_api_key=_env("POSTHOG_PERSONAL_API_KEY"),
    )


def _request(
    cfg: PostHogConfig,
    method: str,
    path: str,
    body: Optional[Dict[str, Any]] = None,
    query: Optional[Dict[str, str]] = None,
    timeout_s: int = 30,
) -> Dict[str, Any]:
    url = f"{cfg.host}{path}"
    if query:
        url = f"{url}?{urllib.parse.urlencode(query)}"

    headers = {
        "Authorization": f"Bearer {cfg.personal_api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")

    # PostHog cloud occasionally returns transient 502/503/504.
    # Retry a few times to make dashboard creation more robust.
    retries = 4 if method in ("GET", "POST", "PATCH") else 1
    for attempt in range(1, retries + 1):
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                raw = resp.read().decode("utf-8")
                if not raw:
                    return {}
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8") if e.fp else ""
            # Only retry transient gateway errors.
            if e.code in (502, 503, 504) and attempt < retries:
                time.sleep(0.5 * attempt)
                continue
            raise RuntimeError(
                f"HTTP {e.code} {method} {url}\n{raw or e.reason}"
            ) from None
        except (urllib.error.URLError, http.client.RemoteDisconnected) as e:
            # Connection resets / remote closes happen sometimes on PostHog cloud.
            if attempt < retries:
                time.sleep(0.5 * attempt)
                continue
            raise RuntimeError(f"Network error {method} {url}: {e}") from None


def _paginate(
    cfg: PostHogConfig,
    path: str,
    *,
    search: Optional[str] = None,
    page_size: int = 100,
) -> Iterable[Dict[str, Any]]:
    # PostHog list endpoints are typically DRF-style paginated:
    # { count, next, previous, results: [...] }
    query: Dict[str, str] = {"limit": str(page_size)}
    if search:
        query["search"] = search
    next_path = path
    next_query = query
    while True:
        payload = _request(cfg, "GET", next_path, query=next_query)
        results = payload.get("results")
        if isinstance(results, list):
            for item in results:
                if isinstance(item, dict):
                    yield item
        nxt = payload.get("next")
        if not nxt:
            break
        # `next` is a full URL; convert back into path+query
        u = urllib.parse.urlparse(nxt)
        next_path = u.path
        next_query = dict(urllib.parse.parse_qsl(u.query))


def _find_by_exact_name_first_page(
    cfg: PostHogConfig,
    path: str,
    *,
    name: str,
    limit: int = 100,
) -> Optional[int]:
    """
    PostHog's `search` parameter is substring-ish and can return a lot of rows.
    For our use case we only need to scan the first page and find an exact name
    match to avoid slow pagination.
    """
    payload = _request(
        cfg,
        "GET",
        path,
        query={"search": name, "limit": str(limit)},
    )
    results = payload.get("results", [])
    if not isinstance(results, list):
        return None
    for item in results:
        if not isinstance(item, dict):
            continue
        if item.get("name") == name and isinstance(item.get("id"), int):
            return item["id"]
    return None


def ensure_dashboard(cfg: PostHogConfig, name: str, description: str = "") -> int:
    existing_id = _find_by_exact_name_first_page(
        cfg, f"/api/projects/{cfg.project_id}/dashboards/", name=name
    )
    if existing_id is not None:
        return existing_id
    created = _request(
        cfg,
        "POST",
        f"/api/projects/{cfg.project_id}/dashboards/",
        body={"name": name, "description": description},
    )
    if not isinstance(created.get("id"), int):
        raise RuntimeError(f"Unexpected create dashboard response: {created}")
    return created["id"]


def ensure_insight(
    cfg: PostHogConfig,
    name: str,
    query_obj: Dict[str, Any],
    description: str = "",
    tags: Optional[List[str]] = None,
) -> int:
    # IMPORTANT: PostHog expects saved "insights" to be an InsightVizNode (or similar)
    # so the UI can render charts. A raw TrendsQuery runs fine via /query/, but will
    # show up as JSON in dashboards.
    # HogQL (DataVisualizationNode) should NOT be wrapped in InsightVizNode.
    query_kind = query_obj.get("kind", "")
    if query_kind == "DataVisualizationNode":
        # Already wrapped for HogQL - use as-is
        viz_query_obj = query_obj
    else:
        viz_query_obj: Dict[str, Any] = {
            "kind": "InsightVizNode",
            "source": query_obj,
            # NOTE: Some PostHog versions reject a top-level `display` field here.
            # The UI can pick a default visualization and you can change it manually.
        }

    existing_id = _find_by_exact_name_first_page(
        cfg, f"/api/projects/{cfg.project_id}/insights/", name=name
    )
    if existing_id is not None:
        # Upsert: patch query/metadata so we can iterate programmatically.
        body: Dict[str, Any] = {"name": name, "query": viz_query_obj}
        if description:
            body["description"] = description
        if tags:
            body["tags"] = tags
        _request(cfg, "PATCH", f"/api/projects/{cfg.project_id}/insights/{existing_id}/", body=body)
        return existing_id

    body: Dict[str, Any] = {"name": name, "query": viz_query_obj}
    if description:
        body["description"] = description
    if tags:
        body["tags"] = tags
    created = _request(cfg, "POST", f"/api/projects/{cfg.project_id}/insights/", body=body)
    if not isinstance(created.get("id"), int):
        raise RuntimeError(f"Unexpected create insight response: {created}")
    return created["id"]


def attach_insight_to_dashboard(cfg: PostHogConfig, dashboard_id: int, insight_id: int) -> None:
    """
    Preferred: create a dashboard tile.
    Fallback: patch insight dashboards if dashboard_tiles isn't enabled for your plan/version.
    """
    global _DASHBOARD_TILES_SUPPORTED

    def _patch_insight_dashboards() -> None:
        # Fallback: PATCH the insight with dashboards array
        # (May overwrite dashboards; so we first fetch, then merge.)
        ins = _request(cfg, "GET", f"/api/projects/{cfg.project_id}/insights/{insight_id}/")
        existing = ins.get("dashboards") or []
        dashboards = {d for d in existing if isinstance(d, int)}
        dashboards.add(dashboard_id)
        _request(
            cfg,
            "PATCH",
            f"/api/projects/{cfg.project_id}/insights/{insight_id}/",
            body={"dashboards": sorted(dashboards)},
        )

    if _DASHBOARD_TILES_SUPPORTED is False:
        _patch_insight_dashboards()
        return

    try:
        _request(
            cfg,
            "POST",
            f"/api/projects/{cfg.project_id}/dashboard_tiles/",
            body={"dashboard": dashboard_id, "insight": insight_id},
        )
        _DASHBOARD_TILES_SUPPORTED = True
        return
    except RuntimeError as e:
        # If the endpoint doesn't exist (404), don't keep retrying it for every tile.
        msg = str(e)
        if "HTTP 404" in msg and "/dashboard_tiles/" in msg:
            _DASHBOARD_TILES_SUPPORTED = False
            sys.stderr.write("[warn] PostHog /dashboard_tiles/ endpoint not found; using insight.dashboard fallback.\n")
            _patch_insight_dashboards()
            return

        sys.stderr.write(f"[warn] dashboard_tiles failed; falling back to PATCH insight dashboards.\n{e}\n")
        _patch_insight_dashboards()


def run_query(cfg: PostHogConfig, query_obj: Dict[str, Any]) -> Dict[str, Any]:
    # Query endpoint is the fastest "does this work?" test.
    # Docs indicate body includes `query`.
    # For DataVisualizationNode (HogQL), extract the inner HogQLQuery for /query/
    query_kind = query_obj.get("kind", "")
    if query_kind == "DataVisualizationNode" and query_obj.get("source"):
        actual_query = query_obj["source"]
    else:
        actual_query = query_obj
    return _request(cfg, "POST", f"/api/projects/{cfg.project_id}/query/", body={"query": actual_query})


def _events_node(
    event: str,
    *,
    name: Optional[str] = None,
    math: Optional[str] = None,
    math_property: Optional[str] = None,
    properties: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    node: Dict[str, Any] = {"kind": "EventsNode", "event": event}
    if name:
        # PostHog uses `custom_name` for the legend label, not `name`
        node["custom_name"] = name
    if math:
        node["math"] = math
    if math_property:
        node["math_property"] = math_property
    if properties:
        node["properties"] = properties
    return node


def _event_prop_equals(key: str, value: Any) -> Dict[str, Any]:
    # Verified working with /query/:
    # {key, type: "event", operator: "exact", value}
    return {"key": key, "type": "event", "operator": "exact", "value": value}


def trends_query(events: List[Dict[str, Any]], *, days: int = 7, interval: str = "day") -> Dict[str, Any]:
    return {
        "kind": "TrendsQuery",
        "series": events,
        "interval": interval,
        "dateRange": {"date_from": f"-{days}d"},
    }

def funnels_query(steps: List[Dict[str, Any]], *, days: int = 14) -> Dict[str, Any]:
    return {
        "kind": "FunnelsQuery",
        "series": steps,
        "dateRange": {"date_from": f"-{days}d"},
    }


def stickiness_query(events: List[Dict[str, Any]], *, days: int = 14, interval: str = "day") -> Dict[str, Any]:
    return {
        "kind": "StickinessQuery",
        "series": events,
        "interval": interval,
        "dateRange": {"date_from": f"-{days}d"},
    }


def lifecycle_query(events: List[Dict[str, Any]], *, days: int = 30, interval: str = "day") -> Dict[str, Any]:
    return {
        "kind": "LifecycleQuery",
        "series": events,
        "interval": interval,
        "dateRange": {"date_from": f"-{days}d"},
    }


def paths_query(*, start_event: str, days: int = 14) -> Dict[str, Any]:
    # NOTE: Your PostHog plan shows an "Advanced paths" upsell in the UI, but the basic
    # PathsQuery is still available via /query/ with a minimal pathsFilter.
    return {
        "kind": "PathsQuery",
        "pathsFilter": {"startPoint": start_event},
        "dateRange": {"date_from": f"-{days}d"},
    }


def core_health_tiles() -> List[Tuple[str, Dict[str, Any], str, List[str]]]:
    """
    A small, stable set of tiles that should validate quickly.
    Returns: (tile_name, query_obj, description, tags)
    """
    return [
        (
            "Generate: success vs failure",
            trends_query(
                [
                    _events_node("generate_succeeded", name="generate_succeeded"),
                    _events_node("generate_failed", name="generate_failed"),
                ],
                days=7,
                interval="day",
            ),
            "Counts of generate success vs failure (last 7d).",
            ["core", "health"],
        ),
        (
            "Generate succeeded by auth_state",
            trends_query(
                [
                    _events_node(
                        "generate_succeeded",
                        name="guest",
                        properties=[_event_prop_equals("auth_state", "guest")],
                    ),
                    _events_node(
                        "generate_succeeded",
                        name="spotify",
                        properties=[_event_prop_equals("auth_state", "spotify")],
                    ),
                ],
                days=14,
                interval="day",
            ),
            "Who is succeeding: guest vs logged-in (last 14d).",
            ["core", "auth"],
        ),
        (
            "DAU: generate_succeeded",
            trends_query(
                [
                    _events_node(
                        "generate_succeeded",
                        name="DAU(generate_succeeded)",
                        math="dau",
                    )
                ],
                days=14,
                interval="day",
            ),
            "Daily active creators (defined as users who generated successfully).",
            ["core", "usage"],
        ),
        (
            "Output used (any method)",
            trends_query([_events_node("output_used", name="output_used")], days=7, interval="day"),
            "Canonical value moment: output_used (last 7d).",
            ["core", "value"],
        ),
        (
            "DAU: output_used",
            trends_query(
                [
                    _events_node(
                        "output_used",
                        name="DAU(output_used)",
                        math="dau",
                    )
                ],
                days=14,
                interval="day",
            ),
            "Daily active value moments (users who used output).",
            ["core", "usage"],
        ),
        (
            "Style refine: success vs failure",
            trends_query(
                [
                    # Use legacy refine_* with refine_type filter so historical data shows up.
                    _events_node(
                        "refine_succeeded",
                        name="style_refine_succeeded",
                        properties=[_event_prop_equals("refine_type", "style")],
                    ),
                    _events_node(
                        "refine_failed",
                        name="style_refine_failed",
                        properties=[_event_prop_equals("refine_type", "style")],
                    ),
                ],
                days=7,
                interval="day",
            ),
            "Style refinement reliability (last 7d).",
            ["core", "style_refine"],
        ),
        (
            "Lyrics AI edit: success vs failure",
            trends_query(
                [
                    _events_node(
                        "refine_succeeded",
                        name="lyrics_ai_edit_succeeded",
                        properties=[_event_prop_equals("refine_type", "lyrics")],
                    ),
                    _events_node(
                        "refine_failed",
                        name="lyrics_ai_edit_failed",
                        properties=[_event_prop_equals("refine_type", "lyrics")],
                    ),
                ],
                days=7,
                interval="day",
            ),
            "Lyrics AI edit reliability (last 7d).",
            ["core", "lyrics_ai_edit"],
        ),
        (
            "Generate latency p95 (duration_ms)",
            trends_query(
                [_events_node("generate_succeeded", name="p95(duration_ms)", math="p95", math_property="duration_ms")],
                days=7,
                interval="day",
            ),
            "Generate p95 latency over time (last 7d).",
            ["core", "performance"],
        ),
        (
            "Style refine latency p95 (duration_ms)",
            trends_query(
                [
                    _events_node(
                        "refine_succeeded",
                        name="p95(duration_ms)",
                        math="p95",
                        math_property="duration_ms",
                        properties=[_event_prop_equals("refine_type", "style")],
                    )
                ],
                days=7,
                interval="day",
            ),
            "Style refine p95 latency over time (last 7d).",
            ["core", "performance"],
        ),
        (
            "Generate failed by error_type (common)",
            trends_query(
                [
                    _events_node(
                        "generate_failed",
                        name="NetworkError",
                        properties=[_event_prop_equals("error_type", "NetworkError")],
                    ),
                    _events_node(
                        "generate_failed",
                        name="TimeoutError",
                        properties=[_event_prop_equals("error_type", "TimeoutError")],
                    ),
                    _events_node(
                        "generate_failed",
                        name="APIError",
                        properties=[_event_prop_equals("error_type", "APIError")],
                    ),
                    _events_node("generate_failed", name="all_generate_failed"),
                ],
                days=14,
                interval="day",
            ),
            "Error mix for generate_failed (last 14d).",
            ["core", "errors"],
        ),
    ]

def output_behavior_tiles() -> List[Tuple[str, Dict[str, Any], str, List[str]]]:
    return [
        (
            "Output used (any method)",
            trends_query([_events_node("output_used", name="output_used")], days=14, interval="day"),
            "Canonical value moment: output_used (last 14d).",
            ["output", "value"],
        ),
        (
            "Output used by method",
            trends_query(
                [
                    _events_node("output_used", name="open_suno", properties=[_event_prop_equals("method", "open_suno")]),
                    _events_node("output_used", name="copy_lyrics", properties=[_event_prop_equals("method", "copy_lyrics")]),
                    _events_node("output_used", name="copy_style_prompt", properties=[_event_prop_equals("method", "copy_style_prompt")]),
                ],
                days=14,
                interval="day",
            ),
            "How users extract value: method mix (last 14d).",
            ["output", "value"],
        ),
        (
            "Output used by origin_mode",
            trends_query(
                [
                    _events_node("output_used", name="generated", properties=[_event_prop_equals("origin_mode", "generated")]),
                    _events_node("output_used", name="loaded", properties=[_event_prop_equals("origin_mode", "loaded")]),
                    _events_node("output_used", name="new", properties=[_event_prop_equals("origin_mode", "new")]),
                ],
                days=14,
                interval="day",
            ),
            "Did usage happen right after generation vs from loaded content? (last 14d).",
            ["output", "paths"],
        ),
        (
            "Suno link clicked",
            trends_query([_events_node("suno_link_clicked", name="suno_link_clicked")], days=14, interval="day"),
            "Direct Suno usage intent (last 14d).",
            ["output", "suno"],
        ),
        (
            "Copied to clipboard",
            trends_query([_events_node("copied_to_clipboard", name="copied_to_clipboard")], days=14, interval="day"),
            "Clipboard usage volume (last 14d).",
            ["output", "clipboard"],
        ),
        (
            "Clipboard failures",
            trends_query([_events_node("copied_to_clipboard_failed", name="copied_to_clipboard_failed")], days=14, interval="day"),
            "Clipboard reliability (last 14d).",
            ["output", "reliability"],
        ),
    ]


def iteration_tiles() -> List[Tuple[str, Dict[str, Any], str, List[str]]]:
    return [
        (
            "Style refine succeeded",
            trends_query(
                [
                    _events_node(
                        "refine_succeeded",
                        name="style_refine_succeeded",
                        properties=[_event_prop_equals("refine_type", "style")],
                    )
                ],
                days=14,
                interval="day",
            ),
            "How often users refine styles (last 14d).",
            ["iteration", "style_refine"],
        ),
        (
            "Lyrics AI edit succeeded",
            trends_query(
                [
                    _events_node(
                        "refine_succeeded",
                        name="lyrics_ai_edit_succeeded",
                        properties=[_event_prop_equals("refine_type", "lyrics")],
                    )
                ],
                days=14,
                interval="day",
            ),
            "How often users run lyrics AI edits (last 14d).",
            ["iteration", "lyrics_ai_edit"],
        ),
        (
            "Manual lyrics edits saved",
            trends_query([_events_node("lyrics_manual_edit_saved", name="lyrics_manual_edit_saved")], days=14, interval="day"),
            "Manual lyric editing volume (last 14d).",
            ["iteration", "manual_edits"],
        ),
        (
            "Song/style title changes",
            trends_query(
                [
                    _events_node("song_title_changed", name="song_title_changed"),
                    _events_node("style_title_changed", name="style_title_changed"),
                ],
                days=14,
                interval="day",
            ),
            "Renaming behavior (manual vs AI sources can be added later).",
            ["iteration", "naming"],
        ),
        (
            "Edit/Refine failures (high-level)",
            trends_query(
                [
                    _events_node(
                        "refine_failed",
                        name="style_refine_failed",
                        properties=[_event_prop_equals("refine_type", "style")],
                    ),
                    _events_node(
                        "refine_failed",
                        name="lyrics_ai_edit_failed",
                        properties=[_event_prop_equals("refine_type", "lyrics")],
                    ),
                    _events_node("lyrics_manual_edit_save_failed", name="lyrics_manual_edit_save_failed"),
                ],
                days=14,
                interval="day",
            ),
            "High-level reliability for iteration actions (last 14d).",
            ["iteration", "reliability"],
        ),
    ]


def library_tiles() -> List[Tuple[str, Dict[str, Any], str, List[str]]]:
    return [
        (
            "Library navigation: style/thread selected",
            trends_query(
                [
                    _events_node("style_selected", name="style_selected"),
                    _events_node("thread_selected", name="thread_selected"),
                ],
                days=14,
                interval="day",
            ),
            "How often users load existing content (last 14d).",
            ["library", "navigation"],
        ),
        (
            "New lyrics variation clicked",
            trends_query([_events_node("new_lyrics_variation_clicked", name="new_lyrics_variation_clicked")], days=14, interval="day"),
            "Starting a new song on an existing style (last 14d).",
            ["library", "creation"],
        ),
        (
            "New lyrics in style (end-to-end)",
            trends_query(
                [
                    _events_node("new_lyrics_in_style_succeeded", name="new_lyrics_in_style_succeeded"),
                    _events_node("new_lyrics_in_style_failed", name="new_lyrics_in_style_failed"),
                ],
                days=14,
                interval="day",
            ),
            "Creating new lyrics within an existing style (last 14d).",
            ["library", "creation", "reliability"],
        ),
        (
            "Deletes + reorders",
            trends_query(
                [
                    _events_node("style_deleted", name="style_deleted"),
                    _events_node("song_deleted", name="song_deleted"),
                    _events_node("songs_reordered", name="songs_reordered"),
                ],
                days=14,
                interval="day",
            ),
            "Destructive/organizing actions (last 14d).",
            ["library", "management"],
        ),
        (
            "Delete/reorder failures",
            trends_query(
                [
                    _events_node("style_delete_failed", name="style_delete_failed"),
                    _events_node("song_delete_failed", name="song_delete_failed"),
                    _events_node("songs_reorder_failed", name="songs_reorder_failed"),
                ],
                days=14,
                interval="day",
            ),
            "Reliability of delete/reorder actions (last 14d).",
            ["library", "reliability"],
        ),
    ]


def backend_observability_tiles() -> List[Tuple[str, Dict[str, Any], str, List[str]]]:
    return [
        (
            "LLM calls volume",
            trends_query([_events_node("llm_call", name="llm_call")], days=14, interval="day"),
            "Backend LLM call volume (last 14d).",
            ["backend", "llm"],
        ),
        (
            "LLM calls: success vs failure",
            trends_query(
                [
                    _events_node("llm_call", name="succeeded", properties=[_event_prop_equals("status", "succeeded")]),
                    _events_node("llm_call", name="failed", properties=[_event_prop_equals("status", "failed")]),
                ],
                days=14,
                interval="day",
            ),
            "Backend LLM reliability (last 14d).",
            ["backend", "llm", "reliability"],
        ),
        (
            "LLM calls by operation (selected)",
            trends_query(
                [
                    _events_node("llm_call", name="style.generate", properties=[_event_prop_equals("operation", "style.generate")]),
                    _events_node("llm_call", name="lyrics.generate", properties=[_event_prop_equals("operation", "lyrics.generate")]),
                    _events_node("llm_call", name="song.generate", properties=[_event_prop_equals("operation", "song.generate")]),
                    _events_node("llm_call", name="refine.call", properties=[_event_prop_equals("operation", "refine.call")]),
                    _events_node("llm_call", name="refine.planner", properties=[_event_prop_equals("operation", "refine.planner")]),
                    _events_node("llm_call", name="repairs", properties=[_event_prop_equals("is_repair", True)]),
                ],
                days=14,
                interval="day",
            ),
            "Which internal steps are running (selected ops; last 14d).",
            ["backend", "llm"],
        ),
        (
            "Repair agent invoked/validated",
            trends_query(
                [
                    _events_node("repair_agent_invoked", name="repair_agent_invoked"),
                    _events_node("repair_agent_validated", name="repair_agent_validated"),
                ],
                days=14,
                interval="day",
            ),
            "Repair loop activity (last 14d).",
            ["backend", "repair"],
        ),
    ]

def hogql_query(query: str) -> Dict[str, Any]:
    """Create a HogQL insight query. Results render as a table by default.
    Note: HogQL queries use DataVisualizationNode, not InsightVizNode."""
    return {
        "kind": "DataVisualizationNode",
        "source": {
            "kind": "HogQLQuery",
            "query": query,
        },
    }


def prompt_quality_tiles() -> List[Tuple[str, Dict[str, Any], str, List[str]]]:
    """
    Prompt/tag quality & engagement deep-dive (kept OUT of the exec dashboard to reduce noise).
    """
    return [
        (
            "Top 15 tags used (last 30d)",
            hogql_query("""
SELECT
  arrayJoin(JSONExtractArrayRaw(properties, 'tags_selected')) as tag,
  count() as count
FROM events
WHERE event = 'generate_succeeded'
  AND timestamp > now() - interval 30 day
GROUP BY tag
ORDER BY count DESC
LIMIT 15
            """.strip()),
            "Most frequently selected tags in successful generations (HogQL).",
            ["prompt_quality", "tags", "hogql"],
        ),
        (
            "Generate succeeded by primary_tag_bucket (selected)",
            trends_query(
                [
                    _events_node("generate_succeeded", name="electronic", properties=[_event_prop_equals("primary_tag_bucket", "electronic")]),
                    _events_node("generate_succeeded", name="hip-hop", properties=[_event_prop_equals("primary_tag_bucket", "hip-hop")]),
                    _events_node("generate_succeeded", name="indie rock", properties=[_event_prop_equals("primary_tag_bucket", "indie rock")]),
                    _events_node("generate_succeeded", name="cinematic", properties=[_event_prop_equals("primary_tag_bucket", "cinematic")]),
                    _events_node("generate_succeeded", name="other", properties=[_event_prop_equals("primary_tag_bucket", "other")]),
                ],
                days=30,
                interval="day",
            ),
            "Volume of successful generations by tag bucket (curated; last 30d).",
            ["prompt_quality", "tags"],
        ),
        (
            "Output used by primary_tag_bucket (selected)",
            trends_query(
                [
                    _events_node("output_used", name="electronic", properties=[_event_prop_equals("primary_tag_bucket", "electronic")]),
                    _events_node("output_used", name="hip-hop", properties=[_event_prop_equals("primary_tag_bucket", "hip-hop")]),
                    _events_node("output_used", name="indie rock", properties=[_event_prop_equals("primary_tag_bucket", "indie rock")]),
                    _events_node("output_used", name="cinematic", properties=[_event_prop_equals("primary_tag_bucket", "cinematic")]),
                    _events_node("output_used", name="other", properties=[_event_prop_equals("primary_tag_bucket", "other")]),
                ],
                days=30,
                interval="day",
            ),
            "Value moments (output_used) by tag bucket (curated; last 30d).",
            ["prompt_quality", "tags"],
        ),
        (
            "Generate clicked: used_randomize_style vs not",
            trends_query(
                [
                    _events_node("generate_clicked", name="used_randomize_style=true", properties=[_event_prop_equals("used_randomize_style", True)]),
                    _events_node("generate_clicked", name="used_randomize_style=false", properties=[_event_prop_equals("used_randomize_style", False)]),
                ],
                days=30,
                interval="day",
            ),
            "How often users generate after using randomize-style (last 30d).",
            ["prompt_quality", "randomize"],
        ),
        (
            "Generate clicked: used_randomize_lyrics vs not",
            trends_query(
                [
                    _events_node("generate_clicked", name="used_randomize_lyrics=true", properties=[_event_prop_equals("used_randomize_lyrics", True)]),
                    _events_node("generate_clicked", name="used_randomize_lyrics=false", properties=[_event_prop_equals("used_randomize_lyrics", False)]),
                ],
                days=30,
                interval="day",
            ),
            "How often users generate after using randomize-lyrics (last 30d).",
            ["prompt_quality", "randomize"],
        ),
        (
            "Avg tags per generation (last 30d)",
            hogql_query("""
SELECT
  round(avg(properties.tags_count), 2) as avg_tags,
  count() as generations
FROM events
WHERE event = 'generate_succeeded'
  AND timestamp > now() - interval 30 day
            """.strip()),
            "Average number of tags selected per successful generation.",
            ["prompt_quality", "tags", "hogql"],
        ),
        (
            "Tag sources breakdown (last 30d)",
            hogql_query("""
SELECT
  sum(properties.tags_recommended_count) as recommended,
  sum(properties.tags_auto_picked_count) as auto_picked
FROM events
WHERE event = 'generate_succeeded'
  AND timestamp > now() - interval 30 day
            """.strip()),
            "Total tags by source: recommended clicks vs auto-picked from 'Surprise me'.",
            ["prompt_quality", "tags", "hogql"],
        ),
    ]

def journeys_tiles() -> List[Tuple[str, Dict[str, Any], str, List[str]]]:
    return [
        (
            "Funnel: generate_succeeded → output_used",
            funnels_query(
                [
                    _events_node("generate_succeeded", name="generate_succeeded"),
                    _events_node("output_used", name="output_used"),
                ],
                days=14,
            ),
            "Core value funnel (last 14d).",
            ["journeys", "funnels"],
        ),
        (
            "Funnel: refine(style) → output_used",
            funnels_query(
                [
                    _events_node(
                        "refine_succeeded",
                        name="refine_succeeded(style)",
                        properties=[_event_prop_equals("refine_type", "style")],
                    ),
                    _events_node("output_used", name="output_used"),
                ],
                days=30,
            ),
            "Do style refinements lead to output usage? (last 30d).",
            ["journeys", "funnels"],
        ),
        (
            "Stickiness: output_used",
            stickiness_query([_events_node("output_used", name="output_used")], days=14, interval="day"),
            "How many days per period users hit output_used (last 14d).",
            ["journeys", "stickiness"],
        ),
        (
            "Lifecycle: output_used",
            lifecycle_query([_events_node("output_used", name="output_used")], days=30, interval="day"),
            "New vs returning vs resurrecting vs dormant (last 30d).",
            ["journeys", "lifecycle"],
        ),
        (
            "Paths from output_used (basic)",
            paths_query(start_event="output_used", days=14),
            "Basic paths starting at output_used (last 14d).",
            ["journeys", "paths"],
        ),
    ]


def cmd_list_projects(cfg: PostHogConfig) -> int:
    payload = _request(cfg, "GET", "/api/projects/")
    results = payload.get("results", [])
    print(json.dumps(results, indent=2))
    return 0


def cmd_ensure_core_health(cfg: PostHogConfig, dashboard_name: str) -> int:
    dash_id = ensure_dashboard(cfg, dashboard_name, description="Auto-managed by scripts/posthog_dashboards.py")
    print(f"[ok] dashboard: {dashboard_name} (id={dash_id})")

    tiles = core_health_tiles()
    return _ensure_tiles(cfg, dash_id, tiles)


def _ensure_tiles(
    cfg: PostHogConfig,
    dashboard_id: int,
    tiles: List[Tuple[str, Dict[str, Any], str, List[str]]],
) -> int:
    failures = 0
    for (tile_name, query_obj, desc, tags) in tiles:
        print(f"\n== {tile_name} ==")
        # Validate query first (fast feedback)
        try:
            t0 = time.time()
            run_query(cfg, query_obj)
            dt_ms = int((time.time() - t0) * 1000)
            print(f"[ok] query ran in {dt_ms}ms")
        except Exception as e:
            failures += 1
            print(f"[fail] query error: {e}")
            continue

        # Create insight + attach
        try:
            insight_id = ensure_insight(cfg, tile_name, query_obj, description=desc, tags=tags)
            attach_insight_to_dashboard(cfg, dashboard_id, insight_id)
            print(f"[ok] insight attached (id={insight_id})")
        except Exception as e:
            failures += 1
            print(f"[fail] create/attach error: {e}")
            continue

        # Optionally refresh the saved insight (forces evaluation)
        try:
            refreshed = _request(
                cfg,
                "GET",
                f"/api/projects/{cfg.project_id}/insights/{insight_id}/",
                query={"refresh": "true"},
            )
            # We don't rely on exact shape; just show a tiny summary.
            keys = [k for k in ("result", "results", "data") if k in refreshed]
            print(f"[ok] refreshed insight (keys: {keys or 'no result keys found'})")
        except Exception as e:
            print(f"[warn] refresh failed (non-fatal): {e}")

    if failures:
        print(f"\n[done] core health: {len(tiles) - failures} ok, {failures} failed")
        return 2
    print(f"\n[done] core health: all {len(tiles)} tiles ok")
    return 0


def cmd_ensure_dashboard_pack(cfg: PostHogConfig, pack: str) -> int:
    packs: Dict[str, Tuple[str, List[Tuple[str, Dict[str, Any], str, List[str]]]]] = {
        "core-health": ("Core Health (Exec)", core_health_tiles()),
        "output": ("Output / Export Behavior", output_behavior_tiles()),
        "iteration": ("Iteration (Refine + Manual Edit)", iteration_tiles()),
        "library": ("Library Engagement", library_tiles()),
        "backend": ("Backend LLM + Repair (Obs)", backend_observability_tiles()),
        "journeys": ("Journeys (Funnels + Stickiness + Lifecycle)", journeys_tiles()),
        "prompt-quality": ("Prompt Quality (Tags)", prompt_quality_tiles()),
    }
    if pack not in packs:
        raise SystemExit(f"Unknown pack '{pack}'. Choose one of: {', '.join(sorted(packs.keys()))}")
    dash_name, tiles = packs[pack]
    dash_id = ensure_dashboard(cfg, dash_name, description="Auto-managed by scripts/posthog_dashboards.py")
    print(f"[ok] dashboard: {dash_name} (id={dash_id})")
    return _ensure_tiles(cfg, dash_id, tiles)


def cmd_ensure_all(cfg: PostHogConfig) -> int:
    failures = 0
    for pack in ["core-health", "output", "iteration", "library", "backend", "journeys", "prompt-quality"]:
        print(f"\n\n#############################\n# PACK: {pack}\n#############################")
        rc = cmd_ensure_dashboard_pack(cfg, pack)
        if rc != 0:
            failures += 1
    if failures:
        print(f"\n[done] ensure-all: {failures} packs had failures")
        return 2
    print("\n[done] ensure-all: all packs ok")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="PostHog dashboard automation for Pseuno AI")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list-projects", help="List projects visible to this API key")

    core = sub.add_parser("ensure-core-health", help="Create/update Core Health dashboard + tiles and validate queries")
    core.add_argument("--dashboard-name", default="Core Health (Exec)", help="Dashboard name to create/update")

    pack = sub.add_parser("ensure-pack", help="Create/update a dashboard pack (output, iteration, library, backend)")
    pack.add_argument("--pack", required=True, help="One of: core-health, output, iteration, library, backend")

    ensure_all = sub.add_parser("ensure-all", help="Create/update all dashboard packs and validate queries")
    ensure_all.add_argument(
        "--loop",
        action="store_true",
        help="Re-run until success (exit code 0) or until --max-attempts is reached",
    )
    ensure_all.add_argument(
        "--sleep",
        type=float,
        default=3.0,
        help="Seconds to wait between attempts when using --loop",
    )
    ensure_all.add_argument(
        "--max-attempts",
        type=int,
        default=30,
        help="Maximum attempts when using --loop",
    )

    return p


def main() -> int:
    args = build_parser().parse_args()
    cfg = _cfg()

    if args.cmd == "list-projects":
        return cmd_list_projects(cfg)
    if args.cmd == "ensure-core-health":
        return cmd_ensure_core_health(cfg, args.dashboard_name)
    if args.cmd == "ensure-pack":
        return cmd_ensure_dashboard_pack(cfg, args.pack)
    if args.cmd == "ensure-all":
        if not args.loop:
            return cmd_ensure_all(cfg)

        attempt = 0
        while True:
            attempt += 1
            print(f"\n\n=============================\nATTEMPT {attempt}/{args.max_attempts}\n=============================")
            rc = cmd_ensure_all(cfg)
            if rc == 0:
                return 0
            if attempt >= args.max_attempts:
                return rc
            try:
                time.sleep(max(0.0, float(args.sleep)))
            except KeyboardInterrupt:
                return 130

    raise SystemExit(f"Unknown command: {args.cmd}")


if __name__ == "__main__":
    raise SystemExit(main())

