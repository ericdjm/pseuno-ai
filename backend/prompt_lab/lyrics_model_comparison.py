#!/usr/bin/env python3
"""
Lyrics Model Comparison: gemini-2.5-flash vs gemini-3-flash-preview (minimal thinking)

Runs the full V10 pipeline for 10 test cases with each model as the lyrics generator,
then prints a side-by-side comparison of speed and lyrics quality.

Usage:
    cd backend && python prompt_lab/lyrics_model_comparison.py
"""

import asyncio
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Path setup
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from app.config import Settings
from app.schemas.advanced import AdvancedGenerateRequest
from app.services.agent_prompt_graph import AgentPromptGraph, GeminiChatClient


OUTPUT_DIR = Path(__file__).parent / "results" / "lyrics_comparison"


@dataclass
class LyricsModelConfig:
    name: str
    lyrics_model: str
    thinking_level_override: Optional[str] = None
    thinking_budget_override: Optional[int] = None


CONFIGS = [
    LyricsModelConfig(
        name="2.5-flash (baseline)",
        lyrics_model="gemini-2.5-flash",
        # Default thinking budget (1024) — no override
    ),
    LyricsModelConfig(
        name="3-flash minimal",
        lyrics_model="gemini-3-flash-preview",
        thinking_level_override="minimal",
    ),
]


def build_graph(settings: Settings, config: LyricsModelConfig) -> AgentPromptGraph:
    """Create an AgentPromptGraph with the lyrics model swapped."""
    # Override lyrics_model in settings
    patched_settings = settings.model_copy(
        update={"lyrics_model": config.lyrics_model}
    )
    graph = AgentPromptGraph(settings=patched_settings)
    # Clear cache and pre-populate with configured lyrics client
    graph._llm_cache = {}

    kwargs = {}
    if config.thinking_level_override:
        kwargs["thinking_level_override"] = config.thinking_level_override
    if config.thinking_budget_override is not None:
        kwargs["thinking_budget_override"] = config.thinking_budget_override

    lyrics_client = GeminiChatClient(
        api_key=patched_settings.gemini_api_key,
        model=config.lyrics_model,
        temperature=patched_settings.llm_temperature,
        timeout=patched_settings.http_timeout,
        **kwargs,
    )
    graph._llm_cache["lyrics_model"] = lyrics_client
    return graph


def load_test_cases() -> List[dict]:
    p = Path(__file__).parent / "test_cases" / "test_cases_speed_bench.json"
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


async def run_single(
    graph: AgentPromptGraph,
    test_case: dict,
    variant: str = "v10_suno_friendly",
) -> Dict[str, Any]:
    """Run a single generation and capture full results."""
    request = AdvancedGenerateRequest(
        user_prompt=test_case["user_prompt"],
        lyrics_about=test_case["lyrics_about"],
        selected_artists=test_case.get("selected_artists", []),
        tags=test_case.get("tags", []),
        prompt_variant=variant,
    )
    wall_start = time.time()
    try:
        result = await graph.generate(request)
        wall_ms = int((time.time() - wall_start) * 1000)

        # Extract lyrics timing
        lyrics_ms = 0
        total_ms = 0
        debug = result.get("debug_info", {})
        for span in debug.get("spans", []):
            if span.get("name") == "lyrics.generate":
                lyrics_ms = span.get("elapsed_ms", 0)
        total_ms = debug.get("summary", {}).get("total_elapsed_ms", 0)
        repairs = debug.get("summary", {}).get("repairs", 0)

        return {
            "test_case": test_case["name"],
            "wall_ms": wall_ms,
            "total_ms": total_ms,
            "lyrics_ms": lyrics_ms,
            "repairs": repairs,
            "concept_title": result.get("concept_title", ""),
            "lyrics": result.get("lyrics", ""),
            "suno_prompt": result.get("suno_prompt", ""),
            "style_name": result.get("style_name", ""),
            "error": None,
        }
    except Exception as e:
        wall_ms = int((time.time() - wall_start) * 1000)
        return {
            "test_case": test_case["name"],
            "wall_ms": wall_ms,
            "total_ms": wall_ms,
            "lyrics_ms": 0,
            "repairs": 0,
            "concept_title": "",
            "lyrics": "",
            "suno_prompt": "",
            "style_name": "",
            "error": str(e),
        }


