"""
V5 Hybrid Variant

Combines V1's prose SUNO PROMPT accuracy with V4's lyric profile system.

Architecture:
  [PARALLEL]
    ├── Style Branch: generate_style (V1 prose) → validate → [repair]
    └── Lyrics Branch: infer_profile (fast) → generate_lyrics → validate → [repair]
  → finalize (merge)

The key insight: V1's prose format produces more accurate genre/era content.
"""

from app.prompts.registry import register_variant
from app.prompts.specs import (
    # Style side: uses V1's prose specs (full 500-char budget)
    POLICY,
    OUTPUT_CONTRACT_STYLE,
    TASK_STYLE,
    SUNO_PROMPT_SPEC_V5,  # Prose format, full 500-char budget
    EXCLUDE_SPEC,
    PARAMETER_SPEC,
    STYLE_REPAIR_AGENT_PROSE,  # Repair for prose format
    # Lyrics side: same as V4
    OUTPUT_CONTRACT_LYRICS,
    TASK_LYRICS_WITH_PROFILE,
    LYRICS_SPEC,
    SONG_TITLE_SPEC,
    LYRIC_PROFILE_SPEC,
    LYRICS_REPAIR_AGENT,
    PROFILE_INFERENCE_AGENT,
)

# Style Agent: V5's prose spec (full 500-char budget)
STYLE_AGENT = f"""\
{POLICY}
{OUTPUT_CONTRACT_STYLE}
{TASK_STYLE}
{SUNO_PROMPT_SPEC_V5}
{EXCLUDE_SPEC}
{PARAMETER_SPEC}
"""

# Lyrics Agent: same as V4 (receives profile from fast inference step)
LYRICS_AGENT = f"""\
{POLICY}
{OUTPUT_CONTRACT_LYRICS}
{TASK_LYRICS_WITH_PROFILE}
{LYRICS_SPEC}
{SONG_TITLE_SPEC}
{LYRIC_PROFILE_SPEC}
"""

# Register this variant
register_variant(
    id="v5_hybrid",
    description="V5 hybrid: V1 prose style + V4 lyrics",
    architecture="two_step",
    uses_lyric_profile=True,
    style_agent=STYLE_AGENT,
    style_repair_agent=STYLE_REPAIR_AGENT_PROSE,
    lyrics_agent=LYRICS_AGENT,
    lyrics_repair_agent=LYRICS_REPAIR_AGENT,
    profile_inference_agent=PROFILE_INFERENCE_AGENT,
    is_default=False,
)
