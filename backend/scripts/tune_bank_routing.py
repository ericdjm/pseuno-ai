#!/usr/bin/env python3
"""
Bank Routing Tuner

This script iteratively tests and tunes the lyrics topic bank routing system
until it meets accuracy thresholds for artist → bank associations.

Run: python scripts/tune_bank_routing.py

It will:
1. Test 50+ artists against their expected primary banks
2. Measure hit rate (did expected bank appear in top 3?)
3. Identify systematic failures and suggest fixes
4. Loop until accuracy exceeds threshold
"""

import asyncio
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

# Add app to path
sys.path.insert(0, "/app")

from app.services.lyrics_topic_generator import LyricsTopicGenerator, RecencyMemory
from app.services.lyrics_topic_traits import (
    get_default_traits,
    infer_traits_from_tags,
    extract_traits_from_style_prompt,
    merge_traits,
    score_bank_match,
    GENRE_TRAIT_MAP,
    MOOD_TRAIT_MAP,
)
from app.services.lyrics_topic_banks import TOPIC_BANKS


@dataclass
class ArtistTestCase:
    """An artist with expected bank associations."""
    name: str
    genres: List[str]  # Genre tags that would come from Spotify
    expected_banks: List[str]  # Banks that should rank highly (in order of preference)
    style_keywords: List[str] = None  # Keywords extracted from style prompt
    
    def __post_init__(self):
        if self.style_keywords is None:
            self.style_keywords = []


# =============================================================================
# ARTIST TEST CASES - 50+ artists across genres
# Each maps to expected banks based on their lyrical themes
# =============================================================================

