"""
V8 Channel Split Variant

Extends V6/V7 with a "channel split" mechanism to prevent vocalist leakage:
when a user asks for "Singer of X singing for Y", this variant explicitly
splits guidance into VOCAL_REFERENCE (voice-only) vs MUSIC_TARGET (everything else).

Architecture:
  [PARALLEL]
    ├── Style Branch: genre_disambiguate_v3 → split_decision → format_v8_context → generate_style → validate → [repair]
    └── Lyrics Branch: infer_profile (fast) → generate_lyrics → validate → [repair]
  → finalize (merge)

The key insight: When user phrasing indicates a vocalist-for-band combination,
we must prevent the vocalist's band from leaking into instrumentation/genre/production.
V8 enforces explicit channel separation in the style context.

Split decision precedence:
1. Schema-based role detection (from GENRE_DISAMBIGUATION_AGENT_V3)
2. High-confidence regex fallback
3. No split (fall back to V6/V7 behavior)
"""

from app.prompts.registry import register_variant
from app.prompts.specs import (
    # Style side: uses V5's prose specs (full 500-char budget)
    POLICY,
    OUTPUT_CONTRACT_STYLE,
    TASK_STYLE,
    SUNO_PROMPT_SPEC_V5,  # Prose format, full 500-char budget
    EXCLUDE_SPEC,
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
    # V8: Genre disambiguation with role fields (V3)
    GENRE_DISAMBIGUATION_AGENT_V3,
)

# Style Agent: V5's prose spec (same as V5/V6/V7)
STYLE_AGENT = f"""\
{POLICY}
{OUTPUT_CONTRACT_STYLE}
{TASK_STYLE}
{SUNO_PROMPT_SPEC_V5}
{EXCLUDE_SPEC}
{PARAMETER_SPEC}
"""

# Lyrics Agent: same as V5/V6/V7 (receives profile from fast inference step)
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
    id="v8_channel_split",
    description="V8 channel split: prevents vocalist leakage via VOCAL_REFERENCE vs MUSIC_TARGET separation",
    architecture="two_step",
    uses_lyric_profile=True,
    style_agent=STYLE_AGENT,
    style_repair_agent=STYLE_REPAIR_AGENT_PROSE,
    lyrics_agent=LYRICS_AGENT,
    lyrics_repair_agent=LYRICS_REPAIR_AGENT,
    profile_inference_agent=PROFILE_INFERENCE_AGENT,
    genre_disambiguation_agent=GENRE_DISAMBIGUATION_AGENT_V3,
    is_default=False,
    deprecated=True,  # Hidden from UI, superseded by V9+
)
