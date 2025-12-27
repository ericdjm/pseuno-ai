"""
V1 Baseline Variant

The original modular prompt. Single-step architecture.
"""

from app.prompts.registry import register_variant
from app.prompts.specs import (
    POLICY,
    OUTPUT_CONTRACT,
    TASK,
    LYRICS_SPEC,
    SONG_TITLE_SPEC,
    SUNO_PROMPT_SPEC,
    EXCLUDE_SPEC,
    PARAMETER_SPEC,
)

# Compose the song agent prompt
SONG_AGENT = f"""\
{POLICY}
{OUTPUT_CONTRACT}
{TASK}
{LYRICS_SPEC}
{SONG_TITLE_SPEC}
{SUNO_PROMPT_SPEC}
{EXCLUDE_SPEC}
{PARAMETER_SPEC}
"""

# Compose the repair agent prompt
REPAIR_AGENT = f"""\
You are "Suno Formatter (Repair)."
Your job is to repair the previous output so it strictly follows the required format.
Return ONLY the repaired final output — no explanations.

{OUTPUT_CONTRACT}
{LYRICS_SPEC}
{SONG_TITLE_SPEC}
{SUNO_PROMPT_SPEC}
{EXCLUDE_SPEC}
{PARAMETER_SPEC}
"""

# Register this variant
register_variant(
    id="v1",
    description="Original modular prompt (baseline)",
    architecture="single_step",
    song_agent=SONG_AGENT,
    repair_agent=REPAIR_AGENT,
)