ARTIST_TEST_CASES = [
    # --- COASTAL / CALIFORNIA ---
    ArtistTestCase(
        name="Red Hot Chili Peppers",
        genres=["rock", "funk rock", "alternative rock"],
        expected_banks=["coastal_mysticism", "body_groove", "psychedelic_perception"],
        style_keywords=["california", "coastal", "funky"],
    ),
    ArtistTestCase(
        name="Sublime",
        genres=["ska", "reggae", "rock"],
        expected_banks=["coastal_mysticism", "body_groove"],
        style_keywords=["beach", "california", "laid-back"],
    ),
    ArtistTestCase(
        name="Jack Johnson",
        genres=["folk", "acoustic", "soft rock"],
        expected_banks=["coastal_mysticism", "whimsical_nature_folk", "domestic_quiet"],
        style_keywords=["beach", "mellow", "acoustic"],
    ),
    ArtistTestCase(
        name="Best Coast",
        genres=["indie rock", "surf rock"],
        expected_banks=["coastal_mysticism", "new_love_electricity"],
        style_keywords=["california", "beach", "dreamy"],
    ),
    
    # --- FOLK / PASTORAL ---
    ArtistTestCase(
        name="Fleet Foxes",
        genres=["indie folk", "folk rock", "baroque pop"],
        expected_banks=["whimsical_nature_folk", "spiritual_existential", "coastal_mysticism"],
        style_keywords=["nature", "pastoral", "harmonies"],
    ),
    ArtistTestCase(
        name="Bon Iver",
        genres=["indie folk", "folk", "ambient"],
        expected_banks=["whimsical_nature_folk", "melancholy_stillness", "spiritual_existential"],
        style_keywords=["nature", "introspective", "atmospheric"],
    ),
    ArtistTestCase(
        name="Iron and Wine",
        genres=["folk", "indie folk"],
        expected_banks=["whimsical_nature_folk", "domestic_quiet", "melancholy_stillness"],
        style_keywords=["pastoral", "quiet", "intimate"],
    ),
    ArtistTestCase(
        name="The Lumineers",
        genres=["folk rock", "americana"],
        expected_banks=["whimsical_nature_folk", "domestic_quiet", "confessional_heartbreak"],
        style_keywords=["folk", "americana", "storytelling"],
    ),
    ArtistTestCase(
        name="Mumford and Sons",
        genres=["folk rock", "indie folk"],
        expected_banks=["whimsical_nature_folk", "spiritual_existential", "post_breakup_liberation"],
        style_keywords=["folk", "anthemic", "hopeful"],
    ),
    
    # --- DOMESTIC / INTIMATE ---
    ArtistTestCase(
        name="Phoebe Bridgers",
        genres=["indie rock", "indie folk", "sad"],
        expected_banks=["melancholy_stillness", "confessional_heartbreak", "domestic_quiet"],
        style_keywords=["quiet", "sad", "intimate"],
    ),
    ArtistTestCase(
        name="Sufjan Stevens",
        genres=["indie folk", "baroque pop", "art pop"],
        expected_banks=["domestic_quiet", "spiritual_existential", "whimsical_nature_folk"],
        style_keywords=["intimate", "spiritual", "delicate"],
    ),
    ArtistTestCase(
        name="Elliott Smith",
        genres=["indie folk", "singer-songwriter"],
        expected_banks=["melancholy_stillness", "confessional_heartbreak", "domestic_quiet"],
        style_keywords=["quiet", "sad", "vulnerable"],
    ),
    
    # --- HIP-HOP / RAP ---
    ArtistTestCase(
        name="Kendrick Lamar",
        genres=["hip-hop", "conscious rap", "west coast hip-hop"],
        expected_banks=["political_systems_critique", "spiritual_existential", "emo_rap_vulnerability"],
        style_keywords=["political", "introspective", "storytelling"],
    ),
    ArtistTestCase(
        name="J. Cole",
        genres=["hip-hop", "conscious rap"],
        expected_banks=["emo_rap_vulnerability", "political_systems_critique", "confessional_heartbreak"],
        style_keywords=["introspective", "storytelling", "vulnerable"],
    ),
    ArtistTestCase(
        name="Travis Scott",
        genres=["hip-hop", "trap"],
        expected_banks=["body_groove", "psychedelic_perception", "manic_velocity"],
        style_keywords=["dark", "trippy", "party"],
    ),
    ArtistTestCase(
        name="Drake",
        genres=["hip-hop", "r&b", "pop rap"],
        expected_banks=["confessional_heartbreak", "emo_rap_vulnerability", "body_groove"],
        style_keywords=["emotional", "romantic", "introspective"],
    ),
    ArtistTestCase(
        name="Juice WRLD",
        genres=["hip-hop", "emo rap", "trap"],
        expected_banks=["emo_rap_vulnerability", "confessional_heartbreak", "warm_numbness"],
        style_keywords=["sad", "vulnerable", "heartbreak"],
    ),
    ArtistTestCase(
        name="XXXTentacion",
        genres=["hip-hop", "emo rap"],
        expected_banks=["emo_rap_vulnerability", "warm_numbness", "confessional_heartbreak"],
        style_keywords=["dark", "sad", "vulnerable"],
    ),
    ArtistTestCase(
        name="Megan Thee Stallion",
        genres=["hip-hop", "southern hip-hop"],
        expected_banks=["body_groove", "rebellion_defiance", "post_breakup_liberation"],
        style_keywords=["confident", "party", "empowering"],
    ),
    ArtistTestCase(
        name="Tyler, the Creator",
        genres=["hip-hop", "alternative hip-hop"],
        expected_banks=["absurdist_comedy", "psychedelic_perception", "confessional_heartbreak"],
        style_keywords=["weird", "playful", "colorful"],
    ),
    
    # --- ROCK / ALTERNATIVE ---
    ArtistTestCase(
        name="Radiohead",
        genres=["alternative rock", "art rock", "electronic"],
        expected_banks=["consciousness_metaphysical", "scifi_dystopia_philosophy", "melancholy_stillness"],
        style_keywords=["existential", "dark", "experimental"],
    ),
    ArtistTestCase(
        name="Rage Against the Machine",
        genres=["rock", "rap metal", "alternative metal"],
        expected_banks=["political_systems_critique", "rebellion_defiance"],
        style_keywords=["political", "angry", "aggressive"],
    ),
    ArtistTestCase(
        name="Green Day",
        genres=["punk rock", "pop punk", "alternative rock"],
        expected_banks=["rebellion_defiance", "political_systems_critique", "post_breakup_liberation"],
        style_keywords=["rebellious", "youthful", "political"],
    ),
    ArtistTestCase(
        name="My Chemical Romance",
        genres=["alternative rock", "emo", "post-hardcore"],
        expected_banks=["emo_rap_vulnerability", "rebellion_defiance", "mythology_allegory"],
        style_keywords=["dramatic", "dark", "theatrical"],
    ),
    ArtistTestCase(
        name="Arctic Monkeys",
        genres=["indie rock", "alternative rock"],
        expected_banks=["new_love_electricity", "body_groove", "confessional_heartbreak"],
        style_keywords=["witty", "urban", "romantic"],
    ),
    
    # --- METAL / PROG ---
    ArtistTestCase(
        name="Tool",
        genres=["progressive metal", "alternative metal"],
        expected_banks=["consciousness_metaphysical", "spiritual_existential", "psychedelic_perception"],
        style_keywords=["spiritual", "dark", "philosophical"],
    ),
    ArtistTestCase(
        name="Mastodon",
        genres=["progressive metal", "sludge metal"],
        expected_banks=["mythology_allegory", "consciousness_metaphysical", "psychedelic_perception"],
        style_keywords=["epic", "mythological", "heavy"],
    ),
    ArtistTestCase(
        name="Opeth",
        genres=["progressive metal", "death metal", "progressive rock"],
        expected_banks=["melancholy_stillness", "consciousness_metaphysical", "whimsical_nature_folk"],
        style_keywords=["melancholic", "progressive", "nature"],
    ),
    ArtistTestCase(
        name="Gojira",
        genres=["progressive metal", "death metal"],
        expected_banks=["spiritual_existential", "political_systems_critique", "whimsical_nature_folk"],
        style_keywords=["environmental", "spiritual", "heavy"],
    ),
    ArtistTestCase(
        name="Slipknot",
        genres=["nu metal", "heavy metal"],
        expected_banks=["rebellion_defiance", "emo_rap_vulnerability", "manic_velocity"],
        style_keywords=["aggressive", "angry", "dark"],
    ),
    
    # --- ELECTRONIC ---
    ArtistTestCase(
        name="Burial",
        genres=["electronic", "dubstep", "ambient"],
        expected_banks=["warm_numbness", "scifi_dystopia_philosophy", "melancholy_stillness"],
        style_keywords=["dark", "urban", "melancholic"],
    ),
    ArtistTestCase(
        name="Aphex Twin",
        genres=["electronic", "idm", "ambient"],
        expected_banks=["psychedelic_perception", "absurdist_comedy", "consciousness_metaphysical"],
        style_keywords=["weird", "experimental", "surreal"],
    ),
    ArtistTestCase(
        name="The Prodigy",
        genres=["electronic", "big beat", "breakbeat"],
        expected_banks=["manic_velocity", "rebellion_defiance", "body_groove"],
        style_keywords=["aggressive", "energetic", "dark"],
    ),
    ArtistTestCase(
        name="Daft Punk",
        genres=["electronic", "house", "disco"],
        expected_banks=["body_groove", "scifi_dystopia_philosophy", "new_love_electricity"],
        style_keywords=["futuristic", "dance", "romantic"],
    ),
    ArtistTestCase(
        name="Portishead",
        genres=["trip-hop", "electronic", "art rock"],
        expected_banks=["warm_numbness", "melancholy_stillness", "confessional_heartbreak", "scifi_dystopia_philosophy"],
        style_keywords=["dark", "moody", "cinematic"],
    ),
    
    # --- R&B / SOUL ---
    ArtistTestCase(
        name="Frank Ocean",
        genres=["r&b", "alternative r&b", "neo-soul"],
        expected_banks=["confessional_heartbreak", "new_love_electricity", "melancholy_stillness"],
        style_keywords=["vulnerable", "romantic", "introspective"],
    ),
    ArtistTestCase(
        name="SZA",
        genres=["r&b", "alternative r&b", "neo-soul"],
        expected_banks=["confessional_heartbreak", "new_love_electricity", "post_breakup_liberation"],
        style_keywords=["vulnerable", "romantic", "empowering"],
    ),
    ArtistTestCase(
        name="The Weeknd",
        genres=["r&b", "pop", "alternative r&b"],
        expected_banks=["confessional_heartbreak", "warm_numbness", "body_groove"],
        style_keywords=["dark", "sensual", "melancholic"],
    ),
    ArtistTestCase(
        name="Erykah Badu",
        genres=["neo-soul", "r&b", "jazz"],
        expected_banks=["spiritual_existential", "consciousness_metaphysical", "new_love_electricity"],
        style_keywords=["spiritual", "soulful", "mystical"],
    ),
    
    # --- POP ---
    ArtistTestCase(
        name="Taylor Swift",
        genres=["pop", "country pop", "indie folk"],
        expected_banks=["confessional_heartbreak", "new_love_electricity", "post_breakup_liberation"],
        style_keywords=["storytelling", "romantic", "confessional"],
    ),
    ArtistTestCase(
        name="Billie Eilish",
        genres=["pop", "electropop", "dark pop"],
        expected_banks=["warm_numbness", "emo_rap_vulnerability", "absurdist_comedy"],
        style_keywords=["dark", "whispered", "moody"],
    ),
    ArtistTestCase(
        name="Lorde",
        genres=["pop", "art pop", "electropop"],
        expected_banks=["melancholy_stillness", "consciousness_metaphysical", "domestic_quiet"],
        style_keywords=["introspective", "suburban", "poetic"],
    ),
    ArtistTestCase(
        name="Lana Del Rey",
        genres=["pop", "dream pop", "baroque pop"],
        expected_banks=["coastal_mysticism", "melancholy_stillness", "confessional_heartbreak"],
        style_keywords=["nostalgic", "cinematic", "California"],
    ),
    ArtistTestCase(
        name="Charli XCX",
        genres=["pop", "hyperpop", "electropop"],
        expected_banks=["body_groove", "manic_velocity", "absurdist_comedy"],
        style_keywords=["party", "chaotic", "futuristic"],
    ),
    
    # --- PSYCHEDELIC ---
    ArtistTestCase(
        name="Tame Impala",
        genres=["psychedelic rock", "indie rock", "synth-pop"],
        expected_banks=["psychedelic_perception", "new_love_electricity", "consciousness_metaphysical"],
        style_keywords=["dreamy", "trippy", "introspective"],
    ),
    ArtistTestCase(
        name="King Gizzard",
        genres=["psychedelic rock", "garage rock", "progressive rock"],
        expected_banks=["psychedelic_perception", "scifi_dystopia_philosophy", "mythology_allegory"],
        style_keywords=["weird", "sci-fi", "energetic"],
    ),
    ArtistTestCase(
        name="Pink Floyd",
        genres=["progressive rock", "psychedelic rock"],
        expected_banks=["consciousness_metaphysical", "psychedelic_perception", "spiritual_existential"],
        style_keywords=["philosophical", "surreal", "epic"],
    ),
    
    # --- ABSURDIST / WEIRD ---
    ArtistTestCase(
        name="Weird Al Yankovic",
        genres=["comedy", "pop", "novelty"],
        expected_banks=["absurdist_comedy"],
        style_keywords=["comedy", "parody", "silly"],
    ),
    ArtistTestCase(
        name="They Might Be Giants",
        genres=["alternative rock", "indie rock"],
        expected_banks=["absurdist_comedy", "whimsical_nature_folk"],
        style_keywords=["quirky", "weird", "playful"],
    ),
    ArtistTestCase(
        name="100 gecs",
        genres=["hyperpop", "electronic"],
        expected_banks=["absurdist_comedy", "manic_velocity", "body_groove"],
        style_keywords=["chaotic", "weird", "loud"],
    ),
]


