"""
Schemas for saved Suno prompts (favorites).
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class SunoPromptCreate(BaseModel):
    """Request to save a new Suno prompt."""

    suno_prompt: str = Field(..., min_length=1, max_length=2000)
    exclude: str = Field(default="", max_length=500)
    weirdness: int = Field(default=50, ge=0, le=100)
    style_influence: int = Field(default=50, ge=0, le=100)
    title: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = Field(default=None, max_length=2000)


class SunoPromptUpdate(BaseModel):
    """Request to update a saved Suno prompt (partial update)."""

    title: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = Field(default=None, max_length=2000)
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
    """Response for a single saved Suno prompt."""

    id: int
    suno_prompt: str
    exclude: str
    weirdness: int
    style_influence: int
    title: Optional[str]
    notes: Optional[str]
    visibility: str
    share_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SunoPromptListResponse(BaseModel):
    """Response for listing saved Suno prompts."""

    prompts: list[SunoPromptResponse]
    total: int
