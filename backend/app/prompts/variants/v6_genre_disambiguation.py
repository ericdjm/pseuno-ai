"""
V6 Genre Disambiguation Variant

Extends V5 hybrid with an additional Gemini pre-call before style generation
to infer era-specific genres and commonly-confused-but-incorrect genres for each artist.

Architecture:
  [PARALLEL]
    ├── Style Branch: genre_disambiguate → generate_style (V5 prose) → validate → [repair]
    └── Lyrics Branch: infer_profile (fast) → generate_lyrics → validate → [repair]
  → finalize (merge)

The key insight: By explicitly identifying genres and "not-genres" for each artist
(especially with era-specific context), we reduce subgenre drift in the SUNO prompt.
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
    # V6: Genre disambiguation
    GENRE_DISAMBIGUATION_AGENT,
)

# Style Agent: V5's prose spec (same as V5)
STYLE_AGENT = f"""\
{POLICY}
{OUTPUT_CONTRACT_STYLE}
{TASK_STYLE}
{SUNO_PROMPT_SPEC_V5}
{EXCLUDE_SPEC}
{PARAMETER_SPEC}
"""

# Lyrics Agent: same as V5/V4 (receives profile from fast inference step)
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
    id="v6_genre_disambiguation",
    description="V6 genre disambiguation: V5 + pre-style genre enrichment",
    architecture="two_step",
    uses_lyric_profile=True,
    style_agent=STYLE_AGENT,
    style_repair_agent=STYLE_REPAIR_AGENT_PROSE,
    lyrics_agent=LYRICS_AGENT,
    lyrics_repair_agent=LYRICS_REPAIR_AGENT,
    profile_inference_agent=PROFILE_INFERENCE_AGENT,
    genre_disambiguation_agent=GENRE_DISAMBIGUATION_AGENT,
    is_default=True,
)

