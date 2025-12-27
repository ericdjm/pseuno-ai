"""
V3 Two-Step Variant

Separates style and lyrics generation into two parallel LLM calls.
NO lyric profile - keeps it simple like V2 but split.

Architecture:
  [PARALLEL]
    ├── Style Branch: generate_style → validate → [repair]
    └── Lyrics Branch: generate_lyrics → validate → [repair]
  → finalize (merge)
"""

from app.prompts.registry import register_variant
from app.prompts.specs import (
    POLICY,
    OUTPUT_CONTRACT_STYLE,
    OUTPUT_CONTRACT_LYRICS,
    TASK_STYLE,
    TASK_LYRICS,
    LYRICS_SPEC,
    SONG_TITLE_SPEC,
    SUNO_PROMPT_SPEC_V2,
    EXCLUDE_SPEC,
    PARAMETER_SPEC,
    STYLE_REPAIR_AGENT,
    LYRICS_REPAIR_AGENT,
)

# Step 1: Style Agent (generates SUNO PROMPT, EXCLUDE, WEIRDNESS, STYLE INFLUENCE)
STYLE_AGENT = f"""\
{POLICY}
{OUTPUT_CONTRACT_STYLE}
{TASK_STYLE}
{SUNO_PROMPT_SPEC_V2}
{EXCLUDE_SPEC}
{PARAMETER_SPEC}
"""

# Step 2: Lyrics Agent (generates SONG TITLE, LYRICS)
# Includes all the specs that V1/V2 have for lyrics
LYRICS_AGENT = f"""\
{POLICY}
{OUTPUT_CONTRACT_LYRICS}
{TASK_LYRICS}
{LYRICS_SPEC}
{SONG_TITLE_SPEC}
"""

# Register this variant
register_variant(
    id="v3_two_step",
    description="V3 two-step: parallel style + lyrics, NO lyric profile",
    architecture="two_step",
    uses_lyric_profile=False,
    style_agent=STYLE_AGENT,
    style_repair_agent=STYLE_REPAIR_AGENT,
    lyrics_agent=LYRICS_AGENT,
    lyrics_repair_agent=LYRICS_REPAIR_AGENT,
)
