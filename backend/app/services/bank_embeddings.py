"""
Pre-computed embeddings for lyrics topic bank descriptions.

This module provides semantic similarity-based bank scoring as an
alternative/supplement to trait-based matching. It's especially useful
for understanding artist names and style descriptions that don't map
well to predefined traits.

Flow:
1. At startup (or lazily), embed all bank descriptions
2. When classifying style_prompt, embed it and find similar banks
3. Return similarity scores to blend with trait-based scores
"""

import asyncio
import json
import logging
import re
import time
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.config import get_settings
from app.services.lyrics_topic_banks import TOPIC_BANKS, TopicBank
from app.services.lyrics_topic_traits import infer_traits_from_tags

logger = logging.getLogger(__name__)

# Cache file for pre-computed embeddings
EMBEDDINGS_CACHE_PATH = Path(__file__).parent / "_bank_embeddings_cache.json"

# Embedding dimension (depends on model)
# gemini-embedding-001 produces 768-dimensional embeddings
EMBEDDING_DIM = 768


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot_product = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)


_GENERIC_STYLE_PHRASES = {
    "avant garde",
    "avant-garde",
    "experimental",
    "alternative",
    "indie",
    "art rock",
    "prog",
    "progressive",
    "psychedelic",
    "jazzy",
    "jazz",
    "ambient",
    "electronic",
    "rock",
    "metal",
    "pop",
    "hip hop",
    "hip-hop",
    "rap",
    "folk",
    "punk",
    "post punk",
    "post-punk",
}


def _split_style_prompt_influences(style_prompt: str) -> List[str]:
    """
    Split a free-text style prompt into "influence" phrases.

    We bias toward the first mentioned influence and toward non-generic phrases
    (often artist names) so similarity routing becomes more opinionated.
    """
    s = style_prompt.strip()
    if not s:
        return []

    # Normalize common lead-ins
    s = re.sub(
        r"^\s*(a\s+mix\s+of|mix\s+of|in\s+the\s+style\s+of|like|inspired\s+by)\s+",
        "",
        s,
        flags=re.I,
    )

    # Replace separators with a common delimiter
    s = re.sub(r"\s*(/|&|\+|,|;)\s*", " | ", s)
    s = re.sub(r"\s+\b(with|and|plus|meets|x)\b\s+", " | ", s, flags=re.I)

    parts = [p.strip(" .") for p in s.split("|")]
    # Keep reasonably informative chunks
    parts = [p for p in parts if len(p) >= 3]
    # Cap to avoid huge embedding batches on long prompts
    return parts[:6]


def _influence_weight(phrase: str, idx: int) -> float:
    """
    Heuristic specificity weight:
    - artist-like phrases (don't map to known tag traits) get boosted
    - broad genre/style descriptors get downweighted
    - earlier mentions get a slight boost
    """
    p = phrase.strip()
    if not p:
        return 0.0

    p_norm = re.sub(r"\s+", " ", p.lower())
    p_norm = p_norm.strip(" .")

    # Generic descriptors should not dominate routing.
    if p_norm in _GENERIC_STYLE_PHRASES:
        base = 0.95
    else:
        # If it maps to known trait tags, it's likely a genre/mood (broad).
        # If it doesn't, it's more likely a specific entity (artist/scene/era).
        base = 1.25 if not infer_traits_from_tags([p]) else 1.0

    # Multi-word and capitalized phrases tend to be proper nouns (artist-like).
    words = [w for w in re.split(r"\s+", p) if w]
    if any(ch.isupper() for ch in p) and len(words) >= 2:
        base += 0.2

    # Bias toward earlier mentions (user typically lists primary first).
    if idx == 0:
        base *= 1.05
    elif idx == 1:
        base *= 1.02

    return float(min(max(base, 0.7), 1.7))


def _weighted_mean(values: List[float], weights: List[float]) -> float:
    denom = sum(weights)
    if denom <= 0:
        return 0.0
    return sum(v * w for v, w in zip(values, weights)) / denom


def _get_embedding_client():
    """Get the Google GenAI client for embeddings."""
    from google import genai

    settings = get_settings()
    api_key = settings.gemini_api_key
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY required for embeddings")

    return genai.Client(api_key=api_key)


def _embed_texts_sync(
    texts: List[str], model: str = "gemini-embedding-001"
) -> List[List[float]]:
    """Embed multiple texts synchronously."""
    client = _get_embedding_client()

    embeddings = []
    # Batch in groups of 100 (API limit)
    for i in range(0, len(texts), 100):
        batch = texts[i : i + 100]
        result = client.models.embed_content(
            model=model,
            contents=batch,
        )
        for emb in result.embeddings:
            embeddings.append(emb.values)

    return embeddings


