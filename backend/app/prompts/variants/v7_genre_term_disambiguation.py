"""
V7 Genre + Term Disambiguation Variant

Extends V6 with vocabulary guidance (terms_to_use, terms_to_avoid) to prevent
the style model from misinterpreting genre labels like "math" as "shreddy".

Architecture:
  [PARALLEL]
    ├── Style Branch: genre_term_disambiguate → generate_style (V5 prose) → validate → [repair]
    └── Lyrics Branch: infer_profile (fast) → generate_lyrics → validate → [repair]
  → finalize (merge)

The key insight: V6 identified genres and not-genres, but terms like "math metal"
could still cause drift. V7 adds explicit vocabulary guidance:
- terms_to_use[]: safe, Suno-friendly descriptors for texture/feel
- terms_to_avoid[]: commonly misinterpreted or hallucinated terms

This guidance is injected into the style agent context to improve SUNO PROMPT accuracy.
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
    # V7: Genre + term disambiguation (enhanced V6)
    GENRE_DISAMBIGUATION_AGENT_V2,
)

# Style Agent: V5's prose spec (same as V5/V6)
STYLE_AGENT = f"""\
{POLICY}
{OUTPUT_CONTRACT_STYLE}
{TASK_STYLE}
{SUNO_PROMPT_SPEC_V5}
{EXCLUDE_SPEC}
{PARAMETER_SPEC}
"""

# Lyrics Agent: same as V5/V6 (receives profile from fast inference step)
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
    id="v7_genre_term_disambiguation",
    description="V7 genre+vocab guardrails: V6 + terms_to_use/terms_to_avoid guidance",
    architecture="two_step",
    uses_lyric_profile=True,
    style_agent=STYLE_AGENT,
    style_repair_agent=STYLE_REPAIR_AGENT_PROSE,
    lyrics_agent=LYRICS_AGENT,
    lyrics_repair_agent=LYRICS_REPAIR_AGENT,
    profile_inference_agent=PROFILE_INFERENCE_AGENT,
    genre_disambiguation_agent=GENRE_DISAMBIGUATION_AGENT_V2,
    is_default=False,
)
