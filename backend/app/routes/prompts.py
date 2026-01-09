"""
CRUD routes for saved Suno prompts (favorites).

Supports two auth modes:
1. Spotify session (user_id from session store) - for linked users
2. Device token (guest user from cookie) - for anonymous users

The create endpoint will auto-create a guest user if needed and set the device_token cookie.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import LyricsThread, SunoPrompt, User
from app.deps import (
    get_current_user_id_optional,
    get_db,
    get_device_user,
    get_or_create_device_user,
)
from app.schemas.prompts import (
    SunoPromptCreate,
    SunoPromptListResponse,
    SunoPromptResponse,
    SunoPromptUpdate,
)
from app.schemas.lyrics_threads import LyricsThreadSummary

router = APIRouter()

# Cookie settings for device token (1 year expiry)
DEVICE_TOKEN_MAX_AGE = 365 * 24 * 60 * 60  # 1 year in seconds


def _get_user_id_or_raise(
    spotify_user_id: str | None,
    device_user: User | None,
) -> str:
    """
    Get user_id from either Spotify session or device token.
    Raises 401 if neither is available.
    """
    if spotify_user_id:
        return spotify_user_id
    if device_user:
        return device_user.id
    raise HTTPException(
        status_code=401,
        detail="Not authenticated. Please log in or enable cookies.",
    )


def _prompt_to_response(prompt: SunoPrompt, db: Session) -> SunoPromptResponse:
    """Convert a SunoPrompt to SunoPromptResponse, including threads_count."""
    threads_count = (
        db.scalar(
            select(func.count())
            .select_from(LyricsThread)
            .where(LyricsThread.style_prompt_id == prompt.id)
        )
        or 0
    )

    return SunoPromptResponse(
        id=prompt.id,
        suno_prompt=prompt.suno_prompt,
        lyrics=prompt.lyrics,
        exclude=prompt.exclude,
        weirdness=prompt.weirdness,
        style_influence=prompt.style_influence,
        title=prompt.title,
        notes=prompt.notes,
        is_favorite=prompt.is_favorite,
        auto_tags=prompt.auto_tags,
        generation_id=prompt.generation_id,
        visibility=prompt.visibility,
        share_id=prompt.share_id,
        parent_prompt_id=prompt.parent_prompt_id,
        source_action=prompt.source_action,
        threads_count=threads_count,
        created_at=prompt.created_at,
        updated_at=prompt.updated_at,
    )


@router.post("", response_model=SunoPromptResponse, status_code=status.HTTP_201_CREATED)
def create_prompt(
    body: SunoPromptCreate,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Save a new Suno prompt as a favorite.
    Works for both Spotify-authenticated users and guests (via device token).
    If guest and no device_token cookie, creates a new guest user and sets cookie.
    """
    settings = get_settings()

    # Try Spotify session first
    spotify_user_id = get_current_user_id_optional(request)

    if spotify_user_id:
        user_id = spotify_user_id
    else:
        # Fall back to device token (create guest user if needed)
        user, created = get_or_create_device_user(request, db)
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

    prompt = SunoPrompt(
        owner_user_id=user_id,
        suno_prompt=body.suno_prompt,
        lyrics=body.lyrics,
        exclude=body.exclude,
        weirdness=body.weirdness,
        style_influence=body.style_influence,
        title=body.title,
        notes=body.notes,
        is_favorite=body.is_favorite,
        auto_tags=body.auto_tags,
        source_action="manual_save",
    )
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    return _prompt_to_response(prompt, db)


