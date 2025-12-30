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

# Maximum characters for the exclude field (V9+: increased from 100 to 500)
SUNO_EXCLUDE_MAX_CHARS = 500

# ===========================================================================
# Lyrics Generation Limits
# ===========================================================================

# No character limit on lyrics - Suno accepts any length
LYRICS_MAX_VERSES = 3
LYRICS_MAX_CHORUSES = 4
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

# ===========================================================================
# V8 Channel Split Constants
# ===========================================================================

# Minimum confidence threshold for role assignment from genre disambiguation
V8_ROLE_CONFIDENCE_THRESHOLD = 0.7

# Whether to enable regex fallback for split detection (can be disabled for testing)
V8_REGEX_ENABLED = True

# Set of variant IDs that use V8 channel split logic
V8_SPLIT_ENABLED_VARIANTS = {
    "v8_channel_split",
    "v9_comprehensive_exclude",
    "v10_suno_friendly",
}
