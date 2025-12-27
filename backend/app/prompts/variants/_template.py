"""
TEMPLATE: Copy this file to create a new variant

Steps:
1. Copy this file to vX_my_variant.py (replace X with version number)
2. Update the variant ID, description, and prompts
3. Add import to __init__.py: from app.prompts.variants import vX_my_variant
4. Test: the variant will appear in the UI automatically

Architecture options:
- "single_step": One LLM call generates everything (requires song_agent + repair_agent)
- "two_step": Separate calls for style and lyrics (requires style_agent + lyrics_agent)
"""

from app.prompts.registry import register_variant
from app.prompts.specs import (
    # Core components
    POLICY,
    OUTPUT_CONTRACT,           # For single-step (all 6 sections)
    OUTPUT_CONTRACT_STYLE,     # For two-step style agent (4 sections)
    OUTPUT_CONTRACT_LYRICS,    # For two-step lyrics agent (2 sections)
    TASK,                      # For single-step
    TASK_STYLE,               # For two-step style agent
    TASK_LYRICS,              # For two-step lyrics (no profile)
    TASK_LYRICS_WITH_PROFILE, # For two-step lyrics (with profile)
    
    # Content specs
    LYRICS_SPEC,
    SONG_TITLE_SPEC,
    SUNO_PROMPT_SPEC,         # Original style
    SUNO_PROMPT_SPEC_V2,      # MAX mode style
    EXCLUDE_SPEC,
    PARAMETER_SPEC,
    VOCAL_FORMATTING_SPEC,
    LYRIC_PROFILE_SPEC,       # Density, pacing, etc.
)

# ===========================================================================
# SINGLE-STEP EXAMPLE
# ===========================================================================
# Uncomment this section for a single-step variant

# SONG_AGENT = f"""\
# {POLICY}
# {OUTPUT_CONTRACT}
# {TASK}
# {LYRICS_SPEC}
# {SONG_TITLE_SPEC}
# {SUNO_PROMPT_SPEC_V2}  # or SUNO_PROMPT_SPEC for original style
# {EXCLUDE_SPEC}
# {PARAMETER_SPEC}
# """
# 
# REPAIR_AGENT = f"""\
# You are "Suno Formatter (Repair)."
# Return ONLY the repaired output — no explanations.
# 
# {OUTPUT_CONTRACT}
# {LYRICS_SPEC}
# {SONG_TITLE_SPEC}
# {SUNO_PROMPT_SPEC_V2}
# {EXCLUDE_SPEC}
# {PARAMETER_SPEC}
# """
# 
# register_variant(
#     id="vX_my_variant",
#     description="My custom variant description",
#     architecture="single_step",
#     song_agent=SONG_AGENT,
#     repair_agent=REPAIR_AGENT,
#     experimental=True,  # Mark as experimental until tested
# )

# ===========================================================================
# TWO-STEP EXAMPLE (with lyric profile)
# ===========================================================================
# Uncomment this section for a two-step variant

# STYLE_AGENT = f"""\
# {POLICY}
# {OUTPUT_CONTRACT_STYLE}
# {TASK_STYLE}
# {SUNO_PROMPT_SPEC_V2}
# {EXCLUDE_SPEC}
# {PARAMETER_SPEC}
# """
# 
# LYRICS_AGENT = f"""\
# ═══════════════════════════════════════════════════════════════════════════════
# POLICY
# ═══════════════════════════════════════════════════════════════════════════════
# Role: Song lyrics and title writer.
# Prohibitions:
# - No style/production terms in lyrics.
# - No copying user input verbatim.
# - No explanations or prose outside the output.
# 
# {OUTPUT_CONTRACT_LYRICS}
# {VOCAL_FORMATTING_SPEC}
# {LYRIC_PROFILE_SPEC}  # Remove this line for no profile
# {TASK_LYRICS_WITH_PROFILE}  # Use TASK_LYRICS for no profile
# """
# 
# register_variant(
#     id="vX_my_variant",
#     description="My custom two-step variant",
#     architecture="two_step",
#     uses_lyric_profile=True,  # Set to False if not using profile
#     style_agent=STYLE_AGENT,
#     lyrics_agent=LYRICS_AGENT,
#     experimental=True,
# )

