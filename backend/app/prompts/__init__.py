"""
Prompts Package

A modular system for managing prompt variants.

Usage:
    from app.prompts import get_variant, list_variants, PROMPT_VARIANTS

    # Get a specific variant
    v3 = get_variant("v3_two_step")
    print(v3.style_agent)

    # List all variants
    for variant in list_variants():
        print(f"{variant.id}: {variant.description}")

    # Legacy dict format (backwards compatible)
    variant_dict = PROMPT_VARIANTS["v1"]

Adding a new variant:
    1. Create a file in app/prompts/variants/ (e.g., v5_my_variant.py)
    2. Import specs you need from app.prompts.specs
    3. Compose your prompts
    4. Call register_variant() with your config
    5. Add import to app/prompts/variants/__init__.py

    See existing variant files for examples.
"""

__all__ = [
    # Registry API
    "register_variant",
    "get_variant",
    "list_variants",
    "get_default_variant",
    "to_legacy_dict",
    "PromptVariant",
    # Specs
    "POLICY",
    "OUTPUT_CONTRACT",
    "OUTPUT_CONTRACT_FULL",
    "OUTPUT_CONTRACT_STYLE",
    "OUTPUT_CONTRACT_LYRICS",
    "TASK",
    "TASK_FULL",
    "TASK_STYLE",
    "TASK_STYLE_WITH_PROFILE",
    "TASK_LYRICS",
    "TASK_LYRICS_WITH_PROFILE",
    "TASK_LYRICS_SIMPLE",
    "OUTPUT_CONTRACT_STYLE_WITH_PROFILE",
    "LYRICS_SPEC",
    "SONG_TITLE_SPEC",
    "SUNO_PROMPT_SPEC",
    "SUNO_PROMPT_SPEC_V5",
    "SUNO_PROMPT_SPEC_V2",
    "EXCLUDE_SPEC",
    "PARAMETER_SPEC",
    "LYRIC_PROFILE_SPEC",
    "VOCAL_FORMATTING_SPEC",
    # Repair and inference prompts
    "STYLE_REPAIR_AGENT",
    "STYLE_REPAIR_AGENT_WITH_PROFILE",
    "STYLE_REPAIR_AGENT_PROSE",
    "LYRICS_REPAIR_AGENT",
    "PROFILE_INFERENCE_AGENT",
    "GENRE_DISAMBIGUATION_AGENT",
    # Legacy exports
    "PROMPT_VARIANTS",
    "AVAILABLE_MODELS",
    "get_prompt_variant",
    "SONG_AGENT_SYSTEM_PROMPT",
    "REPAIR_AGENT_SYSTEM_PROMPT",
    "SONG_AGENT_SYSTEM_PROMPT_V2",
    "REPAIR_AGENT_SYSTEM_PROMPT_V2",
    "STYLE_AGENT_SYSTEM_PROMPT",
    "LYRICS_AGENT_SYSTEM_PROMPT",
    "LYRICS_AGENT_SYSTEM_PROMPT_V3",
    "LYRICS_AGENT_SYSTEM_PROMPT_V4",
    "LYRICS_SIMPLE_PROMPT",
    "LYRICS_SYSTEM_PROMPT",
]

# Import registry functions
from app.prompts.registry import (
    register_variant,
    get_variant,
    list_variants,
    get_default_variant,
    to_legacy_dict,
    PromptVariant,
)

# Import all specs for convenience
from app.prompts.specs import (
    # Core
    POLICY,
    OUTPUT_CONTRACT,
    OUTPUT_CONTRACT_FULL,
    OUTPUT_CONTRACT_STYLE,
    OUTPUT_CONTRACT_STYLE_WITH_PROFILE,
    OUTPUT_CONTRACT_LYRICS,
    TASK,
    TASK_FULL,
    TASK_STYLE,
    TASK_STYLE_WITH_PROFILE,
    TASK_LYRICS,
    TASK_LYRICS_WITH_PROFILE,
    TASK_LYRICS_SIMPLE,
    # Content specs
    LYRICS_SPEC,
    SONG_TITLE_SPEC,
    SUNO_PROMPT_SPEC,
    SUNO_PROMPT_SPEC_V5,
    SUNO_PROMPT_SPEC_V2,
    EXCLUDE_SPEC,
    PARAMETER_SPEC,
    LYRIC_PROFILE_SPEC,
    VOCAL_FORMATTING_SPEC,
    # Repair and inference prompts
    STYLE_REPAIR_AGENT,
    STYLE_REPAIR_AGENT_WITH_PROFILE,
    STYLE_REPAIR_AGENT_PROSE,
    LYRICS_REPAIR_AGENT,
    PROFILE_INFERENCE_AGENT,
    GENRE_DISAMBIGUATION_AGENT,
)

# Import all variants (this triggers registration)
from app.prompts import variants  # noqa: F401

# Generate legacy PROMPT_VARIANTS dict for backwards compatibility
PROMPT_VARIANTS = to_legacy_dict()

# Export available models (keep here for now, could move to separate module)
AVAILABLE_MODELS = [
    {"id": "gemini-3-flash-preview", "name": "Gemini 3 Flash", "provider": "google"},
    {"id": "gpt-5.2-chat-latest", "name": "GPT-5.2 Chat", "provider": "openai"},
    {"id": "gpt-4.1-mini", "name": "GPT-4.1 Mini", "provider": "openai"},
    {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "provider": "openai"},
]


# Legacy exports for backwards compatibility
def get_prompt_variant(variant: str = "v1") -> dict:
    """Get a specific prompt variant for A/B testing. (Legacy API)"""
    return get_variant(variant).to_dict()


# Legacy prompt aliases - these point to V1/V4 prompts
SONG_AGENT_SYSTEM_PROMPT = get_variant("v1").song_agent
REPAIR_AGENT_SYSTEM_PROMPT = get_variant("v1").repair_agent
SONG_AGENT_SYSTEM_PROMPT_V2 = get_variant("v2_reddit_tricks").song_agent
REPAIR_AGENT_SYSTEM_PROMPT_V2 = get_variant("v2_reddit_tricks").repair_agent
STYLE_AGENT_SYSTEM_PROMPT = get_variant("v3_two_step").style_agent
LYRICS_AGENT_SYSTEM_PROMPT = get_variant("v4_lyric_profile").lyrics_agent
LYRICS_AGENT_SYSTEM_PROMPT_V3 = get_variant("v3_two_step").lyrics_agent
LYRICS_AGENT_SYSTEM_PROMPT_V4 = get_variant("v4_lyric_profile").lyrics_agent

# Simple lyrics prompt for /lyrics-only endpoint (expects suno_prompt + lyrics_about only)
LYRICS_SIMPLE_PROMPT = f"""\
{POLICY}
{OUTPUT_CONTRACT_LYRICS}
{TASK_LYRICS_SIMPLE}
{LYRICS_SPEC}
{SONG_TITLE_SPEC}
"""

# LYRICS_SYSTEM_PROMPT: used by /lyrics-only endpoint which passes suno_prompt + lyrics_about
LYRICS_SYSTEM_PROMPT = LYRICS_SIMPLE_PROMPT
