#!/usr/bin/env python3
"""
Speed Benchmark — Measure the impact of pipeline optimizations.

Usage:
    # Quick validation (2 test cases, 1 run, baseline only):
    python prompt_lab/speed_bench.py --experiments baseline --runs 1 --quick

    # Single experiment:
    python prompt_lab/speed_bench.py --experiments baseline max_tokens_style --runs 3

    # All experiments (parallel by default):
    python prompt_lab/speed_bench.py --runs 3

    # Control parallelism (default: 3 concurrent generations):
    python prompt_lab/speed_bench.py --runs 3 --parallel 4

    # Sequential mode (like before):
    python prompt_lab/speed_bench.py --runs 3 --parallel 1

    # Combined experiment (stacks all winners after individual runs):
    python prompt_lab/speed_bench.py --experiments combined --runs 3
"""

import argparse
import asyncio
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent directory to path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))
# Also add prompt_lab directory for sibling imports
sys.path.insert(0, str(Path(__file__).parent))

from app.config import Settings
from app.schemas.advanced import AdvancedGenerateRequest
from experiments import (
    ALL_EXPERIMENTS,
    EXPERIMENTS_BY_NAME,
    ExperimentConfig,
    apply_experiment,
)


OUTPUT_DIR = Path(__file__).parent / "results" / "speed_bench"

# Span names we extract per-operation timing for
TRACKED_SPANS = [
    "style.genre_disambiguate",
    "style.generate",
    "style.name_generate",
    "lyrics.profile_infer",
    "lyrics.generate",
]


def load_test_cases(path: Optional[str] = None) -> List[dict]:
    """Load test cases from JSON."""
    if path:
        p = Path(path)
    else:
        p = Path(__file__).parent / "test_cases" / "test_cases_speed_bench.json"
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_span_timings(debug_info: dict) -> Dict[str, int]:
    """Extract per-span elapsed_ms from debug_info."""
    timings: Dict[str, int] = {}
    if not debug_info:
        return timings
    for span in debug_info.get("spans", []):
        name = span.get("name", "")
        elapsed = span.get("elapsed_ms", 0)
        # For tracked spans, record the timing (first occurrence wins)
        if name in TRACKED_SPANS and name not in timings:
            timings[name] = elapsed
        # Aggregate repair spans
        if ".repair." in name:
            timings.setdefault("repairs_total_ms", 0)
            timings["repairs_total_ms"] += elapsed
    # Total from summary
    summary = debug_info.get("summary", {})
    timings["total_ms"] = summary.get("total_elapsed_ms", 0)
    timings["llm_calls"] = summary.get("llm_calls", 0)
    timings["repairs"] = summary.get("repairs", 0)
    return timings


def evaluate_quality(result: dict) -> Dict[str, Any]:
    """Evaluate quality signals from a generation result."""
    signals: Dict[str, Any] = {}

    # Check for truncation indicators
    suno = result.get("suno_prompt", "")
    lyrics = result.get("lyrics", "")
    signals["suno_prompt_chars"] = len(suno)
    signals["lyrics_chars"] = len(lyrics)
    signals["has_title"] = bool(result.get("concept_title", "").strip())
    signals["has_lyrics"] = bool(lyrics.strip())
    signals["has_suno_prompt"] = bool(suno.strip())

    # Count lyric section tags
    import re
    section_tags = re.findall(r"\[.*?\]", lyrics)
    signals["section_count"] = len(section_tags)

    # Check suno prompt length constraint (<=500)
    signals["suno_prompt_over_500"] = len(suno) > 500

    # Repair count from debug_info
    debug = result.get("debug_info", {})
    signals["repairs"] = debug.get("summary", {}).get("repairs", 0)
    signals["success"] = debug.get("summary", {}).get("success", False)

    return signals


def quality_verdict(signals: Dict[str, Any]) -> str:
    """Return PASS/WATCH/FAIL based on quality signals."""
    if not signals.get("success"):
        return "FAIL"
    if not signals.get("has_lyrics") or not signals.get("has_suno_prompt"):
        return "FAIL"
    if signals.get("suno_prompt_over_500"):
        return "WATCH"
    if signals.get("section_count", 0) < 3:
        return "WATCH"
    if signals.get("repairs", 0) >= 2:
        return "WATCH"
    return "PASS"


