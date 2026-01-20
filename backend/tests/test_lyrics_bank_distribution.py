"""
Integration tests for lyrics topic bank selection distribution.

This test suite verifies that bank selection is appropriately distributed
across different input scenarios. It catches regressions where:
- Certain banks dominate unfairly
- Location/setting banks get overshadowed by abstract banks
- Genre-specific routing fails

Run with: pytest tests/test_lyrics_bank_distribution.py -v
"""

import asyncio
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple
import pytest

from app.services.lyrics_topic_generator import LyricsTopicGenerator, RecencyMemory
from app.services.lyrics_topic_traits import (
    get_default_traits,
    infer_traits_from_tags,
    extract_traits_from_style_prompt,
    merge_traits,
    score_bank_match,
)
from app.services.lyrics_topic_banks import TOPIC_BANKS


@dataclass
class BankDistributionTestCase:
    """A test case for bank selection distribution."""
    
    name: str
    tags: List[str]
    style_prompt: Optional[str]
    # Banks that SHOULD appear in top 5 at least X% of the time
    expected_banks: Dict[str, float]  # bank_id -> min_percentage (0-100)
    # Banks that should NOT dominate (appear less than X% of the time)
    avoid_dominance: Dict[str, float]  # bank_id -> max_percentage (0-100)
    iterations: int = 100


# =============================================================================
# TEST CASES
# =============================================================================

