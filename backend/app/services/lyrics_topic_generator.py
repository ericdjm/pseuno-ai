"""
Lyrics topic generator service.

Generates a short lyric topic/theme based on genre/mood/style influences.
Uses trait-based routing to select from curated topic banks.

Design principles:
- Pure: does not call external APIs directly (LLM classification is async/optional)
- Fast: trait scoring is instant, no LLM at generation time
- Varied: recency memory prevents repeats within a session
- Extensible: async classifier can improve routing (future)
"""

import random
from collections import deque
from dataclasses import dataclass
from typing import Dict, List, Optional

from app.services.lyrics_topic_banks import TOPIC_BANKS
import re
from app.services.lyrics_topic_traits import (
    extract_traits_from_style_prompt,
    get_default_traits,
    infer_traits_from_tags,
    merge_traits,
    score_bank_match,
)


@dataclass
class LyricsTopicResult:
    """Result of lyrics topic generation."""

    topic: str
    bank_id: str
    traits_used: Dict[str, float]
    chosen_moods: List[str]  # Kept for backward compatibility
    reasoning: Optional[str] = None


class RecencyMemory:
    """
    Tracks recently used prompts to avoid repetition.

    Per-session memory with configurable window size.
    In production, this should be stored in Redis/session store keyed by device_id.
    """

    def __init__(self, max_size: int = 30):
        self._recent: deque[str] = deque(maxlen=max_size)

    def is_recent(self, prompt: str) -> bool:
        """Check if a prompt was recently used."""
        return prompt in self._recent

    def record(self, prompt: str) -> None:
        """Record a prompt as recently used."""
        self._recent.append(prompt)

    def filter_prompts(self, prompts: tuple[str, ...]) -> List[str]:
        """Return prompts not in recent memory."""
        return [p for p in prompts if p not in self._recent]

    def clear(self) -> None:
        """Clear recency memory."""
        self._recent.clear()


