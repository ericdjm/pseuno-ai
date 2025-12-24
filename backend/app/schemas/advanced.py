"""
Minimal generation models for the Suno formatter agent.
"""

from typing import Optional

from pydantic import BaseModel, Field, model_validator

from app.constants import (
    SUNO_PROMPT_MAX_CHARS,
    LYRICS_TOPIC_MAX_CHARS,
    MAX_ARTISTS_COUNT,
    MAX_ARTIST_NAME_CHARS,
    MAX_TAGS_COUNT,
    MAX_TAG_CHARS,
)


class AdvancedGenerateRequest(BaseModel):
    """
    Minimal request for the agent.
    """

    user_prompt: str = Field(
        ...,
        max_length=SUNO_PROMPT_MAX_CHARS,
        description="User prompt describing the song style",
    )
    lyrics_about: str = Field(
        ...,
        max_length=LYRICS_TOPIC_MAX_CHARS,
        description="Topic or theme for the lyrics",
    )
    # Cap list sizes + overall input size to prevent abuse / runaway costs.
    selected_artists: list[str] = Field(
        default_factory=list,
        max_length=MAX_ARTISTS_COUNT,
        description="Optional artist influences (names never shown in prompt)",
    )
    tags: list[str] = Field(
        default_factory=list,
        max_length=MAX_TAGS_COUNT,
        description="Optional style tags",
    )

    @model_validator(mode="after")
    def validate_lists(self):
        # Enforce per-item caps to prevent abuse (even if caller bypasses frontend).
        self.selected_artists = [
            a.strip()[:MAX_ARTIST_NAME_CHARS]
            for a in self.selected_artists
            if a and a.strip()
        ][:MAX_ARTISTS_COUNT]
        self.tags = [t.strip()[:MAX_TAG_CHARS] for t in self.tags if t and t.strip()][
            :MAX_TAGS_COUNT
        ]
        return self


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


class LyricsOnlyRequest(BaseModel):
    """
    Request for lyrics-only generation (reusing a saved Suno prompt).
    """

    suno_prompt: str = Field(
        ...,
        max_length=SUNO_PROMPT_MAX_CHARS,
        description="The saved Suno prompt to use as style context",
    )
    lyrics_about: str = Field(
        ...,
        max_length=LYRICS_TOPIC_MAX_CHARS,
        description="Topic or theme for the new lyrics",
    )


class LyricsOnlyResponse(BaseModel):
    """
    Response with generated lyrics and song title.
    """

    song_title: str = Field(description="Generated song title")
    lyrics: str = Field(description="Generated lyrics")
