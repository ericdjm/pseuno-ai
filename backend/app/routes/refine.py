"""
Unified refinement endpoint for multi-field edits.

POST /generate/refine

Applies a single user instruction to refine multiple song fields at once.
If the suno_prompt changes, a new prompt history entry is auto-saved.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import LyricsThread, SunoPrompt
from app.deps import get_current_user_id_optional, get_db, get_or_create_device_user
from app.schemas.unified_refine import (
    UnifiedRefineRequest,
    UnifiedRefineResponse,
)
from app.services.unified_refine_service import refine_all

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/generate", tags=["Refinement"])

# Cookie settings for device token (1 year expiry)
DEVICE_TOKEN_MAX_AGE = 365 * 24 * 60 * 60  # 1 year in seconds


def _derive_title_from_prompt(suno_prompt: str, auto_tags: list[str]) -> str:
    """
    Derive a title from auto_tags or suno_prompt, matching /generate/advanced behavior.
    """
    if auto_tags:
        # Use top 3 tags joined with bullet
        return " • ".join(tag.title() for tag in auto_tags[:3])

    # Fallback: first line of suno_prompt (up to 50 chars)
    first_line = suno_prompt.split("\n")[0].strip()
    if len(first_line) > 50:
        return first_line[:47] + "..."
    return first_line or "Refined Prompt"


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

If the suno_prompt is changed, a new prompt history entry is automatically saved.

**Examples:**
- "make the ending a dubstep drop" → updates lyrics, prompt, possibly exclude
- "make it more experimental" → increases weirdness, may update prompt
- "change the chorus to be about love" → updates lyrics only
""",
)
async def unified_refine(
    request: UnifiedRefineRequest,
    fastapi_request: Request,
    response: Response,
    db: Session = Depends(get_db),
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
            settings = get_settings()

        # Call unified refine service
        updated_snapshot, changed_fields, assistant_message, debug_info = (
            await refine_all(
                request=request,
                settings=settings,
            )
        )

        logger.info(
            f"Unified refine: changed_fields={changed_fields}, "
            f"change_request='{request.change_request[:50]}...'"
        )

        # === Persist changes to database ===
        saved_prompt_id = None
        saved_thread_id = None
        updates_persisted = True  # Assume success, set to False on failure

        if "suno_prompt" in changed_fields:
            # Style changed: create NEW StylePrompt + fork LyricsThread
            try:
                # Resolve user: Spotify session OR device token (create guest if needed)
                spotify_user_id = get_current_user_id_optional(fastapi_request)

                if spotify_user_id:
                    user_id = spotify_user_id
                else:
                    # Fall back to device token (create guest user if needed)
                    user, created = get_or_create_device_user(fastapi_request, db)
                    user_id = user.id

                    if created:
                        # Set device_token cookie for new guest users
                        response.set_cookie(
                            key="device_token",
                            value=user.device_token,
                            httponly=True,
                            secure=settings.session_cookie_secure,
                            samesite=settings.session_cookie_samesite,
                            max_age=DEVICE_TOKEN_MAX_AGE,
                        )

                # Create the prompt history record
                # Use passed-in auto_tags (from original generation) and add "refined" tag
                auto_tags = list(request.auto_tags or [])
                # Case-insensitive check for existing "refined" tag
                has_refined = any(t.lower() == "refined" for t in auto_tags)
                if not has_refined:
                    auto_tags.insert(0, "refined")
                # Derive style title from original tags (excluding "refined")
                title_tags = [t for t in auto_tags if t.lower() != "refined"]
                style_title = _derive_title_from_prompt(
                    updated_snapshot["suno_prompt"], title_tags
                )

                # Create new StylePrompt with parent linking
                prompt = SunoPrompt(
                    owner_user_id=user_id,
                    parent_prompt_id=request.base_prompt_id,  # Link to parent
                    source_action="refine",
                    suno_prompt=updated_snapshot["suno_prompt"],
                    lyrics=updated_snapshot["lyrics"],
                    exclude=updated_snapshot["exclude"],
                    weirdness=updated_snapshot["weirdness"],
                    style_influence=request.style_influence,
                    title=style_title,
                    is_favorite=False,
                    auto_tags=auto_tags,
                    generation_id=None,  # Refine doesn't have a generation_id
                )
                db.add(prompt)
                db.flush()  # Get the ID before creating thread
                saved_prompt_id = prompt.id

                # Use song title for the thread (not style title)
                # Prefer updated_snapshot["title"] (song title), fall back to previous thread title
                song_title = updated_snapshot["title"]
                if not song_title and request.base_thread_id:
                    # Try to get the previous thread's title
                    prev_thread = db.query(LyricsThread).filter(
                        LyricsThread.id == request.base_thread_id
                    ).first()
                    if prev_thread:
                        song_title = prev_thread.title or style_title
                if not song_title:
                    song_title = style_title  # Final fallback

                # Fork the LyricsThread if we have a base_thread_id
                if request.base_thread_id:
                    thread = LyricsThread(
                        style_prompt_id=prompt.id,
                        parent_thread_id=request.base_thread_id,
                        title=song_title,  # Use song title, not style title
                        lyrics_text=updated_snapshot["lyrics"],
                        source_action="refine_fork",
                    )
                    db.add(thread)
                    db.flush()
                    saved_thread_id = thread.id
                else:
                    # No base thread - create a new thread with the lyrics
                    thread = LyricsThread(
                        style_prompt_id=prompt.id,
                        parent_thread_id=None,
                        title=song_title,
                        lyrics_text=updated_snapshot["lyrics"],
                        source_action="refine_initial",
                    )
                    db.add(thread)
                    db.flush()
                    saved_thread_id = thread.id

                db.commit()
                logger.info(
                    "Auto-saved refined prompt id=%d thread=%d for user=%s",
                    saved_prompt_id,
                    saved_thread_id,
                    user_id,
                )

            except Exception as e:
                # Don't fail the request if auto-save fails - just log it
                logger.warning("Failed to auto-save refined prompt: %s", e)
                db.rollback()
                saved_prompt_id = None
                saved_thread_id = None
                updates_persisted = False

        else:
            # Style did NOT change: update existing records in-place
            try:
                needs_commit = False

                # Update LyricsThread if lyrics or title changed
                if request.base_thread_id and (
                    "lyrics" in changed_fields or "title" in changed_fields
                ):
                    thread = db.query(LyricsThread).filter(
                        LyricsThread.id == request.base_thread_id
                    ).first()
                    if thread:
                        if "lyrics" in changed_fields:
                            thread.lyrics_text = updated_snapshot["lyrics"]
                        if "title" in changed_fields:
                            thread.title = updated_snapshot["title"]
                        needs_commit = True
                        logger.info(
                            "Updated LyricsThread id=%d with changed_fields=%s",
                            request.base_thread_id,
                            [f for f in ["lyrics", "title"] if f in changed_fields],
                        )

                # Update SunoPrompt if exclude or weirdness changed
                if request.base_prompt_id and (
                    "exclude" in changed_fields or "weirdness" in changed_fields
                ):
                    prompt = db.query(SunoPrompt).filter(
                        SunoPrompt.id == request.base_prompt_id
                    ).first()
                    if prompt:
                        if "exclude" in changed_fields:
                            prompt.exclude = updated_snapshot["exclude"]
                        if "weirdness" in changed_fields:
                            prompt.weirdness = updated_snapshot["weirdness"]
                        needs_commit = True
                        logger.info(
                            "Updated SunoPrompt id=%d with changed_fields=%s",
                            request.base_prompt_id,
                            [f for f in ["exclude", "weirdness"] if f in changed_fields],
                        )

                if needs_commit:
                    db.commit()

            except Exception as e:
                logger.warning("Failed to update existing records: %s", e)
                db.rollback()
                updates_persisted = False

        return UnifiedRefineResponse(
            suno_prompt=updated_snapshot["suno_prompt"],
            lyrics=updated_snapshot["lyrics"],
            exclude=updated_snapshot["exclude"],
            title=updated_snapshot["title"],
            weirdness=updated_snapshot["weirdness"],
            changed_fields=changed_fields,
            assistant_message=assistant_message,
            debug_info=debug_info,
            updates_persisted=updates_persisted,
            saved_prompt_id=saved_prompt_id,
            saved_thread_id=saved_thread_id,
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
