"""
Schemas for saved Suno prompts (favorites).
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from app.constants import (
    SUNO_PROMPT_MAX_CHARS,
    SUNO_EXCLUDE_MAX_CHARS,
    SAVED_PROMPT_TITLE_MAX_CHARS,
    SAVED_PROMPT_NOTES_MAX_CHARS,
)


class SunoPromptCreate(BaseModel):
    """Request to save a new Suno prompt."""

    # Suno hard cap: prompts cannot exceed SUNO_PROMPT_MAX_CHARS
    suno_prompt: str = Field(..., min_length=1, max_length=SUNO_PROMPT_MAX_CHARS)
    lyrics: str = Field(default="")
    exclude: str = Field(default="", max_length=SUNO_EXCLUDE_MAX_CHARS)
    weirdness: int = Field(default=50, ge=0, le=100)
    style_influence: int = Field(default=50, ge=0, le=100)
    title: Optional[str] = Field(default=None, max_length=SAVED_PROMPT_TITLE_MAX_CHARS)
    notes: Optional[str] = Field(default=None, max_length=SAVED_PROMPT_NOTES_MAX_CHARS)
    is_favorite: bool = Field(default=True)  # Manual saves default to favorite
    auto_tags: list[str] = Field(default=[])


class SunoPromptUpdate(BaseModel):
    """Request to update a saved Suno prompt (partial update)."""

    title: Optional[str] = Field(default=None, max_length=SAVED_PROMPT_TITLE_MAX_CHARS)
    notes: Optional[str] = Field(default=None, max_length=SAVED_PROMPT_NOTES_MAX_CHARS)
    is_favorite: Optional[bool] = Field(default=None)
    visibility: Optional[str] = Field(
        default=None, pattern="^(private|unlisted|public)$"
    )

    @model_validator(mode="before")
    @classmethod
    def reject_null_visibility(cls, data):
        """Reject explicit null for visibility (DB column is NOT NULL)."""
        if (
            isinstance(data, dict)
            and "visibility" in data
            and data["visibility"] is None
        ):
            raise ValueError("visibility cannot be set to null")
        return data


class SunoPromptResponse(BaseModel):
    """Response for a single saved Suno prompt (StylePrompt)."""

    id: int
    suno_prompt: str
    lyrics: str
    exclude: str
    weirdness: int
    style_influence: int
    title: Optional[str]
    notes: Optional[str]
    is_favorite: bool
    auto_tags: list[str]
    generation_id: Optional[str]
    visibility: str
    share_id: str
    # Iteration chain
    parent_prompt_id: Optional[int] = None
    source_action: str = "unknown"
    # Count of LyricsThreads (songs) under this StylePrompt
    threads_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SunoPromptListResponse(BaseModel):
    """Response for listing saved Suno prompts."""

    prompts: list[SunoPromptResponse]
    total: int
