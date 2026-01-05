"""
Influence provider abstractions for genres and artists.

These providers determine which genres/artists to use as influences for
generating Suno input concepts. The architecture allows plugging in
multiple sources (manual input, Spotify, user profiles) without
changing the core generation logic.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Sequence


@dataclass
class InfluenceContext:
    """Context passed to providers to help them determine influences."""

    user_id: Optional[str] = None  # For future auth integration
    # Future: session_id, preferences, etc.


# Alias for backward compatibility
ArtistInfluenceContext = InfluenceContext


# =============================================================================
# GENRE PROVIDERS
# =============================================================================


class GenreInfluenceProvider(ABC):
    """Abstract base for genre influence providers."""

    @abstractmethod
    async def get_influence_genres(self, ctx: InfluenceContext) -> List[str]:
        """Return a list of genres to use as influences."""
        ...


class ManualInputGenreProvider(GenreInfluenceProvider):
    """
    Provider that returns exactly what was passed in from the request body.
    This is the primary provider for v1.
    """

    def __init__(self, genres: Sequence[str]):
        self._genres = list(genres)

    async def get_influence_genres(self, ctx: InfluenceContext) -> List[str]:
        return self._genres


class FallbackSeedGenreProvider(GenreInfluenceProvider):
    """
    Provider that returns a predefined list of seed genres
    when no other sources are available.
    """

    # Diverse seed genres for fallback
    DEFAULT_SEEDS = [
        "indie rock",
        "electronic",
        "hip-hop",
        "R&B",
        "ambient",
        "trip-hop",
        "post-punk",
        "synth-pop",
        "shoegaze",
        "jazz fusion",
        "neo-soul",
        "art pop",
        "progressive rock",
        "lo-fi",
        "dream pop",
        "industrial",
        "funk",
        "psychedelic",
        "house",
        "folk",
    ]

    def __init__(self, seeds: Optional[Sequence[str]] = None):
        self._seeds = list(seeds) if seeds else self.DEFAULT_SEEDS

    async def get_influence_genres(self, ctx: InfluenceContext) -> List[str]:
        return self._seeds


class CompositeGenreInfluenceProvider(GenreInfluenceProvider):
    """
    Composes multiple genre providers and merges their results.
    """

    def __init__(
        self,
        providers: Sequence[GenreInfluenceProvider],
        max_genres: int = 20,
    ):
        self._providers = list(providers)
        self._max_genres = max_genres

    async def get_influence_genres(self, ctx: InfluenceContext) -> List[str]:
        import asyncio

        results = await asyncio.gather(
            *(p.get_influence_genres(ctx) for p in self._providers)
        )

        # Merge and deduplicate, preserving order
        seen: set[str] = set()
        merged: list[str] = []
        for genre_list in results:
            for genre in genre_list:
                normalized = genre.strip()
                if normalized and normalized.lower() not in seen:
                    seen.add(normalized.lower())
                    merged.append(normalized)
                    if len(merged) >= self._max_genres:
                        return merged

        return merged


# =============================================================================
# ARTIST PROVIDERS (kept for future use)
# =============================================================================


class ArtistInfluenceProvider(ABC):
    """Abstract base for artist influence providers."""

    @abstractmethod
    async def get_influence_artists(
        self, ctx: InfluenceContext
    ) -> List[str]:
        """Return a list of artist names to use as influences."""
        ...


class ManualInputArtistProvider(ArtistInfluenceProvider):
    """
    Provider that returns exactly what was passed in from the request body.
    This is the primary provider for v1.
    """

    def __init__(self, artists: Sequence[str]):
        self._artists = list(artists)

    async def get_influence_artists(
        self, ctx: InfluenceContext
    ) -> List[str]:
        return self._artists


class EmptyProvider(ArtistInfluenceProvider):
    """Provider that always returns an empty list (for anonymous/default sessions)."""

    async def get_influence_artists(
        self, ctx: InfluenceContext
    ) -> List[str]:
        return []


class FallbackSeedProvider(ArtistInfluenceProvider):
    """
    Provider that returns a predefined list of seed artists
    when no other sources are available.
    """

    # Diverse seed artists across genres for fallback
    DEFAULT_SEEDS = [
        "Radiohead",
        "Daft Punk",
        "Kendrick Lamar",
        "Björk",
        "The Strokes",
        "Portishead",
        "OutKast",
        "Tame Impala",
        "FKA twigs",
        "LCD Soundsystem",
        "Massive Attack",
        "Frank Ocean",
        "Aphex Twin",
        "St. Vincent",
        "Flying Lotus",
    ]

    def __init__(self, seeds: Optional[Sequence[str]] = None):
        self._seeds = list(seeds) if seeds else self.DEFAULT_SEEDS

    async def get_influence_artists(
        self, ctx: InfluenceContext
    ) -> List[str]:
        return self._seeds


class CompositeArtistInfluenceProvider(ArtistInfluenceProvider):
    """
    Composes multiple providers and merges their results.

    For v1: instantiate with [ManualInputArtistProvider(artists_from_body)]
    Later: add SpotifyArtistProvider, UserProfileArtistProvider, etc.
    """

    def __init__(
        self,
        providers: Sequence[ArtistInfluenceProvider],
        max_artists: int = 20,
    ):
        self._providers = list(providers)
        self._max_artists = max_artists

    async def get_influence_artists(
        self, ctx: InfluenceContext
    ) -> List[str]:
        import asyncio

        results = await asyncio.gather(
            *(p.get_influence_artists(ctx) for p in self._providers)
        )

        # Merge and deduplicate, preserving order
        seen: set[str] = set()
        merged: list[str] = []
        for artist_list in results:
            for artist in artist_list:
                normalized = artist.strip()
                if normalized and normalized.lower() not in seen:
                    seen.add(normalized.lower())
                    merged.append(normalized)
                    if len(merged) >= self._max_artists:
                        return merged

        return merged

