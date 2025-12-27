"""
Shared constants for the Pseuno AI application.

This module contains tunable values that are used across multiple modules
(prompts, schemas, frontend caps, etc.) to ensure consistency.
"""

# ===========================================================================
# Suno API Limits
# ===========================================================================

# Maximum characters for a Suno prompt (hard limit from Suno)
SUNO_PROMPT_MAX_CHARS = 500

# V5 hybrid: MAX headers are 92 chars, leaving 408 for prose
SUNO_PROMPT_MAX_CHARS_V5_PROSE = 400  # Rounded down for safety

# Maximum characters for the exclude field
SUNO_EXCLUDE_MAX_CHARS = 100

# ===========================================================================
# Lyrics Generation Limits
# ===========================================================================

# Lyrics character limits
LYRICS_PROMPT_TARGET = 750  # What we tell the model (they overshoot)
LYRICS_HARD_LIMIT = 1000  # Suno's actual limit (triggers repair)
LYRICS_MAX_VERSES = 3
LYRICS_MAX_CHORUSES = 3
LYRICS_LINES_PER_SECTION = "1-8"
LYRICS_TOPIC_MAX_CHARS = 500

# ===========================================================================
# Allowed Section Tags
# ===========================================================================

ALLOWED_SECTION_TAGS = [
    "[Verse]",
    "[Chorus]",
    "[Bridge]",
    "[Breakdown]",
    "[Outro]",
    "[Instrumental]",
    "[Intro]",
    "[Pre-Chorus]",
    "[Post-Chorus]",
]
ALLOWED_SECTION_TAGS_STR = ", ".join(ALLOWED_SECTION_TAGS)

# ===========================================================================
# List Size Limits (for abuse prevention)
# ===========================================================================

MAX_ARTISTS_COUNT = 20
MAX_ARTIST_NAME_CHARS = 60
MAX_TAGS_COUNT = 25
MAX_TAG_CHARS = 40

# ===========================================================================
# Saved Prompt Limits
# ===========================================================================

SAVED_PROMPT_TITLE_MAX_CHARS = 255
SAVED_PROMPT_NOTES_MAX_CHARS = 2000
