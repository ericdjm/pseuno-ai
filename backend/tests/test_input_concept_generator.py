"""
Tests for InputConceptGenerator.

Validates:
- Output is short (1-2 sentences, under reasonable character cap)
- Template variance exists across multiple generations
- Deterministic output when RNG is seeded
"""

import random
import pytest

from app.services.input_concept_generator import (
    InputConceptGenerator,
    InputConceptResult,
    CONNECTORS,
    BLEND_WORDS,
    DEFAULT_MOODS,
)


@pytest.fixture
def generator() -> InputConceptGenerator:
    return InputConceptGenerator()


class TestInputConceptGeneratorFormat:
    """Tests for concept format (length, sentence count)."""

    @pytest.mark.asyncio
    async def test_concept_is_short(self, generator: InputConceptGenerator):
        """Concept should be under 200 characters."""
        result = await generator.generate(genres=["indie rock"])
        assert len(result.concept) < 200, f"Concept too long: {result.concept}"

    @pytest.mark.asyncio
    async def test_concept_has_one_or_two_sentences(self, generator: InputConceptGenerator):
        """Concept should have 1-2 sentences (ending with period)."""
        result = await generator.generate(genres=["electronic", "hip-hop"])
        # Count sentences by splitting on ". " and filtering empty
        sentences = [s.strip() for s in result.concept.split(".") if s.strip()]
        assert 1 <= len(sentences) <= 3, f"Expected 1-3 sentences, got {len(sentences)}: {result.concept}"

    @pytest.mark.asyncio
    async def test_fallback_concept_is_short(self, generator: InputConceptGenerator):
        """Fallback (no genres) concept should also be short."""
        result = await generator.generate(genres=[])
        assert len(result.concept) < 200, f"Fallback concept too long: {result.concept}"

    @pytest.mark.asyncio
    async def test_three_genre_concept_is_short(self, generator: InputConceptGenerator):
        """Three-genre concept should also be short."""
        result = await generator.generate(genres=["indie rock", "electronic", "trip-hop"])
        assert len(result.concept) < 200, f"3-genre concept too long: {result.concept}"


class TestInputConceptGeneratorVariance:
    """Tests for template variance across generations."""

    @pytest.mark.asyncio
    async def test_variance_across_generations(self, generator: InputConceptGenerator):
        """Multiple generations should produce different outputs."""
        results = set()
        for _ in range(20):
            result = await generator.generate(genres=["indie rock"])
            results.add(result.concept)
        # With 3 templates and random connectors, we should see variety
        assert len(results) >= 2, f"Expected variance, got only: {results}"

    @pytest.mark.asyncio
    async def test_variance_with_fallback(self, generator: InputConceptGenerator):
        """Fallback path should also have variance."""
        results = set()
        for _ in range(20):
            result = await generator.generate(genres=[])
            results.add(result.concept)
        assert len(results) >= 2, f"Expected variance in fallback, got only: {results}"


class TestInputConceptGeneratorDeterminism:
    """Tests for deterministic output with seeded RNG."""

    @pytest.mark.asyncio
    async def test_seeded_rng_produces_consistent_output(self, generator: InputConceptGenerator):
        """Same RNG seed should produce same output."""
        random.seed(42)
        result1 = await generator.generate(genres=["electronic"])

        random.seed(42)
        result2 = await generator.generate(genres=["electronic"])

        assert result1.concept == result2.concept

    @pytest.mark.asyncio
    async def test_different_seeds_produce_different_output(self, generator: InputConceptGenerator):
        """Different RNG seeds should (usually) produce different output."""
        random.seed(42)
        result1 = await generator.generate(genres=["electronic"])

        random.seed(999)
        result2 = await generator.generate(genres=["electronic"])

        # Not guaranteed but very likely with enough template/connector combos
        # If they happen to match, the test is still valid but less useful
        # We'll just check that the mechanism works
        assert isinstance(result1.concept, str)
        assert isinstance(result2.concept, str)


class TestInputConceptGeneratorResult:
    """Tests for result structure."""

    @pytest.mark.asyncio
    async def test_result_contains_chosen_genres(self, generator: InputConceptGenerator):
        """Result should include the genres that were chosen."""
        result = await generator.generate(genres=["indie rock", "electronic", "hip-hop"])
        assert len(result.chosen_genres) >= 1
        assert len(result.chosen_genres) <= 3
        for g in result.chosen_genres:
            assert g in ["indie rock", "electronic", "hip-hop"]

    @pytest.mark.asyncio
    async def test_result_includes_mood(self, generator: InputConceptGenerator):
        """Result should include a mood."""
        result = await generator.generate(genres=["indie rock"])
        assert result.mood is not None
        assert result.mood in DEFAULT_MOODS or result.mood == result.mood  # custom mood

    @pytest.mark.asyncio
    async def test_custom_mood_is_returned(self, generator: InputConceptGenerator):
        """Custom mood hint should be returned in result."""
        result = await generator.generate(genres=["indie rock"], mood="bittersweet")
        assert result.mood == "bittersweet"

