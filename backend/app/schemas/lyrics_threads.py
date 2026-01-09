"""
Schemas for LyricsThreads (songs/variations) and LyricsCheckpoints.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# === LyricsThread Schemas ===


class LyricsThreadCreate(BaseModel):
    """Request to create a new LyricsThread (song) under a StylePrompt."""

    style_prompt_id: int = Field(..., description="ID of the parent StylePrompt")
    title: Optional[str] = Field(
        default=None, max_length=255, description="Optional song title"
    )
    seed_from_thread_id: Optional[int] = Field(
        default=None,
        description="If provided, seed lyrics_text from this thread (fork)",
    )


class LyricsThreadUpdate(BaseModel):
    """Request to update a LyricsThread (partial update)."""

    title: Optional[str] = Field(default=None, max_length=255)
    lyrics_text: Optional[str] = Field(default=None)


class LyricsThreadResponse(BaseModel):
    """Response for a single LyricsThread."""

    id: int
    style_prompt_id: int
    parent_thread_id: Optional[int]
    title: Optional[str]
    lyrics_text: str
    source_action: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LyricsThreadSummary(BaseModel):
    """Summary of a LyricsThread for listing (without full lyrics)."""

    id: int
    title: Optional[str]
    source_action: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# === LyricsCheckpoint Schemas ===


class LyricsCheckpointCreate(BaseModel):
    """Request to create a checkpoint (snapshot) of current lyrics."""

    label: Optional[str] = Field(
        default=None, max_length=255, description="Optional label for the checkpoint"
    )


class LyricsCheckpointResponse(BaseModel):
    """Response for a single LyricsCheckpoint."""

    id: int
    thread_id: int
    label: Optional[str]
    lyrics_text: str
    created_at: datetime

    model_config = {"from_attributes": True}


class LyricsCheckpointListResponse(BaseModel):
    """Response for listing checkpoints of a thread."""

    checkpoints: list[LyricsCheckpointResponse]
    total: int
