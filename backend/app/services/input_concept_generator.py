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
    # Additional genres for expanded coverage
    "trap": {
        "texture": "808 bass drops and skittering hi-hats",
        "vibe": "dark and hypnotic",
        "energy": "slow-burning tension with explosive drops",
    },
    "drill": {
        "texture": "sliding 808s and aggressive flows",
        "vibe": "cold and menacing",
        "energy": "relentless pressure with sparse melodies",
    },
    "emo rap": {
        "texture": "melancholic melodies and raw vocals",
        "vibe": "vulnerable and confessional",
        "energy": "emotional peaks with introspective valleys",
    },
    "cloud rap": {
        "texture": "dreamy synths and hazy production",
        "vibe": "ethereal and detached",
        "energy": "floating rhythms that drift and shimmer",
    },
    "boom bap": {
        "texture": "crisp drums and soulful samples",
        "vibe": "classic and head-nodding",
        "energy": "steady grooves with lyrical precision",
    },
    "g-funk": {
        "texture": "smooth synths and laid-back bass",
        "vibe": "West Coast and sun-soaked",
        "energy": "cruising rhythms with melodic hooks",
    },
    "crunk": {
        "texture": "aggressive chants and heavy bass",
        "vibe": "high energy and confrontational",
        "energy": "relentless party energy that demands movement",
    },
    "grime": {
        "texture": "icy synths and rapid-fire flows",
        "vibe": "raw and urban",
        "energy": "aggressive tempos with sharp edges",
    },
    "hyperpop": {
        "texture": "maximalist production and pitched vocals",
        "vibe": "chaotic and futuristic",
        "energy": "overwhelming sonic assault with euphoric peaks",
    },
    "vaporwave": {
        "texture": "chopped samples and reverb-drenched synths",
        "vibe": "nostalgic and surreal",
        "energy": "slow-motion grooves that feel like memory",
    },
    "synthwave": {
        "texture": "pulsing arpeggios and retro synths",
        "vibe": "80s nostalgia and neon-lit",
        "energy": "driving rhythms that chase the horizon",
    },
    "future bass": {
        "texture": "wobbly synths and pitched vocal chops",
        "vibe": "emotional and uplifting",
        "energy": "euphoric builds with cathartic drops",
    },
    "deep house": {
        "texture": "warm pads and rolling basslines",
        "vibe": "hypnotic and sophisticated",
        "energy": "slow-burning grooves that evolve subtly",
    },
    "techno": {
        "texture": "pounding kicks and mechanical rhythms",
        "vibe": "dark and industrial",
        "energy": "relentless forward motion that never stops",
    },
    "trance": {
        "texture": "euphoric melodies and pulsing builds",
        "vibe": "transcendent and anthemic",
        "energy": "soaring peaks that lift and release",
    },
    "dubstep": {
        "texture": "massive bass wobbles and aggressive drops",
        "vibe": "heavy and confrontational",
        "energy": "tension-building intros with devastating releases",
    },
    "drum and bass": {
        "texture": "rapid breakbeats and deep sub-bass",
        "vibe": "intense and propulsive",
        "energy": "high-speed rhythms that never let up",
    },
    "idm": {
        "texture": "glitchy rhythms and experimental sound design",
        "vibe": "cerebral and avant-garde",
        "energy": "unpredictable patterns that challenge and reward",
    },
    "downtempo": {
        "texture": "lush textures and spacious production",
        "vibe": "contemplative and warm",
        "energy": "slow, deliberate rhythms that breathe",
    },
    "chillout": {
        "texture": "soft pads and gentle rhythms",
        "vibe": "relaxed and ambient",
        "energy": "floating grooves that calm and soothe",
    },
    "grunge": {
        "texture": "dirty guitars and raw vocals",
        "vibe": "angsty and authentic",
        "energy": "dynamic swings between quiet and loud",
    },
    "post-rock": {
        "texture": "layered guitars and cinematic builds",
        "vibe": "epic and emotional",
        "energy": "slow crescendos that explode into catharsis",
    },
    "math rock": {
        "texture": "complex time signatures and intricate riffs",
        "vibe": "technical and playful",
        "energy": "unpredictable patterns with tight precision",
    },
    "stoner rock": {
        "texture": "heavy riffs and fuzz-drenched tones",
        "vibe": "hypnotic and primal",
        "energy": "slow, crushing grooves that build weight",
    },
    "doom metal": {
        "texture": "glacial tempos and massive distortion",
        "vibe": "oppressive and monolithic",
        "energy": "crushing weight that moves like molasses",
    },
    "black metal": {
        "texture": "tremolo riffs and blast beats",
        "vibe": "cold and atmospheric",
        "energy": "relentless fury with moments of haunting beauty",
    },
    "death metal": {
        "texture": "guttural vocals and technical riffs",
        "vibe": "brutal and uncompromising",
        "energy": "blistering speed with crushing breakdowns",
    },
    "progressive metal": {
        "texture": "complex arrangements and technical precision",
        "vibe": "epic and cerebral",
        "energy": "dynamic journeys through multiple movements",
    },
    "metalcore": {
        "texture": "breakdowns and melodic passages",
        "vibe": "aggressive and anthemic",
        "energy": "explosive verses with soaring choruses",
    },
    "djent": {
        "texture": "polyrhythmic chugs and atmospheric passages",
        "vibe": "technical and immersive",
        "energy": "precise grooves with ambient interludes",
    },
    "nu metal": {
        "texture": "downtuned riffs and hip-hop rhythms",
        "vibe": "aggressive and angsty",
        "energy": "bouncing grooves with explosive outbursts",
    },
    "power metal": {
        "texture": "soaring vocals and triumphant melodies",
        "vibe": "epic and fantasy-driven",
        "energy": "galloping rhythms with anthemic peaks",
    },
    "americana": {
        "texture": "rootsy instrumentation and storytelling",
        "vibe": "authentic and heartland",
        "energy": "honest grooves with emotional depth",
    },
    "bluegrass": {
        "texture": "acoustic strings and virtuosic picking",
        "vibe": "traditional and spirited",
        "energy": "rapid tempos with joyful interplay",
    },
    "outlaw country": {
        "texture": "raw guitars and defiant vocals",
        "vibe": "rebellious and authentic",
        "energy": "honest storytelling with no-frills attitude",
    },
    "indie folk": {
        "texture": "acoustic warmth and intimate vocals",
        "vibe": "personal and pastoral",
        "energy": "gentle strums with heartfelt delivery",
    },
    "chamber folk": {
        "texture": "orchestral arrangements and delicate vocals",
        "vibe": "elegant and introspective",
        "energy": "carefully crafted dynamics that breathe",
    },
    "quiet storm": {
        "texture": "smooth production and romantic vocals",
        "vibe": "intimate and sensual",
        "energy": "slow-burning grooves that seduce",
    },
    "afrobeat": {
        "texture": "polyrhythmic drums and horn sections",
        "vibe": "celebratory and hypnotic",
        "energy": "extended grooves that build collective movement",
    },
    "reggaeton": {
        "texture": "dembow rhythms and catchy hooks",
        "vibe": "party-ready and infectious",
        "energy": "irresistible grooves built for the club",
    },
    "latin pop": {
        "texture": "tropical rhythms and polished production",
        "vibe": "passionate and accessible",
        "energy": "danceable beats with romantic hooks",
    },
    "bossa nova": {
        "texture": "gentle guitar and sway rhythms",
        "vibe": "sophisticated and relaxed",
        "energy": "understated grooves that breathe warmth",
    },
    "flamenco": {
        "texture": "nylon guitar and percussive rhythms",
        "vibe": "passionate and dramatic",
        "energy": "building intensity with explosive flourishes",
    },
    "k-pop": {
        "texture": "polished production and hook-driven melodies",
        "vibe": "vibrant and precision-crafted",
        "energy": "high-energy performances with dynamic shifts",
    },
    "j-pop": {
        "texture": "bright melodies and playful arrangements",
        "vibe": "colorful and energetic",
        "energy": "catchy hooks with emotional sincerity",
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
CONNECTORS = [
    "with",
    "featuring",
    "built on",
    "driven by",
    "anchored by",
    "layered with",
]
BLEND_WORDS = [
    "blend",
    "mix",
    "fusion",
    "crossover",
    "collision",
    "meeting point",
    "marriage",
]

# Natural language openers for more organic phrasing
# These must work grammatically with patterns like "{opener} {genre}..." or "{opener} {g1} and {g2}..."
OPENERS = [
    # Imaginative
    "Imagine",
    "Picture",
    "Think",
    "Envision",
    # Descriptive
    "Something that sounds like",
    "Music that feels like",
    "The sonic equivalent of",
    "A soundscape inspired by",
    # Tribute
    "A love letter to",
    "An ode to",
    "A tribute to",
    "A nod to",
    # Evocative
    "Channeling the spirit of",
    "Capturing the essence of",
    "What happens when you combine",
    "The sound of",
    # Casual
    "Vibes of",
    "The energy of",
    "A modern take on",
]

# Action-oriented verbs for dynamic templates
ACTION_VERBS = [
    # Collision
    "meets",
    "crashes into",
    "collides with",
    "slams into",
    # Fusion
    "bleeds into",
    "merges with",
    "fuses with",
    "melts into",
    # Dance
    "dances with",
    "grooves with",
    "vibes with",
    "flows into",
    # Layering
    "wraps around",
    "layers over",
    "weaves through",
    "threads into",
    # Tension
    "clashes with",
    "wrestles with",
    "tangles with",
    "sparks against",
]

# Vibe descriptors for endings
VIBE_ENDINGS = [
    # Breathing room
    "Let it breathe.",
    "Give it space.",
    "Let it unfold.",
    # Raw energy
    "Keep it raw.",
    "Keep it real.",
    "Keep it honest.",
    "Stay authentic.",
    # Impact
    "Make it hit.",
    "Make it land.",
    "Make it count.",
    "Make it stick.",
    # Movement
    "Keep it moving.",
    "Let it flow.",
    "Keep the momentum.",
    # Evolution
    "Let it evolve.",
    "Let it grow.",
    "Let it build.",
    # Emotional
    "Make it feel alive.",
    "Make it resonate.",
    "Make it memorable.",
    # Weight
    "Something with weight.",
    "Something that lingers.",
    "Something undeniable.",
    "Something you can feel.",
    "Something that stays with you.",
    # Minimal closers
    "No filler.",
    "All signal.",
    "Pure intent.",
    "Nothing wasted.",
]


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
        Generate a natural-sounding concept string from chosen genres.

        Uses multiple template styles to avoid "mad libs" repetitiveness:
        - Descriptive ("A track with...")
        - Evocative ("Imagine..." / "Picture...")
        - Action-oriented ("Where X meets Y")
        - Minimal ("X vibes. Keep it raw.")

        Returns (concept, inferred_mood)
        """
        mood = mood_hint or random.choice(DEFAULT_MOODS)
        conn = random.choice(CONNECTORS)
        opener = random.choice(OPENERS)
        action = random.choice(ACTION_VERBS)
        ending = random.choice(VIBE_ENDINGS)

        if not chosen_genres:
            # Complete fallback - no genres
            texture = random.choice(DEFAULT_TEXTURES)
            vibe = random.choice(DEFAULT_VIBES)
            templates = [
                f"A track {conn} {texture}. {ending}",
                f"{opener} {texture}. {vibe.capitalize()} and expressive.",
                f"Something {conn} {texture}. {ending}",
            ]
            return random.choice(templates), mood

        # Build concept from genre descriptors
        # Note: Do NOT capitalize genre/artist names - preserve original casing
        if len(chosen_genres) == 1:
            genre = chosen_genres[0]
            desc = self._get_genre_descriptor(genre)
            templates = [
                # Descriptive
                f"A {genre} track {conn} {desc['texture']}.",
                f"{_cap_first(genre)} vibes, {conn} {desc['texture']}.",
                # Evocative
                f"{opener} {genre}. {_cap_first(desc['texture'])}.",
                f"Channeling {genre}. {_cap_first(desc['vibe'])} energy.",
                # Minimal
                f"{_cap_first(genre)}. {ending}",
                f"Pure {genre}. {_cap_first(desc['texture'])}.",
                # Energy-focused
                f"A {genre} song that {desc['energy']}.",
            ]
        elif len(chosen_genres) == 2:
            g1, g2 = chosen_genres
            d1 = self._get_genre_descriptor(g1)
            d2 = self._get_genre_descriptor(g2)
            blend = random.choice(BLEND_WORDS)
            templates = [
                # Action-oriented
                f"Where {g1} {action} {g2}. {_cap_first(d1['texture'])}.",
                f"{_cap_first(g1)} {action} {g2}. {ending}",
                # Blend-focused
                f"A {blend} of {g1} and {g2}. {_cap_first(d1['vibe'])}.",
                f"The {blend} of {g1} and {g2}. {ending}",
                # Evocative
                f"{opener} {g1} and {g2} had a conversation. {_cap_first(d1['texture'])}.",
                f"{opener} {g1} through a {g2} lens.",
                # Minimal
                f"{_cap_first(g1)} meets {g2}. {ending}",
                f"{_cap_first(g1)} and {g2}. {_cap_first(d2['vibe'])} vibes.",
            ]
        elif len(chosen_genres) == 3:
            g1, g2, g3 = chosen_genres[:3]
            d1 = self._get_genre_descriptor(g1)
            templates = [
                # Descriptive
                f"Drawing from {g1}, {g2}, and {g3}. {_cap_first(d1['texture'])}.",
                f"Taking cues from {g1}, {g2}, {g3}. {ending}",
                # Action-oriented
                f"{_cap_first(g1)} {action} {g2}, with {g3} undertones.",
                f"Where {g1}, {g2}, and {g3} overlap. {_cap_first(d1['vibe'])}.",
                # Evocative
                f"{opener} {g1}, {g2}, and {g3} in the same room.",
                f"A three-way {random.choice(BLEND_WORDS)} of {g1}, {g2}, {g3}.",
                # Minimal
                f"{_cap_first(g1)}, {g2}, {g3}. {ending}",
            ]
        elif len(chosen_genres) == 4:
            g1, g2, g3, g4 = chosen_genres[:4]
            d1 = self._get_genre_descriptor(g1)
            blend = random.choice(BLEND_WORDS)
            templates = [
                # Descriptive
                f"A {blend} of {g1}, {g2}, {g3}, and {g4}. {_cap_first(d1['texture'])}.",
                f"Pulling from {g1}, {g2}, {g3}, {g4}. {ending}",
                # Action-oriented
                f"Where {g1} and {g2} meet {g3} and {g4}. {_cap_first(d1['vibe'])}.",
                # Evocative
                f"{opener} {g1}, {g2}, {g3}, and {g4} all at once.",
                f"Weaving {g1}, {g2}, {g3}, {g4} together. {ending}",
                # Minimal
                f"{_cap_first(g1)}, {g2}, {g3}, {g4}. {ending}",
            ]
        else:  # 5+ genres
            g1, g2, g3, g4, g5 = chosen_genres[:5]
            d1 = self._get_genre_descriptor(g1)
            blend = random.choice(BLEND_WORDS)
            templates = [
                # Descriptive
                f"A rich {blend} of {g1}, {g2}, {g3}, {g4}, and {g5}. {_cap_first(d1['texture'])}.",
                f"Pulling from {g1}, {g2}, {g3}, {g4}, {g5}. {ending}",
                # Action-oriented
                f"Where {g1} and {g2} collide with {g3}, {g4}, {g5}.",
                # Evocative
                f"Blending {g1}, {g2}, {g3}, {g4}, {g5} into something new.",
                f"{opener} all of {g1}, {g2}, {g3}, {g4}, {g5} at once. {ending}",
                # Minimal
                f"{_cap_first(g1)}, {g2}, {g3}, {g4}, {g5}. Eclectic and {d1['vibe']}.",
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