def run_single_test(
    artist: ArtistTestCase,
    iterations: int = 50,
) -> Tuple[Counter, Dict[str, float]]:
    """
    Test an artist's routing and return bank distribution.
    
    Returns:
        - Counter of bank selections
        - Dict of top 5 banks with percentages
    """
    results = Counter()
    
    # Combine genres and style keywords as tags
    tags = artist.genres + artist.style_keywords
    style_prompt = artist.name  # Use artist name as style prompt
    
    for i in range(iterations):
        gen = LyricsTopicGenerator(seed=i * 1000, recency_memory=RecencyMemory(max_size=3))
        
        # Simulate the real routing logic
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
        
        result = asyncio.get_event_loop().run_until_complete(
            gen.generate(
                tags=tags,
                style_prompt=style_prompt,
                trait_overrides=traits if (inferred_tag_traits or inferred_style_traits) else None,
            )
        )
        results[result.bank_id] += 1
    
    # Calculate top 5 percentages
    total = iterations
    sorted_banks = sorted(results.items(), key=lambda x: -x[1])[:5]
    top_5 = {bank_id: (count / total) * 100 for bank_id, count in sorted_banks}
    
    return results, top_5


def check_hit(artist: ArtistTestCase, top_banks: Dict[str, float], top_n: int = 3) -> bool:
    """Check if any expected bank is in the top N selections."""
    top_bank_ids = list(top_banks.keys())[:top_n]
    return any(bank in top_bank_ids for bank in artist.expected_banks)


