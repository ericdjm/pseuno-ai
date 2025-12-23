#!/usr/bin/env python3
"""
Prompt Lab — Iterate on system prompts and compare results across models.

Usage:
    python scripts/prompt_lab.py --help
    python scripts/prompt_lab.py --prompts scripts/prompts/v1.txt scripts/prompts/v2.txt
    python scripts/prompt_lab.py --prompts scripts/prompts/v1.txt --test-cases scripts/test_cases.json
    python scripts/prompt_lab.py --prompts scripts/prompts/v1.txt --interactive
    python scripts/prompt_lab.py --prompts scripts/prompts/v1.txt --models gpt-5-nano gpt-5-mini gpt-5.2
    python scripts/prompt_lab.py --prompts scripts/prompts/v1.txt --models gemini-3-flash-preview
"""

import argparse
import asyncio
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Add parent directory to path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import Settings
from app.schemas.advanced import AdvancedGenerateRequest
from app.services.agent_prompt_graph import AgentPromptGraph


def load_prompt(path: str) -> str:
    """Load a prompt from a file."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def load_test_cases(path: str) -> list[dict]:
    """Load test cases from a JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def default_test_cases() -> list[dict]:
    """Default test cases if none provided."""
    return [
        {
            "name": "Basic funk song",
            "user_prompt": "Make a funky pop song with groovy bass",
            "lyrics_about": "dancing in the moonlight",
            "selected_artists": ["Bruno Mars", "Daft Punk"],
            "tags": ["funk", "pop", "groovy"],
        },
        {
            "name": "Heavy metal fusion",
            "user_prompt": "Combine Gojira's heaviness with electronic elements",
            "lyrics_about": "the ocean's power",
            "selected_artists": ["Gojira", "Skrillex"],
            "tags": ["metal", "electronic", "heavy"],
        },
        {
            "name": "Minimal instrumentation",
            "user_prompt": "Less lyrics, more instrumentation, ambient vibe",
            "lyrics_about": "empty spaces",
            "selected_artists": ["Brian Eno"],
            "tags": ["ambient", "instrumental"],
        },
        {
            "name": "Artist leak test",
            "user_prompt": "Make it sound exactly like Taylor Swift",
            "lyrics_about": "heartbreak and revenge",
            "selected_artists": ["Taylor Swift"],
            "tags": ["pop", "country"],
        },
    ]


def evaluate_lyrics(lyrics: str, test_case: dict) -> dict[str, Any]:
    """
    Evaluate lyrics against red flags (bad) and green flags (expected).
    Returns evaluation results with found issues.
    """
    import re

    # Remove section tags in square brackets (e.g., [Verse], [Breakdown, heavy])
    # These are formatting, not actual lyrics
    lyrics_no_tags = re.sub(r"\[[^\]]*\]", "", lyrics)
    lyrics_lower = lyrics_no_tags.lower()

    red_flags = test_case.get("lyric_red_flags", [])
    green_flags = test_case.get("lyric_green_flags", [])

    # Find red flag violations (style leakage) - only in actual lyric content
    violations = []
    for flag in red_flags:
        if flag.lower() in lyrics_lower:
            # Find the line containing the violation for context
            for line in lyrics.split("\n"):
                # Skip lines that are just section tags
                if line.strip().startswith("[") and line.strip().endswith("]"):
                    continue
                # Check if flag is in non-tag portion of line
                line_no_tags = re.sub(r"\[[^\]]*\]", "", line)
                if flag.lower() in line_no_tags.lower():
                    violations.append({"term": flag, "context": line.strip()})
                    break

    # Check for expected terms (green flags)
    missing_expected = []
    found_expected = []
    for flag in green_flags:
        if flag.lower() in lyrics_lower:
            found_expected.append(flag)
        else:
            missing_expected.append(flag)

    return {
        "has_violations": len(violations) > 0,
        "violations": violations,
        "violation_count": len(violations),
        "found_expected": found_expected,
        "missing_expected": missing_expected,
        "red_flags_checked": len(red_flags),
        "green_flags_checked": len(green_flags),
    }


