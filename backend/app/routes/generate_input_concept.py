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
    LyricsRefinementRequest,
    LyricsRefinementResponse,
    LyricsTopicRequest,
    LyricsTopicResponse,
    RefinementRequest,
    RefinementResponse,
)
from app.services.input_concept_generator import (
    InputConceptGenerator,
    create_generator_with_providers,
    refine_concept_with_llm,
    refine_lyrics_with_llm,
)
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
    except Exception as e:
        logger.exception("Error generating input concept")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate input concept",
        )


@router.post(
    "/refine-concept",
    response_model=RefinementResponse,
    summary="Refine an existing prompt based on user feedback",
    description="""
Refine an existing Suno concept based on user's change request.

Uses an LLM to make targeted edits to the prompt while preserving
the original intent and structure.

**Input:**
- `current_prompt`: The existing prompt text (1-500 chars)
- `change_request`: What the user wants to change (1-500 chars)

**Output:**
- `refined_prompt`: The updated prompt incorporating requested changes
- `changes_made`: Optional summary of changes (for debugging)

**Example:**
```
{
  "current_prompt": "A dreamy indie rock track...",
  "change_request": "Make it more upbeat and add electronic elements"
}
```
""",
)
async def refine_concept(
    request: RefinementRequest,
    fastapi_request: Request,
) -> RefinementResponse:
    """Refine an existing prompt based on user feedback."""

    try:
        # Get settings from app state
        settings = fastapi_request.app.state.settings if hasattr(fastapi_request.app.state, 'settings') else None
        if settings is None:
            from app.config import get_settings
            settings = get_settings()

        # Call LLM refiner
        refined_prompt = await refine_concept_with_llm(
            current_prompt=request.current_prompt,
            change_request=request.change_request,
            settings=settings,
        )

        logger.info(
            f"Refined concept: original_len={len(request.current_prompt)}, "
            f"refined_len={len(refined_prompt)}"
        )

        return RefinementResponse(
            refined_prompt=refined_prompt,
            changes_made=None,  # Could extract diff summary later if needed
        )

    except RuntimeError as e:
        # API key missing
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception("Error refining concept")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to refine concept",
        )


@router.post(
    "/refine-lyrics",
    response_model=LyricsRefinementResponse,
    summary="Refine lyrics based on user feedback",
    description="""
Refine existing lyrics based on user change requests while preserving structure markers.

The refinement:
- Preserves ALL structure markers like [Verse], [Chorus], [Bridge], etc.
- Makes ONLY the changes specifically requested by the user
- Keeps the lyrical style and tone consistent unless asked to change

Examples of change requests:
- "change the chorus to be more upbeat"
- "add another verse"
- "make the bridge darker"
- "remove the third verse"
""",
)
async def refine_lyrics(
    request: LyricsRefinementRequest,
    fastapi_request: Request,
) -> LyricsRefinementResponse:
    """Refine lyrics based on user feedback while preserving structure."""

    try:
        # Get settings from app state
        settings = fastapi_request.app.state.settings if hasattr(fastapi_request.app.state, 'settings') else None
        if settings is None:
            from app.config import get_settings
            settings = get_settings()

        # Call LLM refiner
        refined_lyrics = await refine_lyrics_with_llm(
            current_lyrics=request.current_lyrics,
            change_request=request.change_request,
            settings=settings,
        )

        logger.info(
            f"Refined lyrics: original_len={len(request.current_lyrics)}, "
            f"refined_len={len(refined_lyrics)}"
        )

        return LyricsRefinementResponse(
            refined_lyrics=refined_lyrics,
            changes_made=None,  # Could extract diff summary later if needed
        )

    except RuntimeError as e:
        # API key missing
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception("Error refining lyrics")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to refine lyrics",
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

        logger.info(
            f"Generated lyrics topic: chosen_moods={result.chosen_moods}"
        )

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
    except Exception as e:
        logger.exception("Error generating lyrics topic")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate lyrics topic",
        )
