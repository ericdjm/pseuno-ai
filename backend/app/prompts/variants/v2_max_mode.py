"""
V2 MAX Mode Variant

V1 base with Reddit-style MAX mode headers and structured metadata format.
Single-step architecture.
"""

from app.prompts.registry import register_variant
from app.prompts.specs import (
    POLICY,
    OUTPUT_CONTRACT,
    TASK,
    LYRICS_SPEC,
    SONG_TITLE_SPEC,
    SUNO_PROMPT_SPEC_V2,
    EXCLUDE_SPEC,
    PARAMETER_SPEC,
)

# Compose the song agent prompt with V2 suno spec
SONG_AGENT = f"""\
{POLICY}
{OUTPUT_CONTRACT}
{TASK}
{LYRICS_SPEC}
{SONG_TITLE_SPEC}
{SUNO_PROMPT_SPEC_V2}
{EXCLUDE_SPEC}
{PARAMETER_SPEC}
"""

# Compose the repair agent prompt with V2 suno spec
REPAIR_AGENT = f"""\
You are "Suno Formatter (Repair) V2."
Your job is to repair the previous output so it strictly follows the required format.
Return ONLY the repaired final output — no explanations.

{OUTPUT_CONTRACT}
{LYRICS_SPEC}
{SONG_TITLE_SPEC}
{SUNO_PROMPT_SPEC_V2}
{EXCLUDE_SPEC}
{PARAMETER_SPEC}
"""

# Register this variant
register_variant(
    id="v2_reddit_tricks",
    description="V2 with MAX mode headers, realism tags, metadata format",
    architecture="single_step",
    song_agent=SONG_AGENT,
    repair_agent=REPAIR_AGENT,
)