async def run_single(
    graph,
    test_case: dict,
    experiment_name: str,
    run_idx: int,
    variant: str = "v10_suno_friendly",
    semaphore: Optional[asyncio.Semaphore] = None,
) -> Dict[str, Any]:
    """Run a single test case and return timing + quality data."""
    request = AdvancedGenerateRequest(
        user_prompt=test_case["user_prompt"],
        lyrics_about=test_case["lyrics_about"],
        selected_artists=test_case.get("selected_artists", []),
        tags=test_case.get("tags", []),
        prompt_variant=variant,
    )

    async def _do_generate():
        wall_start = time.time()
        try:
            result = await graph.generate(request)
            wall_ms = int((time.time() - wall_start) * 1000)

            timings = extract_span_timings(result.get("debug_info", {}))
            quality = evaluate_quality(result)
            verdict = quality_verdict(quality)

            return {
                "experiment": experiment_name,
                "test_case": test_case["name"],
                "run": run_idx,
                "wall_ms": wall_ms,
                "timings": timings,
                "quality": quality,
                "verdict": verdict,
                "error": None,
                "result_summary": {
                    "concept_title": result.get("concept_title", ""),
                    "suno_prompt_preview": (result.get("suno_prompt", ""))[:150],
                    "lyrics_preview": (result.get("lyrics", ""))[:200],
                    "style_name": result.get("style_name", ""),
                },
            }
        except Exception as e:
            wall_ms = int((time.time() - wall_start) * 1000)
            return {
                "experiment": experiment_name,
                "test_case": test_case["name"],
                "run": run_idx,
                "wall_ms": wall_ms,
                "timings": {"total_ms": wall_ms},
                "quality": {},
                "verdict": "FAIL",
                "error": str(e),
                "result_summary": None,
            }

    if semaphore:
        async with semaphore:
            return await _do_generate()
    return await _do_generate()


async def run_experiment(
    settings: Settings,
    config: ExperimentConfig,
    test_cases: List[dict],
    runs: int,
    variant: str = "v10_suno_friendly",
    semaphore: Optional[asyncio.Semaphore] = None,
) -> List[Dict[str, Any]]:
    """Run all test cases x runs for a single experiment.

    When a semaphore is provided, individual generations are gated by it,
    allowing multiple experiments to interleave their calls safely.
    """
    graph = apply_experiment(settings, config)

    # Launch all (test_case, run) pairs as concurrent tasks gated by semaphore
    tasks = []
    for tc in test_cases:
        for run_idx in range(runs):
            tasks.append(
                run_single(graph, tc, config.name, run_idx, variant=variant, semaphore=semaphore)
            )

    results = await asyncio.gather(*tasks)
    return list(results)


def compute_summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute aggregate statistics for an experiment's results."""
    successful = [r for r in results if r["error"] is None]
    total_times = [r["timings"].get("total_ms", r["wall_ms"]) for r in successful]

    if not total_times:
        return {
            "median_ms": 0,
            "mean_ms": 0,
            "p90_ms": 0,
            "min_ms": 0,
            "max_ms": 0,
            "success_rate": 0.0,
            "avg_repairs": 0.0,
            "verdicts": {"PASS": 0, "WATCH": 0, "FAIL": len(results)},
            "per_span_median": {},
        }

    # Per-span medians
    per_span: Dict[str, List[int]] = {}
    for r in successful:
        for span_name in TRACKED_SPANS:
            if span_name in r["timings"]:
                per_span.setdefault(span_name, []).append(r["timings"][span_name])

    per_span_median = {k: int(statistics.median(v)) for k, v in per_span.items()}

    # Verdict counts
    verdicts = {"PASS": 0, "WATCH": 0, "FAIL": 0}
    for r in results:
        verdicts[r["verdict"]] = verdicts.get(r["verdict"], 0) + 1

    sorted_times = sorted(total_times)
    p90_idx = max(0, int(len(sorted_times) * 0.9) - 1)

    return {
        "median_ms": int(statistics.median(total_times)),
        "mean_ms": int(statistics.mean(total_times)),
        "p90_ms": sorted_times[p90_idx],
        "min_ms": min(total_times),
        "max_ms": max(total_times),
        "success_rate": len(successful) / len(results),
        "avg_repairs": statistics.mean(
            [r["timings"].get("repairs", 0) for r in successful]
        ) if successful else 0,
        "verdicts": verdicts,
        "per_span_median": per_span_median,
    }