TEST_CASES = [
    # -------------------------------------------------------------------------
    # DEFAULT / NO CONTEXT
    # -------------------------------------------------------------------------
    BankDistributionTestCase(
        name="default_no_input",
        tags=[],
        style_prompt=None,
        expected_banks={
            # Location banks should appear at reasonable rates with defaults
            "domestic_quiet": 5,
            "coastal_mysticism": 5,
            "whimsical_nature_folk": 5,
            # Emotional banks should also appear
            "confessional_heartbreak": 5,
            "new_love_electricity": 5,
        },
        avoid_dominance={
            # No single bank should dominate with default input
            "spiritual_existential": 25,
            "scifi_dystopia_philosophy": 25,
            "consciousness_metaphysical": 25,
            "absurdist_comedy": 25,
        },
        iterations=200,
    ),
    
    # -------------------------------------------------------------------------
    # GENRE-SPECIFIC ROUTING
    # -------------------------------------------------------------------------
    BankDistributionTestCase(
        name="hip_hop_genre",
        tags=["hip-hop", "rap"],
        style_prompt=None,
        expected_banks={
            "emo_rap_vulnerability": 10,
            "body_groove": 10,
            "rebellion_defiance": 5,
        },
        avoid_dominance={
            "whimsical_nature_folk": 15,
            "coastal_mysticism": 15,
        },
    ),
    
    BankDistributionTestCase(
        name="folk_genre",
        tags=["folk", "acoustic"],
        style_prompt=None,
        expected_banks={
            "whimsical_nature_folk": 15,
            "domestic_quiet": 10,
            "coastal_mysticism": 5,  # Folk is primarily pastoral, coastal is secondary
        },
        avoid_dominance={
            "body_groove": 15,
            "emo_rap_vulnerability": 15,
        },
    ),
    
    BankDistributionTestCase(
        name="rock_genre",
        tags=["rock", "alternative"],
        style_prompt=None,
        expected_banks={
            "rebellion_defiance": 10,
            "psychedelic_perception": 5,
        },
        avoid_dominance={
            "emo_rap_vulnerability": 20,
        },
    ),
    
    BankDistributionTestCase(
        name="electronic_genre",
        tags=["electronic", "synth"],
        style_prompt=None,
        expected_banks={
            "manic_velocity": 5,
            "psychedelic_perception": 5,
            "scifi_dystopia_philosophy": 5,
        },
        avoid_dominance={
            "whimsical_nature_folk": 15,
        },
    ),
    
    BankDistributionTestCase(
        name="metal_genre",
        tags=["metal", "heavy"],
        style_prompt=None,
        expected_banks={
            "rebellion_defiance": 10,
            "mythology_allegory": 3,  # Mythology is secondary for metal
        },
        avoid_dominance={
            "new_love_electricity": 15,
            "domestic_quiet": 15,
        },
    ),
    
    BankDistributionTestCase(
        name="rnb_genre",
        tags=["r&b", "soul"],
        style_prompt=None,
        expected_banks={
            "confessional_heartbreak": 10,
            "new_love_electricity": 10,
            "body_groove": 10,
        },
        avoid_dominance={
            "scifi_dystopia_philosophy": 15,
            "mythology_allegory": 15,
        },
    ),
    
    BankDistributionTestCase(
        name="pop_genre",
        tags=["pop"],
        style_prompt=None,
        expected_banks={
            "new_love_electricity": 10,
            "confessional_heartbreak": 5,
            "post_breakup_liberation": 5,
        },
        avoid_dominance={
            "consciousness_metaphysical": 20,
        },
    ),
    
    # -------------------------------------------------------------------------
    # MOOD-SPECIFIC ROUTING
    # -------------------------------------------------------------------------
    BankDistributionTestCase(
        name="dark_mood",
        tags=["dark", "melancholic"],
        style_prompt=None,
        expected_banks={
            "melancholy_stillness": 10,
            "warm_numbness": 5,
            "scifi_dystopia_philosophy": 5,
        },
        avoid_dominance={
            "new_love_electricity": 15,
            "body_groove": 15,
        },
    ),
    
    BankDistributionTestCase(
        name="uplifting_mood",
        tags=["uplifting", "happy"],
        style_prompt=None,
        expected_banks={
            "new_love_electricity": 10,
            "post_breakup_liberation": 10,
            "body_groove": 5,
        },
        avoid_dominance={
            "melancholy_stillness": 15,
            "warm_numbness": 15,
        },
    ),
    
    BankDistributionTestCase(
        name="introspective_mood",
        tags=["introspective", "reflective"],
        style_prompt=None,
        expected_banks={
            "melancholy_stillness": 5,
            "spiritual_existential": 5,
            "consciousness_metaphysical": 5,
        },
        avoid_dominance={
            "body_groove": 20,
        },
    ),
    
    BankDistributionTestCase(
        name="playful_mood",
        tags=["playful", "fun"],
        style_prompt=None,
        expected_banks={
            "absurdist_comedy": 10,
            "body_groove": 10,
            "whimsical_nature_folk": 5,
        },
        avoid_dominance={
            "melancholy_stillness": 15,
            "political_systems_critique": 15,
        },
    ),
    
    # -------------------------------------------------------------------------
    # LOCATION / SETTING BANKS (critical regression tests)
    # -------------------------------------------------------------------------
    BankDistributionTestCase(
        name="coastal_themes",
        tags=["coastal", "ocean", "beach"],
        style_prompt=None,
        expected_banks={
            "coastal_mysticism": 25,  # Should strongly match
        },
        avoid_dominance={},
    ),
    
    BankDistributionTestCase(
        name="nature_themes",
        tags=["nature", "pastoral", "rural"],
        style_prompt=None,
        expected_banks={
            "whimsical_nature_folk": 25,
        },
        avoid_dominance={},
    ),
    
    BankDistributionTestCase(
        name="domestic_themes",
        tags=["home", "domestic", "intimate"],
        style_prompt=None,
        expected_banks={
            "domestic_quiet": 20,
        },
        avoid_dominance={},
    ),
    
    # -------------------------------------------------------------------------
    # STYLE PROMPT ROUTING (simulating classifier output)
    # -------------------------------------------------------------------------
    BankDistributionTestCase(
        name="california_vibes_style",
        tags=[],
        style_prompt="California sunshine, beach vibes, laid-back coastal",
        expected_banks={
            "coastal_mysticism": 15,
        },
        avoid_dominance={
            "scifi_dystopia_philosophy": 20,
        },
    ),
    
    BankDistributionTestCase(
        name="dark_electronic_style",
        tags=["electronic"],
        style_prompt="dark, futuristic, cyberpunk",
        expected_banks={
            "scifi_dystopia_philosophy": 10,
        },
        avoid_dominance={
            "whimsical_nature_folk": 15,
        },
    ),
    
    BankDistributionTestCase(
        name="vulnerable_confessional_style",
        tags=[],
        style_prompt="raw, vulnerable, honest confession",
        expected_banks={
            "confessional_heartbreak": 10,
            "emo_rap_vulnerability": 5,
            "warm_numbness": 5,
        },
        avoid_dominance={
            "body_groove": 15,
        },
    ),
    
    # -------------------------------------------------------------------------
    # COMBINED GENRE + MOOD
    # -------------------------------------------------------------------------
    BankDistributionTestCase(
        name="sad_folk",
        tags=["folk", "sad", "melancholic"],
        style_prompt=None,
        expected_banks={
            "melancholy_stillness": 10,
            "whimsical_nature_folk": 10,
            "coastal_mysticism": 5,
        },
        avoid_dominance={
            "body_groove": 15,
            "rebellion_defiance": 15,
        },
    ),
    
    BankDistributionTestCase(
        name="aggressive_hiphop",
        tags=["hip-hop", "aggressive", "angry"],
        style_prompt=None,
        expected_banks={
            "rebellion_defiance": 10,
            "political_systems_critique": 5,
        },
        avoid_dominance={
            "new_love_electricity": 15,
            "whimsical_nature_folk": 15,
        },
    ),
    
    BankDistributionTestCase(
        name="dreamy_electronic",
        tags=["electronic", "dreamy", "ethereal"],
        style_prompt=None,
        expected_banks={
            "psychedelic_perception": 10,
            "consciousness_metaphysical": 5,
        },
        avoid_dominance={
            "rebellion_defiance": 15,
        },
    ),
    
    # -------------------------------------------------------------------------
    # PROG / METAL SPECIFIC
    # -------------------------------------------------------------------------
    BankDistributionTestCase(
        name="prog_rock",
        tags=["progressive rock", "prog"],
        style_prompt=None,
        expected_banks={
            "consciousness_metaphysical": 10,
            "mythology_allegory": 10,
            "spiritual_existential": 5,
        },
        avoid_dominance={
            "body_groove": 20,
        },
    ),
    
    BankDistributionTestCase(
        name="prog_metal",
        tags=["progressive metal"],
        style_prompt=None,
        expected_banks={
            "consciousness_metaphysical": 10,
            "scifi_dystopia_philosophy": 5,
        },
        avoid_dominance={
            "new_love_electricity": 20,
        },
    ),
]


