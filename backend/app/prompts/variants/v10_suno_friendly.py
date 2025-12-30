"""
V10 Suno-Friendly Variant

A/B test variant against V9. Uses musical descriptors that Suno is more likely
to understand, rather than technical audio engineering terms.

Key differences from V9:

SUNO_PROMPT (main prompt):
- Guides model to use musical/stylistic terms over engineering jargon
- "warm analog feel" instead of "tube saturation at 2dB"
- "shimmering guitars", "punchy drums" instead of technical processing terms

EXCLUDE (drift blockers):
- "brick-wall compression" → "overcompressed", "no dynamics"
- "quantized drums" → "robotic drums", "mechanical timing"
- "digital clipping" → "harsh digital", "distorted mix"
- "studio overdubs" → "overproduced", "too polished"

Architecture: Same as V8/V9
  [PARALLEL]
    ├── Style Branch: genre_disambiguate_v3 → split_decision → format_v8_context → generate_style → validate → [repair]
    └── Lyrics Branch: infer_profile (fast) → generate_lyrics → validate → [repair]
  → finalize (merge)

This variant is for A/B testing. Compare outputs with V9 in Suno to determine
which terminology produces better results.
"""

from app.prompts.registry import register_variant
from app.prompts.specs import (
    # Style side: V10's Suno-friendly specs
    POLICY,
    OUTPUT_CONTRACT_STYLE,
    TASK_STYLE,
    SUNO_PROMPT_SPEC_V10,  # V10: Suno-friendly prompt spec (musical descriptors)
    EXCLUDE_SPEC_V10,  # V10: Suno-friendly exclude spec (musical descriptors)
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
    # V8/V9/V10: Genre disambiguation with role fields (V3)
    GENRE_DISAMBIGUATION_AGENT_V3,
)

# Style Agent: V10's Suno-friendly prompt + exclude specs
STYLE_AGENT = f"""\
{POLICY}
{OUTPUT_CONTRACT_STYLE}
{TASK_STYLE}
{SUNO_PROMPT_SPEC_V10}
{EXCLUDE_SPEC_V10}
{PARAMETER_SPEC}
"""

# Lyrics Agent: same as V5/V6/V7/V8/V9 (receives profile from fast inference step)
LYRICS_AGENT = f"""\
{POLICY}
{OUTPUT_CONTRACT_LYRICS}
{TASK_LYRICS_WITH_PROFILE}
{LYRICS_SPEC}
{SONG_TITLE_SPEC}
{LYRIC_PROFILE_SPEC}
"""

# Register this variant (opt-in for A/B testing, V9 remains default)
register_variant(
    id="v10_suno_friendly",
    description="V10 Suno-friendly: musical descriptors in EXCLUDE (A/B test vs V9)",
    architecture="two_step",
    uses_lyric_profile=True,
    style_agent=STYLE_AGENT,
    style_repair_agent=STYLE_REPAIR_AGENT_PROSE,
    lyrics_agent=LYRICS_AGENT,
    lyrics_repair_agent=LYRICS_REPAIR_AGENT,
    profile_inference_agent=PROFILE_INFERENCE_AGENT,
    genre_disambiguation_agent=GENRE_DISAMBIGUATION_AGENT_V3,
    is_default=True,  # V10 is the default (Suno-friendly language)
)