def analyze_failures(
    artists: List[ArtistTestCase],
    results: Dict[str, Tuple[Counter, Dict[str, float]]],
) -> Dict[str, List[str]]:
    """
    Analyze failures and identify patterns.
    
    Returns dict of issues: {issue_type: [details]}
    """
    issues = defaultdict(list)
    
    for artist in artists:
        _, top_banks = results[artist.name]
        
        if not check_hit(artist, top_banks, top_n=3):
            # Failure - analyze why
            top_bank_ids = list(top_banks.keys())
            
            # Check if expected banks score at all
            counter, _ = results[artist.name]
            for expected in artist.expected_banks:
                if counter.get(expected, 0) == 0:
                    issues["zero_score_expected"].append(
                        f"{artist.name}: {expected} never selected (expected)"
                    )
                elif counter.get(expected, 0) < 5:  # <10% of 50 iterations
                    issues["low_score_expected"].append(
                        f"{artist.name}: {expected} only {counter[expected]}% (expected)"
                    )
            
            # Check what's winning instead
            winner = top_bank_ids[0]
            if winner not in artist.expected_banks:
                issues["wrong_winner"].append(
                    f"{artist.name}: Got {winner} (expected {artist.expected_banks[0]})"
                )
            
            # Check genre coverage
            for genre in artist.genres:
                if genre.lower() not in GENRE_TRAIT_MAP:
                    issues["missing_genre"].append(f"{artist.name}: Genre '{genre}' not mapped")
            
            # Check style keyword coverage
            for kw in artist.style_keywords:
                if kw.lower() not in MOOD_TRAIT_MAP:
                    issues["missing_keyword"].append(f"{artist.name}: Keyword '{kw}' not mapped")
    
    return dict(issues)


