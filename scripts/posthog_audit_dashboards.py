#!/usr/bin/env python3
"""
Audit PostHog dashboards for "does this tile have data?" across multiple query kinds.

Why:
- Different insight types return different `result` shapes (Trends vs Funnels vs Paths).
- This script standardizes a robust check so we don't incorrectly mark Paths as empty.
"""

from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class Cfg:
    host: str
    project_id: str
    personal_key: str


def _env(name: str, default: Optional[str] = None) -> str:
    v = os.environ.get(name, default)
    if not v:
        raise SystemExit(f"Missing env var: {name}")
    return v


def cfg() -> Cfg:
    host = os.environ.get("POSTHOG_HOST", "https://us.posthog.com").rstrip("/")
    return Cfg(host=host, project_id=_env("POSTHOG_PROJECT_ID"), personal_key=_env("POSTHOG_PERSONAL_API_KEY"))


def get_json(cfg: Cfg, path: str) -> Dict[str, Any]:
    url = f"{cfg.host}{path}"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {cfg.personal_key}", "Accept": "application/json"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def _sum_numeric_list(xs: Any) -> float:
    if not isinstance(xs, list):
        return 0.0
    return float(sum(x for x in xs if isinstance(x, (int, float))))


def tile_has_data(insight: Dict[str, Any]) -> Tuple[bool, str]:
    query = insight.get("query") or {}
    kind = None
    if isinstance(query, dict):
        kind = query.get("kind")
        if kind == "InsightVizNode":
            src = query.get("source")
            if isinstance(src, dict):
                kind = src.get("kind") or kind

    result = insight.get("result")
    if not isinstance(result, list) or len(result) == 0:
        return False, f"{kind or 'unknown'}:no_result"

    # Trends/Lifecycle/Stickiness often return series dicts with count/data.
    if kind in ("TrendsQuery", "LifecycleQuery", "StickinessQuery"):
        total = 0.0
        for s in result:
            if not isinstance(s, dict):
                continue
            if isinstance(s.get("count"), (int, float)):
                total += float(s["count"])
            total += _sum_numeric_list(s.get("data"))
        return (total > 0.0), (f"{kind}:ok" if total > 0 else f"{kind}:all_zero")

    # Funnels returns list of step objects; treat any non-zero count/conversion as data.
    if kind == "FunnelsQuery":
        total = 0.0
        for step in result:
            if not isinstance(step, dict):
                continue
            for k in ("count", "conversion_rate", "average_conversion_time"):
                if isinstance(step.get(k), (int, float)):
                    total += float(step[k])
        return (total > 0.0), (f"{kind}:ok" if total > 0 else f"{kind}:all_zero")

    # Paths returns list of edges with a `value` weight.
    if kind == "PathsQuery":
        total = 0.0
        for edge in result:
            if isinstance(edge, dict) and isinstance(edge.get("value"), (int, float)):
                total += float(edge["value"])
        return (total > 0.0), (f"{kind}:ok" if total > 0 else f"{kind}:all_zero")

    # Default: any non-empty result list is "has data"
    return True, f"{kind or 'unknown'}:nonempty"


def main() -> int:
    cfg0 = cfg()

    dashboards = {
        "Core Health (Exec)": 1075557,
        "Output / Export Behavior": 1075558,
        "Iteration (Refine + Manual Edit)": 1075564,
        "Library Engagement": 1075565,
        "Backend LLM + Repair (Obs)": 1075566,
        "Journeys (Funnels + Stickiness + Lifecycle)": 1075635,
    }

    failures = 0
    for name, did in dashboards.items():
        d = get_json(cfg0, f"/api/projects/{cfg0.project_id}/dashboards/{did}/")
        tiles = d.get("tiles", [])
        ok = 0
        bad: List[Tuple[str, str]] = []
        for t in tiles:
            ins = (t.get("insight") or {}) if isinstance(t, dict) else {}
            title = ins.get("name") if isinstance(ins, dict) else None
            title = title or "(no name)"
            has, reason = tile_has_data(ins if isinstance(ins, dict) else {})
            if has:
                ok += 1
            else:
                bad.append((title, reason))
        print(f"\n## {name}: {ok}/{len(tiles)} tiles have data")
        for (title, reason) in bad:
            print(f"- {title} ({reason})")
        if bad:
            failures += 1

    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

