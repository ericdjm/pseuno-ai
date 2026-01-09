"""
Unified refinement schemas for multi-field edits.

These models define the request/response shapes for the /generate/refine endpoint
which can update prompt, lyrics, exclude, title, and weirdness in a single turn.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class UnifiedRefineRequest(BaseModel):
    """Request to refine multiple fields based on a single user instruction."""

    # Current snapshot
    suno_prompt: str = Field(
        description="Current Suno style prompt",
        max_length=500,
    )
    lyrics: str = Field(
        description="Current lyrics with structure markers",
        max_length=5000,
    )
    exclude: str = Field(
        default="",
        description="Current exclude terms (comma-separated)",
        max_length=500,
    )
    title: str = Field(
        default="",
        description="Current song title",
        max_length=120,
    )
    weirdness: int = Field(
        default=50,
        ge=0,
        le=100,
        description="Current weirdness value (0-100)",
    )
    style_influence: int = Field(
        default=50,
        ge=0,
        le=100,
        description="Current style influence value (0-100)",
    )
    auto_tags: List[str] = Field(
        default=[],
        description="Current auto-generated tags for the prompt",
    )

    # User instruction
    change_request: str = Field(
        description="What the user wants to change",
        min_length=1,
        max_length=1000,
    )


class UnifiedRefineResponse(BaseModel):
    """Response containing the updated snapshot and list of changed fields."""

    # Updated snapshot
    suno_prompt: str = Field(description="Updated Suno style prompt")
    lyrics: str = Field(description="Updated lyrics")
    exclude: str = Field(description="Updated exclude terms")
    title: str = Field(description="Updated title")
    weirdness: int = Field(description="Updated weirdness (0-100)")

    # Metadata
    changed_fields: List[str] = Field(
        description="List of fields that were modified (e.g. ['suno_prompt', 'lyrics', 'exclude'])"
    )
    assistant_message: Optional[str] = Field(
        default=None,
        description="Optional message from the assistant (e.g. clarification or explanation)",
    )
    debug_info: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Debug trace with timing information for each step",
    )


# Internal schema for planner LLM output
class ExcludeUpdate(BaseModel):
    """How to update the exclude field."""

    mode: str = Field(description="'replace', 'append', or 'remove_terms'")
    value: str = Field(description="The terms to apply based on mode")


class PlannerOutput(BaseModel):
    """Structured output from the planner LLM."""

    # Style prompt
    edit_style: bool = Field(default=False, description="Whether to edit the style prompt")
    style_change_request: Optional[str] = Field(
        default=None, description="What to change in the style prompt"
    )

    # Lyrics
    edit_lyrics: bool = Field(default=False, description="Whether to edit the lyrics")
    lyrics_change_request: Optional[str] = Field(
        default=None, description="What to change in the lyrics"
    )

    # Exclude
    exclude_update: Optional[ExcludeUpdate] = Field(
        default=None, description="How to update exclude terms"
    )

    # Title
    title_update: Optional[str] = Field(
        default=None, description="New title value (if changing)"
    )

    # Weirdness
    weirdness_update: Optional[int] = Field(
        default=None, description="New weirdness value (if changing)"
    )

    # Optional assistant message
    assistant_message: Optional[str] = Field(
        default=None, description="Optional message to show user"
    )

