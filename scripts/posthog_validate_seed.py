#!/usr/bin/env python3
"""
Validate that a smoke-test `seed_id` produced the expected PostHog events AND that
each event contains key required properties.

This is a pragmatic “accuracy check” for our instrumentation contract:
- Ensures event names are ingested
- Ensures required properties exist (e.g., *_failed has error_type)

It does NOT prove real UI flows emit the right events at the right times; for that,
add Playwright E2E that drives the app and inspects capture payloads.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class Cfg:
    host: str
    project_id: str
    personal_key: str


def _env(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        raise SystemExit(f"Missing env var: {name}")
    return v


def _cfg() -> Cfg:
    host = os.environ.get("POSTHOG_HOST", "https://us.posthog.com").rstrip("/")
    return Cfg(host=host, project_id=_env("POSTHOG_PROJECT_ID"), personal_key=_env("POSTHOG_PERSONAL_API_KEY"))


def _post_query(cfg: Cfg, query: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{cfg.host}/api/projects/{cfg.project_id}/query/"
    body = json.dumps({"query": query}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {cfg.personal_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def _hogql_rows(cfg: Cfg, seed_id: str, limit: int = 500) -> List[List[Any]]:
    q = {
        "kind": "HogQLQuery",
        "query": (
            "select event, properties "
            "from events "
            "where properties['seed_id'] = {seed} "
            "order by timestamp desc "
            f"limit {int(limit)}"
        ),
        "values": {"seed": seed_id},
    }
    res = _post_query(cfg, q)
    rows = res.get("results")
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, list)]


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python3 scripts/posthog_validate_seed.py <seed_id>", file=sys.stderr)
        return 2
    seed_id = sys.argv[1]
    cfg = _cfg()

    rows = _hogql_rows(cfg, seed_id)
    if not rows:
        print("[fail] no events found for seed_id (maybe indexing delay?)")
        return 2

    # Map: event -> list of properties dicts
    by_event: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        if len(row) != 2:
            continue
        event = row[0]
        props = row[1]
        if not isinstance(event, str):
            continue
        if isinstance(props, str):
            try:
                props = json.loads(props)
            except Exception:
                props = {}
        if isinstance(props, dict):
            by_event.setdefault(event, []).append(props)

    # Minimal contract rules (extend as needed)
    required_keys: Dict[str, List[str]] = {
        "generate_succeeded": ["duration_ms", "auth_state"],
        "generate_failed": ["duration_ms", "error_type", "auth_state"],
        "output_used": ["method", "origin_mode", "auth_state"],
        "copied_to_clipboard_failed": ["error_type"],
        "draft_lyrics_failed": ["error_type", "duration_ms"],
        "new_lyrics_in_style_failed": ["error_type", "duration_ms"],
        "refine_failed": ["error_type", "duration_ms", "refine_type"],
        "llm_call": ["operation", "provider", "model", "duration_ms", "status"],
        "repair_agent_invoked": ["repair_kind", "attempt", "issues_count"],
        "repair_agent_validated": ["repair_kind", "attempt", "fixed"],
    }

    failures: List[str] = []
    for event, keys in required_keys.items():
        if event not in by_event:
            failures.append(f"missing event: {event}")
            continue
        sample = by_event[event][0]
        missing = [k for k in keys if k not in sample or sample.get(k) is None]
        if missing:
            failures.append(f"{event}: missing props {missing}")

    # Generic rule: any *_failed should include error_type
    for event, props_list in by_event.items():
        if event.endswith("_failed"):
            for p in props_list:
                if p.get("error_type") is None:
                    failures.append(f"{event}: error_type missing")
                    break

    if failures:
        print("[fail] validation issues:")
        for f in failures:
            print(f"- {f}")
        print(f"[info] events seen: {sorted(by_event.keys())}")
        return 2

    print(f"[ok] seed_id {seed_id}: validation passed ({sum(len(v) for v in by_event.values())} events)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