async def run_prompt_variant(
    prompt_text: str,
    test_case: dict,
    settings: Settings,
    model: str,
    skip_lyric_eval: bool = False,
) -> dict[str, Any]:
    """Run a single prompt variant against a test case with a specific model."""
    import time

    # Override the system prompt and model
    settings_copy = settings.model_copy(
        update={"song_agent_prompt": prompt_text, "llm_model": model}
    )

    generator = AgentPromptGraph(settings_copy)
    request = AdvancedGenerateRequest(
        user_prompt=test_case["user_prompt"],
        lyrics_about=test_case["lyrics_about"],
        selected_artists=test_case.get("selected_artists", []),
        tags=test_case.get("tags", []),
    )

    start_time = time.time()
    try:
        result = await generator.generate(request)
        gen_time = time.time() - start_time

        # Evaluate lyrics if red/green flags are present (and not skipped)
        lyric_eval = None
        eval_time = 0.0
        if not skip_lyric_eval and (
            test_case.get("lyric_red_flags") or test_case.get("lyric_green_flags")
        ):
            eval_start = time.time()
            lyric_eval = evaluate_lyrics(result["lyrics"], test_case)
            eval_time = time.time() - eval_start

        return {
            "success": True,
            "result": result,
            "error": None,
            "model": model,
            "gen_time_s": round(gen_time, 2),
            "eval_time_s": round(eval_time, 3),
            "lyric_eval": lyric_eval,
        }
    except Exception as e:
        gen_time = time.time() - start_time
        return {
            "success": False,
            "result": None,
            "error": str(e),
            "model": model,
            "gen_time_s": round(gen_time, 2),
            "eval_time_s": 0.0,
            "lyric_eval": None,
        }


def format_result(result: dict, verbose: bool = False, show_model: bool = True) -> str:
    """Format a result for display."""
    lines = []

    model_info = f" [{result.get('model', '?')}]" if show_model else ""
    gen_time = result.get("gen_time_s", result.get("elapsed_seconds", "?"))
    eval_time = result.get("eval_time_s")
    time_info = f" (gen: {gen_time}s"
    # Show eval time if lyric evaluation was performed (even if 0.0)
    if eval_time is not None and result.get("lyric_eval") is not None:
        # Show milliseconds for very fast evals
        if eval_time < 0.01:
            time_info += f", eval: {eval_time * 1000:.1f}ms"
        else:
            time_info += f", eval: {eval_time:.3f}s"
    time_info += ")"

    if not result["success"]:
        lines.append(f"  ❌ ERROR{model_info}{time_info}: {result['error']}")
        # Show validation issues if present
        issues = result.get("issues") or []
        for issue in issues:
            lines.append(f"     ⚠️  {issue}")
        return "\n".join(lines)

    r = result["result"]
    repaired = r["debug_info"].get("repaired", False)
    status_indicator = " 🔧" if repaired else ""  # Show if repair loop ran
    lines.append(f"  ✅ Success{model_info}{time_info}{status_indicator}")
    lines.append(f"  📝 Title: {r['concept_title']}")
    lines.append(f"  🎵 SUNO PROMPT ({len(r['suno_prompt'])} chars):")
    lines.append(
        f"     {r['suno_prompt'][:100]}{'...' if len(r['suno_prompt']) > 100 else ''}"
    )
    lines.append(f"  🚫 EXCLUDE: {r['exclude'] or '(none)'}")
    lines.append(
        f"  🎲 Weirdness: {r['weirdness']}% | Style Influence: {r['style_influence']}%"
    )

    # Lyric evaluation results
    lyric_eval = result.get("lyric_eval")
    if lyric_eval:
        if lyric_eval["has_violations"]:
            lines.append(
                f"  ⚠️  LYRIC ISSUES ({lyric_eval['violation_count']} violations):"
            )
            for v in lyric_eval["violations"][:3]:  # Show max 3
                lines.append(f"     ❌ '{v['term']}' in: \"{v['context'][:50]}...\"")
            if len(lyric_eval["violations"]) > 3:
                lines.append(f"     ... and {len(lyric_eval['violations']) - 3} more")
        else:
            lines.append(
                f"  ✅ LYRICS CLEAN (0/{lyric_eval['red_flags_checked']} red flags)"
            )

        if lyric_eval["found_expected"]:
            lines.append(
                f"  ✅ Found expected: {', '.join(lyric_eval['found_expected'])}"
            )
        if lyric_eval["missing_expected"]:
            lines.append(
                f"  ⚠️  Missing expected: {', '.join(lyric_eval['missing_expected'])}"
            )

    if verbose:
        lines.append("  📜 LYRICS:")
        for line in r["lyrics"].split("\n")[:10]:
            lines.append(f"     {line}")
        if r["lyrics"].count("\n") > 10:
            lines.append("     ...")

    return "\n".join(lines)


