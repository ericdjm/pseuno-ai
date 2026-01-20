"""
Input concept generation endpoint.

POST /generate/input-concept

Generates a 3-sentence Suno concept from genre influences.
This is the "input side" of generation - the resulting concept can be
passed to /generate/advanced as the prompt field.

v1: No authentication required. Genres come from request body only.
Later: Logged-in users can have genres populated from Spotify/profiles.
"""

import logging

from fastapi import APIRouter, HTTPException, status

from app.config import get_settings
from app.schemas.input_concept import (
    ClassifyStyleRequest,
    ClassifyStyleResponse,
    InputConceptRequest,
    InputConceptResponse,
    LyricsTopicDebugInfo,
    LyricsTopicRequest,
    LyricsTopicResponse,
)
from app.services.input_concept_generator import (
    create_generator_with_providers,
)
from app.services.lyrics_topic_generator import generate_lyrics_topic
from app.services.lyrics_topic_traits import (
    extract_traits_from_style_prompt,
    get_default_traits,
    infer_traits_from_tags,
    merge_traits,
    score_bank_match,
    scores_to_probabilities,
    STYLE_PROMPT_KEYWORDS,
)
from app.services.lyrics_topic_banks import TOPIC_BANKS
from app.services.bank_embeddings import compute_bank_similarities

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/generate", tags=["generation"])


@router.post(
    "/input-concept",
    response_model=InputConceptResponse,
    summary="Generate a short Suno concept from genre influences",
    description="""
Generate a 3-sentence concept describing a musical style/vibe.

The concept is based on:
- Genre influences (from request body, or fallback seeds if empty)
- 1-3 genres are randomly selected from the list
- Optional mood hint

The returned concept can be passed directly to `/generate/advanced`
as the `user_prompt` field for full Suno prompt generation.

**v1 behavior:**
- No login required
- Genres come from request body only
- If genres array is empty, uses internal seed genres
- Artists array is passed through for future use (not used in v1)

**Future behavior:**
- Logged-in users can have genres populated from Spotify
- Additional providers can merge multiple genre sources
""",
)
async def generate_input_concept(
    request: InputConceptRequest,
) -> InputConceptResponse:
    """Generate a 3-sentence Suno concept from genre influences."""

    try:
        # Create generator (v1: only uses ManualInputGenreProvider)
        generator, providers = await create_generator_with_providers(
            request_genres=request.genres,
            request_artists=request.artists,
            user_id=None,  # v1: no auth
            candidate_genres=request.candidate_genres,
        )

        # Get merged genre list from all providers
        from app.services.artist_influence import InfluenceContext

        ctx = InfluenceContext(user_id=None)
        merged_genres = await providers.get_influence_genres(ctx)

        # Generate concept
        result = await generator.generate(
            genres=merged_genres,
            artists=request.artists,
            mood=request.mood,
        )

        logger.info(
            f"Generated input concept: chosen_genres={result.chosen_genres}, "
            f"genres_count={len(result.genres)}"
        )

        return InputConceptResponse(
            concept=result.concept,
            chosen_genres=result.chosen_genres,
            genres=result.genres,
            artists=result.artists,
            mood=result.mood,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception:
        logger.exception("Error generating input concept")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate input concept",
        )