def print_comparison_table(
    all_summaries: Dict[str, Dict[str, Any]],
    baseline_name: str = "baseline",
):
    """Print a formatted comparison table."""
    baseline = all_summaries.get(baseline_name)
    baseline_median = baseline["median_ms"] if baseline else 0

    print("\n" + "=" * 100)
    print("SPEED BENCHMARK COMPARISON")
    print("=" * 100)

    header = f"{'Experiment':<28} | {'Median':>8} | {'vs Base':>8} | {'p90':>8} | {'Repairs':>8} | {'Quality':>8}"
    print(header)
    print("-" * 100)

    for name, summary in all_summaries.items():
        median = summary["median_ms"]
        p90 = summary["p90_ms"]
        repairs = f"{summary['avg_repairs']:.2f}"

        if name == baseline_name or not baseline_median:
            vs_base = "---"
        else:
            pct = ((median - baseline_median) / baseline_median) * 100
            vs_base = f"{pct:+.1f}%"

        # Quality = PASS if all PASS, WATCH if any WATCH, FAIL if any FAIL
        verdicts = summary["verdicts"]
        if verdicts.get("FAIL", 0) > 0:
            quality = "FAIL"
        elif verdicts.get("WATCH", 0) > 0:
            quality = "WATCH"
        else:
            quality = "PASS"

        print(
            f"{name:<28} | {median:>7}ms | {vs_base:>8} | {p90:>7}ms | {repairs:>8} | {quality:>8}"
        )

    print("=" * 100)

    # Per-span breakdown
    print("\nPER-SPAN MEDIAN (ms):")
    print("-" * 100)
    span_header = f"{'Experiment':<28}"
    for span in TRACKED_SPANS:
        short = span.split(".")[-1][:12]
        span_header += f" | {short:>12}"
    print(span_header)
    print("-" * 100)

    for name, summary in all_summaries.items():
        row = f"{name:<28}"
        for span in TRACKED_SPANS:
            val = summary["per_span_median"].get(span)
            row += f" | {val:>11}ms" if val is not None else f" | {'---':>12}"
        print(row)
    print("-" * 100)