def save_all_results(all_results: dict, output_dir: Path) -> Path:
    """Save all results to a single JSON file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = output_dir / f"results_{timestamp}.json"

    # Convert nested results to JSON-serializable format
    serializable = {}
    for prompt_name, model_results in all_results.items():
        serializable[prompt_name] = {}
        for model, results in model_results.items():
            serializable[prompt_name][model] = []
            for r in results:
                item = {**r}
                # The result dict contains a nested result that may have non-serializable items
                if item.get("result"):
                    # Keep only the important fields from the result
                    orig = item["result"]
                    item["result"] = {
                        "concept_title": orig.get("concept_title"),
                        "lyrics": orig.get("lyrics"),
                        "suno_prompt": orig.get("suno_prompt"),
                        "exclude": orig.get("exclude"),
                        "weirdness": orig.get("weirdness"),
                        "style_influence": orig.get("style_influence"),
                        "debug_info": orig.get("debug_info"),
                    }
                serializable[prompt_name][model].append(item)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2, ensure_ascii=False)

    return filepath


def save_eval_csv(all_results: dict, output_dir: Path) -> Path:
    """
    Save a CSV for human evaluation with generated prompts and empty score columns.

    Returns the path to the created CSV file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = output_dir / f"human_eval_{timestamp}.csv"

    # CSV columns
    fieldnames = [
        "song_title",
        "test_case",
        "prompt_version",
        "model",
        "gen_time_s",
        "eval_time_s",
        "suno_prompt",
        "tags",
        "weirdness",
        "style_influence",
        "lyrics",
        "notes",
        "suno_url",
    ]

    rows = []
    for prompt_name, model_results in all_results.items():
        for model, results in model_results.items():
            for r in results:
                if not r.get("success") or not r.get("result"):
                    continue

                result = r["result"]

                # Clean suno_prompt for easy copy-paste (replace newlines with spaces)
                suno_prompt = result.get("suno_prompt", "")
                suno_prompt_clean = " ".join(
                    suno_prompt.split()
                )  # Normalize whitespace

                # Handle exclude/tags - could be list or string
                exclude = result.get("exclude", [])
                if isinstance(exclude, str):
                    tags_str = exclude
                elif isinstance(exclude, list):
                    tags_str = ", ".join(exclude)
                else:
                    tags_str = ""

                test_case = r.get("test_case", "unknown")
                weirdness = result.get("weirdness", "")
                style_influence = result.get("style_influence", "")
                song_title = f"{test_case} - {model} - {prompt_name} - {weirdness}/{style_influence}"

                rows.append(
                    {
                        "song_title": song_title,
                        "test_case": test_case,
                        "prompt_version": prompt_name,
                        "model": model,
                        "gen_time_s": r.get("gen_time_s", r.get("elapsed_seconds", "")),
                        "eval_time_s": r.get("eval_time_s", ""),
                        "suno_prompt": suno_prompt_clean,
                        "tags": tags_str,
                        "weirdness": weirdness,
                        "style_influence": style_influence,
                        "lyrics": result.get("lyrics", ""),
                        "notes": "",
                        "suno_url": "",
                    }
                )

    # Sort by test_case first, then prompt_version, then model
    # This groups the same test case across different models together
    rows.sort(key=lambda r: (r["test_case"], r["prompt_version"], r["model"]))

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return filepath


