"""
V9 Comprehensive EXCLUDE Variant

Extends V8 channel split with enhanced EXCLUDE generation:
- Leverages genre disambiguation data (GENRE_AVOID, VOCAB_TO_AVOID, INSTRUMENTS_TO_AVOID)
- Adds era-appropriate production anti-patterns
- Generates comprehensive drift blockers (8-12 items, up to 300 chars)

Architecture:
  [PARALLEL]
    ├── Style Branch: genre_disambiguate_v3 → split_decision → format_v8_context → generate_style → validate → [repair]
    └── Lyrics Branch: infer_profile (fast) → generate_lyrics → validate → [repair]
  → finalize (merge)

Key changes from V8:
- Uses EXCLUDE_SPEC_V9 (300 char limit, data-driven from genre disambiguation)
- Instructs model to synthesize EXCLUDE from GENRE_AVOID, VOCAB_TO_AVOID, etc.
- Adds production anti-pattern guidance (e.g., 70s rock → no "brick-wall compression")
"""

from app.prompts.registry import register_variant
from app.prompts.specs import (
    # Style side: uses V5's prose specs (full 500-char budget)
    POLICY,
    OUTPUT_CONTRACT_STYLE,
    TASK_STYLE,
    SUNO_PROMPT_SPEC_V5,  # Prose format, full 500-char budget
    EXCLUDE_SPEC_V9,  # V9: Comprehensive exclude spec (300 chars, data-driven)
    PARAMETER_SPEC,
    STYLE_REPAIR_AGENT_PROSE,  # Repair for prose format
    # Lyrics side: same as V5/V4
    OUTPUT_CONTRACT_LYRICS,
    TASK_LYRICS_WITH_PROFILE,
    LYRICS_SPEC,
    SONG_TITLE_SPEC,
    LYRIC_PROFILE_SPEC,
    LYRICS_REPAIR_AGENT,
    PROFILE_INFERENCE_AGENT,
    # V8/V9: Genre disambiguation with role fields (V3)
    GENRE_DISAMBIGUATION_AGENT_V3,
)

# Style Agent: V5's prose spec with V9's comprehensive EXCLUDE spec
STYLE_AGENT = f"""\
{POLICY}
{OUTPUT_CONTRACT_STYLE}
{TASK_STYLE}
{SUNO_PROMPT_SPEC_V5}
{EXCLUDE_SPEC_V9}
{PARAMETER_SPEC}
"""

# Lyrics Agent: same as V5/V6/V7/V8 (receives profile from fast inference step)
LYRICS_AGENT = f"""\
{POLICY}
{OUTPUT_CONTRACT_LYRICS}
{TASK_LYRICS_WITH_PROFILE}
{LYRICS_SPEC}
{SONG_TITLE_SPEC}
{LYRIC_PROFILE_SPEC}
"""

# Register this variant as the new default
register_variant(
    id="v9_comprehensive_exclude",
    description="V9 comprehensive exclude: data-driven EXCLUDE (300 chars) + V8 channel split",
    architecture="two_step",
    uses_lyric_profile=True,
    style_agent=STYLE_AGENT,
    style_repair_agent=STYLE_REPAIR_AGENT_PROSE,
    lyrics_agent=LYRICS_AGENT,
    lyrics_repair_agent=LYRICS_REPAIR_AGENT,
    profile_inference_agent=PROFILE_INFERENCE_AGENT,
    genre_disambiguation_agent=GENRE_DISAMBIGUATION_AGENT_V3,
    is_default=True,
)