def save_results(
    all_results: Dict[str, List[Dict[str, Any]]],
    all_summaries: Dict[str, Dict[str, Any]],
):
    """Save full results and summaries to JSON."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Full results
    results_path = OUTPUT_DIR / f"results_{timestamp}.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nFull results saved to: {results_path}")

    # Summary table
    summary_path = OUTPUT_DIR / f"summary_{timestamp}.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(all_summaries, f, indent=2, ensure_ascii=False, default=str)
    print(f"Summary saved to: {summary_path}")


async def main():
    parser = argparse.ArgumentParser(description="Speed optimization benchmark harness")
    parser.add_argument(
        "--experiments",
        nargs="*",
        default=None,
        help="Experiment names to run (default: all). Use 'combined' to build a stacked config.",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Number of runs per test case (default: 3)",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick mode: use only first 2 test cases",
    )
    parser.add_argument(
        "--test-cases",
        type=str,
        default=None,
        help="Path to test cases JSON (default: test_cases_speed_bench.json)",
    )
    parser.add_argument(
        "--variant",
        type=str,
        default="v10_suno_friendly",
        help="Prompt variant to use (default: v10_suno_friendly)",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=3,
        help="Max concurrent generations across all experiments (default: 3). Use 1 for sequential.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=5.0,
        help="Percent speedup threshold for 'combined' experiment (default: 5.0)",
    )

    args = parser.parse_args()

    # Load settings
    settings = Settings()
    print(f"Style model: {settings.style_model}")
    print(f"Lyrics model: {settings.lyrics_model}")
    print(f"Genre disambiguation model: {settings.genre_disambiguation_model}")
    print(f"Profile inference model: {settings.profile_inference_model}")
    print(f"Title generation model: {settings.title_generation_model}")
    print(f"Variant: {args.variant}")
    print(f"Parallelism: {args.parallel} concurrent generations")

    # Load test cases
    test_cases = load_test_cases(args.test_cases)
    if args.quick:
        test_cases = test_cases[:2]
    print(f"\nTest cases: {len(test_cases)}, Runs per case: {args.runs}")

    # Determine experiments to run
    if args.experiments:
        experiment_names = args.experiments
    else:
        experiment_names = [e.name for e in ALL_EXPERIMENTS]

    # Handle 'combined' — run all individual experiments first, then stack winners
    run_combined = "combined" in experiment_names
    if run_combined:
        experiment_names = [n for n in experiment_names if n != "combined"]
        # Ensure baseline is included
        if "baseline" not in experiment_names:
            experiment_names.insert(0, "baseline")

    experiments = []
    for name in experiment_names:
        if name in EXPERIMENTS_BY_NAME:
            experiments.append(EXPERIMENTS_BY_NAME[name])
        else:
            print(f"WARNING: Unknown experiment '{name}', skipping.")

    if not experiments:
        print("No experiments to run!")
        return

    # Global semaphore limits concurrent generations across all experiments
    semaphore = asyncio.Semaphore(args.parallel)

    # ── Run all experiments concurrently ──────────────────────────────────
    total_gens = len(experiments) * len(test_cases) * args.runs
    print(f"\nLaunching {len(experiments)} experiments ({total_gens} total generations, max {args.parallel} concurrent)...")

    async def _run_one(exp: ExperimentConfig) -> tuple:
        """Run a single experiment and return (name, results)."""
        results = await run_experiment(
            settings, exp, test_cases, args.runs,
            variant=args.variant, semaphore=semaphore,
        )
        return exp.name, results

    # Fire all experiments concurrently — the semaphore gates actual API calls
    exp_tasks = [_run_one(exp) for exp in experiments]
    completed_pairs = await asyncio.gather(*exp_tasks)

    all_results: Dict[str, List[Dict[str, Any]]] = {}
    all_summaries: Dict[str, Dict[str, Any]] = {}
    for name, results in completed_pairs:
        all_results[name] = results
        all_summaries[name] = compute_summary(results)

    # Print per-experiment progress summary
    for name in [e.name for e in experiments]:
        summary = all_summaries[name]
        n_pass = summary["verdicts"].get("PASS", 0)
        n_watch = summary["verdicts"].get("WATCH", 0)
        n_fail = summary["verdicts"].get("FAIL", 0)
        total = n_pass + n_watch + n_fail
        print(f"  {name:<28} done  median={summary['median_ms']}ms  "
              f"[{n_pass}P/{n_watch}W/{n_fail}F of {total}]")

    # Build and run 'combined' experiment if requested
    if run_combined and "baseline" in all_summaries:
        baseline_median = all_summaries["baseline"]["median_ms"]
        winners = []
        for name, summary in all_summaries.items():
            if name == "baseline":
                continue
            speedup = ((baseline_median - summary["median_ms"]) / baseline_median) * 100
            has_quality = summary["verdicts"].get("FAIL", 0) == 0
            if speedup >= args.threshold and has_quality:
                winners.append(name)
                print(f"  Winner: {name} ({speedup:+.1f}%)")

        if winners:
            print(f"\nBuilding combined experiment from: {winners}")
            combined = ExperimentConfig(
                name="combined",
                description=f"Stacked winners: {', '.join(winners)}",
            )
            # Merge all winner configs
            for name in winners:
                cfg = EXPERIMENTS_BY_NAME[name]
                if cfg.max_output_tokens_by_model_field:
                    if combined.max_output_tokens_by_model_field is None:
                        combined.max_output_tokens_by_model_field = {}
                    combined.max_output_tokens_by_model_field.update(
                        cfg.max_output_tokens_by_model_field
                    )
                if cfg.thinking_budget_override is not None:
                    combined.thinking_budget_override = cfg.thinking_budget_override
                if cfg.thinking_level_override:
                    combined.thinking_level_override = cfg.thinking_level_override
                if cfg.use_native_async:
                    combined.use_native_async = True
                if cfg.parallel_style_name:
                    combined.parallel_style_name = True
                if cfg.temperature_by_model_field:
                    if combined.temperature_by_model_field is None:
                        combined.temperature_by_model_field = {}
                    combined.temperature_by_model_field.update(
                        cfg.temperature_by_model_field
                    )

            print(f"Running combined experiment...")
            results = await run_experiment(
                settings, combined, test_cases, args.runs,
                variant=args.variant, semaphore=semaphore,
            )
            all_results["combined"] = results
            all_summaries["combined"] = compute_summary(results)
        else:
            print(f"\nNo experiments met the {args.threshold}% threshold for combined.")

    # Print comparison and save
    print_comparison_table(all_summaries)
    save_results(all_results, all_summaries)


if __name__ == "__main__":
    asyncio.run(main())
