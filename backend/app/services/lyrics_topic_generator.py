"""
Lyrics topic generator service.

Generates a short lyric topic/theme based on genre/mood influences.
This is the "lyrics input side" - the returned topic can be used
as the lyrics_about field in full generation.

Design principles:
- Pure: does not call external APIs directly
- Simple: v1 uses templates with variance; can be upgraded to LLM-based later
- Aligned: optionally incorporates style_prompt context for coherence
"""

import random
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class LyricsTopicResult:
    """Result of lyrics topic generation."""

    topic: str
    chosen_moods: List[str]
    reasoning: Optional[str] = None


# Theme templates by mood category
MOOD_THEMES: dict[str, list[str]] = {
    "melancholic": [
        "A bittersweet memory of someone who slipped away",
        "The quiet ache of an empty room",
        "Watching rain trace paths down a window, thinking of what could have been",
        "The last conversation that never happened",
        "Finding old photos and reliving faded moments",
    ],
    "uplifting": [
        "Breaking free and chasing the horizon",
        "Dancing through the chaos with unshakable joy",
        "The moment everything clicks into place",
        "Rising from the ashes stronger than before",
        "Celebrating the small victories that matter most",
    ],
    "romantic": [
        "The electric moment before a first kiss",
        "Falling in love in the most unexpected place",
        "A love letter written but never sent",
        "The comfort of knowing someone truly sees you",
        "Late night conversations that last until dawn",
    ],
    "rebellious": [
        "Refusing to play by their rules anymore",
        "Burning bridges with zero regrets",
        "The thrill of choosing chaos over conformity",
        "Standing alone against the world",
        "Reclaiming your power from those who took it",
    ],
    "nostalgic": [
        "Summer nights that seemed to last forever",
        "The soundtrack of your teenage years",
        "Returning to a place that's changed but still feels like home",
        "Missing the person you used to be",
        "Old friends reuniting after years apart",
    ],
    "introspective": [
        "Questioning everything you thought you knew",
        "The quiet battle between who you are and who you want to be",
        "Learning to be comfortable in your own skin",
        "The weight of unspoken thoughts",
        "Finding meaning in the mundane",
    ],
    "dark": [
        "The shadows that follow even in daylight",
        "Confronting the demons you've been running from",
        "The seductive pull of self-destruction",
        "Secrets buried so deep they've become part of you",
        "Walking the line between sanity and surrender",
    ],
    "playful": [
        "A ridiculous adventure with no destination in mind",
        "Flirting with danger just for the fun of it",
        "Inside jokes that only you and your crew understand",
        "Making bad decisions with good friends",
        "The absurdity of everyday life",
    ],
    "empowering": [
        "Owning your story, scars and all",
        "The confidence that comes from surviving",
        "Telling your doubters to watch and learn",
        "Becoming the person others underestimated",
        "Turning pain into unstoppable power",
    ],
    "dreamy": [
        "Floating through a world that exists only at night",
        "Losing yourself in a daydream you don't want to leave",
        "The blurred line between fantasy and reality",
        "Chasing visions that dissolve at dawn",
        "A love that feels like a beautiful hallucination",
    ],
}

# Genre-to-mood affinities (for when no moods are provided)
GENRE_MOOD_AFFINITIES: dict[str, list[str]] = {
    "indie rock": ["melancholic", "introspective", "nostalgic"],
    "electronic": ["dreamy", "dark", "uplifting"],
    "hip-hop": ["rebellious", "empowering", "playful"],
    "r&b": ["romantic", "introspective", "dreamy"],
    "pop": ["uplifting", "romantic", "playful"],
    "metal": ["dark", "rebellious", "empowering"],
    "folk": ["nostalgic", "introspective", "melancholic"],
    "punk": ["rebellious", "dark", "playful"],
    "ambient": ["dreamy", "introspective", "melancholic"],
    "jazz": ["romantic", "introspective", "nostalgic"],
    "country": ["nostalgic", "romantic", "melancholic"],
    "dance": ["uplifting", "playful", "empowering"],
}

# Fallback seed moods when nothing is provided
FALLBACK_MOODS = ["introspective", "uplifting", "melancholic", "romantic", "dreamy"]


class LyricsTopicGenerator:
    """
    Generates short lyric topics based on mood/genre influences.

    v1: Template-based with variance.
    Future: Can be upgraded to LLM-based for more creative results.
    """

    def __init__(self, seed: Optional[int] = None):
        """
        Initialize the generator.

        Args:
            seed: Optional random seed for reproducible results (testing).
        """
        self._rng = random.Random(seed)

    async def generate(
        self,
        genres: List[str],
        moods: List[str],
        style_prompt: Optional[str] = None,
    ) -> LyricsTopicResult:
        """
        Generate a lyric topic from influences.

        Args:
            genres: List of genre influences (used to infer moods if moods empty).
            moods: List of mood tags.
            style_prompt: Optional style prompt for context alignment.

        Returns:
            LyricsTopicResult with topic and metadata.
        """
        # Determine which moods to use
        effective_moods = self._resolve_moods(genres, moods)

        # Pick 1-2 moods to blend
        num_moods = min(len(effective_moods), self._rng.randint(1, 2))
        chosen_moods = self._rng.sample(effective_moods, num_moods)

        # Generate topic from chosen moods
        topic = self._generate_topic_from_moods(chosen_moods, style_prompt)

        return LyricsTopicResult(
            topic=topic,
            chosen_moods=chosen_moods,
            reasoning=f"Blended moods: {', '.join(chosen_moods)}",
        )

    def _resolve_moods(
        self,
        genres: List[str],
        moods: List[str],
    ) -> List[str]:
        """Determine effective moods from inputs or fallbacks."""
        # If moods provided, use them (filter to known moods)
        if moods:
            known_moods = [m.lower() for m in moods if m.lower() in MOOD_THEMES]
            if known_moods:
                return known_moods

        # Infer moods from genres
        inferred_moods: set[str] = set()
        for genre in genres:
            genre_lower = genre.lower()
            for known_genre, affinities in GENRE_MOOD_AFFINITIES.items():
                if known_genre in genre_lower or genre_lower in known_genre:
                    inferred_moods.update(affinities)
                    break

        if inferred_moods:
            return list(inferred_moods)

        # Fallback to seed moods
        return FALLBACK_MOODS.copy()

    def _generate_topic_from_moods(
        self,
        chosen_moods: List[str],
        style_prompt: Optional[str],
    ) -> str:
        """Generate a topic string from chosen moods."""
        # Collect candidate themes from all chosen moods
        candidates: List[str] = []
        for mood in chosen_moods:
            if mood in MOOD_THEMES:
                candidates.extend(MOOD_THEMES[mood])

        if not candidates:
            # Ultimate fallback
            candidates = [
                "A moment that changed everything",
                "The feeling of being truly alive",
                "Searching for meaning in the noise",
            ]

        # Pick a random theme
        topic = self._rng.choice(candidates)

        # Optionally add style context hint
        if style_prompt and len(style_prompt) > 20:
            # Extract a vibe hint if style_prompt is substantial
            # Just return the base topic for v1 (LLM integration later)
            pass

        return topic


async def generate_lyrics_topic(
    genres: List[str],
    moods: List[str],
    style_prompt: Optional[str] = None,
) -> LyricsTopicResult:
    """
    Convenience function to generate a lyrics topic.

    Args:
        genres: List of genre influences.
        moods: List of mood tags.
        style_prompt: Optional style prompt for context.

    Returns:
        LyricsTopicResult with the generated topic.
    """
    generator = LyricsTopicGenerator()
    return await generator.generate(genres, moods, style_prompt)
