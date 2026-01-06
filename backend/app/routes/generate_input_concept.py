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

from fastapi import APIRouter, HTTPException, Request, status

from app.schemas.input_concept import (
    InputConceptRequest,
    InputConceptResponse,
    LyricsTopicRequest,
    LyricsTopicResponse,
)
from app.schemas.unified_refine import (
    UnifiedRefineRequest,
    UnifiedRefineResponse,
)
from app.services.input_concept_generator import (
    create_generator_with_providers,
)
from app.services.unified_refine_service import refine_all
from app.services.lyrics_topic_generator import generate_lyrics_topic

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

**v1 behavior:**
- No login required
- Template-based generation with mood-theme mapping
- If no moods or genres provided, uses random seed moods
""",
)
async def generate_lyrics_topic_endpoint(
    request: LyricsTopicRequest,
) -> LyricsTopicResponse:
    """Generate a short lyrics topic from mood/genre influences."""

    try:
        result = await generate_lyrics_topic(
            genres=request.genres,
            moods=request.moods,
            style_prompt=request.style_prompt,
        )

        logger.info(f"Generated lyrics topic: chosen_moods={result.chosen_moods}")

        return LyricsTopicResponse(
            topic=result.topic,
            chosen_moods=result.chosen_moods,
            reasoning=result.reasoning,
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
    "/refine",
    response_model=UnifiedRefineResponse,
    summary="Unified refinement for multi-field edits",
    description="""
Apply a single user instruction to refine multiple song fields at once.

This endpoint can update:
- **suno_prompt**: The Suno style prompt
- **lyrics**: The song lyrics
- **exclude**: Terms to exclude from generation
- **title**: The song title
- **weirdness**: The experimental-ness level (0-100)

The backend uses an LLM planner to decide which fields to modify based on
the user's natural language request, then applies targeted edits.

**Examples:**
- "make the ending a dubstep drop" → updates lyrics, prompt, possibly exclude
- "make it more experimental" → increases weirdness, may update prompt
- "change the chorus to be about love" → updates lyrics only
""",
)
async def unified_refine(
    request: UnifiedRefineRequest,
    fastapi_request: Request,
) -> UnifiedRefineResponse:
    """Apply multi-field edits based on a single user instruction."""

    try:
        # Get settings from app state
        settings = (
            fastapi_request.app.state.settings
            if hasattr(fastapi_request.app.state, "settings")
            else None
        )
        if settings is None:
            from app.config import get_settings

            settings = get_settings()

        # Call unified refine service
        updated_snapshot, changed_fields, assistant_message, debug_info = await refine_all(
            request=request,
            settings=settings,
        )

        logger.info(
            f"Unified refine: changed_fields={changed_fields}, "
            f"change_request='{request.change_request[:50]}...'"
        )

        return UnifiedRefineResponse(
            suno_prompt=updated_snapshot["suno_prompt"],
            lyrics=updated_snapshot["lyrics"],
            exclude=updated_snapshot["exclude"],
            title=updated_snapshot["title"],
            weirdness=updated_snapshot["weirdness"],
            changed_fields=changed_fields,
            assistant_message=assistant_message,
            debug_info=debug_info,
        )

    except RuntimeError as e:
        error_msg = str(e)
        if "timed out" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=error_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception:
        logger.exception("Error in unified refine")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to refine",
        )
