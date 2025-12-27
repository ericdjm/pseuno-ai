"""
Minimal generation models for the Suno formatter agent.
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


# ===========================================================================
# DEBUG TRACE SCHEMA (v1)
# ===========================================================================

SpanKind = Literal[
    "llm_call",
    "validate",
    "parse",
    "format_context",
    "repair",
    "profile_infer",
    "branch",
    "other",
]


class DebugSpan(BaseModel):
    """A single span in the debug trace timeline."""

    id: str = Field(description="Unique span identifier")
    parent_id: Optional[str] = Field(
        default=None, description="Parent span ID for nesting"
    )
    name: str = Field(
        description="Span name (e.g., 'style.generate', 'lyrics.repair.1')"
    )
    kind: SpanKind = Field(description="Type of operation")
    start_ms: int = Field(description="Start time in ms since generation start")
    end_ms: int = Field(description="End time in ms since generation start")
    elapsed_ms: int = Field(description="Duration in ms")
    meta: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structured metadata (model, prompt_chars, response_chars, issues, etc.)",
    )
    artifacts: Dict[str, str] = Field(
        default_factory=dict,
        description="Raw text artifacts (system_prompt, user_message, raw_response) - hidden by default in UI",
    )


class DebugTraceSummary(BaseModel):
    """High-level summary of the generation."""

    variant: str = Field(description="Prompt variant used (e.g., v5_hybrid)")
    model: str = Field(description="Primary LLM model used")
    fast_model: Optional[str] = Field(
        default=None, description="Fast model for profile inference (if used)"
    )
    total_elapsed_ms: int = Field(description="Total generation time in ms")
    llm_calls: int = Field(description="Number of LLM calls made")
    repairs: int = Field(description="Number of repair attempts")
    architecture: str = Field(
        description="Generation architecture (single_step or two_step)"
    )
    success: bool = Field(default=True, description="Whether generation succeeded")
    error: Optional[str] = Field(default=None, description="Error message if failed")


class DebugTrace(BaseModel):
    """
    Unified debug trace returned in AdvancedGenerateResponse.debug_info.
    Version 1 schema - all variants (V1-V5) use this same structure.
    """

    version: int = Field(default=1, description="Schema version for forward compat")
    summary: DebugTraceSummary = Field(description="High-level generation summary")
    spans: List[DebugSpan] = Field(
        default_factory=list, description="Ordered timeline of spans"
    )

from app.constants import (
    SUNO_PROMPT_MAX_CHARS,
    LYRICS_TOPIC_MAX_CHARS,
    MAX_ARTISTS_COUNT,
    MAX_ARTIST_NAME_CHARS,
    MAX_TAGS_COUNT,
    MAX_TAG_CHARS,
)

# Available prompt variants for A/B testing
PromptVariant = Literal["v1", "v2_reddit_tricks", "v3_two_step", "v4_lyric_profile", "v5_hybrid", "v6_genre_disambiguation"]

# Lyric control enums - user can set to 'auto' to let the model infer
LyricAudience = Literal["auto", "kids", "general", "adult"]
LyricDirectness = Literal["auto", "direct", "balanced", "metaphor_heavy"]
LyricHumor = Literal["auto", "none", "light", "comedic", "crude"]
LyricExplicitness = Literal["auto", "clean", "innuendo", "explicit"]
LyricPersona = Literal["auto", "earnest", "playful", "aggressive", "romantic", "melancholic"]
LyricDensity = Literal[
    "auto",
    "sparse",    # Fewer words, more breathing room, atmospheric
    "standard",  # Normal lyric density
    "dense",     # Lots of lyrics, wordy, rap-influenced or storytelling
]
LyricPacing = Literal[
    "auto",
    "slow",   # Rhyme every line (AABB), more syllables per line, ballad feel
    "mid",    # Standard pacing
    "fast",   # Rhyme every other line (ABAB/ABCB), fewer syllables, punchy
]


class LyricControls(BaseModel):
    """
    Optional user overrides for lyric generation style.
    All fields default to 'auto' which lets the model infer from context.
    """

    audience: LyricAudience = Field(
        default="auto",
        description="Target audience: kids (simple/clear), general, or adult",
    )
    directness: LyricDirectness = Field(
        default="auto",
        description="How literally to express the topic: direct, balanced, or metaphor_heavy",
    )
    humor: LyricHumor = Field(
        default="auto",
        description="Amount and style of humor: none, light, comedic, or crude",
    )
    explicitness: LyricExplicitness = Field(
        default="auto",
        description="Content rating: clean, innuendo, or explicit",
    )
    persona: LyricPersona = Field(
        default="auto",
        description="Emotional stance of the lyrics: earnest, playful, aggressive, romantic, or melancholic",
    )
    density: LyricDensity = Field(
        default="auto",
        description="How many lyrics: sparse (atmospheric), standard, or dense (wordy)",
    )
    pacing: LyricPacing = Field(
        default="auto",
        description="Tempo feel: slow (rhyme every line), mid, or fast (rhyme every other line)",
    )


class LyricProfile(BaseModel):
    """
    The resolved lyric profile (no 'auto' values - all resolved to concrete choices).
    Generated by the LyricProfile system prompt or set from user overrides.
    """

    audience: Literal["kids", "general", "adult"] = "general"
    directness: Literal["direct", "balanced", "metaphor_heavy"] = "balanced"
    humor: Literal["none", "light", "comedic", "crude"] = "none"
    explicitness: Literal["clean", "innuendo", "explicit"] = "clean"
    persona: Literal["earnest", "playful", "aggressive", "romantic", "melancholic"] = "earnest"
    density: Literal["sparse", "standard", "dense"] = "standard"
    pacing: Literal["slow", "mid", "fast"] = "mid"
    devices: list[str] = Field(
        default_factory=list,
        description="Lyric devices to lean on (e.g., call_and_response, internal_rhyme)",
    )
    avoid: list[str] = Field(
        default_factory=list,
        description="Pitfalls to avoid (e.g., overly_abstract_metaphors_for_kids)",
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
    prompt_variant: Optional[PromptVariant] = Field(
        default=None,
        description="Prompt variant to use (v1=baseline, v2_reddit_tricks=advanced). Uses server default if not specified.",
    )
    model: Optional[str] = Field(
        default=None,
        description="LLM model for single-step generation (V1/V2). Uses server default if not specified.",
    )
    style_model: Optional[str] = Field(
        default=None,
        description="LLM model for SUNO prompt/style generation (two-step). Uses server default if not specified.",
    )
    lyrics_model: Optional[str] = Field(
        default=None,
        description="LLM model for lyrics generation (two-step). Uses server default if not specified.",
    )
    lyric_controls: Optional[LyricControls] = Field(
        default=None,
        description="Optional lyric style controls. Fields set to 'auto' will be inferred from context.",
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
