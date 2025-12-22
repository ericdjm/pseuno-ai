"""
Minimal generation models for the Suno formatter agent.
"""

from typing import Optional
from pydantic import BaseModel, Field


class AdvancedGenerateRequest(BaseModel):
    """
    Minimal request for the agent.
    """
    user_prompt: str = Field(
        ...,
        max_length=500,
        description="User prompt describing the song style",
    )
    lyrics_about: str = Field(
        ...,
        max_length=500,
        description="Topic or theme for the lyrics",
    )
    selected_artists: list[str] = Field(
        default_factory=list,
        description="Optional artist influences (names never shown in prompt)",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Optional style tags",
    )


class AdvancedGenerateResponse(BaseModel):
    """
    Response with separated artifacts and parameters.
    """
    concept_title: str
    lyrics: str = Field(description="Human-facing lyrical content")
    suno_prompt: str = Field(description="Machine-facing generation instructions")
    exclude: str = Field(description="Comma-separated excludes")
    weirdness: int = Field(description="Weirdness percent (0-100)", ge=0, le=100)
    style_influence: int = Field(
        description="Style influence percent (0-100)", ge=0, le=100
    )
    generation_id: str = Field(description="Reference ID for this generation")
    debug_info: Optional[dict] = None
