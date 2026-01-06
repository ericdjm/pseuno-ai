"""
Refinement schemas for editing existing Suno prompts and lyrics.

These models define the request/response shapes for the /refine-concept
and /refine-lyrics endpoints.
"""

from pydantic import BaseModel, Field


class RefinementRequest(BaseModel):
    """Request to refine an existing Suno prompt based on user feedback."""

    current_prompt: str = Field(
        description="The current prompt text to refine",
        min_length=1,
        max_length=500,
    )
    change_request: str = Field(
        description="Description of what the user wants to change",
        min_length=1,
        max_length=500,
    )


class RefinementResponse(BaseModel):
    """Response containing the refined prompt."""

    refined_prompt: str = Field(
        description="The refined prompt incorporating requested changes"
    )


class LyricsRefinementRequest(BaseModel):
    """Request to refine lyrics based on user feedback."""

    current_lyrics: str = Field(
        description="The current lyrics text to refine (with structure markers like [Verse], [Chorus])",
        max_length=3000,
    )
    change_request: str = Field(
        description="What the user wants to change in the lyrics",
        min_length=1,
        max_length=500,
    )


class LyricsRefinementResponse(BaseModel):
    """Response containing the refined lyrics."""

    refined_lyrics: str = Field(
        description="The updated lyrics after applying user-requested changes",
        max_length=3000,
    )

