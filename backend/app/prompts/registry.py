"""
Prompt Variant Registry

A clean system for managing prompt variants that allows easy addition
of new variants without affecting existing ones.

Usage:
    from app.prompts.registry import register_variant, get_variant, list_variants

    # Register a new variant
    register_variant(
        id="v5_experimental",
        description="Experimental variant with new features",
        two_step=True,
        uses_lyric_profile=True,
        style_agent=MY_STYLE_PROMPT,
        lyrics_agent=MY_LYRICS_PROMPT,
    )

    # Get a variant
    variant = get_variant("v5_experimental")

    # List all variants
    all_variants = list_variants()
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Literal

# Type for variant architecture
Architecture = Literal["single_step", "two_step"]


@dataclass
class PromptVariant:
    """
    A prompt variant configuration.
    
    Attributes:
        id: Unique identifier (e.g., "v1", "v2_reddit_tricks")
        description: Human-readable description for UI
        architecture: "single_step" or "two_step"
        uses_lyric_profile: Whether this variant uses lyric profile controls
        
        # Single-step prompts (architecture="single_step")
        song_agent: Full song generation prompt
        repair_agent: Repair/fix prompt for validation failures
        
        # Two-step prompts (architecture="two_step")
        style_agent: Style generation prompt (step 1)
        style_repair_agent: Repair prompt for style validation failures
        lyrics_agent: Lyrics generation prompt (step 2)
        lyrics_repair_agent: Repair prompt for lyrics validation failures
        profile_inference_agent: Fast prompt for inferring lyric profile (V4 only)
        
        # Optional metadata
        is_default: Whether this is the default variant
        experimental: Mark as experimental (shown with warning in UI)
        deprecated: Mark as deprecated (hidden from UI by default)
    """
    id: str
    description: str
    architecture: Architecture = "single_step"
    uses_lyric_profile: bool = False
    
    # Single-step prompts
    song_agent: Optional[str] = None
    repair_agent: Optional[str] = None
    
    # Two-step prompts
    style_agent: Optional[str] = None
    style_repair_agent: Optional[str] = None
    lyrics_agent: Optional[str] = None
    lyrics_repair_agent: Optional[str] = None
    profile_inference_agent: Optional[str] = None  # For V4: fast profile inference
    genre_disambiguation_agent: Optional[str] = None  # For V6: pre-style genre enrichment
    
    # Metadata
    is_default: bool = False
    experimental: bool = False
    deprecated: bool = False
    
    def __post_init__(self):
        """Validate the variant configuration."""
        if self.architecture == "single_step":
            if not self.song_agent:
                raise ValueError(f"Variant {self.id}: single_step requires song_agent")
            if not self.repair_agent:
                raise ValueError(f"Variant {self.id}: single_step requires repair_agent")
        elif self.architecture == "two_step":
            if not self.style_agent:
                raise ValueError(f"Variant {self.id}: two_step requires style_agent")
            if not self.style_repair_agent:
                raise ValueError(f"Variant {self.id}: two_step requires style_repair_agent")
            if not self.lyrics_agent:
                raise ValueError(f"Variant {self.id}: two_step requires lyrics_agent")
            if not self.lyrics_repair_agent:
                raise ValueError(f"Variant {self.id}: two_step requires lyrics_repair_agent")
            if self.uses_lyric_profile and not self.profile_inference_agent:
                raise ValueError(f"Variant {self.id}: uses_lyric_profile requires profile_inference_agent")
    
    @property
    def two_step(self) -> bool:
        """Backwards compatibility property."""
        return self.architecture == "two_step"
    
    @property
    def prompt_length(self) -> int:
        """Total prompt length in characters (for UI display)."""
        return sum(self.prompt_lengths)

    @property
    def prompt_lengths(self) -> List[int]:
        """
        Individual prompt lengths for each LLM call (for UI display).
        
        Single-step: [song_agent, repair_agent]
        Two-step: [style_agent, style_repair, lyrics_agent, lyrics_repair]
        Two-step with profile: [profile_inference, style_agent, style_repair, lyrics_agent, lyrics_repair]
        Two-step with genre disambiguation: [genre_disambig, style_agent, style_repair, lyrics_agent, lyrics_repair]
        """
        if self.architecture == "single_step":
            return [len(self.song_agent or ""), len(self.repair_agent or "")]
        else:
            lengths = []
            if self.genre_disambiguation_agent:
                lengths.append(len(self.genre_disambiguation_agent))
            if self.profile_inference_agent:
                lengths.append(len(self.profile_inference_agent))
            lengths.extend([
                len(self.style_agent or ""),
                len(self.style_repair_agent or ""),
                len(self.lyrics_agent or ""),
                len(self.lyrics_repair_agent or ""),
            ])
            return lengths
    
    def to_dict(self) -> Dict:
        """Convert to legacy dict format for backwards compatibility."""
        result = {
            "description": self.description,
            "two_step": self.two_step,
            "uses_lyric_profile": self.uses_lyric_profile,
        }
        if self.architecture == "single_step":
            result["song_agent"] = self.song_agent
            result["repair_agent"] = self.repair_agent
        else:
            result["style_agent"] = self.style_agent
            result["style_repair_agent"] = self.style_repair_agent
            result["lyrics_agent"] = self.lyrics_agent
            result["lyrics_repair_agent"] = self.lyrics_repair_agent
            if self.profile_inference_agent:
                result["profile_inference_agent"] = self.profile_inference_agent
            if self.genre_disambiguation_agent:
                result["genre_disambiguation_agent"] = self.genre_disambiguation_agent
        return result


# Global registry
_REGISTRY: Dict[str, PromptVariant] = {}


def register_variant(
    id: str,
    description: str,
    architecture: Architecture = "single_step",
    uses_lyric_profile: bool = False,
    song_agent: Optional[str] = None,
    repair_agent: Optional[str] = None,
    style_agent: Optional[str] = None,
    style_repair_agent: Optional[str] = None,
    lyrics_agent: Optional[str] = None,
    lyrics_repair_agent: Optional[str] = None,
    profile_inference_agent: Optional[str] = None,
    genre_disambiguation_agent: Optional[str] = None,
    is_default: bool = False,
    experimental: bool = False,
    deprecated: bool = False,
) -> PromptVariant:
    """
    Register a new prompt variant.
    
    Example:
        register_variant(
            id="v5_experimental",
            description="My new variant",
            architecture="two_step",
            style_agent=MY_STYLE_PROMPT,
            lyrics_agent=MY_LYRICS_PROMPT,
        )
    """
    if id in _REGISTRY:
        raise ValueError(f"Variant '{id}' is already registered")
    
    variant = PromptVariant(
        id=id,
        description=description,
        architecture=architecture,
        uses_lyric_profile=uses_lyric_profile,
        song_agent=song_agent,
        repair_agent=repair_agent,
        style_agent=style_agent,
        style_repair_agent=style_repair_agent,
        lyrics_agent=lyrics_agent,
        lyrics_repair_agent=lyrics_repair_agent,
        profile_inference_agent=profile_inference_agent,
        genre_disambiguation_agent=genre_disambiguation_agent,
        is_default=is_default,
        experimental=experimental,
        deprecated=deprecated,
    )
    
    _REGISTRY[id] = variant
    return variant


def get_variant(id: str) -> PromptVariant:
    """Get a registered variant by ID."""
    if id not in _REGISTRY:
        available = list(_REGISTRY.keys())
        raise ValueError(f"Unknown variant: {id}. Available: {available}")
    return _REGISTRY[id]


def list_variants(
    include_deprecated: bool = False,
    include_experimental: bool = True,
) -> List[PromptVariant]:
    """List all registered variants."""
    variants = list(_REGISTRY.values())
    
    if not include_deprecated:
        variants = [v for v in variants if not v.deprecated]
    
    if not include_experimental:
        variants = [v for v in variants if not v.experimental]
    
    return variants


def get_default_variant() -> PromptVariant:
    """Get the default variant."""
    for variant in _REGISTRY.values():
        if variant.is_default:
            return variant
    # Fallback to first registered
    if _REGISTRY:
        return next(iter(_REGISTRY.values()))
    raise ValueError("No variants registered")


def to_legacy_dict() -> Dict[str, Dict]:
    """
    Convert registry to legacy PROMPT_VARIANTS dict format.
    For backwards compatibility during migration.
    """
    return {v.id: v.to_dict() for v in _REGISTRY.values()}