@router.post(
    "/lyrics-topic",
    response_model=LyricsTopicResponse,
    summary="Generate a short lyrics topic from mood/genre influences",
    description="""
Generate a 1-2 sentence lyrics topic or theme based on influences.

The topic is based on:
- Mood tags (if provided)
- Genre influences (used to infer moods if no moods provided)
- Optional style prompt (for context alignment)

The returned topic can be used as the `lyrics_about` field
in `/generate/advanced` or `/generate/lyrics-only`.

**v2 behavior:**
- No login required
- Trait-based bank selection with 40+ curated topic banks
- If no moods or genres provided, uses default balanced traits
""",
)
async def generate_lyrics_topic_endpoint(
    request: LyricsTopicRequest,
) -> LyricsTopicResponse:
    """Generate a short lyrics topic from mood/genre influences."""
    import re
    from app.services.posthog_capture import capture_background

    try:
        # High-signal routing log (dev): confirms whether this request actually used async signals.
        if get_settings().debug:
            logger.info(
                "LyricsTopic request routing: tags=%s style_len=%s trait_overrides=%s bank_sims=%s",
                len(request.genres or []) + len(request.moods or []),
                len((request.style_prompt or "").strip()),
                len(request.trait_overrides or {}),
                len(request.bank_similarities or {}),
            )

        # Build debug info if in dev mode
        debug_info = None
        if get_settings().debug:
            tags = request.genres + request.moods
            tag_traits = infer_traits_from_tags(tags) if tags else {}
            debug_bank_sims = request.bank_similarities or None

            # Check if trait_overrides are provided (from LLM classifier)
            def _is_informative_override(traits_in: dict | None) -> bool:
                if not traits_in:
                    return False
                vals = [float(v) for v in traits_in.values() if isinstance(v, (int, float))]
                if not vals:
                    return False
                max_w = max(vals)
                num_mid = sum(1 for v in vals if v >= 0.55)
                return num_mid >= 2 or max_w >= 0.75

            has_classifier_overrides = bool(
                request.trait_overrides and _is_informative_override(request.trait_overrides)
            )

            if has_classifier_overrides:
                # Use LLM classifier traits for debug display
                style_traits = request.trait_overrides or {}
                merged = request.trait_overrides or {}
                matched_keywords = ["[LLM classifier]"]
            else:
                # Fall back to keyword extraction
                style_traits = (
                    extract_traits_from_style_prompt(request.style_prompt)
                    if request.style_prompt
                    else {}
                )
                merged = (
                    merge_traits(tag_traits, style_traits, strategy="max")
                    if (tag_traits or style_traits)
                    else get_default_traits()
                )
                # Find matched keywords from style_prompt
                matched_keywords = []
                if request.style_prompt:
                    prompt_lower = request.style_prompt.lower()
                    for keyword in STYLE_PROMPT_KEYWORDS:
                        if re.search(rf"\b{re.escape(keyword)}\b", prompt_lower):
                            matched_keywords.append(keyword)

                # IMPORTANT: We do NOT compute embeddings inside /generate/lyrics-topic.
                # Embedding-based routing is asynchronous via /generate/classify-style.

            # Score banks and get top candidates using the actual traits that will be used
            effective_traits = (
                request.trait_overrides if has_classifier_overrides else merged
            )
            traits_for_scoring = effective_traits
            bank_scores = {
                bid: score_bank_match(traits_for_scoring, bank.traits)
                for bid, bank in TOPIC_BANKS.items()
            }

            def _topk_linear_probabilities(scores: dict, k: int = 10) -> dict:
                if not scores:
                    return {}
                items = sorted(scores.items(), key=lambda x: -x[1])[:k]
                clamped = [(bid, float(s)) for bid, s in items if float(s) > 0]
                total = sum(s for _, s in clamped)
                if total <= 1e-9:
                    uniform = 1.0 / len(items)
                    return {bid: uniform for bid, _ in items}
                return {bid: s / total for bid, s in clamped}

            # Blend with bank_similarities if provided
            if debug_bank_sims:
                if tag_traits or has_classifier_overrides:
                    has_real_traits = True
                elif style_traits:
                    max_w = max(style_traits.values()) if style_traits else 0.0
                    has_real_traits = (len(style_traits) >= 2) or (max_w >= 0.65)
                else:
                    has_real_traits = False
                if not has_real_traits:
                    # Match generator behavior: route by similarity using top-K linear normalization.
                    bank_scores = dict(debug_bank_sims)
                else:
                    embedding_weight = 0.3
                    trait_weight = 1.0 - embedding_weight
                    for bank_id in bank_scores:
                        trait_score = bank_scores[bank_id]
                        emb_score = debug_bank_sims.get(bank_id, 0.0)
                        bank_scores[bank_id] = (trait_score * trait_weight) + (
                            emb_score * embedding_weight
                        )

            if tag_traits or has_classifier_overrides:
                has_real_traits_for_temp = True
            elif style_traits:
                max_w = max(style_traits.values()) if style_traits else 0.0
                has_real_traits_for_temp = (len(style_traits) >= 2) or (max_w >= 0.65)
            else:
                has_real_traits_for_temp = False
            if debug_bank_sims and not has_real_traits_for_temp:
                probabilities = _topk_linear_probabilities(debug_bank_sims, k=10)
            else:
                probabilities = _topk_linear_probabilities(bank_scores, k=10)
            top_banks = sorted(
                [(bid, prob) for bid, prob in probabilities.items()],
                key=lambda x: -x[1],
            )[:8]

            debug_info = LyricsTopicDebugInfo(
                tag_traits={
                    k: round(v, 3)
                    for k, v in sorted(tag_traits.items(), key=lambda x: -x[1])[:10]
                },
                style_prompt_traits={
                    k: round(v, 3)
                    for k, v in sorted(style_traits.items(), key=lambda x: -x[1])[:10]
                },
                merged_traits={
                    k: round(v, 3)
                    for k, v in sorted(
                        (effective_traits or {}).items(), key=lambda x: -x[1]
                    )[:12]
                },
                top_banks=[
                    {
                        "bank_id": bid,
                        "probability": round(prob, 3),
                        "name": TOPIC_BANKS.get(bid).name if TOPIC_BANKS.get(bid) else bid,
                    }
                    for bid, prob in top_banks
                ],
                style_prompt_keywords_matched=matched_keywords,
            )

        result = await generate_lyrics_topic(
            genres=request.genres,
            moods=request.moods,
            style_prompt=request.style_prompt,
            trait_overrides=request.trait_overrides,
            bank_similarities=request.bank_similarities,
        )

        logger.info(
            f"Generated lyrics topic: bank_id={result.bank_id}, "
            f"chosen_moods={result.chosen_moods}"
        )

        # Track the generated topic for analytics
        capture_background(
            "lyrics_topic.generated",
            properties={
                "bank_id": result.bank_id,
                "topic_preview": result.topic[:50] if result.topic else None,
                "input_genres": request.genres[:5] if request.genres else [],
                "input_moods": request.moods[:5] if request.moods else [],
                "has_style_prompt": bool(request.style_prompt),
            },
        )

        return LyricsTopicResponse(
            topic=result.topic,
            bank_id=result.bank_id,
            chosen_moods=result.chosen_moods,
            reasoning=result.reasoning,
            debug=debug_info,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception:
        logger.exception("Error generating lyrics topic")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate lyrics topic",
        )