async def main():
    settings = Settings()
    test_cases = load_test_cases()  # All 10

    print(f"Running lyrics model comparison: {len(test_cases)} test cases x {len(CONFIGS)} configs")
    print(f"Current lyrics model: {settings.lyrics_model}")
    print()

    all_results: Dict[str, List[Dict[str, Any]]] = {}

    # Use semaphore to limit concurrent API calls (each generation makes ~5 calls internally)
    semaphore = asyncio.Semaphore(2)

    for config in CONFIGS:
        print(f"{'='*80}")
        print(f"Running: {config.name} (model={config.lyrics_model})")
        print(f"{'='*80}")

        graph = build_graph(settings, config)
        results = []

        async def _run_with_sem(tc):
            async with semaphore:
                r = await run_single(graph, tc)
                status = "OK" if not r["error"] else f"ERR: {r['error'][:50]}"
                print(f"  {tc['name']:<55} {r['total_ms']:>6}ms (lyrics: {r['lyrics_ms']:>5}ms) {status}")
                return r

        tasks = [_run_with_sem(tc) for tc in test_cases]
        results = await asyncio.gather(*tasks)
        all_results[config.name] = list(results)
        print()

    # ── Print comparison ──────────────────────────────────────────────────
    print("\n" + "=" * 120)
    print("LYRICS MODEL COMPARISON RESULTS")
    print("=" * 120)

    config_names = [c.name for c in CONFIGS]
    baseline_name = config_names[0]

    # Speed summary table
    print(f"\n{'TEST CASE':<55} ", end="")
    for name in config_names:
        print(f"| {name:>20} ", end="")
    print(f"| {'Delta':>10}")
    print("-" * 120)

    for i, tc in enumerate(test_cases):
        print(f"{tc['name']:<55} ", end="")
        times = []
        for name in config_names:
            r = all_results[name][i]
            lyrics_ms = r["lyrics_ms"]
            times.append(lyrics_ms)
            print(f"| {lyrics_ms:>17}ms ", end="")
        if times[0] > 0:
            delta_pct = ((times[1] - times[0]) / times[0]) * 100
            print(f"| {delta_pct:>+8.1f}%", end="")
        else:
            print(f"| {'---':>10}", end="")
        print()

    # Median/mean summary
    print("-" * 120)
    for stat_name, stat_fn in [("Median", lambda vals: sorted(vals)[len(vals) // 2]),
                                ("Mean", lambda vals: sum(vals) / len(vals))]:
        print(f"{stat_name + ' lyrics_ms':<55} ", end="")
        times = []
        for name in config_names:
            vals = [r["lyrics_ms"] for r in all_results[name] if not r["error"]]
            s = int(stat_fn(vals)) if vals else 0
            times.append(s)
            print(f"| {s:>17}ms ", end="")
        if times[0] > 0:
            delta = ((times[1] - times[0]) / times[0]) * 100
            print(f"| {delta:>+8.1f}%", end="")
        print()

    # Total pipeline time
    print()
    print(f"{'Total pipeline time (median)':<55} ", end="")
    pipeline_times = []
    for name in config_names:
        vals = [r["total_ms"] for r in all_results[name] if not r["error"]]
        med = sorted(vals)[len(vals) // 2] if vals else 0
        pipeline_times.append(med)
        print(f"| {med:>17}ms ", end="")
    if pipeline_times[0] > 0:
        delta = ((pipeline_times[1] - pipeline_times[0]) / pipeline_times[0]) * 100
        print(f"| {delta:>+8.1f}%", end="")
    print()

    print("=" * 120)

    # ── Side-by-side lyrics comparison ────────────────────────────────────
    print("\n\n")
    print("=" * 120)
    print("LYRICS QUALITY COMPARISON (side by side)")
    print("=" * 120)

    for i, tc in enumerate(test_cases):
        print(f"\n{'─'*120}")
        print(f"TEST CASE {i+1}: {tc['name']}")
        print(f"  Prompt: {tc['user_prompt']}")
        print(f"  About:  {tc['lyrics_about']}")
        print(f"  Artists: {', '.join(tc.get('selected_artists', [])) or 'none'}")
        print(f"{'─'*120}")

        for config_name in config_names:
            r = all_results[config_name][i]
            print(f"\n  ┌── {config_name} ──────────────────────────────────")
            print(f"  │ Title: {r['concept_title']}")
            print(f"  │ Time: {r['total_ms']}ms total, {r['lyrics_ms']}ms lyrics")
            print(f"  │ Repairs: {r['repairs']}")
            if r["error"]:
                print(f"  │ ERROR: {r['error']}")
            else:
                # Print full lyrics with indent
                print(f"  │")
                print(f"  │ LYRICS:")
                for line in r["lyrics"].split("\n"):
                    print(f"  │   {line}")
            print(f"  └{'─'*60}")

    # ── Save results ──────────────────────────────────────────────────────
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_path = OUTPUT_DIR / f"lyrics_comparison_{timestamp}.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nFull results saved to: {results_path}")


if __name__ == "__main__":
    asyncio.run(main())