async def _embed_texts_async(
    texts: List[str], model: str = "gemini-embedding-001"
) -> List[List[float]]:
    """Embed texts asynchronously."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _embed_texts_sync, texts, model)


def _build_bank_text(bank: TopicBank) -> str:
    """Build a descriptive text for a bank to embed."""
    # Combine name, description, and a sample of prompts for richer context
    sample_prompts = list(bank.prompts)[:5]
    prompt_sample = " | ".join(sample_prompts)

    return f"{bank.name}: {bank.description}. Examples: {prompt_sample}"


def _load_cached_embeddings() -> Optional[Dict[str, List[float]]]:
    """Load pre-computed embeddings from cache file."""
    if not EMBEDDINGS_CACHE_PATH.exists():
        return None

    try:
        with open(EMBEDDINGS_CACHE_PATH) as f:
            data = json.load(f)
            # Validate structure
            if isinstance(data, dict) and all(
                isinstance(v, list) and len(v) == EMBEDDING_DIM for v in data.values()
            ):
                return data
    except Exception as e:
        logger.warning(f"Failed to load embeddings cache: {e}")

    return None


def _save_cached_embeddings(embeddings: Dict[str, List[float]]) -> None:
    """Save embeddings to cache file."""
    try:
        with open(EMBEDDINGS_CACHE_PATH, "w") as f:
            json.dump(embeddings, f)
        logger.info(f"Saved {len(embeddings)} bank embeddings to cache")
    except Exception as e:
        logger.warning(f"Failed to save embeddings cache: {e}")


@lru_cache(maxsize=1)
def get_bank_embeddings() -> Dict[str, List[float]]:
    """
    Get embeddings for all bank descriptions.

    Tries to load from cache first, generates if needed.
    Uses lru_cache to avoid regenerating during runtime.
    """
    # Try cache first
    cached = _load_cached_embeddings()
    if cached:
        # Verify cache matches current bank ids exactly (no missing and no extras).
        current_ids = set(TOPIC_BANKS.keys())
        cached_ids = set(cached.keys())
        missing = current_ids - cached_ids
        extra = cached_ids - current_ids
        if not missing and not extra:
            logger.info(f"Loaded {len(cached)} bank embeddings from cache")
            return cached
        logger.info(
            f"Embeddings cache mismatch (missing={len(missing)}, extra={len(extra)}), regenerating..."
        )

    # Generate embeddings for all banks
    logger.info("Generating bank embeddings...")
    start = time.time()

    bank_ids = list(TOPIC_BANKS.keys())
    bank_texts = [_build_bank_text(TOPIC_BANKS[bid]) for bid in bank_ids]

    try:
        embeddings_list = _embed_texts_sync(bank_texts)
        embeddings = {bank_ids[i]: embeddings_list[i] for i in range(len(bank_ids))}

        # Save to cache
        _save_cached_embeddings(embeddings)

        logger.info(
            f"Generated {len(embeddings)} embeddings in {time.time()-start:.1f}s"
        )
        return embeddings

    except Exception as e:
        logger.error(f"Failed to generate bank embeddings: {e}")
        # Return empty dict - system will fall back to trait-based only
        return {}


async def compute_bank_similarities(
    style_prompt: str,
    top_k: int = 10,
) -> Dict[str, float]:
    """
    Compute semantic similarity between a style prompt and all banks.

    Args:
        style_prompt: User's style description
        top_k: Return only top K most similar banks

    Returns:
        Dict of bank_id -> similarity score (0.0 to 1.0)
    """
    from app.services.posthog_capture import capture_background

    if not style_prompt or len(style_prompt.strip()) < 5:
        return {}

    start = time.time()

    # Get pre-computed bank embeddings
    bank_embeddings = get_bank_embeddings()
    if not bank_embeddings:
        return {}

    try:
        influences = _split_style_prompt_influences(style_prompt)
        if not influences:
            influences = [style_prompt]
        weights = [_influence_weight(p, i) for i, p in enumerate(influences)]

        # Embed each influence phrase (batched)
        influence_embeddings = await _embed_texts_async(influences)

        # Compute similarities
        similarities: List[Tuple[str, float]] = []
        for bank_id in TOPIC_BANKS.keys():
            bank_emb = bank_embeddings.get(bank_id)
            if not bank_emb:
                continue
            sims = [_cosine_similarity(e, bank_emb) for e in influence_embeddings]
            sim = _weighted_mean(sims, weights)
            similarities.append((bank_id, sim))

        # Sort and take top K (prefer positive similarities so we don't return "dead" candidates)
        similarities.sort(key=lambda x: -x[1])
        positive = [(bid, s) for bid, s in similarities if s > 0]
        top_similar = positive[:top_k] if len(positive) >= 3 else similarities[:top_k]

        latency_ms = int((time.time() - start) * 1000)

        capture_background(
            "bank_embeddings.similarity_computed",
            distinct_id="backend",
            properties={
                "latency_ms": latency_ms,
                "style_prompt_length": len(style_prompt),
                "num_influences": len(influences),
                "influences": influences[:3],
                "influence_weights": [round(w, 2) for w in weights[:3]],
                "top_bank": top_similar[0][0] if top_similar else None,
                "top_score": round(top_similar[0][1], 3) if top_similar else None,
            },
        )

        if top_similar:
            logger.debug(
                f"Bank similarity computed in {latency_ms}ms, "
                f"top: {top_similar[0][0]}={top_similar[0][1]:.3f}"
            )
        else:
            logger.debug(
                f"Bank similarity computed in {latency_ms}ms, no positive matches"
            )

        return {bank_id: float(score) for bank_id, score in top_similar}

    except Exception as e:
        logger.warning(f"Bank similarity computation failed: {e}")
        return {}


def blend_trait_and_embedding_scores(
    trait_scores: Dict[str, float],
    embedding_scores: Dict[str, float],
    embedding_weight: float = 0.3,
) -> Dict[str, float]:
    """
    Blend trait-based and embedding-based bank scores.

    Args:
        trait_scores: Scores from trait matching (all banks)
        embedding_scores: Scores from embedding similarity (top K only)
        embedding_weight: How much to weight embedding scores (0.0-1.0)

    Returns:
        Blended scores for all banks
    """
    if not embedding_scores:
        return trait_scores

    blended = {}
    trait_weight = 1.0 - embedding_weight

    for bank_id, trait_score in trait_scores.items():
        emb_score = embedding_scores.get(bank_id, 0.0)
        blended[bank_id] = (trait_score * trait_weight) + (emb_score * embedding_weight)

    return blended


# Pre-warm cache on module import (optional, can be lazy)
# Uncomment to pre-compute at startup:
# try:
#     get_bank_embeddings()
# except Exception:
#     pass