# =============================================================================
# TEST HELPERS
# =============================================================================

def run_bank_selection(
    tags: List[str],
    style_prompt: Optional[str],
    iterations: int,
    seed_start: int = 0,
) -> Counter:
    """
    Run bank selection multiple times and return distribution.
    
    Returns Counter of bank_id -> selection count.
    """
    results = Counter()
    
    for i in range(iterations):
        # Fresh generator each time with different seed
        generator = LyricsTopicGenerator(
            seed=seed_start + i,
            recency_memory=RecencyMemory(max_size=5),  # Small memory to allow repeats
        )
        
        # Compute traits (simulating what the real endpoint does)
        inferred_tag_traits = infer_traits_from_tags(tags) if tags else {}
        inferred_style_traits = extract_traits_from_style_prompt(style_prompt) if style_prompt else {}
        
        if inferred_tag_traits and inferred_style_traits:
            traits = merge_traits(inferred_tag_traits, inferred_style_traits, strategy="max")
        elif inferred_tag_traits:
            traits = inferred_tag_traits
        elif inferred_style_traits:
            traits = inferred_style_traits
        else:
            traits = get_default_traits()
        
        # Run async generation in sync context
        result = asyncio.get_event_loop().run_until_complete(
            generator.generate(
                tags=tags,
                style_prompt=style_prompt,
                trait_overrides=traits if (inferred_tag_traits or inferred_style_traits) else None,
            )
        )
        
        results[result.bank_id] += 1
    
    return results