class LyricsTopicGenerator:
    """
    Generates lyrics topics via trait-based bank selection.

    Flow:
    1. Infer traits from tags (instant heuristics)
    2. Score all banks against traits
    3. Sample a bank proportional to scores (or pool from top banks if multi_bank=True)
    4. Sample a prompt from that bank (avoiding recents)
    """

    def __init__(
        self,
        seed: Optional[int] = None,
        recency_memory: Optional[RecencyMemory] = None,
    ):
        """
        Initialize the generator.

        Args:
            seed: Optional random seed for reproducible results (testing).
            recency_memory: Optional shared recency memory (for session persistence).
        """
        self._rng = random.Random(seed)
        self._recency = recency_memory or RecencyMemory()

    def _get_top_banks(
        self,
        probabilities: Dict[str, float],
        max_banks: int = 3,
        min_probability: float = 0.1,
    ) -> List[tuple[str, float]]:
        """
        Get top banks that meet the probability threshold.

        When trait_overrides come from the async classifier with multi-modal
        distributions (e.g., 40% prog metal, 35% djent), this allows sampling
        from a weighted pool of the top matching banks instead of just one.

        Args:
            probabilities: bank_id -> probability from softmax
            max_banks: Maximum banks to include in pool
            min_probability: Minimum probability to include a bank

        Returns:
            List of (bank_id, probability) tuples, sorted by probability desc
        """
        # Sort by probability descending
        sorted_banks = sorted(probabilities.items(), key=lambda x: -x[1])

        # Take top banks that meet threshold
        top_banks = []
        for bank_id, prob in sorted_banks[:max_banks]:
            if prob >= min_probability:
                top_banks.append((bank_id, prob))

        return top_banks

    async def generate(
        self,
        tags: List[str],
        style_prompt: Optional[str] = None,
        trait_overrides: Optional[Dict[str, float]] = None,
        bank_similarities: Optional[Dict[str, float]] = None,
        multi_bank_pool: bool = False,
    ) -> LyricsTopicResult:
        """
        Generate a lyrics topic from user context.

        Args:
            tags: List of genre/mood/artist tags (unified).
            style_prompt: Optional style description (for future async classifier).
            trait_overrides: Optional pre-computed traits (from async classifier cache).
            bank_similarities: Optional embedding-based similarity scores for banks.
            multi_bank_pool: If True, pool prompts from top banks weighted by score.
                             Useful when async classifier returns multi-modal traits.

        Returns:
            LyricsTopicResult with topic and metadata.
        """
        def _is_informative_override(traits_in: Dict[str, float]) -> bool:
            if not traits_in:
                return False
            # Treat 1 generic trait as low-confidence; require either multiple traits
            # or a strong top trait.
            max_w = max(traits_in.values()) if traits_in else 0.0
            num_mid = sum(1 for v in traits_in.values() if v >= 0.55)
            return num_mid >= 2 or max_w >= 0.75

        # Step 1: Determine traits
        informative_trait_overrides = bool(trait_overrides and _is_informative_override(trait_overrides))
        if informative_trait_overrides:
            traits = trait_overrides or {}
            inferred_tag_traits = {}
            inferred_style_traits = {}
        else:
            # Start with tag-based traits
            inferred_tag_traits = infer_traits_from_tags(tags) if tags else {}

            # Extract traits from style_prompt (if provided)
            inferred_style_traits = (
                extract_traits_from_style_prompt(style_prompt) if style_prompt else {}
            )

            # Merge: style_prompt supplements but doesn't override explicit tags
            if inferred_tag_traits and inferred_style_traits:
                traits = merge_traits(
                    inferred_tag_traits, inferred_style_traits, strategy="max"
                )
            elif inferred_tag_traits:
                traits = inferred_tag_traits
            elif inferred_style_traits:
                traits = inferred_style_traits
            else:
                traits = get_default_traits()

        # IMPORTANT: We do NOT compute embeddings inside /generate/lyrics-topic.
        # Embedding-based routing is asynchronous: the frontend calls /generate/classify-style
        # in the background and passes bank_similarities into this endpoint when ready.

        # "Real traits" should override embeddings. But weak single-keyword matches
        # (e.g., "rich") shouldn't drown out explicit entities (e.g., an artist name).
        if inferred_tag_traits:
            has_real_traits = True
        elif informative_trait_overrides:
            has_real_traits = True
        elif inferred_style_traits:
            max_w = max(inferred_style_traits.values()) if inferred_style_traits else 0.0
            has_real_traits = (len(inferred_style_traits) >= 2) or (max_w >= 0.65)
        else:
            has_real_traits = False

        # Step 2: Score all banks (trait-based)
        traits_for_scoring = traits
        trait_bank_scores: Dict[str, float] = {}
        for bank_id, bank in TOPIC_BANKS.items():
            score = score_bank_match(traits_for_scoring, bank.traits)
            trait_bank_scores[bank_id] = score

        def _topk_linear_probabilities(scores: Dict[str, float], k: int = 10) -> Dict[str, float]:
            """
            Take top-K scores and normalize linearly:
              p_i = score_i / sum(top_k_scores)

            This matches the desired behavior: if top scores are 25/20/5,
            probabilities become 50%/40%/10%.
            """
            if not scores:
                return {}
            items = sorted(scores.items(), key=lambda x: -x[1])[:k]
            # Drop non-positive scores (they produce 0-probability "phantom" entries like
            # "position 1,3,4" in the UI). Then renormalize.
            clamped = [(bid, float(s)) for bid, s in items if float(s) > 0]
            total = sum(s for _, s in clamped)
            if total <= 1e-9:
                # If everything is <=0, fall back to uniform over the raw top-K list.
                uniform = 1.0 / len(items)
                return {bid: uniform for bid, _ in items}
            return {bid: s / total for bid, s in clamped}

        # If the classifier provided bank_similarities but we otherwise have only defaults,
        # route primarily by similarity (more accurate; avoids default-trait bias).
        if bank_similarities and not has_real_traits:
            # Pure similarity routing: use top-K similarities and normalize linearly.
            probabilities = _topk_linear_probabilities(bank_similarities, k=10)
            bank_scores = dict(bank_similarities)
        else:
            bank_scores = dict(trait_bank_scores)

            # Step 2b: Blend with embedding-based similarities (if provided)
            if bank_similarities:
                # Use embeddings more when they're confident, but keep tags/traits as primary signal.
                sims_sorted = sorted(bank_similarities.values(), reverse=True)
                top = sims_sorted[0] if sims_sorted else 0.0
                second = sims_sorted[1] if len(sims_sorted) > 1 else 0.0
                gap = top - second
                embedding_weight = 0.45 if gap >= 0.02 else 0.3
                trait_weight = 1.0 - embedding_weight
                for bank_id in bank_scores:
                    trait_score = bank_scores[bank_id]
                    emb_score = bank_similarities.get(bank_id, 0.0)
                    bank_scores[bank_id] = (trait_score * trait_weight) + (
                        emb_score * embedding_weight
                    )

            # Step 3: Convert to probabilities (top-K linear normalization)
            probabilities = _topk_linear_probabilities(bank_scores, k=10)

        def sanitize_topic(s: str) -> str:
            # Remove em/en dashes which read AI-ish; prefer commas.
            s = s.replace("—", ", ").replace("–", ", ")
            s = re.sub(r"\s+,", ",", s)
            s = re.sub(r"\s{2,}", " ", s).strip()
            return s

        # Step 4: Sample a bank (or pool from multiple banks)
        if multi_bank_pool and trait_overrides:
            # Multi-bank mode: pool prompts from top banks weighted by probability
            top_banks = self._get_top_banks(
                probabilities, max_banks=3, min_probability=0.1
            )

            if len(top_banks) > 1:
                # Build weighted prompt pool from top banks
                weighted_prompts: List[tuple[str, str, float]] = (
                    []
                )  # (prompt, bank_id, weight)
                for bank_id, prob in top_banks:
                    bank = TOPIC_BANKS[bank_id]
                    available = self._recency.filter_prompts(bank.prompts)
                    if not available:
                        available = list(bank.prompts)
                    for prompt in available:
                        weighted_prompts.append((prompt, bank_id, prob))

                if weighted_prompts:
                    # Sample from pooled prompts weighted by bank probability
                    prompts, bank_ids_list, weights = zip(*weighted_prompts)
                    chosen_idx = self._rng.choices(
                        range(len(prompts)), weights=weights, k=1
                    )[0]
                    topic = sanitize_topic(prompts[chosen_idx])
                    chosen_bank_id = bank_ids_list[chosen_idx]
                    chosen_bank = TOPIC_BANKS[chosen_bank_id]
                    self._recency.record(topic)

                    # Extract mood-like traits for backward compatibility
                    mood_traits = [
                        "melancholic",
                        "uplifting",
                        "romantic",
                        "dark",
                        "playful",
                        "introspective",
                        "empowering",
                    ]
                    chosen_moods = [t for t in mood_traits if traits.get(t, 0) > 0.3]

                    return LyricsTopicResult(
                        topic=topic,
                        bank_id=chosen_bank_id,
                        traits_used=traits,
                        chosen_moods=(
                            chosen_moods if chosen_moods else ["introspective"]
                        ),
                        reasoning=f"Multi-bank pool from {len(top_banks)} banks: {[b[0] for b in top_banks]}",
                    )

        # Standard single-bank mode (or fallback if multi-bank didn't work)
        bank_ids = list(probabilities.keys())
        weights = [probabilities[bid] for bid in bank_ids]
        chosen_bank_id = self._rng.choices(bank_ids, weights=weights, k=1)[0]
        chosen_bank = TOPIC_BANKS[chosen_bank_id]

        # Step 5: Sample a prompt (avoiding recents)
        available_prompts = self._recency.filter_prompts(chosen_bank.prompts)
        if not available_prompts:
            # All prompts recently used - allow any from this bank
            available_prompts = list(chosen_bank.prompts)

        topic = self._rng.choice(available_prompts)
        topic = sanitize_topic(topic)
        self._recency.record(topic)

        # Extract mood-like traits for backward compatibility
        mood_traits = [
            "melancholic",
            "uplifting",
            "romantic",
            "dark",
            "playful",
            "introspective",
            "empowering",
        ]
        chosen_moods = [t for t in mood_traits if traits.get(t, 0) > 0.3]

        return LyricsTopicResult(
            topic=topic,
            bank_id=chosen_bank_id,
            traits_used=traits,
            chosen_moods=chosen_moods if chosen_moods else ["introspective"],
            reasoning=f"Selected bank '{chosen_bank.name}' (score: {bank_scores[chosen_bank_id]:.2f})",
        )

    async def generate_legacy(
        self,
        genres: List[str],
        moods: List[str],
        style_prompt: Optional[str] = None,
    ) -> LyricsTopicResult:
        """
        Legacy API - combines genres and moods into tags.

        This method provides backward compatibility with the old API signature.
        """
        tags = genres + moods
        return await self.generate(tags=tags, style_prompt=style_prompt)