def compute_score_analysis(artist: ArtistTestCase) -> Dict[str, float]:
    """Compute trait scores for each bank given artist's inputs."""
    tags = artist.genres + artist.style_keywords
    
    inferred_tag_traits = infer_traits_from_tags(tags) if tags else {}
    inferred_style_traits = extract_traits_from_style_prompt(artist.name) if artist.name else {}
    
    if inferred_tag_traits and inferred_style_traits:
        traits = merge_traits(inferred_tag_traits, inferred_style_traits, strategy="max")
    elif inferred_tag_traits:
        traits = inferred_tag_traits
    elif inferred_style_traits:
        traits = inferred_style_traits
    else:
        traits = get_default_traits()
    
    scores = {}
    for bank_id, bank in TOPIC_BANKS.items():
        scores[bank_id] = score_bank_match(traits, bank.traits)
    
    return scores


def print_detailed_failure(artist: ArtistTestCase, top_banks: Dict[str, float]):
    """Print detailed analysis of a failing test case."""
    print(f"\n  {artist.name}")
    print(f"    Genres: {artist.genres}")
    print(f"    Keywords: {artist.style_keywords}")
    print(f"    Expected: {artist.expected_banks[:3]}")
    print(f"    Actual top 3: {list(top_banks.keys())[:3]}")
    
    # Show trait scores for expected vs actual
    scores = compute_score_analysis(artist)
    print(f"    Score comparison:")
    for exp in artist.expected_banks[:2]:
        print(f"      {exp}: {scores.get(exp, 0):.3f}")
    for act in list(top_banks.keys())[:2]:
        if act not in artist.expected_banks[:2]:
            print(f"      {act}: {scores.get(act, 0):.3f} (winner)")