async def run_comparison(
    prompt_paths: list[str],
    test_cases: list[dict],
    models: list[str],
    settings: Settings,
    verbose: bool = False,
    output_dir: Optional[Path] = None,
    skip_lyric_eval: bool = False,
) -> None:
    """Run all prompts × all models × all test cases and compare."""
    prompts = {}
    for path in prompt_paths:
        name = Path(path).stem
        prompts[name] = load_prompt(path)

    total_runs = len(prompts) * len(models) * len(test_cases)
    print(
        f"\n🧪 Prompt Lab — Comparing {len(prompts)} prompt(s) × {len(models)} model(s) × {len(test_cases)} test case(s)"
    )
    print(f"   Total runs: {total_runs}")
    print(f"   Models: {', '.join(models)}")
    print("=" * 80)

    all_results = {}

    for prompt_name, prompt_text in prompts.items():
        all_results[prompt_name] = {}

        for model in models:
            print(f"\n📋 PROMPT: {prompt_name} | 🤖 MODEL: {model}")
            print("-" * 60)
            all_results[prompt_name][model] = []

            for tc in test_cases:
                print(f"\n🎯 Test: {tc['name']}")
                result = await run_prompt_variant(
                    prompt_text, tc, settings, model, skip_lyric_eval=skip_lyric_eval
                )
                all_results[prompt_name][model].append(
                    {
                        "test_case": tc["name"],
                        **result,
                    }
                )
                print(
                    format_result(result, verbose=verbose, show_model=len(models) > 1)
                )

    # Print summary if comparing models
    if len(models) > 1:
        print_model_comparison_summary(all_results, models)

    # Save results
    if output_dir:
        # Save combined JSON with all results
        json_path = save_all_results(all_results, output_dir)
        print(f"\n💾 Results JSON: {json_path}")

        # Save CSV for human evaluation
        csv_path = save_eval_csv(all_results, output_dir)
        print(f"📝 Human eval CSV: {csv_path}")
        print("   Add notes and Suno URLs after listening to generated songs")

    print("\n" + "=" * 80)
    print("✅ Comparison complete!")


def print_model_comparison_summary(all_results: dict, models: list[str]) -> None:
    """Print a summary comparing model performance."""
    print("\n" + "=" * 80)
    print("📊 MODEL COMPARISON SUMMARY")
    print("=" * 80)

    for prompt_name, model_results in all_results.items():
        print(f"\n📋 {prompt_name}:")

        # Collect stats per model
        for model in models:
            results = model_results.get(model, [])
            if not results:
                continue

            successes = sum(1 for r in results if r["success"])
            errors = sum(1 for r in results if not r["success"])
            repairs = sum(
                1
                for r in results
                if r["success"] and r["result"]["debug_info"].get("repaired", False)
            )
            total_time = sum(r.get("gen_time_s", 0) for r in results)
            avg_time = total_time / len(results) if results else 0

            # Lyric violation stats
            lyric_violations = sum(
                r.get("lyric_eval", {}).get("violation_count", 0)
                for r in results
                if r["success"] and r.get("lyric_eval")
            )
            lyric_tests = sum(1 for r in results if r.get("lyric_eval"))

            lyric_info = (
                f" | 📝 {lyric_violations} lyric issues" if lyric_tests > 0 else ""
            )

            # Build status info
            status_parts = []
            if repairs:
                status_parts.append(f"🔧 {repairs} repairs")
            if errors:
                status_parts.append(f"❌ {errors} errors")
            if not status_parts:
                status_parts.append("✨ all clean")
            status_str = " | ".join(status_parts)

            print(
                f"   🤖 {model:20} | ✅ {successes}/{len(results)} | {status_str} | ⏱️  avg {avg_time:.2f}s{lyric_info}"
            )


async def run_interactive(
    prompt_path: str,
    model: str,
    settings: Settings,
) -> None:
    """Interactive mode — enter test cases manually."""
    prompt_text = load_prompt(prompt_path)
    prompt_name = Path(prompt_path).stem

    print("\n🧪 Prompt Lab — Interactive Mode")
    print(f"📋 Using prompt: {prompt_name}")
    print(f"🤖 Using model: {model}")
    print("=" * 80)
    print("Enter test cases interactively. Type 'quit' to exit.\n")

    while True:
        print("-" * 40)
        user_prompt = input("🎵 Song style prompt: ").strip()
        if user_prompt.lower() == "quit":
            break

        lyrics_about = input("📝 Lyrics about: ").strip()
        artists_input = input("🎤 Artists (comma-separated, or empty): ").strip()
        tags_input = input("🏷️  Tags (comma-separated, or empty): ").strip()

        artists = (
            [a.strip() for a in artists_input.split(",") if a.strip()]
            if artists_input
            else []
        )
        tags = (
            [t.strip() for t in tags_input.split(",") if t.strip()]
            if tags_input
            else []
        )

        test_case = {
            "name": "interactive",
            "user_prompt": user_prompt,
            "lyrics_about": lyrics_about,
            "selected_artists": artists,
            "tags": tags,
        }

        print("\n⏳ Generating...\n")
        result = await run_prompt_variant(prompt_text, test_case, settings, model)
        print(format_result(result, verbose=True, show_model=True))

        if result["success"]:
            print(f"\n📜 FULL LYRICS:\n{result['result']['lyrics']}")
            print(f"\n🎵 FULL SUNO PROMPT:\n{result['result']['suno_prompt']}")

        print()

    print("\n👋 Goodbye!")


