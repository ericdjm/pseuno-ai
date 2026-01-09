"""
Routes for LyricsThreads (songs/variations) and LyricsCheckpoints.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import LyricsCheckpoint, LyricsThread, SunoPrompt, User
from app.deps import (
    get_current_user_id_optional,
    get_db,
    get_device_user,
    get_or_create_device_user,
)
from app.schemas.lyrics_threads import (
    LyricsCheckpointCreate,
    LyricsCheckpointListResponse,
    LyricsCheckpointResponse,
    LyricsThreadCreate,
    LyricsThreadResponse,
    LyricsThreadUpdate,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/lyrics-threads", tags=["LyricsThreads"])

DEVICE_TOKEN_MAX_AGE = 365 * 24 * 60 * 60  # 1 year


def _get_user_id(request: Request, db: Session, response: Response) -> str:
    """Get user ID from Spotify session or device token."""
    spotify_user_id = get_current_user_id_optional(request)
    if spotify_user_id:
        return spotify_user_id

    user, created = get_or_create_device_user(request, db)
    if created:
        settings = get_settings()
        response.set_cookie(
            key="device_token",
            value=user.device_token,
            httponly=True,
            secure=settings.session_cookie_secure,
            samesite=settings.session_cookie_samesite,
            max_age=DEVICE_TOKEN_MAX_AGE,
        )
    return user.id


def _get_current_user_id(request: Request, db: Session) -> Optional[str]:
    """Get current user ID without creating a new user."""
    spotify_user_id = get_current_user_id_optional(request)
    if spotify_user_id:
        return spotify_user_id

    device_user = get_device_user(request, db)
    if device_user:
        return device_user.id

    return None


def _verify_prompt_ownership(db: Session, prompt_id: int, user_id: str) -> SunoPrompt:
    """Verify the user owns the prompt, return it or raise 404/403."""
    prompt = db.get(SunoPrompt, prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="StylePrompt not found")
    if prompt.owner_user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    return prompt


def _verify_thread_ownership(db: Session, thread_id: int, user_id: str) -> LyricsThread:
    """Verify the user owns the thread (via prompt), return it or raise 404/403."""
    thread = db.get(LyricsThread, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="LyricsThread not found")
    if thread.style_prompt.owner_user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    return thread


# === LyricsThread Endpoints ===


@router.post(
    "", response_model=LyricsThreadResponse, status_code=status.HTTP_201_CREATED
)
def create_lyrics_thread(
    body: LyricsThreadCreate,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> LyricsThreadResponse:
    """Create a new LyricsThread (song) under a StylePrompt.

    If seed_from_thread_id is provided, the new thread's lyrics_text
    will be copied from that thread (fork behavior).
    """
    user_id = _get_user_id(request, db, response)

    # Verify ownership of the parent prompt
    _verify_prompt_ownership(db, body.style_prompt_id, user_id)

    # Determine initial lyrics and parent_thread_id
    lyrics_text = ""
    parent_thread_id = None

    if body.seed_from_thread_id:
        seed_thread = _verify_thread_ownership(db, body.seed_from_thread_id, user_id)
        lyrics_text = seed_thread.lyrics_text
        parent_thread_id = seed_thread.id

    thread = LyricsThread(
        style_prompt_id=body.style_prompt_id,
        parent_thread_id=parent_thread_id,
        title=body.title or "Untitled Song",
        lyrics_text=lyrics_text,
        source_action="new_lyrics_variation",
    )
    db.add(thread)
    db.commit()
    db.refresh(thread)

    logger.info(
        "Created LyricsThread id=%d for prompt=%d user=%s",
        thread.id,
        body.style_prompt_id,
        user_id,
    )
    return thread


@router.get("/{thread_id}", response_model=LyricsThreadResponse)
def get_lyrics_thread(
    thread_id: int,
    request: Request,
    db: Session = Depends(get_db),
    device_user: User | None = Depends(get_device_user),
) -> LyricsThreadResponse:
    """Get a single LyricsThread by ID."""
    user_id = _get_current_user_id(request, db)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    thread = _verify_thread_ownership(db, thread_id, user_id)
    return thread


@router.patch("/{thread_id}", response_model=LyricsThreadResponse)
def update_lyrics_thread(
    thread_id: int,
    body: LyricsThreadUpdate,
    request: Request,
    db: Session = Depends(get_db),
    device_user: User | None = Depends(get_device_user),
) -> LyricsThreadResponse:
    """Update a LyricsThread (title and/or lyrics_text)."""
    user_id = _get_current_user_id(request, db)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    thread = _verify_thread_ownership(db, thread_id, user_id)

    if body.title is not None:
        thread.title = body.title
    if body.lyrics_text is not None:
        thread.lyrics_text = body.lyrics_text

    db.commit()
    db.refresh(thread)

    logger.info("Updated LyricsThread id=%d", thread_id)
    return thread


@router.delete("/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lyrics_thread(
    thread_id: int,
    request: Request,
    db: Session = Depends(get_db),
    device_user: User | None = Depends(get_device_user),
) -> None:
    """Delete a LyricsThread."""
    user_id = _get_current_user_id(request, db)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    thread = _verify_thread_ownership(db, thread_id, user_id)
    db.delete(thread)
    db.commit()
    logger.info("Deleted LyricsThread id=%d", thread_id)


# === Checkpoint Endpoints ===


@router.post(
    "/{thread_id}/checkpoints",
    response_model=LyricsCheckpointResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_checkpoint(
    thread_id: int,
    body: LyricsCheckpointCreate,
    request: Request,
    db: Session = Depends(get_db),
    device_user: User | None = Depends(get_device_user),
) -> LyricsCheckpointResponse:
    """Create a checkpoint (snapshot) of the current lyrics_text."""
    user_id = _get_current_user_id(request, db)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    thread = _verify_thread_ownership(db, thread_id, user_id)

    checkpoint = LyricsCheckpoint(
        thread_id=thread.id,
        label=body.label,
        lyrics_text=thread.lyrics_text,
    )
    db.add(checkpoint)
    db.commit()
    db.refresh(checkpoint)

    logger.info("Created checkpoint id=%d for thread=%d", checkpoint.id, thread_id)
    return checkpoint


@router.get("/{thread_id}/checkpoints", response_model=LyricsCheckpointListResponse)
def list_checkpoints(
    thread_id: int,
    request: Request,
    db: Session = Depends(get_db),
    device_user: User | None = Depends(get_device_user),
) -> LyricsCheckpointListResponse:
    """List all checkpoints for a LyricsThread (newest first)."""
    user_id = _get_current_user_id(request, db)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    thread = _verify_thread_ownership(db, thread_id, user_id)

    query = (
        select(LyricsCheckpoint)
        .where(LyricsCheckpoint.thread_id == thread.id)
        .order_by(LyricsCheckpoint.created_at.desc())
    )
    checkpoints = list(db.scalars(query).all())

    return LyricsCheckpointListResponse(checkpoints=checkpoints, total=len(checkpoints))


@router.post(
    "/{thread_id}/checkpoints/{checkpoint_id}/restore",
    response_model=LyricsThreadResponse,
)
def restore_checkpoint(
    thread_id: int,
    checkpoint_id: int,
    request: Request,
    db: Session = Depends(get_db),
    device_user: User | None = Depends(get_device_user),
) -> LyricsThreadResponse:
    """Restore a thread's lyrics_text from a checkpoint.

    This creates a new checkpoint labeled "Before restore" first,
    then sets the thread's lyrics_text to the checkpoint's content.
    """
    user_id = _get_current_user_id(request, db)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    thread = _verify_thread_ownership(db, thread_id, user_id)

    # Find the checkpoint
    checkpoint = db.get(LyricsCheckpoint, checkpoint_id)
    if not checkpoint or checkpoint.thread_id != thread_id:
        raise HTTPException(status_code=404, detail="Checkpoint not found")

    # Create a "Before restore" checkpoint first
    before_restore = LyricsCheckpoint(
        thread_id=thread.id,
        label="Before restore",
        lyrics_text=thread.lyrics_text,
    )
    db.add(before_restore)

    # Restore
    thread.lyrics_text = checkpoint.lyrics_text
    db.commit()
    db.refresh(thread)

    logger.info("Restored thread=%d from checkpoint=%d", thread_id, checkpoint_id)
    return thread
