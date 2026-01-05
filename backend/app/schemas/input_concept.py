"""
Input concept generation schemas.

These models represent the "input side" of generation:
a short 3-sentence Suno concept based on genre and artist influences.

This is separate from the "output side" (AdvancedGenerate*) which
produces the final 500-char Suno prompt + lyrics.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class InputConceptRequest(BaseModel):
    """Request to generate a short Suno concept from genre/artist influences."""

    genres: List[str] = Field(
        default_factory=list,
        description="List of genres to draw influence from. "
        "1-3 will be randomly selected. If empty, fallback genres are used.",
        max_length=20,
    )
    artists: List[str] = Field(
        default_factory=list,
        description="List of artist names (for future use, currently passed through). "
        "Not used in v1 generation.",
        max_length=20,
    )
    mood: Optional[str] = Field(
        default=None,
        description="Optional mood hint (e.g., 'dark', 'uplifting', 'nostalgic')",
        max_length=100,
    )


class InputConceptResponse(BaseModel):
    """Response containing the generated input concept."""

    concept: str = Field(
        description="3-sentence Suno concept describing the style/vibe"
    )
    chosen_genres: List[str] = Field(
        default_factory=list,
        description="The 1-3 genres randomly selected for this concept",
    )
    genres: List[str] = Field(
        default_factory=list,
        description="Full list of genres considered (for downstream handoff)",
    )
    artists: List[str] = Field(
        default_factory=list,
        description="Full list of artists (passed through for future use)",
    )
    mood: Optional[str] = Field(
        default=None,
        description="Mood used in generation (echoed back or inferred)",
    )