@router.get("", response_model=SunoPromptListResponse)
def list_prompts(
    request: Request,
    db: Session = Depends(get_db),
    device_user: User | None = Depends(get_device_user),
    limit: int = 50,
    offset: int = 0,
    favorites_only: bool = False,
):
    """
    List the current user's prompts (Spotify or guest).

    Args:
        favorites_only: If True, only return prompts where is_favorite=True.
                       If False (default), return all prompts (full history).
    """
    spotify_user_id = get_current_user_id_optional(request)
    user_id = _get_user_id_or_raise(spotify_user_id, device_user)

    # Base filter: user's prompts
    base_filter = SunoPrompt.owner_user_id == user_id

    # Apply favorites filter if requested
    if favorites_only:
        base_filter = base_filter & (SunoPrompt.is_favorite == True)  # noqa: E712

    query = (
        select(SunoPrompt)
        .where(base_filter)
        .order_by(SunoPrompt.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    prompts = list(db.scalars(query).all())

    total_query = select(func.count()).select_from(SunoPrompt).where(base_filter)
    total = db.scalar(total_query) or 0

    # Convert to response objects with threads_count
    prompt_responses = [_prompt_to_response(p, db) for p in prompts]
    return SunoPromptListResponse(prompts=prompt_responses, total=total)


@router.get("/{prompt_id}", response_model=SunoPromptResponse)
def get_prompt(
    prompt_id: int,
    request: Request,
    db: Session = Depends(get_db),
    device_user: User | None = Depends(get_device_user),
):
    """Get a single saved prompt by ID (owner only)."""
    spotify_user_id = get_current_user_id_optional(request)
    user_id = _get_user_id_or_raise(spotify_user_id, device_user)

    prompt = db.get(SunoPrompt, prompt_id)

    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    if prompt.owner_user_id != user_id:
        raise HTTPException(
            status_code=403, detail="Not authorized to access this prompt"
        )

    return _prompt_to_response(prompt, db)


@router.get("/{prompt_id}/threads", response_model=list[LyricsThreadSummary])
def get_prompt_threads(
    prompt_id: int,
    request: Request,
    db: Session = Depends(get_db),
    device_user: User | None = Depends(get_device_user),
):
    """Get all LyricsThreads (songs) for a StylePrompt (owner only).

    Used by sidebar to expand a StylePrompt and show its songs.
    """
    spotify_user_id = get_current_user_id_optional(request)
    user_id = _get_user_id_or_raise(spotify_user_id, device_user)

    prompt = db.get(SunoPrompt, prompt_id)

    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    if prompt.owner_user_id != user_id:
        raise HTTPException(
            status_code=403, detail="Not authorized to access this prompt"
        )

    query = (
        select(LyricsThread)
        .where(LyricsThread.style_prompt_id == prompt_id)
        .order_by(LyricsThread.updated_at.desc())
    )
    threads = list(db.scalars(query).all())
    return threads


@router.patch("/{prompt_id}", response_model=SunoPromptResponse)
def update_prompt(
    prompt_id: int,
    body: SunoPromptUpdate,
    request: Request,
    db: Session = Depends(get_db),
    device_user: User | None = Depends(get_device_user),
):
    """Update a saved prompt's title, notes, is_favorite, or visibility (owner only)."""
    spotify_user_id = get_current_user_id_optional(request)
    user_id = _get_user_id_or_raise(spotify_user_id, device_user)

    prompt = db.get(SunoPrompt, prompt_id)

    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    if prompt.owner_user_id != user_id:
        raise HTTPException(
            status_code=403, detail="Not authorized to update this prompt"
        )

    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(prompt, key, value)

    db.commit()
    db.refresh(prompt)
    return _prompt_to_response(prompt, db)


@router.delete("/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_prompt(
    prompt_id: int,
    request: Request,
    db: Session = Depends(get_db),
    device_user: User | None = Depends(get_device_user),
):
    """Delete a saved prompt (owner only)."""
    spotify_user_id = get_current_user_id_optional(request)
    user_id = _get_user_id_or_raise(spotify_user_id, device_user)

    prompt = db.get(SunoPrompt, prompt_id)

    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    if prompt.owner_user_id != user_id:
        raise HTTPException(
            status_code=403, detail="Not authorized to delete this prompt"
        )

    db.delete(prompt)
    db.commit()


@router.get("/shared/{share_id}", response_model=SunoPromptResponse)
def get_shared_prompt(
    share_id: str,
    db: Session = Depends(get_db),
):
    """
    Get a prompt by its share_id (public access).
    Only returns prompts with visibility != 'private'.
    """
    prompt = db.scalar(select(SunoPrompt).where(SunoPrompt.share_id == share_id))

    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    if prompt.visibility == "private":
        raise HTTPException(status_code=404, detail="Prompt not found")

    return _prompt_to_response(prompt, db)