# =============================================================================
# MODULE-LEVEL STATE
# =============================================================================

# Module-level recency memory (persists across requests in same process)
# In production, this should be per-session via Redis/session store
_default_recency = RecencyMemory(max_size=30)


# =============================================================================
# CONVENIENCE FUNCTIONS (maintain backward compatibility)
# =============================================================================


async def generate_lyrics_topic(
    genres: List[str],
    moods: List[str],
    style_prompt: Optional[str] = None,
    trait_overrides: Optional[Dict[str, float]] = None,
    bank_similarities: Optional[Dict[str, float]] = None,
) -> LyricsTopicResult:
    """
    Convenience function matching the existing API signature.

    Combines genres and moods into unified tags for the new system.

    Args:
        genres: List of genre influences.
        moods: List of mood tags.
        style_prompt: Optional style prompt for context.
        trait_overrides: Optional pre-computed traits from async classifier.
        bank_similarities: Optional embedding-based similarity scores for banks.

    Returns:
        LyricsTopicResult with the generated topic.
    """
    tags = genres + moods
    generator = LyricsTopicGenerator(recency_memory=_default_recency)
    # Use multi-bank when we have classifier results
    use_multi_bank = trait_overrides is not None or bank_similarities is not None
    return await generator.generate(
        tags=tags,
        style_prompt=style_prompt,
        trait_overrides=trait_overrides,
        bank_similarities=bank_similarities,
        multi_bank_pool=use_multi_bank,
    )


async def generate_lyrics_topic_from_tags(
    tags: List[str],
    style_prompt: Optional[str] = None,
    trait_overrides: Optional[Dict[str, float]] = None,
) -> LyricsTopicResult:
    """
    Generate a lyrics topic from unified tags.

    This is the preferred API for new code.

    Args:
        tags: List of genre/mood/artist tags (unified).
        style_prompt: Optional style description.
        trait_overrides: Optional pre-computed traits.

    Returns:
        LyricsTopicResult with the generated topic.
    """
    generator = LyricsTopicGenerator(recency_memory=_default_recency)
    return await generator.generate(
        tags=tags,
        style_prompt=style_prompt,
        trait_overrides=trait_overrides,
    )
