"""
Input concept generator service.

Generates a short (1-2 sentence) Suno concept based on genre influences.
This is the "input side" of generation - the resulting concept is later
passed to the full output generator (AgentPromptGraph) as the prompt.

Design principles:
- Pure: does not call Spotify or databases directly
- Modular: receives genres from providers, doesn't know where they came from
- Simple: v1 uses templates with variance; can be upgraded to LLM-based later
"""

import random
from dataclasses import dataclass
from typing import List, Optional, Sequence

from app.services.artist_influence import (
    InfluenceContext,
    GenreInfluenceProvider,
    CompositeGenreInfluenceProvider,
    FallbackSeedGenreProvider,
    ManualInputGenreProvider,
)


def _cap_first(s: str) -> str:
    """
    Capitalize only the first character, preserving the rest.

    Used for descriptor text (texture, vibe) that we control, NOT for artist/genre
    names which should preserve their original casing from Spotify (e.g., "TOOL",
    "deadmau5", "sunkissed", "k.d. lang").
    """
    if not s:
        return s
    return s[0].upper() + s[1:]


@dataclass
class InputConceptResult:
    """Result of input concept generation."""

    concept: str
    chosen_genres: List[str]
    genres: List[str]
    artists: List[str]  # Passed through for future use
    mood: Optional[str]


# Genre style descriptors for rich concept generation
GENRE_DESCRIPTORS: dict[str, dict[str, str]] = {
    "indie rock": {
        "texture": "jangly guitars and lo-fi warmth",
        "vibe": "intimate and understated",
        "energy": "builds from quiet verses to anthemic choruses",
    },
    "electronic": {
        "texture": "synthesized textures and crisp digital production",
        "vibe": "futuristic and immersive",
        "energy": "pulsing rhythms that evolve throughout",
    },
    "hip-hop": {
        "texture": "heavy bass and punchy drums",
        "vibe": "confident and rhythmically driven",
        "energy": "layered beats with dynamic flow",
    },
    "r&b": {
        "texture": "smooth vocals and silky production",
        "vibe": "sensual and emotionally rich",
        "energy": "grooves that sway between tension and release",
    },
    "ambient": {
        "texture": "washes of reverb and delicate drones",
        "vibe": "meditative and spacious",
        "energy": "slowly evolving soundscapes",
    },
    "trip-hop": {
        "texture": "downtempo beats with cinematic strings",
        "vibe": "dark and atmospheric",
        "energy": "brooding rhythms with unexpected samples",
    },
    "post-punk": {
        "texture": "angular guitars and driving basslines",
        "vibe": "moody and urgent",
        "energy": "restless momentum with sharp dynamics",
    },
    "synth-pop": {
        "texture": "bright synths and polished production",
        "vibe": "nostalgic yet modern",
        "energy": "catchy hooks with danceable grooves",
    },
    "shoegaze": {
        "texture": "walls of distorted guitars and ethereal vocals",
        "vibe": "dreamy and overwhelming",
        "energy": "enveloping waves of sound",
    },
    "jazz fusion": {
        "texture": "complex harmonies and virtuosic instrumentation",
        "vibe": "sophisticated and exploratory",
        "energy": "dynamic interplay between players",
    },
    "neo-soul": {
        "texture": "warm keys and organic grooves",
        "vibe": "soulful and introspective",
        "energy": "laid-back rhythms with emotional depth",
    },
    "art pop": {
        "texture": "unconventional arrangements and bold production",
        "vibe": "theatrical and avant-garde",
        "energy": "surprising shifts and artistic ambition",
    },
    "progressive rock": {
        "texture": "complex time signatures and layered compositions",
        "vibe": "epic and cerebral",
        "energy": "dynamic journeys through multiple movements",
    },
    "lo-fi": {
        "texture": "dusty samples and tape hiss",
        "vibe": "nostalgic and relaxed",
        "energy": "gentle beats perfect for focus",
    },
    "dream pop": {
        "texture": "shimmering guitars and breathy vocals",
        "vibe": "hazy and romantic",
        "energy": "floating melodies in lush reverb",
    },
    "industrial": {
        "texture": "harsh electronics and mechanical rhythms",
        "vibe": "aggressive and confrontational",
        "energy": "pounding beats with distorted textures",
    },
    "funk": {
        "texture": "tight bass grooves and rhythmic guitar",
        "vibe": "playful and infectious",
        "energy": "irresistible rhythms that demand movement",
    },
    "psychedelic": {
        "texture": "swirling effects and mind-bending production",
        "vibe": "trippy and expansive",
        "energy": "hypnotic patterns that shift and morph",
    },
    "house": {
        "texture": "four-on-the-floor beats and warm basslines",
        "vibe": "uplifting and communal",
        "energy": "driving rhythms built for the dancefloor",
    },
    "folk": {
        "texture": "acoustic instruments and natural warmth",
        "vibe": "earnest and storytelling",
        "energy": "gentle strums with heartfelt delivery",
    },
    "folk pop": {
        "texture": "acoustic warmth with polished melodies",
        "vibe": "approachable and heartfelt",
        "energy": "uplifting hooks with organic instrumentation",
    },
    "indie pop": {
        "texture": "bright melodies and quirky production",
        "vibe": "charming and offbeat",
        "energy": "catchy hooks with an independent spirit",
    },
    "alt-rock": {
        "texture": "crunchy guitars and dynamic arrangements",
        "vibe": "raw and authentic",
        "energy": "tension between quiet verses and explosive choruses",
    },
    "alternative rock": {
        "texture": "crunchy guitars and dynamic arrangements",
        "vibe": "raw and authentic",
        "energy": "tension between quiet verses and explosive choruses",
    },
    "punk": {
        "texture": "fast tempos and distorted power chords",
        "vibe": "rebellious and urgent",
        "energy": "raw energy with no-frills attitude",
    },
    "pop": {
        "texture": "polished production and memorable hooks",
        "vibe": "catchy and accessible",
        "energy": "irresistible melodies built for replay",
    },
    "rock": {
        "texture": "driving guitars and powerful drums",
        "vibe": "energetic and bold",
        "energy": "anthemic riffs with raw power",
    },
    "metal": {
        "texture": "heavy riffs and thundering percussion",
        "vibe": "intense and powerful",
        "energy": "relentless momentum with crushing weight",
    },
    "country": {
        "texture": "twangy guitars and storytelling lyrics",
        "vibe": "honest and grounded",
        "energy": "heartland grooves with authentic character",
    },
    "blues": {
        "texture": "soulful bends and expressive vocals",
        "vibe": "raw and emotional",
        "energy": "slow burns with cathartic releases",
    },
    "soul": {
        "texture": "rich vocals and warm instrumentation",
        "vibe": "passionate and moving",
        "energy": "deep grooves with emotional intensity",
    },
    "reggae": {
        "texture": "offbeat rhythms and mellow basslines",
        "vibe": "laid-back and uplifting",
        "energy": "steady grooves that sway and flow",
    },
    "classical": {
        "texture": "orchestral arrangements and timeless composition",
        "vibe": "elegant and refined",
        "energy": "dynamic movements with expressive range",
    },
    "jazz": {
        "texture": "sophisticated harmonies and improvisation",
        "vibe": "smooth and spontaneous",
        "energy": "fluid interplay between musicians",
    },
}

