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

import asyncio
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

        Randomly selects 1-3 genres from the list (fallback seeds if empty).
        Uses template variants for natural variance across generations.
        """
        ctx = InfluenceContext(user_id=user_id)

        # Build genre list from manual input
        genre_list = list(genres) if genres else []

        # If empty, use fallback provider
        if not genre_list:
            fallback_genres = await self._fallback_provider.get_influence_genres(ctx)
            genre_list = fallback_genres

        # Pick 1-3 random genres
        num_to_pick = min(random.randint(1, 3), len(genre_list))
        chosen_genres = random.sample(genre_list, num_to_pick) if genre_list else []

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
        if len(chosen_genres) == 1:
            genre = chosen_genres[0]
            desc = self._get_genre_descriptor(genre)
            templates = [
                f"A {genre} track {conn} {desc['texture']}.",
                f"{genre.capitalize()}. {desc['texture'].capitalize()}.",
                f"{genre.capitalize()} vibes, {conn} {desc['texture']}.",
            ]
        elif len(chosen_genres) == 2:
            g1, g2 = chosen_genres
            d1 = self._get_genre_descriptor(g1)
            blend = random.choice(BLEND_WORDS)
            templates = [
                f"A {blend} of {g1} and {g2}. {d1['texture'].capitalize()}.",
                f"{g1.capitalize()} meets {g2}, {conn} {d1['texture']}.",
                f"{g1.capitalize()}/{g2} {blend}. {d1['vibe'].capitalize()}.",
            ]
        else:  # 3 genres
            g1, g2, g3 = chosen_genres[:3]
            d1 = self._get_genre_descriptor(g1)
            templates = [
                f"{g1.capitalize()}, {g2}, and {g3}. {d1['texture'].capitalize()}.",
                f"A take on {g1}, {g2}, {g3}. {d1['texture'].capitalize()}.",
                f"Crossing {g1} with {g2} and {g3}. {d1['vibe'].capitalize()}.",
            ]

        return random.choice(templates), mood

    def _get_genre_descriptor(self, genre: str) -> dict[str, str]:
        """Get descriptor for a genre, with fallback for unknown genres."""
        key = genre.lower().strip()
        if key in GENRE_DESCRIPTORS:
            return GENRE_DESCRIPTORS[key]
        # Fallback for unknown genre
        return {
            "texture": f"elements characteristic of {genre}",
            "vibe": random.choice(DEFAULT_VIBES),
            "energy": random.choice(DEFAULT_ENERGIES),
        }


async def create_generator_with_providers(
    request_genres: Sequence[str],
    request_artists: Sequence[str] = (),
    user_id: Optional[str] = None,
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
    generator = InputConceptGenerator()

    return generator, composite


# =============================================================================
# PROMPT REFINEMENT
# =============================================================================


async def refine_concept_with_llm(
    current_prompt: str,
    change_request: str,
    settings,
) -> str:
    """
    Refine an existing prompt based on user feedback using LLM.

    Uses the default model from settings to make targeted edits to the prompt
    while preserving the original intent.
    """
    import httpx

    # Decide which model/API to use
    model = settings.llm_model
    is_gemini = model in {
        "gemini-3-flash-preview",
        "gemini-3-pro-preview",
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-2.0-flash",
    }

    system_prompt = """You are a helpful assistant that refines Suno music prompts based on user feedback.

Your task:
1. Read the current prompt and the user's change request
2. Make ONLY the changes the user requested
3. Preserve all other aspects of the original prompt
4. Keep the result concise (max 500 characters)
5. Return ONLY the refined prompt, no explanations or preamble

The prompt should describe a musical style/vibe in 2-3 clear sentences."""

    user_message = f"""Current prompt:
{current_prompt}

Change request:
{change_request}

Refined prompt:"""

    if is_gemini:
        # Use Google Generative AI (new google-genai SDK)
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is required for Gemini models")

        from google import genai
        from google.genai import types

        def _sync_generate():
            client = genai.Client(api_key=settings.gemini_api_key)
            config = types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=500,
                system_instruction=system_prompt,
            )
            response = client.models.generate_content(
                model=model,
                contents=[
                    types.Content(
                        role="user", parts=[types.Part.from_text(text=user_message)]
                    )
                ],
                config=config,
            )
            return response.text if response.text else ""

        refined = await asyncio.to_thread(_sync_generate)
        refined = refined.strip()

    else:
        # Use OpenAI-compatible API
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required for OpenAI models")

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0.7,
            "max_tokens": 500,
        }

        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            refined = data["choices"][0]["message"]["content"].strip()

    # Enforce max length
    if len(refined) > 500:
        refined = refined[:500].rsplit(" ", 1)[0]  # Trim at word boundary

    return refined


async def refine_lyrics_with_llm(
    current_lyrics: str,
    change_request: str,
    settings,
) -> str:
    """
    Refine lyrics using LLM based on user feedback while preserving structure.

    Args:
        current_lyrics: The current lyrics text with structure markers
        change_request: What the user wants to change
        settings: App settings (contains llm_model, openai_api_key, etc.)

    Returns:
        The refined lyrics as a string
    """
    import httpx

    model = settings.llm_model
    is_gemini = "gemini" in model.lower()

    system_prompt = """You are a lyrics refinement assistant. Your job is to:

1. Preserve ALL structure markers like [Verse], [Chorus], [Bridge], [Outro], [Intro], etc.
2. Make ONLY the changes the user specifically requested
3. Do not modify parts of the lyrics the user didn't mention
4. Keep the lyrical style and tone consistent with the original unless asked to change it
5. Return ONLY the complete refined lyrics with all structure markers intact

Examples:
- If user says "change the chorus", only modify the [Chorus] section
- If user says "add another verse", insert a new [Verse] section in an appropriate location
- If user says "make it darker", adjust the tone while preserving the structure

Important: Return the COMPLETE lyrics, not just the changed parts."""

    user_message = f"""Current lyrics:
{current_lyrics}

Change request:
{change_request}

Refined lyrics:"""

    if is_gemini:
        # Use Google Generative AI (new google-genai SDK)
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is required for Gemini models")

        from google import genai
        from google.genai import types

        def _sync_generate():
            client = genai.Client(api_key=settings.gemini_api_key)
            config = types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=2000,
                system_instruction=system_prompt,
            )
            response = client.models.generate_content(
                model=model,
                contents=[
                    types.Content(
                        role="user", parts=[types.Part.from_text(text=user_message)]
                    )
                ],
                config=config,
            )
            return response.text if response.text else ""

        refined = await asyncio.to_thread(_sync_generate)
        refined = refined.strip()

    else:
        # Use OpenAI-compatible API
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required for OpenAI models")

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0.7,
            "max_tokens": 2000,
        }

        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            refined = data["choices"][0]["message"]["content"].strip()

    # Enforce max length
    if len(refined) > 3000:
        refined = refined[:3000].rsplit("\n", 1)[0]  # Trim at line boundary

    return refined