@router.post(
    "/classify-style",
    response_model=ClassifyStyleResponse,
    summary="Classify a style prompt into trait weights using LLM",
    description="""
Asynchronously classify a style prompt (artist names, genre descriptions, vibes)
into trait weights using a fast LLM.

This is designed to be called when the user types in the style prompt field.
The response can be cached and passed as `trait_overrides` to `/lyrics-topic`
for more accurate topic selection.

**Use case:**
1. User types "Red Hot Chili Peppers funk rock vibes"
2. Frontend calls this endpoint (async, non-blocking)
3. Response: `{"traits": {"coastal": 0.8, "playful": 0.6, "rock_friendly": 0.7}}`
4. Frontend caches this
5. When user clicks "randomize lyrics topic", pass traits as `trait_overrides`
""",
)
async def classify_style_endpoint(
    request: ClassifyStyleRequest,
) -> ClassifyStyleResponse:
    """Classify a style prompt into trait weights."""
    from app.services.style_classifier import classify_style_prompt

    result = await classify_style_prompt(request.style_prompt)

    if get_settings().debug:
        sims = result.get("bank_similarities") or {}
        top = sorted(sims.items(), key=lambda x: -x[1])[:3]
        logger.info(
            "ClassifyStyle completed: prompt_len=%s traits=%s bank_sims=%s top=%s",
            len((request.style_prompt or "").strip()),
            len(result.get("traits") or {}),
            len(sims),
            [(k, round(v, 3)) for k, v in top],
        )

    return ClassifyStyleResponse(
        traits=result.get("traits", {}),
        bank_similarities=result.get("bank_similarities", {}),
        latency_ms=result.get("latency_ms", 0),
        success=result.get("success", False),
        error=result.get("error"),
        )