def run_full_test() -> Tuple[float, Dict[str, List[str]]]:
    """
    Run full test suite and return accuracy + issues.
    """
    print("=" * 70)
    print("BANK ROUTING ACCURACY TEST")
    print("=" * 70)
    print(f"\nTesting {len(ARTIST_TEST_CASES)} artists...")
    
    results = {}
    hits = 0
    failures = []
    
    for i, artist in enumerate(ARTIST_TEST_CASES):
        counter, top_banks = run_single_test(artist, iterations=50)
        results[artist.name] = (counter, top_banks)
        
        hit = check_hit(artist, top_banks, top_n=3)
        if hit:
            hits += 1
            status = "✓"
        else:
            failures.append(artist)
            status = "✗"
        
        # Progress indicator
        if (i + 1) % 10 == 0:
            print(f"  Tested {i + 1}/{len(ARTIST_TEST_CASES)}...")
    
    accuracy = hits / len(ARTIST_TEST_CASES) * 100
    
    print(f"\n{'=' * 70}")
    print(f"RESULTS: {hits}/{len(ARTIST_TEST_CASES)} = {accuracy:.1f}% accuracy")
    print(f"{'=' * 70}")
    
    if failures:
        print(f"\nFailed cases ({len(failures)}):")
        for artist in failures:
            print_detailed_failure(artist, results[artist.name][1])
    
    # Analyze patterns
    issues = analyze_failures(ARTIST_TEST_CASES, results)
    
    if issues:
        print(f"\n{'=' * 70}")
        print("ISSUE ANALYSIS")
        print(f"{'=' * 70}")
        for issue_type, details in issues.items():
            print(f"\n{issue_type} ({len(details)} cases):")
            for detail in details[:5]:  # Show first 5
                print(f"  - {detail}")
            if len(details) > 5:
                print(f"  ... and {len(details) - 5} more")
    
    return accuracy, issues


def suggest_fixes(issues: Dict[str, List[str]]) -> List[str]:
    """Suggest fixes based on identified issues."""
    suggestions = []
    
    if "missing_genre" in issues:
        genres = set()
        for detail in issues["missing_genre"]:
            # Extract genre from "Artist: Genre 'X' not mapped"
            if "'" in detail:
                genre = detail.split("'")[1]
                genres.add(genre)
        if genres:
            suggestions.append(f"Add these genres to GENRE_TRAIT_MAP: {genres}")
    
    if "missing_keyword" in issues:
        keywords = set()
        for detail in issues["missing_keyword"]:
            if "'" in detail:
                kw = detail.split("'")[1]
                keywords.add(kw)
        if keywords:
            suggestions.append(f"Add these keywords to MOOD_TRAIT_MAP: {keywords}")
    
    if "zero_score_expected" in issues:
        banks = set()
        for detail in issues["zero_score_expected"]:
            # Extract bank name
            parts = detail.split(":")
            if len(parts) >= 2:
                bank = parts[1].strip().split()[0]
                banks.add(bank)
        if banks:
            suggestions.append(f"These banks never get selected - check trait overlap: {banks}")
    
    return suggestions


def main():
    """Main entry point - run tests and report."""
    print("\n" + "=" * 70)
    print("LYRICS BANK ROUTING TUNER")
    print("=" * 70)
    print("\nThis script tests artist→bank routing accuracy.")
    print("Target: 80% of artists should have expected banks in top 3.\n")
    
    accuracy, issues = run_full_test()
    
    print(f"\n{'=' * 70}")
    print("SUMMARY")
    print(f"{'=' * 70}")
    print(f"Accuracy: {accuracy:.1f}%")
    print(f"Target: 80%")
    print(f"Status: {'✓ PASS' if accuracy >= 80 else '✗ FAIL'}")
    
    if accuracy < 80:
        suggestions = suggest_fixes(issues)
        if suggestions:
            print(f"\n{'=' * 70}")
            print("SUGGESTED FIXES")
            print(f"{'=' * 70}")
            for i, suggestion in enumerate(suggestions, 1):
                print(f"{i}. {suggestion}")
    
    return accuracy >= 80


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
