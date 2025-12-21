"""
Advanced generation models for vibe-first composition
"""

from typing import Optional, Literal
from pydantic import BaseModel, Field


# === Vibe-First Models ===

class VibeIntent(BaseModel):
    """Emotional and sensory outcome goals"""
    primary_feeling: str = Field(description="Main emotional target (e.g., 'chills', 'make me cry', 'euphoria')")
    sensory_goals: list[str] = Field(default=[], description="Physical/sensory outcomes (e.g., 'goosebumps', 'full body movement')")
    context: Optional[str] = Field(default=None, description="Use case (e.g., 'perfect for a mushroom trip', 'running at 3am')")


class VocalControls(BaseModel):
    """Orthogonal vocal layer controls"""
    intensity: Literal["whisper", "soft", "conversational", "powerful", "screaming"] = "conversational"
    range: Literal["narrow", "moderate", "wide", "extreme"] = "moderate"
    harmonies: bool = False
    experimental: list[str] = Field(default=[], description="e.g., 'throat singing', 'techno chants', 'breath-based'")
    voice_as_instrument: bool = False


class RhythmControls(BaseModel):
    """Orthogonal rhythm layer controls"""
    complexity: Literal["simple", "moderate", "polyrhythmic", "chaotic"] = "moderate"
    accents: list[str] = Field(default=[], description="e.g., 'odd accents', 'off-beat', 'silence → slam'")
    drops: Literal["none", "occasional", "frequent", "random"] = "occasional"
    tempo_feel: Optional[str] = Field(default=None, description="e.g., 'tempo illusions', 'accelerating'")


class TextureControls(BaseModel):
    """Orthogonal texture layer controls"""
    organic_vs_synthetic: int = Field(default=50, ge=0, le=100, description="0=pure organic, 100=pure synthetic")
    acoustic_vs_electronic: int = Field(default=50, ge=0, le=100)
    raw_vs_processed: int = Field(default=50, ge=0, le=100, description="0=raw/live, 100=hyper-processed")
    atmosphere: list[str] = Field(default=[], description="e.g., 'ritual', 'club', 'industrial', 'cathedral'")


class StructureControls(BaseModel):
    """Orthogonal structure layer controls"""
    form_hints: list[str] = Field(default=[], description="e.g., 'verse/chorus', 'build/drop', 'freeform'")
    fake_drops: bool = False
    collapses: bool = False
    unresolved: bool = False
    intentional_chaos: bool = False


class RuleBreaking(BaseModel):
    """Explicit conventions to violate"""
    break_melody: bool = Field(default=False, description="Unresolved melodies")
    break_rhythm: bool = Field(default=False, description="Rhythm from breath, not beats")
    break_structure: bool = Field(default=False, description="Silence as structure")
    break_vocals: bool = Field(default=False, description="Voice pushed beyond comfort")
    permission_to_violate: list[str] = Field(default=[], description="Custom rule breaks")


class ContentTheme(BaseModel):
    """Symbolic anchor for lyrics"""
    theme_type: Literal["work", "transition", "ritual", "system", "grief", "creation", "conflict", "transformation"] = "work"
    specific_topic: Optional[str] = Field(default=None, description="e.g., 'building tools', 'leaving a job'")
    metaphor_depth: Literal["literal", "symbolic", "abstract"] = "symbolic"
    repetition_style: Literal["minimal", "chant", "mantra", "obsessive"] = "chant"


class ContrastIteration(BaseModel):
    """Refine by contrast, not correction"""
    reference_id: Optional[str] = Field(default=None, description="Previous generation to contrast from")
    less_of: list[str] = Field(default=[], description="Elements to reduce (e.g., 'less country')")
    more_of: list[str] = Field(default=[], description="Elements to amplify (e.g., 'more drops')")
    push_direction: Optional[str] = Field(default=None, description="e.g., 'harder', 'softer', 'weirder'")
    keep_elements: list[str] = Field(default=[], description="What to preserve from reference")


# === Mode Presets ===

GenerationMode = Literal[
    "ritual",      # Work as ritual, creation through friction
    "grief",       # Emotional processing, cathartic
    "chaos",       # Intentional disorder, rupture
    "work",        # Labor, process, building
    "flow",        # Continuity, trance, movement
    "transition",  # Change, transformation, thresholds
    "hope_threat", # Technology duality, future ambiguity
    "custom"       # User-defined
]


# === Advanced Generate Request ===

class AdvancedGenerateRequest(BaseModel):
    """
    Vibe-first generation request with orthogonal controls
    """
    # Core vibe
    vibe_intent: Optional[VibeIntent] = None
    mode: GenerationMode = "custom"
    
    # Orthogonal layers
    vocals: Optional[VocalControls] = None
    rhythm: Optional[RhythmControls] = None
    texture: Optional[TextureControls] = None
    structure: Optional[StructureControls] = None
    
    # Content
    content_theme: Optional[ContentTheme] = None
    
    # Rule breaking
    rule_breaking: Optional[RuleBreaking] = None
    
    # Iteration
    contrast: Optional[ContrastIteration] = None
    
    # Lyric density (auto-calculated or manual)
    lyric_density: Literal["minimal", "sparse", "moderate", "rich"] = "moderate"
    
    # Legacy compatibility
    time_range: str = Field(default="medium_term", pattern="^(short_term|medium_term|long_term)$")
    extra_notes: Optional[str] = None

    # Agent context inputs (dynamic per request)
    user_prompt: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Minimal user text about the song they want"
    )
    selected_artists: list[str] = Field(default_factory=list, description="User-selected artists to influence style")
    excluded_artists: list[str] = Field(default_factory=list, description="Artists to exclude from influence")
    selected_genres: list[str] = Field(default_factory=list, description="User-selected genres to emphasize")
    custom_vibes: list[str] = Field(default_factory=list, description="User-selected vibes/moods")
    
    # Output preferences
    separate_artifacts: bool = Field(
        default=True,
        description="Generate separate lyrics (human) and prompt (machine) artifacts"
    )


class AdvancedGenerateResponse(BaseModel):
    """
    Response with separated artifacts and metadata
    """
    concept_title: str
    
    # Separated artifacts
    lyrics: str = Field(description="Human-facing lyrical content")
    suno_prompt: str = Field(description="Machine-facing generation instructions")
    
    # Generation metadata
    vibe_signature: dict = Field(description="Fingerprint of this generation")
    control_layers_used: dict = Field(description="Which orthogonal controls were active")
    
    # For iteration
    generation_id: str = Field(description="Reference ID for contrast iteration")
    
    # Debug
    debug_info: Optional[dict] = None