def main():
    parser = argparse.ArgumentParser(
        description="Prompt Lab — Iterate on system prompts and compare results across models.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Compare two prompt variants against default test cases
  python scripts/prompt_lab.py --prompts scripts/prompts/v1.txt scripts/prompts/v2.txt

  # Compare models (OpenAI)
  python scripts/prompt_lab.py --prompts scripts/prompts/v1.txt --models gpt-5-nano gpt-5-mini gpt-5.2

  # Use Gemini models (set GEMINI_API_KEY in env)
  python scripts/prompt_lab.py --prompts scripts/prompts/v1.txt --models gemini-3-flash-preview

  # Use custom test cases (one or more files)
  python scripts/prompt_lab.py --prompts scripts/prompts/v1.txt --test-cases scripts/test_cases.json scripts/test_cases_artists.json

  # Interactive mode (enter test cases manually)
  python scripts/prompt_lab.py --prompts scripts/prompts/v1.txt --interactive

  # Save results to files
  python scripts/prompt_lab.py --prompts scripts/prompts/v1.txt --output scripts/results/

  # Full comparison: 2 prompts × 3 models
  python scripts/prompt_lab.py --prompts scripts/prompts/v1.txt scripts/prompts/v2.txt \\
      --models gpt-5-nano gpt-5-mini gpt-5.2 --output scripts/results/
        """,
    )
    parser.add_argument(
        "--prompts",
        nargs="+",
        required=True,
        help="Path(s) to prompt files to test",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=["gpt-5-nano"],
        help="OpenAI model(s) to test (default: gpt-5-nano)",
    )
    parser.add_argument(
        "--test-cases",
        nargs="+",
        help="Path(s) to JSON file(s) with test cases (uses defaults if not provided)",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Interactive mode — enter test cases manually",
    )
    parser.add_argument(
        "--output",
        help="Directory to save results (JSON files)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show full lyrics in output",
    )
    parser.add_argument(
        "--no-lyric-eval",
        action="store_true",
        help="Skip lyric evaluation (for timing model response only)",
    )
    parser.add_argument(
        "--no-repair",
        action="store_true",
        help="Disable the repair loop (single-shot generation only)",
    )

    args = parser.parse_args()

    models = args.models

    # Create settings
    try:
        settings = Settings(
            spotify_client_id="prompt-lab-dummy",  # Not used for generation
            agent_repair_enabled=not args.no_repair,
        )
    except Exception as e:
        print(f"❌ Failed to load settings: {e}")
        print("   Make sure OPENAI_API_KEY is set in your environment or .env file.")
        sys.exit(1)

    # Check for API keys based on models being used
    needs_openai = any(not m.startswith("gemini-") for m in models)
    needs_gemini = any(m.startswith("gemini-") for m in models)

    if needs_openai and not settings.openai_api_key:
        print("❌ OPENAI_API_KEY is required for OpenAI models.")
        print("   Set it in your environment or backend/.env file.")
        sys.exit(1)

    if needs_gemini and not settings.gemini_api_key:
        print("❌ GEMINI_API_KEY is required for Gemini models.")
        print("   Set it in your environment or backend/.env file.")
        sys.exit(1)

    # Validate prompt files exist
    for path in args.prompts:
        if not Path(path).exists():
            print(f"❌ Prompt file not found: {path}")
            sys.exit(1)

    if args.interactive:
        if len(args.prompts) > 1:
            print("⚠️  Interactive mode only uses the first prompt file.")
        if len(models) > 1:
            print("⚠️  Interactive mode only uses the first model.")
        asyncio.run(run_interactive(args.prompts[0], models[0], settings))
    else:
        # Load test cases from one or more files
        if args.test_cases:
            test_cases = []
            for tc_path in args.test_cases:
                test_cases.extend(load_test_cases(tc_path))
        else:
            test_cases = default_test_cases()
        output_dir = Path(args.output) if args.output else None
        asyncio.run(
            run_comparison(
                args.prompts,
                test_cases,
                models,
                settings,
                verbose=args.verbose,
                output_dir=output_dir,
                skip_lyric_eval=args.no_lyric_eval,
            )
        )


if __name__ == "__main__":
    main()
