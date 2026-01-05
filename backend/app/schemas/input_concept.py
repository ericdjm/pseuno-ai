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


class RefinementRequest(BaseModel):
    """Request to refine an existing prompt based on user feedback."""

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
    changes_made: Optional[str] = Field(
        default=None,
        description="Optional summary of changes made (for debugging)",
    )


class LyricsRefinementRequest(BaseModel):
    """Request to refine lyrics based on user feedback."""

    current_lyrics: str = Field(
        description="The current lyrics text to refine (with structure markers like [Verse], [Chorus])",
        max_length=3000,
    )
    change_request: str = Field(
        description="What the user wants to change in the lyrics (e.g., 'change the chorus', 'add another verse')",
        min_length=1,
        max_length=500,
    )


class LyricsRefinementResponse(BaseModel):
    """Response containing the refined lyrics."""

    refined_lyrics: str = Field(
        description="The updated lyrics after applying user-requested changes",
        max_length=3000,
    )
    changes_made: Optional[str] = Field(
        default=None,
        description="Optional summary of changes made",
    )


class LyricsTopicRequest(BaseModel):
    """Request to generate a short lyrics topic/theme from genre/mood influences."""

    genres: List[str] = Field(
        default_factory=list,
        description="List of genres to draw thematic influence from. "
        "If empty, uses random seed themes.",
        max_length=20,
    )
    moods: List[str] = Field(
        default_factory=list,
        description="List of mood tags (e.g., 'melancholic', 'uplifting'). "
        "If provided, will influence the lyric theme.",
        max_length=10,
    )
    style_prompt: Optional[str] = Field(
        default=None,
        description="Optional style prompt to align lyric topic with. "
        "If provided, the topic will complement this musical style.",
        max_length=500,
    )


class LyricsTopicResponse(BaseModel):
    """Response containing the generated lyrics topic."""

    topic: str = Field(
        description="A short 1-2 sentence lyric topic or theme",
    )
    chosen_moods: List[str] = Field(
        default_factory=list,
        description="The moods that influenced this topic",
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="Optional reasoning for the topic (for debugging)",
    )