# Fallback descriptors for unknown genres
DEFAULT_TEXTURES = [
    "rich instrumentation",
    "layered sounds",
    "atmospheric depth",
    "textured production",
]
DEFAULT_VIBES = ["evocative", "immersive", "compelling", "distinctive"]
DEFAULT_ENERGIES = [
    "builds throughout",
    "shifts dynamically",
    "carries momentum",
]

# Default moods
DEFAULT_MOODS = [
    "introspective",
    "energetic",
    "dreamy",
    "intense",
    "melancholic",
    "uplifting",
]

# Synonym pools for variance
CONNECTORS = ["with", "featuring", "built on", "driven by"]
BLEND_WORDS = ["blend", "mix", "fusion", "crossover"]


class InputConceptGenerator:
    """
    Generates short Suno concepts from genre influences.

    v1 uses template-based generation with variance; can be upgraded to LLM-based later.
    """

    def __init__(
        self,
        fallback_provider: Optional[GenreInfluenceProvider] = None,
    ):
        self._fallback_provider = fallback_provider or FallbackSeedGenreProvider()

    async def generate(
        self,
        genres: Sequence[str],
        artists: Sequence[str] = (),  # Passed through, not used in v1
        mood: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> InputConceptResult:
        """
        Generate a short concept from the given genre list.

        - If genres is empty: randomly select 1-5 from fallback seeds.
        - If genres is non-empty: include all provided (up to 5), then fill
          remaining slots with fallback seeds not already included.
        - Returns chosen_genres ordered: user-selected first, then auto-filled.
        """
        ctx = InfluenceContext(user_id=user_id)
        MAX_TAGS = 5

        # Get fallback genres for filling
        fallback_genres = await self._fallback_provider.get_influence_genres(ctx)

        # Build genre list from manual input
        user_genres = list(genres) if genres else []

        # Base weights for [1, 2, 3, 4, 5] tags
        # Target distribution: 1=15%, 2=25%, 3=30%, 4=20%, 5=10%
        BASE_WEIGHTS = [3, 5, 6, 4, 2]  # Total 20

        def pick_target_count(min_count: int, max_count: int) -> int:
            """
            Pick a target tag count from min_count to max_count, biased towards lower values.

            When min_count > 1, we absorb the weights of eliminated options into min_count.
            E.g., if min=2, max=5: weights for [2,3,4,5] become [5+4, 3, 2, 1] = [9, 3, 2, 1]
            """
            if min_count > max_count:
                return min_count
            if min_count == max_count:
                return min_count

            # Absorb eliminated weights into the minimum
            absorbed_weight = sum(BASE_WEIGHTS[: min_count - 1]) if min_count > 1 else 0
            remaining_weights = BASE_WEIGHTS[min_count - 1 : max_count]

            # Add absorbed weight to the first (minimum) option
            weights = remaining_weights.copy()
            weights[0] += absorbed_weight

            choices = list(range(min_count, max_count + 1))
            return random.choices(choices, weights=weights)[0]

        if not user_genres:
            # No user input: randomly pick 1-5 from fallback (biased towards fewer)
            max_available = min(MAX_TAGS, len(fallback_genres))
            target = pick_target_count(1, max_available) if max_available > 0 else 0
            chosen_genres = (
                random.sample(fallback_genres, target)
                if fallback_genres and target > 0
                else []
            )
            genre_list = fallback_genres
        else:
            # User provided genres: include all (up to 5), then maybe fill with fallback
            chosen_genres = user_genres[:MAX_TAGS]  # User-selected, capped at 5

            if len(chosen_genres) < MAX_TAGS:
                # Randomly decide how many extra tags to add (biased towards fewer/none)
                chosen_lower = {g.lower() for g in chosen_genres}
                available_fallbacks = [
                    g for g in fallback_genres if g.lower() not in chosen_lower
                ]

                if available_fallbacks:
                    # Pick target total: min is current count, max is up to MAX_TAGS
                    min_total = len(chosen_genres)
                    max_total = min(
                        MAX_TAGS, len(chosen_genres) + len(available_fallbacks)
                    )

                    target_total = pick_target_count(min_total, max_total)

                    num_to_fill = target_total - len(chosen_genres)
                    if num_to_fill > 0:
                        auto_filled = random.sample(available_fallbacks, num_to_fill)
                        chosen_genres = (
                            chosen_genres + auto_filled
                        )  # User first, then auto

            genre_list = user_genres

        # Generate short concept with template variance
        concept, inferred_mood = self._generate_concept(
            chosen_genres=chosen_genres,
            mood_hint=mood,
        )

        return InputConceptResult(
            concept=concept,
            chosen_genres=chosen_genres,
            genres=genre_list,
            artists=list(artists),  # Pass through
            mood=inferred_mood or mood,
        )

    def _generate_concept(
        self,
        chosen_genres: List[str],
        mood_hint: Optional[str],
    ) -> tuple[str, Optional[str]]:
        """
        Generate a 2-3 sentence concept string from chosen genres.

        Returns (concept, inferred_mood)
        """
        mood = mood_hint or random.choice(DEFAULT_MOODS)
        conn = random.choice(CONNECTORS)

        if not chosen_genres:
            # Complete fallback - no genres
            texture = random.choice(DEFAULT_TEXTURES)
            vibe = random.choice(DEFAULT_VIBES)
            templates = [
                f"A track {conn} {texture}. {vibe.capitalize()} and expressive.",
                f"Something {conn} {texture}. Let it breathe.",
                f"A song {conn} {texture}. Keep it {vibe}.",
            ]
            return random.choice(templates), mood

        # Build concept from genre descriptors
        # Note: Do NOT capitalize genre/artist names - preserve original casing from Spotify
        # (e.g., "TOOL", "deadmau5", "sunkissed", "k.d. lang")
        # Only use _cap_first() for descriptor texts (texture, vibe) that we control.
        if len(chosen_genres) == 1:
            genre = chosen_genres[0]
            desc = self._get_genre_descriptor(genre)
            templates = [
                f"A {genre} track {conn} {desc['texture']}.",
                f"Inspired by {genre}. {_cap_first(desc['texture'])}.",
                f"Channeling {genre} vibes, {conn} {desc['texture']}.",
            ]
        elif len(chosen_genres) == 2:
            g1, g2 = chosen_genres
            d1 = self._get_genre_descriptor(g1)
            blend = random.choice(BLEND_WORDS)
            templates = [
                f"A {blend} of {g1} and {g2}. {_cap_first(d1['texture'])}.",
                f"Where {g1} meets {g2}, {conn} {d1['texture']}.",
                f"A {g1}/{g2} {blend}. {_cap_first(d1['vibe'])}.",
            ]
        elif len(chosen_genres) == 3:
            g1, g2, g3 = chosen_genres[:3]
            d1 = self._get_genre_descriptor(g1)
            templates = [
                f"Drawing from {g1}, {g2}, and {g3}. {_cap_first(d1['texture'])}.",
                f"A take on {g1}, {g2}, {g3}. {_cap_first(d1['texture'])}.",
                f"Crossing {g1} with {g2} and {g3}. {_cap_first(d1['vibe'])}.",
            ]
        elif len(chosen_genres) == 4:
            g1, g2, g3, g4 = chosen_genres[:4]
            d1 = self._get_genre_descriptor(g1)
            blend = random.choice(BLEND_WORDS)
            templates = [
                f"A {blend} of {g1}, {g2}, {g3}, and {g4}. {_cap_first(d1['texture'])}.",
                f"Where {g1} meets {g2}, {g3}, and {g4}. {_cap_first(d1['vibe'])}.",
                f"Weaving {g1}, {g2}, {g3}, {g4} together. {_cap_first(d1['texture'])}.",
            ]
        else:  # 5+ genres
            g1, g2, g3, g4, g5 = chosen_genres[:5]
            d1 = self._get_genre_descriptor(g1)
            blend = random.choice(BLEND_WORDS)
            templates = [
                f"A rich {blend} of {g1}, {g2}, {g3}, {g4}, and {g5}. {_cap_first(d1['texture'])}.",
                f"Blending {g1}, {g2}, {g3}, {g4}, {g5}. {_cap_first(d1['vibe'])} and eclectic.",
                f"Weaving {g1}, {g2}, {g3}, {g4}, {g5} into something new. {_cap_first(d1['texture'])}.",
            ]

        return random.choice(templates), mood

    def _get_genre_descriptor(self, genre: str) -> dict[str, str]:
        """Get descriptor for a genre, with fallback for unknown genres."""
        key = genre.lower().strip()
        if key in GENRE_DESCRIPTORS:
            return GENRE_DESCRIPTORS[key]
        # Fallback for unknown genre - avoid repeating the genre name since
        # templates already include it (e.g., "{genre} vibes, {conn} {desc['texture']}")
        return {
            "texture": random.choice(DEFAULT_TEXTURES),
            "vibe": random.choice(DEFAULT_VIBES),
            "energy": random.choice(DEFAULT_ENERGIES),
        }


async def create_generator_with_providers(
    request_genres: Sequence[str],
    request_artists: Sequence[str] = (),
    user_id: Optional[str] = None,
    candidate_genres: Sequence[str] = (),
) -> tuple[InputConceptGenerator, CompositeGenreInfluenceProvider]:
    """
    Factory function to create generator with appropriate providers.

    For v1: only ManualInputGenreProvider is used.
    Later: add SpotifyGenreProvider, UserProfileGenreProvider, etc.
    """
    providers: list[GenreInfluenceProvider] = [
        ManualInputGenreProvider(request_genres),
        # Future: SpotifyGenreProvider(user_id) if user_id and has_spotify_connected
        # Future: UserProfileGenreProvider(user_id) if user_id
    ]

    composite = CompositeGenreInfluenceProvider(providers)
    # Candidate genres (e.g., Spotify-aided) should influence only the fallback sampling pool,
    # while request_genres remain the primary, user-selected inputs.
    fallback_provider: Optional[GenreInfluenceProvider] = None
    if candidate_genres:
        fallback_provider = ManualInputGenreProvider(candidate_genres)

    generator = InputConceptGenerator(fallback_provider=fallback_provider)

    return generator, composite
