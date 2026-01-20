#!/usr/bin/env python3
"""
Diagnostic script to see how tags and style_prompt influence lyrics topic generation.

Usage:
    python scripts/diagnose_lyrics_topic.py
    python scripts/diagnose_lyrics_topic.py --tags "indie rock" "melancholic"
    python scripts/diagnose_lyrics_topic.py --style "dark ethereal shoegaze"
    python scripts/diagnose_lyrics_topic.py --tags "metal" --style "aggressive political anthems about revolution"
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.services.lyrics_topic_generator import LyricsTopicGenerator
from app.services.lyrics_topic_banks import TOPIC_BANKS
from app.services.lyrics_topic_traits import (
    extract_traits_from_style_prompt,
    infer_traits_from_tags,
    merge_traits,
    score_bank_match,
    scores_to_probabilities,
)


def print_section(title: str):
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")


def print_traits(traits: dict, limit: int = 10, indent: str = "  "):
    sorted_traits = sorted(traits.items(), key=lambda x: -x[1])[:limit]
    for k, v in sorted_traits:
        bar = "█" * int(v * 20)
        print(f"{indent}{k:<25} {v:.2f} {bar}")


async def diagnose(tags: list[str], style_prompt: str | None, num_samples: int = 5):
    print_section("INPUT")
    print(f"  Tags: {tags if tags else '(none)'}")
    print(f"  Style prompt: \"{style_prompt}\"" if style_prompt else "  Style prompt: (none)")

    # Extract traits from each source
    tag_traits = infer_traits_from_tags(tags) if tags else {}
    style_traits = extract_traits_from_style_prompt(style_prompt) if style_prompt else {}

    print_section("TRAITS FROM TAGS")
    if tag_traits:
        print_traits(tag_traits)
    else:
        print("  (no traits - no tags provided)")

    print_section("TRAITS FROM STYLE PROMPT")
    if style_traits:
        print_traits(style_traits)
    else:
        print("  (no traits - no style prompt provided)")

    # Merge
    if tag_traits and style_traits:
        merged = merge_traits(tag_traits, style_traits, strategy="max")
    elif tag_traits:
        merged = tag_traits
    elif style_traits:
        merged = style_traits
    else:
        from app.services.lyrics_topic_traits import get_default_traits
        merged = get_default_traits()

    print_section("MERGED TRAITS (used for routing)")
    print_traits(merged, limit=12)

    # Score banks
    bank_scores = {}
    for bank_id, bank in TOPIC_BANKS.items():
        score = score_bank_match(merged, bank.traits)
        bank_scores[bank_id] = score

    probabilities = scores_to_probabilities(bank_scores, temperature=0.7)

    print_section("TOP BANKS BY PROBABILITY")
    sorted_probs = sorted(probabilities.items(), key=lambda x: -x[1])[:10]
    for bank_id, prob in sorted_probs:
        bank = TOPIC_BANKS[bank_id]
        bar = "█" * int(prob * 50)
        print(f"  {bank_id:<30} {prob:.1%} {bar}")
        print(f"      {bank.name}")

    print_section(f"SAMPLE OUTPUTS ({num_samples} generations)")
    for i in range(num_samples):
        gen = LyricsTopicGenerator(seed=i * 1000)
        result = await gen.generate(tags=tags, style_prompt=style_prompt)
        topic_preview = result.topic[:65] + "..." if len(result.topic) > 65 else result.topic
        print(f"\n  [{i+1}] Bank: {result.bank_id}")
        print(f"      Topic: {topic_preview}")

    # Compare: what if we only used tags?
    if style_prompt and tags:
        print_section("COMPARISON: TAGS ONLY vs TAGS + STYLE_PROMPT")
        gen_tags_only = LyricsTopicGenerator(seed=42)
        result_tags_only = await gen_tags_only.generate(tags=tags, style_prompt=None)

        gen_with_style = LyricsTopicGenerator(seed=42)
        result_with_style = await gen_with_style.generate(tags=tags, style_prompt=style_prompt)

        print(f"  With TAGS only:")
        print(f"    Bank: {result_tags_only.bank_id}")
        print(f"    Topic: {result_tags_only.topic[:60]}...")

        print(f"\n  With TAGS + STYLE_PROMPT:")
        print(f"    Bank: {result_with_style.bank_id}")
        print(f"    Topic: {result_with_style.topic[:60]}...")

        changed = result_tags_only.bank_id != result_with_style.bank_id
        print(f"\n  ✅ Style prompt changed the bank? {changed}")

    print("\n")


def main():
    parser = argparse.ArgumentParser(
        description="Diagnose how tags and style_prompt influence lyrics topic generation"
    )
    parser.add_argument(
        "--tags", "-t",
        nargs="+",
        default=[],
        help="Genre/mood tags (e.g., 'indie rock' 'melancholic')"
    )
    parser.add_argument(
        "--style", "-s",
        type=str,
        default=None,
        help="Style prompt text"
    )
    parser.add_argument(
        "--samples", "-n",
        type=int,
        default=5,
        help="Number of sample generations to show"
    )

    args = parser.parse_args()

    # Default demo if no args
    if not args.tags and not args.style:
        print("No args provided - running demo with default inputs...")
        args.tags = ["indie rock"]
        args.style = "dark ethereal shoegaze vibes with haunting melodies about loneliness"

    asyncio.run(diagnose(args.tags, args.style, args.samples))


if __name__ == "__main__":
    main()