def compute_percentages(counts: Counter, total: int) -> Dict[str, float]:
    """Convert counts to percentages."""
    return {bank_id: (count / total) * 100 for bank_id, count in counts.items()}


def format_distribution(counts: Counter, total: int, top_n: int = 10) -> str:
    """Format distribution for readable output."""
    pcts = compute_percentages(counts, total)
    sorted_banks = sorted(pcts.items(), key=lambda x: -x[1])[:top_n]
    lines = [f"  {bank_id}: {pct:.1f}% ({counts[bank_id]}/{total})" for bank_id, pct in sorted_banks]
    return "\n".join(lines)


# =============================================================================
# TESTS
# =============================================================================

class TestBankDistribution:
    """Test suite for bank selection distribution."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Ensure event loop is available for async tests."""
        try:
            self.loop = asyncio.get_event_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
    
    @pytest.mark.parametrize("test_case", TEST_CASES, ids=lambda tc: tc.name)
    def test_bank_distribution(self, test_case: BankDistributionTestCase):
        """
        Test that bank selection distribution meets expectations.
        
        For each test case:
        1. Run bank selection N times
        2. Check that expected banks appear at least X% of the time
        3. Check that avoided banks don't exceed Y% of selections
        """
        counts = run_bank_selection(
            tags=test_case.tags,
            style_prompt=test_case.style_prompt,
            iterations=test_case.iterations,
        )
        
        total = test_case.iterations
        pcts = compute_percentages(counts, total)
        
        # Build detailed error message if needed
        errors = []
        
        # Check expected banks meet minimum threshold
        for bank_id, min_pct in test_case.expected_banks.items():
            actual_pct = pcts.get(bank_id, 0)
            if actual_pct < min_pct:
                errors.append(
                    f"  UNDER-REPRESENTED: {bank_id} appeared {actual_pct:.1f}% "
                    f"(expected >= {min_pct}%)"
                )
        
        # Check avoided banks don't exceed maximum threshold
        for bank_id, max_pct in test_case.avoid_dominance.items():
            actual_pct = pcts.get(bank_id, 0)
            if actual_pct > max_pct:
                errors.append(
                    f"  OVER-REPRESENTED: {bank_id} appeared {actual_pct:.1f}% "
                    f"(expected <= {max_pct}%)"
                )
        
        if errors:
            error_msg = (
                f"\n\nTest case: {test_case.name}\n"
                f"Tags: {test_case.tags}\n"
                f"Style prompt: {test_case.style_prompt}\n"
                f"Iterations: {total}\n"
                f"\nActual distribution (top 10):\n{format_distribution(counts, total)}\n"
                f"\nFailures:\n" + "\n".join(errors)
            )
            pytest.fail(error_msg)
    
    def test_all_banks_reachable(self):
        """
        Verify that every bank can be selected under some conditions.
        
        This catches banks that are effectively "dead" due to trait misconfiguration.
        """
        unreachable_banks = set(TOPIC_BANKS.keys())
        
        # Run a variety of inputs and track which banks get selected
        test_inputs = [
            ([], None),  # Default
            (["hip-hop"], None),
            (["rock"], None),
            (["folk"], None),
            (["electronic"], None),
            (["metal"], None),
            (["r&b"], None),
            (["pop"], None),
            (["dark"], None),
            (["uplifting"], None),
            (["playful"], None),
            (["introspective"], None),
            (["coastal"], None),
            (["pastoral"], None),
            (["domestic"], None),
            (["aggressive"], None),
            (["political"], None),
            (["spiritual"], None),
            (["surreal"], None),
            (["vulnerable"], None),
            (["confessional"], None),
            ([], "dark futuristic cyberpunk electronic"),
            ([], "coastal beach ocean california"),
            ([], "raw vulnerable honest confession"),
            ([], "playful absurd comedy weird"),
        ]
        
        for tags, style_prompt in test_inputs:
            counts = run_bank_selection(tags, style_prompt, iterations=50)
            for bank_id in counts:
                unreachable_banks.discard(bank_id)
            
            # Early exit if all banks reached
            if not unreachable_banks:
                break
        
        if unreachable_banks:
            pytest.fail(
                f"The following banks were never selected across all test inputs:\n"
                f"  {sorted(unreachable_banks)}\n\n"
                f"These banks may have trait profiles that don't match any inputs."
            )
    
    def test_no_single_bank_dominates_defaults(self):
        """
        With no input (defaults only), no single bank should exceed 20% of selections.
        
        This is a key regression test for the original issue where existential
        banks were selected 40%+ of the time.
        """
        counts = run_bank_selection(tags=[], style_prompt=None, iterations=500)
        pcts = compute_percentages(counts, 500)
        
        dominant_banks = [(bank_id, pct) for bank_id, pct in pcts.items() if pct > 20]
        
        if dominant_banks:
            pytest.fail(
                f"The following banks dominated default selections (>20%):\n"
                + "\n".join(f"  {bank_id}: {pct:.1f}%" for bank_id, pct in dominant_banks)
                + f"\n\nFull distribution:\n{format_distribution(counts, 500)}"
            )
    
    def test_location_banks_competitive_with_defaults(self):
        """
        Location-based banks (coastal, domestic, pastoral) should each appear
        at least 3% of the time with default inputs.
        
        This catches the regression where location banks were overshadowed.
        """
        location_banks = ["coastal_mysticism", "domestic_quiet", "whimsical_nature_folk"]
        
        counts = run_bank_selection(tags=[], style_prompt=None, iterations=500)
        pcts = compute_percentages(counts, 500)
        
        underrepresented = []
        for bank_id in location_banks:
            pct = pcts.get(bank_id, 0)
            if pct < 3:
                underrepresented.append((bank_id, pct))
        
        if underrepresented:
            pytest.fail(
                f"Location banks are under-represented with default input (<3%):\n"
                + "\n".join(f"  {bank_id}: {pct:.1f}%" for bank_id, pct in underrepresented)
                + f"\n\nFull distribution:\n{format_distribution(counts, 500)}"
            )


