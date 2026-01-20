"""
Artist → Bank Routing Integration Tests

Tests that real artist names + genres route to expected lyric banks.
This ensures the routing system works correctly for typical user inputs.

Run with: pytest tests/test_artist_bank_routing.py -v
"""

import asyncio
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Tuple

import pytest

from app.services.lyrics_topic_generator import LyricsTopicGenerator, RecencyMemory
from app.services.lyrics_topic_traits import (
    get_default_traits,
    infer_traits_from_tags,
    extract_traits_from_style_prompt,
    merge_traits,
)


@dataclass
class ArtistTestCase:
    """An artist with expected bank associations."""
    name: str
    genres: List[str]
    expected_banks: List[str]  # Banks that should rank highly
    style_keywords: List[str] = None
    
    def __post_init__(self):
        if self.style_keywords is None:
            self.style_keywords = []


# =============================================================================
# 50 ARTISTS ACROSS GENRES - Each maps to expected banks
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
        style_keywords=["nostalgic", "cinematic", "california"],
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


def run_artist_test(artist: ArtistTestCase, iterations: int = 50) -> Tuple[Counter, Dict[str, float]]:
    """Run iterations for an artist and return bank distribution."""
    results = Counter()
    tags = artist.genres + artist.style_keywords
    style_prompt = artist.name
    
    for i in range(iterations):
        gen = LyricsTopicGenerator(seed=i * 1000, recency_memory=RecencyMemory(max_size=3))
        
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
    
    total = iterations
    sorted_banks = sorted(results.items(), key=lambda x: -x[1])[:5]
    top_5 = {bank_id: (count / total) * 100 for bank_id, count in sorted_banks}
    
    return results, top_5


class TestArtistBankRouting:
    """
    Integration tests for artist → bank routing.
    
    These tests verify that real artist names + genres route to expected lyric banks.
    """
    
    @pytest.mark.parametrize("artist", ARTIST_TEST_CASES, ids=lambda a: a.name.replace(" ", "_"))
    def test_artist_routes_to_expected_bank(self, artist: ArtistTestCase):
        """Test that each artist routes to at least one of their expected banks in top 3."""
        _, top_banks = run_artist_test(artist, iterations=50)
        
        top_3_bank_ids = list(top_banks.keys())[:3]
        hit = any(bank in top_3_bank_ids for bank in artist.expected_banks)
        
        if not hit:
            # Provide detailed failure message
            pytest.fail(
                f"\n{artist.name} failed to route correctly:"
                f"\n  Genres: {artist.genres}"
                f"\n  Keywords: {artist.style_keywords}"
                f"\n  Expected (any of): {artist.expected_banks[:3]}"
                f"\n  Actual top 3: {top_3_bank_ids}"
            )
    
    def test_overall_accuracy_threshold(self):
        """Aggregate test: at least 80% of artists should route correctly."""
        hits = 0
        failures = []
        
        for artist in ARTIST_TEST_CASES:
            _, top_banks = run_artist_test(artist, iterations=30)  # Fewer iterations for speed
            top_3 = list(top_banks.keys())[:3]
            
            if any(bank in top_3 for bank in artist.expected_banks):
                hits += 1
            else:
                failures.append(artist.name)
        
        accuracy = hits / len(ARTIST_TEST_CASES) * 100
        
        assert accuracy >= 80, (
            f"Overall accuracy {accuracy:.1f}% is below 80% threshold.\n"
            f"Failed artists: {failures}"
        )
    
    def test_genre_coverage(self):
        """Test that we have artists from all major genre families."""
        genres_covered = set()
        for artist in ARTIST_TEST_CASES:
            for genre in artist.genres:
                # Extract base genre (e.g., "hip-hop" from "conscious hip-hop")
                base = genre.split()[-1] if " " in genre else genre
                genres_covered.add(base.lower())
        
        required_genres = {"rock", "pop", "hip-hop", "electronic", "folk", "metal", "r&b"}
        missing = required_genres - genres_covered
        
        assert not missing, f"Test suite missing coverage for genres: {missing}"
    
    def test_bank_coverage(self):
        """Test that all banks appear as expected for at least one artist."""
        from app.services.lyrics_topic_banks import TOPIC_BANKS
        
        expected_banks_used = set()
        for artist in ARTIST_TEST_CASES:
            expected_banks_used.update(artist.expected_banks)
        
        all_bank_ids = set(TOPIC_BANKS.keys())
        not_tested = all_bank_ids - expected_banks_used
        
        assert not not_tested, (
            f"These banks are not expected by any test case: {not_tested}\n"
            "Add artist test cases that expect these banks."
        )
