"""
V4 Lyric Profile Variant

Two-step parallel architecture where:
- Style Branch: generate_style → validate → [repair]
- Lyrics Branch: infer_profile (fast model) → generate_lyrics → validate → [repair]

The profile inference runs on a fast model (gpt-4.1-mini) to minimize latency,
then lyrics generation uses that profile.

Architecture:
  [PARALLEL]
    ├── Style Branch: generate_style → validate → [repair]
    └── Lyrics Branch: infer_profile (fast) → generate_lyrics → validate → [repair]
  → finalize (merge)
"""

from app.prompts.registry import register_variant
from app.prompts.specs import (
    POLICY,
    OUTPUT_CONTRACT_STYLE,
    OUTPUT_CONTRACT_LYRICS,
    TASK_STYLE,
    TASK_LYRICS_WITH_PROFILE,
    LYRICS_SPEC,
    SONG_TITLE_SPEC,
    SUNO_PROMPT_SPEC_V2,
    EXCLUDE_SPEC,
    PARAMETER_SPEC,
    LYRIC_PROFILE_SPEC,
    STYLE_REPAIR_AGENT,
    LYRICS_REPAIR_AGENT,
    PROFILE_INFERENCE_AGENT,
)

# Style Agent (same as V3 - no profile generation here)
STYLE_AGENT = f"""\
{POLICY}
{OUTPUT_CONTRACT_STYLE}
{TASK_STYLE}
{SUNO_PROMPT_SPEC_V2}
{EXCLUDE_SPEC}
{PARAMETER_SPEC}
"""

# Lyrics Agent (receives profile from fast inference step)
# Includes all the specs that V1/V2 have PLUS the lyric profile
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
    id="v4_lyric_profile",
    description="V4 parallel: style + (profile inference → lyrics)",
    architecture="two_step",
    uses_lyric_profile=True,
    style_agent=STYLE_AGENT,
    style_repair_agent=STYLE_REPAIR_AGENT,
    lyrics_agent=LYRICS_AGENT,
    lyrics_repair_agent=LYRICS_REPAIR_AGENT,
    profile_inference_agent=PROFILE_INFERENCE_AGENT,
)