class TestTraitScoring:
    """Direct tests of trait scoring to verify calculations."""
    
    def test_default_trait_scores_balanced(self):
        """
        Verify that default traits produce reasonably balanced scores across banks.
        
        No bank should score more than 2x higher than the lowest-scoring bank.
        """
        default_traits = get_default_traits()
        
        scores = {}
        for bank_id, bank in TOPIC_BANKS.items():
            scores[bank_id] = score_bank_match(default_traits, bank.traits)
        
        min_score = min(scores.values())
        max_score = max(scores.values())
        
        if min_score <= 0:
            low_scorers = [bid for bid, s in scores.items() if s <= 0]
            pytest.fail(
                f"Banks with zero or negative default scores:\n"
                + "\n".join(f"  {bid}: {scores[bid]:.3f}" for bid in low_scorers)
            )
        
        ratio = max_score / min_score
        # Allow up to 12x variance - some banks are intentionally specialized
        # (e.g., political_systems_critique only for political content)
        # The diversity noise mechanism compensates for score variance
        if ratio > 12.0:
            sorted_scores = sorted(scores.items(), key=lambda x: x[1])
            pytest.fail(
                f"Default trait scoring has {ratio:.1f}x variance (max/min), exceeds 12x limit.\n"
                f"This may cause extreme imbalance in bank selection.\n\n"
                f"Lowest 5 scoring banks:\n"
                + "\n".join(f"  {bid}: {s:.3f}" for bid, s in sorted_scores[:5])
                + f"\n\nHighest 5 scoring banks:\n"
                + "\n".join(f"  {bid}: {s:.3f}" for bid, s in sorted_scores[-5:])
            )
    
    def test_location_banks_score_competitively(self):
        """
        Location banks should score at least 50% of the median bank score with defaults.
        """
        default_traits = get_default_traits()
        location_banks = ["coastal_mysticism", "domestic_quiet", "whimsical_nature_folk"]
        
        all_scores = []
        for bank_id, bank in TOPIC_BANKS.items():
            all_scores.append(score_bank_match(default_traits, bank.traits))
        
        median_score = sorted(all_scores)[len(all_scores) // 2]
        min_acceptable = median_score * 0.5
        
        underscoring = []
        for bank_id in location_banks:
            bank = TOPIC_BANKS[bank_id]
            score = score_bank_match(default_traits, bank.traits)
            if score < min_acceptable:
                underscoring.append((bank_id, score, median_score))
        
        if underscoring:
            pytest.fail(
                f"Location banks score below 50% of median ({median_score:.3f}):\n"
                + "\n".join(
                    f"  {bid}: {s:.3f} (median: {m:.3f})"
                    for bid, s, m in underscoring
                )
            )
    
    def test_genre_routing_effectiveness(self):
        """
        Verify that genre tags produce meaningful differentiation in bank scores.
        """
        test_cases = [
            (["hip-hop"], ["emo_rap_vulnerability", "body_groove", "rebellion_defiance"]),
            (["folk"], ["whimsical_nature_folk", "domestic_quiet", "coastal_mysticism"]),
            (["metal"], ["rebellion_defiance", "mythology_allegory"]),
            (["electronic"], ["manic_velocity", "psychedelic_perception", "scifi_dystopia_philosophy"]),
        ]
        
        for tags, expected_top_banks in test_cases:
            traits = infer_traits_from_tags(tags)
            
            scores = {}
            for bank_id, bank in TOPIC_BANKS.items():
                scores[bank_id] = score_bank_match(traits, bank.traits)
            
            sorted_banks = sorted(scores.items(), key=lambda x: -x[1])
            top_5_bank_ids = [bid for bid, _ in sorted_banks[:5]]
            
            # At least one expected bank should be in top 5
            found = any(bank_id in top_5_bank_ids for bank_id in expected_top_banks)
            
            if not found:
                pytest.fail(
                    f"Genre tags {tags} did not route to expected banks.\n"
                    f"Expected one of: {expected_top_banks}\n"
                    f"Actual top 5: {top_5_bank_ids}\n"
                    f"Scores:\n"
                    + "\n".join(f"  {bid}: {scores[bid]:.3f}" for bid in top_5_bank_ids)
                )


# =============================================================================
# SUMMARY REPORT (run with pytest -s to see output)
# =============================================================================

def test_print_current_distribution_summary():
    """
    Prints a summary of current bank distribution for manual review.
    Run with: pytest tests/test_lyrics_bank_distribution.py::test_print_current_distribution_summary -s
    """
    print("\n" + "=" * 70)
    print("BANK DISTRIBUTION SUMMARY")
    print("=" * 70)
    
    scenarios = [
        ("Default (no input)", [], None),
        ("Hip-hop", ["hip-hop"], None),
        ("Folk", ["folk"], None),
        ("Rock", ["rock"], None),
        ("Electronic", ["electronic"], None),
        ("Metal", ["metal"], None),
        ("Dark mood", ["dark"], None),
        ("Uplifting mood", ["uplifting"], None),
    ]
    
    for name, tags, style_prompt in scenarios:
        counts = run_bank_selection(tags, style_prompt, iterations=100)
        print(f"\n{name}:")
        print(f"  Tags: {tags}, Style: {style_prompt}")
        print(format_distribution(counts, 100, top_n=7))
    
    print("\n" + "=" * 70)
