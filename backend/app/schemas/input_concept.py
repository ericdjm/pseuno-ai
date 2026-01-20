"""
Input concept generation schemas.

These models represent the "input side" of generation:
a short 3-sentence Suno concept based on genre and artist influences.

This is separate from the "output side" (AdvancedGenerate*) which
produces the final 500-char Suno prompt + lyrics.
"""

from typing import Any, Dict, List, Optional

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

    candidate_genres: List[str] = Field(
        default_factory=list,
        description=(
            "Optional candidate pool for random tag selection/fill. "
            "When provided, this overrides the server's fallback seed list as the sampling pool. "
            "This is useful for including personalized (e.g., Spotify-aided) tags in v1 without server-side Spotify calls."
        ),
        max_length=200,
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

    trait_overrides: Optional[Dict[str, float]] = Field(
        default=None,
        description="Optional trait weights from async style classifier (LLM).",
    )
    bank_similarities: Optional[Dict[str, float]] = Field(
        default=None,
        description="Optional embedding-based bank similarity scores from async classifier.",
    )


class LyricsTopicDebugInfo(BaseModel):
    """Debug information for lyrics topic generation (dev only)."""

    tag_traits: Dict[str, float] = Field(
        default_factory=dict,
        description="Traits extracted from input tags",
    )
    style_prompt_traits: Dict[str, float] = Field(
        default_factory=dict,
        description="Traits extracted from style_prompt",
    )
    merged_traits: Dict[str, float] = Field(
        default_factory=dict,
        description="Final merged traits used for routing",
    )
    top_banks: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Top candidate banks with probabilities",
    )
    style_prompt_keywords_matched: List[str] = Field(
        default_factory=list,
        description="Keywords from style_prompt that matched trait mappings",
    )


class LyricsTopicResponse(BaseModel):
    """Response containing the generated lyrics topic."""

    topic: str = Field(
        description="A short 1-2 sentence lyric topic or theme",
    )
    bank_id: Optional[str] = Field(
        default=None,
        description="The topic bank this prompt was selected from (for analytics)",
    )
    chosen_moods: List[str] = Field(
        default_factory=list,
        description="The moods that influenced this topic",
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="Optional reasoning for the topic (for debugging)",
    )
    debug: Optional[LyricsTopicDebugInfo] = Field(
        default=None,
        description="Debug info (only populated in dev mode)",
    )


class ClassifyStyleRequest(BaseModel):
    """Request to classify a free-text style prompt into lyric topic routing signals."""

    style_prompt: str = Field(
        description="Free-text style prompt (may include artists, genres, vibes).",
        max_length=2000,
    )


class ClassifyStyleResponse(BaseModel):
    """Response containing classifier-derived routing signals (traits + bank similarities)."""

    traits: Dict[str, float] = Field(
        default_factory=dict,
        description="Trait weights inferred from the style prompt.",
    )
    latency_ms: int = Field(
        default=0,
        description="End-to-end classifier latency in milliseconds.",
    )
    success: bool = Field(
        default=True,
        description="Whether the classification succeeded.",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message when success=false.",
    )
    bank_similarities: Optional[Dict[str, float]] = Field(
        default=None,
        description="Top-K bank similarity scores from embeddings.",
    )

