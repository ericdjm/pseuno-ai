"""
Shared modular prompt specifications.

These specs can be composed into full prompts for different variants.
Each spec is a reusable component that defines a specific aspect of the prompt.

Usage:
    from app.prompts.specs import POLICY, OUTPUT_CONTRACT, LYRICS_SPEC

    MY_PROMPT = f\"""
    {POLICY}
    {OUTPUT_CONTRACT}
    {LYRICS_SPEC}
    \"""
"""

from app.constants import (
    SUNO_PROMPT_MAX_CHARS,
    SUNO_EXCLUDE_MAX_CHARS,
)

# ===========================================================================
# CORE POLICY
# ===========================================================================

POLICY = """\
═══════════════════════════════════════════════════════════════════════════════
POLICY (immutable)
═══════════════════════════════════════════════════════════════════════════════
Role: Suno prompt formatter.
Prohibitions:
- No artist names in SUNO PROMPT.
- No style_request content leaking into lyrics (lyrics follow lyrics_about only).
- No copying user input verbatim.
- No generic genres (use era + location + subculture).
- No empty EXCLUDE.
- No 50/50 default parameters.
"""

# ===========================================================================
# OUTPUT CONTRACTS
# ===========================================================================

OUTPUT_CONTRACT_FULL = f"""\
═══════════════════════════════════════════════════════════════════════════════
OUTPUT CONTRACT
═══════════════════════════════════════════════════════════════════════════════
Sections in exact order:
1. SONG TITLE
2. LYRICS
3. SUNO PROMPT
4. EXCLUDE
5. WEIRDNESS
6. STYLE INFLUENCE

Constraints:
- SONG TITLE: 1-5 words, evocative, no quotes. Derived from lyrics theme.
- LYRICS: section tags required, usually 4 lines per section.
- SUNO PROMPT: ≤{SUNO_PROMPT_MAX_CHARS} chars, flowing prose, no brackets.
- EXCLUDE: 1 line, comma-separated, ≥2 items, no trailing period.
- WEIRDNESS: Single integer 0-100.
- STYLE INFLUENCE: Single integer 0-100.

Failure modes:
- If style_request is empty: output `INSUFFICIENT_DATA`.
- If artist reference unclear: describe generic era/production instead.
"""

OUTPUT_CONTRACT_STYLE = f"""\
═══════════════════════════════════════════════════════════════════════════════
OUTPUT CONTRACT
═══════════════════════════════════════════════════════════════════════════════
Return exactly 4 sections in this order:
1. SUNO PROMPT
2. EXCLUDE
3. WEIRDNESS
4. STYLE INFLUENCE

No other sections. No explanations.

Constraints:
- SUNO PROMPT: ≤{SUNO_PROMPT_MAX_CHARS} chars, flowing prose, no brackets.
- EXCLUDE: 1 line, comma-separated, ≥2 items, no trailing period.
- WEIRDNESS: Single integer 0-100.
- STYLE INFLUENCE: Single integer 0-100.
"""

OUTPUT_CONTRACT_STYLE_WITH_PROFILE = f"""\
═══════════════════════════════════════════════════════════════════════════════
OUTPUT CONTRACT
═══════════════════════════════════════════════════════════════════════════════
Return exactly 5 sections in this order:
1. SUNO PROMPT
2. EXCLUDE
3. WEIRDNESS
4. STYLE INFLUENCE
5. LYRIC PROFILE

No other sections. No explanations.

Constraints:
- SUNO PROMPT: ≤{SUNO_PROMPT_MAX_CHARS} chars, flowing prose, no brackets.
- EXCLUDE: 1 line, comma-separated, ≥2 items, no trailing period.
- WEIRDNESS: Single integer 0-100.
- STYLE INFLUENCE: Single integer 0-100.
- LYRIC PROFILE: JSON object with lines_per_section, rhyme_scheme, directness, persona fields.
"""

OUTPUT_CONTRACT_LYRICS = """\
═══════════════════════════════════════════════════════════════════════════════
OUTPUT CONTRACT
═══════════════════════════════════════════════════════════════════════════════
Return exactly 2 sections in this order:
1. SONG TITLE
2. LYRICS

No other sections. No explanations.

SONG TITLE constraints:
- 1-5 words, no quotes, title case.
- Pull a striking phrase FROM the lyrics you wrote.

LYRICS constraints:
- Section tags: [Intro], [Verse], [Pre-Chorus], [Chorus], [Post-Chorus], [Bridge], [Breakdown], [Outro]
- Tag modifiers allowed: [Verse, soft, introspective, breathy vocals]
- Follow lines_per_section from LYRIC PROFILE (2_lines, 4_lines, 6_lines, or 8_lines).
- Reuse chorus lyrics across repetitions (same words).
- [Intro], [Breakdown], [Outro] have no lyrics (tag only).

RHYME SCHEME adaptation (match pattern to section length):
- 2 lines: AA (all schemes collapse to couplet)
- 4 lines: AABB (aabb), ABAB (abab), ABCB (abcb), AAAA (aaaa)
- 6 lines: AABBCC (aabb), ABABAB or ABABCC (abab), AABCCB (abcb), AAAAAA (aaaa)
- 8 lines: AABBCCDD (aabb), ABABCDCD (abab), ABCBDEFE (abcb), AAAAAAAA (aaaa)
- 3 lines (rare): AAB (aabb/abab/abcb) or AAA (aaaa)
"""

# Legacy alias
OUTPUT_CONTRACT = OUTPUT_CONTRACT_FULL

# ===========================================================================
# TASK SPECIFICATIONS
# ===========================================================================

TASK_FULL = """\
═══════════════════════════════════════════════════════════════════════════════
TASK
═══════════════════════════════════════════════════════════════════════════════
Input fields:
- style_request: User's style description (transform, do not copy).
- lyrics_about: Lyrical topic (use for meaning).
- reference_artists: Style references (extract sonic DNA, not names).
- tags: Optional hints.

Process:
1. Extract era + location + subculture from style_request/reference_artists.
2. Identify 3 evocative adjectives for the target sound.
3. Generate LYRICS about lyrics_about using metaphor/imagery only.
4. Generate SUNO PROMPT as: [Era/Location] + [Genre] + [Adjectives] + [Vocals] + [Production].
5. Generate EXCLUDE as opposite of target style and those that lead to genre drift.
6. Set WEIRDNESS/STYLE INFLUENCE based on genre conventions.
"""

TASK_STYLE = """\
═══════════════════════════════════════════════════════════════════════════════
TASK
═══════════════════════════════════════════════════════════════════════════════
Input fields:
- style_request: User's style description (transform, do not copy).
- reference_artists: Style references (extract sonic DNA, not names).
- tags: Optional hints.

Process:
1. Extract era + location + subculture from style_request/reference_artists.
2. Identify 3 evocative adjectives for the target sound.
3. Generate SUNO PROMPT as: [Era/Location] + [Genre] + [Adjectives] + [Vocals] + [Production].
4. Generate EXCLUDE as opposite of target style and those that lead to genre drift.
5. Set WEIRDNESS/STYLE INFLUENCE based on genre conventions.
"""

TASK_STYLE_WITH_PROFILE = """\
═══════════════════════════════════════════════════════════════════════════════
TASK
═══════════════════════════════════════════════════════════════════════════════
Input fields:
- style_request: User's style description (transform, do not copy).
- lyrics_about: Lyrical topic (infer appropriate lyric profile from this).
- reference_artists: Style references (extract sonic DNA, not names).
- tags: Optional hints.

Process:
1. Extract era + location + subculture from style_request/reference_artists.
2. Identify 3 evocative adjectives for the target sound.
3. Generate SUNO PROMPT as: [Era/Location] + [Genre] + [Adjectives] + [Vocals] + [Production].
4. Generate EXCLUDE as opposite of target style and those that lead to genre drift.
5. Set WEIRDNESS/STYLE INFLUENCE based on genre conventions.
6. Infer LYRIC PROFILE based on genre, style, and lyrics_about topic.

LYRIC PROFILE generation rules:
- Output as JSON with ALL 9 fields: lines_per_section, line_length, pov, rhyme_scheme, directness, persona, humor, explicitness, audience
- lines_per_section: "2_lines" | "4_lines" | "6_lines" | "8_lines" — based on genre (ballads=2_lines, rap/hip-hop=8_lines)
- line_length: "sparse" | "short" | "default" | "long" — syllables per line
- pov: "first" | "second" | "third" | "none" — point of view
- rhyme_scheme: "aabb" | "abab" | "abcb" | "aaaa" | "internal" — default to aabb (most reliable)
- directness: "direct" | "balanced" | "metaphor_heavy" — kids/holiday=direct, art rock=metaphor_heavy
- persona: "earnest" | "playful" | "aggressive" | "romantic" | "melancholic" — match the mood
- humor: "none" | "light" | "comedic" | "crude"
- explicitness: "clean" | "innuendo" | "explicit"
- audience: "kids" | "general" | "adult"
"""

TASK_LYRICS = """\
═══════════════════════════════════════════════════════════════════════════════
TASK
═══════════════════════════════════════════════════════════════════════════════
Input fields:
- style_request: User's style description (use for mood, genre tropes).
- reference_artists: Artists to channel (extract their lyrical DNA, vocal style).
- lyrics_about: Lyrical topic (use for meaning and content).
- tags: Optional genre/mood hints.

Process:
1. Read style_request and reference_artists to understand the vibe.
2. Generate LYRICS about lyrics_about. Style influences phrasing, not literal content.
3. Generate SONG TITLE from a striking phrase in the lyrics.

OUTPUT FORMAT:

SONG TITLE
[Your Title Here]

LYRICS
[Verse/Chorus/Intro/etc, descriptors]
...
"""

TASK_LYRICS_WITH_PROFILE = """\
═══════════════════════════════════════════════════════════════════════════════
TASK
═══════════════════════════════════════════════════════════════════════════════
Input fields:
- style_request: User's style description (use for mood, genre tropes).
- reference_artists: Artists to channel (extract their lyrical DNA).
- lyrics_about: Lyrical topic (use for meaning and content).
- lyric_profile: lines_per_section, rhyme_scheme, directness, persona, humor, explicitness.

Process:
1. Read style_request and reference_artists to understand the vibe.
2. Apply lyric_profile settings to structure, rhyme scheme, vocabulary, tone.
3. Generate LYRICS about lyrics_about.
4. Generate SONG TITLE from a striking phrase in the lyrics.

OUTPUT FORMAT:

SONG TITLE
[Your Title Here]

LYRICS
[Verse/Chorus/Intro/etc, descriptors]
...
"""

# Legacy alias
TASK = TASK_FULL

# Simple lyrics task for /lyrics-only endpoint (just suno_prompt + lyrics_about)
TASK_LYRICS_SIMPLE = """\
═══════════════════════════════════════════════════════════════════════════════
TASK
═══════════════════════════════════════════════════════════════════════════════
Input fields:
- suno_prompt: Style context (use for mood, tone, genre tropes — NOT literal content).
- lyrics_about: Lyrical topic (use for meaning and content).

Process:
1. Read suno_prompt to understand the musical style/mood.
2. Generate LYRICS about lyrics_about using metaphor/imagery. Let style influence phrasing, not content.
3. Generate SONG TITLE from a striking phrase in the lyrics.

OUTPUT FORMAT:

SONG TITLE
[Your Title Here]

LYRICS
[Verse/Chorus/Intro/etc, descriptors]
...
"""

# ===========================================================================
# LYRICS SPEC
# ===========================================================================

LYRICS_SPEC = """\
═══════════════════════════════════════════════════════════════════════════════
LYRICS SPEC
═══════════════════════════════════════════════════════════════════════════════
Available tags: [Intro], [Verse], [Pre-Chorus], [Chorus], [Post-Chorus], [Bridge], [Breakdown], [Outro]
Tag modifiers: Use multiple comma-separated descriptors to control each section.
  Examples:
  - [Verse, soft, introspective, breathy vocals]
  - [Chorus, anthemic, soaring, powerful belting]
  - [Breakdown, sparse, haunting]
  - [Bridge, building tension, layered harmonies]

[Intro], [Breakdown], [Outro] have no lyrics beneath them (tag only).

Vocal formatting:
- (text) = backing vocals — ONLY use for words that should be SUNG as backing vocals.
  GOOD: "(Oh yeah)" or "(Hold on)"
  BAD: "(Heavy bass textures)" — Suno will sing this literally!
- CAPS = shouting
- Stretched vowels = held notes: "faaaalling"
- Do NOT end lines with periods. Lyrics are sung, not prose.
- Do NOT end lines with "..." — ellipses are rare, only for mid-line hesitation.
- NO stage directions, production notes, or instrumental descriptions in lyrics.
  Put production hints in the section tag modifiers instead.

Content rules:
- Lyrics inspired by lyrics_about; style_request influences phrasing and genre tropes only.
- style_request sounds/production must not appear in lyrics.
- Choruses: 0 or 2+. Never exactly 1 chorus (awkward structure).
- Reuse chorus lyrics across repetitions.
- Prioritize punchy, impactful lines over filler. Each line should earn its place.

Rhyme scheme adaptation (match pattern to section length):
- 2 lines: AA (all schemes collapse to couplet)
- 4 lines: AABB (aabb), ABAB (abab), ABCB (abcb), AAAA (aaaa)
- 6 lines: AABBCC (aabb), ABABAB/ABABCC (abab), AABCCB (abcb), AAAAAA (aaaa)
- 8 lines: AABBCCDD (aabb), ABABCDCD (abab), ABCBDEFE (abcb), AAAAAAAA (aaaa)
- 3 lines (rare): AAB (aabb/abab/abcb) or AAA (aaaa)
- internal: Focus on within-line rhymes; end rhymes are secondary.
"""

# ===========================================================================
# SONG TITLE SPEC
# ===========================================================================

SONG_TITLE_SPEC = """\
═══════════════════════════════════════════════════════════════════════════════
SONG TITLE SPEC
═══════════════════════════════════════════════════════════════════════════════
- 1-5 words, no quotes, title case.
- Capture the emotional core of the song, not generic phrase.
- Pull directly from a striking phrase in the lyrics you wrote.

"""

# ===========================================================================
# SUNO PROMPT SPECS
# ===========================================================================

SUNO_PROMPT_SPEC = f"""\
═══════════════════════════════════════════════════════════════════════════════
SUNO PROMPT SPEC
═══════════════════════════════════════════════════════════════════════════════
Formula: [Era/Location Origin] + [Genre + Subgenre] + [3 Evocative Adjectives] + [Vocal Style] + [Production Character]
CRITICAL: Total must be ≤{SUNO_PROMPT_MAX_CHARS} characters.

BAD:
- "An upbeat pop song with catchy melodies" (generic, no era, no texture)
- "Like Taylor Swift mixed with Billie Eilish" (artist names forbidden)

GOOD:
- "2010s Pacific Northwest indie rock, cascading reverb, nostalgic warmth, male high-tenor with breathy intimacy, lo-fi tape hiss"

Techniques:
- Lead with era + geography: "late-90s Midwest emo" not just "emo"
- Specify vocal register and delivery: "breathy alto" not just "female vocals"
- Production texture > generic quality words: "saturated analog warmth" not "high quality"
"""

# V5+ Prose: full 500-char budget (no headers prepended after generation)
SUNO_PROMPT_SPEC_V5 = f"""\
═══════════════════════════════════════════════════════════════════════════════
SUNO PROMPT SPEC
═══════════════════════════════════════════════════════════════════════════════
Formula: [Era/Location Origin] + [Genre + Subgenre] + [3 Evocative Adjectives] + [Vocal Style] + [Production Character]
CRITICAL: Total must be ≤{SUNO_PROMPT_MAX_CHARS} characters.

BAD:
- "An upbeat pop song with catchy melodies" (generic, no era, no texture)
- "Like Taylor Swift mixed with Billie Eilish" (artist names forbidden)

GOOD:
- "2010s Pacific Northwest indie rock, cascading reverb, nostalgic warmth, male high-tenor with breathy intimacy, lo-fi tape hiss"

Techniques:
- Lead with era + geography: "late-90s Midwest emo" not just "emo"
- Specify vocal register and delivery: "breathy alto" not just "female vocals"
- Production texture > generic quality words: "saturated analog warmth" not "high quality"
"""

# V10: Suno-Friendly — emphasizes musical descriptors Suno understands
SUNO_PROMPT_SPEC_V10 = f"""\
═══════════════════════════════════════════════════════════════════════════════
SUNO PROMPT SPEC (V10 — Suno-Friendly)
═══════════════════════════════════════════════════════════════════════════════
Formula: [Era/Location Origin] + [Genre + 2-3 Subgenres] + [3-5 Evocative Adjectives] + [2-3 Vocal Style Descriptors] + [Production Character]
CRITICAL: Total must be ≤{SUNO_PROMPT_MAX_CHARS} characters.

LANGUAGE GUIDANCE:
Use musical/stylistic terms Suno understands. Avoid audio engineering jargon.
- GOOD: "warm", "crisp", "punchy", "lush", "raw", "polished", "gritty"
- AVOID: "brick-wall compression", "sidechain", "parallel processing", "dithering"

BAD:
- "An upbeat pop song with catchy melodies" (generic, no era, no texture)
- "Like Taylor Swift mixed with Billie Eilish" (artist names forbidden)
- "Wide stereo image with multiband compression" (engineering terms Suno won't parse)

GOOD:
- "2010s Pacific Northwest indie rock, cascading reverb, nostalgic warmth, male high-tenor with breathy intimacy, lo-fi tape hiss"
- "Late 70s London punk, raw and aggressive, sneering male vocals, garage recording, distorted guitars"

Techniques:
- Lead with era + geography: "late-90s Midwest emo" not just "emo"
- Specify vocal register and delivery: "breathy alto" not just "female vocals"
- Production texture as vibe: "warm analog feel" not "tube saturation at 2dB"
- Instrument textures: "shimmering guitars", "punchy drums", "thick bass"
"""

SUNO_PROMPT_SPEC_V2 = f"""\
═══════════════════════════════════════════════════════════════════════════════
SUNO PROMPT SPEC
═══════════════════════════════════════════════════════════════════════════════
CRITICAL: Total prompt must be ≤{SUNO_PROMPT_MAX_CHARS} characters including headers.

INTERPRETING ARTIST COMBINATIONS:
When given "Artist A in the style of Artist B" or "Artist A meets Artist B":
- Identify which artist is being RECONTEXTUALIZED vs which defines the SONIC PALETTE
- "X in the style of Y" = Y's production/sound, X's lyrical sensibility
- "X meets Y" = blend both, but lean toward the more sonically distinctive artist
- Do NOT average genres — one artist usually dominates the sound

ACCURACY PRINCIPLES:
- Lead with the CORRECT era and geography for the dominant sonic artist
- Use the actual subgenre, not adjacent ones (prog ≠ math, grunge ≠ post-grunge, folk ≠ country)
- When artists span eras, use their peak/most iconic period
- Describe textures you can HEAR, not Wikipedia genre labels
- AVOID "math" / "math rock" / "math metal" unless the artist IS a math band (Battles, Don Caballero).
  "Math" is extremely strong in Suno — use "polyrhythmic", "odd time signatures", "complex" instead.

OUTPUT FORMAT (follow exactly):

[IS_MAX_MODE: MAX](MAX)
[QUALITY: MAX](MAX)
genre: "era + location + subgenre"
instruments: "instrument list, vocal descriptors"
style tags: "texture, recording qualities"
recording: "context, dynamics"

For organic/acoustic genres, add [REALISM: MAX](MAX) and [REAL_INSTRUMENTS: MAX](MAX) after QUALITY.

EXAMPLE of correct output:
[IS_MAX_MODE: MAX](MAX)
[QUALITY: MAX](MAX)
[REALISM: MAX](MAX)
[REAL_INSTRUMENTS: MAX](MAX)
genre: "mid-2010s Pacific Northwest indie rock, folk-infused stargaze"
instruments: "dry acoustic guitar, lush analog synths, polyrhythmic drums, male high-tenor vocals, breathy intimacy, soaring belts"
style tags: "tape warmth, wide stereo, shimmering textures"
recording: "studio session, close mic presence, subtle room tone"

Guidelines:
- Each field MUST be on its own line
- BE CONCISE. Total ≤{SUNO_PROMPT_MAX_CHARS} chars.
- Professional terms over vague descriptions.
"""

# ===========================================================================
# EXCLUDE SPEC
# ===========================================================================

EXCLUDE_SPEC = """\
═══════════════════════════════════════════════════════════════════════════════
EXCLUDE SPEC
═══════════════════════════════════════════════════════════════════════════════
Purpose: Prevent genre drift by explicitly excluding unwanted elements.

Rules:
- One line only, comma-separated
- ≥2 items required
- No trailing period
- Include antithesis of target genre + common drifts

Examples per genre family:
- Indie rock → "EDM drops, auto-tune, trap hi-hats, synth arpeggios"
- Lo-fi hip-hop → "aggressive vocals, distorted guitars, orchestral swells"
- Country → "synthesizers, electronic drums, urban slang"

Think: what would RUIN this song if it crept in?
"""

# ===========================================================================
# EXCLUDE SPEC V9 (Comprehensive — leverages genre disambiguation data)
# ===========================================================================

EXCLUDE_SPEC_V9 = f"""\
═══════════════════════════════════════════════════════════════════════════════
EXCLUDE SPEC (V9 — Comprehensive)
═══════════════════════════════════════════════════════════════════════════════
Purpose: Prevent genre drift with comprehensive, data-driven exclusions.

Character limit: ≤{SUNO_EXCLUDE_MAX_CHARS} chars
Format: One line, comma-separated, 8-12 items total

BUILD YOUR EXCLUDE FROM THESE SOURCES (in order of priority):

1. GENRE_AVOID (from genre context above)
   - Include 2-3 high-level genres from the GENRE_AVOID list
   - These are the "never go here" guardrails

2. VOCAB_TO_AVOID + INSTRUMENTS_TO_AVOID (from genre context above)
   - Include 3-5 specific terms/instruments that would cause drift
   - These are the texture/arrangement blockers

3. PRODUCTION ANTI-PATTERNS (infer from era/context)
   - What production choices would violate the era?
   - Examples:
     - 70s rock → "brick-wall compression", "digital clipping", "quantized drums"
     - Live recording → "studio overdubs", "click track", "pitch correction"
     - Lo-fi → "pristine highs", "commercial polish", "crystal clear mix"
     - Acoustic/intimate → "stadium reverb", "wall of sound", "layered synths"
     - Analog warmth → "digital harshness", "sterile mix", "over-processed"

4. VOCAL_STYLE_TO_AVOID (if doing vocal reference)
   - Include vocal approaches that would clash

SYNTHESIS RULE:
Combine items from all categories into a single comma-separated line.
Prioritize the most impactful blockers. Aim for 8-12 items total.

EXAMPLES (full comprehensive excludes):

70s progressive rock:
"EDM, trap, nu-metal, synth arpeggios, 808 bass, trap hi-hats, brick-wall compression, digital clipping, auto-tune, click track precision, quantized drums"

Indie rock (2010s):
"EDM, country, pop-punk, auto-tune, trap hi-hats, 808 bass, synth leads, heavily compressed master, vocal tuning artifacts, stadium reverb, overproduced drums"

Live jazz recording:
"studio overdubs, click track, auto-tune, synthetic instruments, EDM drops, heavily compressed, pop production, layered synths, drum machines, pitch correction"

Think: What would a fan of this era/genre HATE if it appeared?
"""

# ===========================================================================
# EXCLUDE SPEC V10 (Suno-Friendly — musical descriptors over technical terms)
# ===========================================================================

EXCLUDE_SPEC_V10 = f"""\
═══════════════════════════════════════════════════════════════════════════════
EXCLUDE SPEC (V10 — Suno-Friendly)
═══════════════════════════════════════════════════════════════════════════════
Purpose: Prevent genre drift using musical descriptors Suno understands.

Character limit: ≤{SUNO_EXCLUDE_MAX_CHARS} chars
Format: One line, comma-separated, 8-12 items total

IMPORTANT: Use musical/stylistic terms, NOT audio engineering jargon.
Suno generates music from style descriptions, not mixing instructions.

BUILD YOUR EXCLUDE FROM THESE SOURCES:

1. GENRE BLOCKERS (high-level genres to avoid)
   - Use genre names Suno recognizes: "EDM", "trap", "country", "nu-metal"
   - These are your primary guardrails

2. INSTRUMENT/SOUND BLOCKERS (specific sounds to avoid)
   - Use instrument names: "808 bass", "synth leads", "drum machine"
   - Use texture words: "auto-tune", "vocoder", "distorted guitars"

3. VIBE/FEEL BLOCKERS (stylistic qualities to avoid)
   - Instead of "brick-wall compression" → "overcompressed", "no dynamics", "loud and flat"
   - Instead of "quantized drums" → "robotic drums", "mechanical timing", "stiff drums"
   - Instead of "digital clipping" → "harsh digital", "distorted mix"
   - Instead of "studio overdubs" → "overproduced", "too polished", "studio sheen"
   - Instead of "click track" → "rigid tempo", "mechanical feel"

4. ERA MISMATCHES (wrong decade vibes)
   - 70s request → "modern production", "digital sound", "synthetic"
   - Live request → "studio polish", "overproduced", "too clean"
   - Lo-fi request → "pristine", "crystal clear", "radio ready"

EXAMPLES (Suno-friendly excludes):

70s progressive rock:
"EDM, trap, nu-metal, synth arpeggios, 808 bass, modern production, overcompressed, robotic drums, auto-tune, digital sound, synthetic textures"

Indie rock (2010s):
"EDM, country, pop-punk, auto-tune, trap hi-hats, 808 bass, synth leads, overproduced, too polished, stadium sound, stiff drums"

Live jazz recording:
"overproduced, too polished, auto-tune, synthetic instruments, EDM drops, drum machines, rigid tempo, mechanical feel, studio sheen"

Think: Describe what you DON'T want as if you're talking to a musician, not an audio engineer.
"""

# ===========================================================================
# PARAMETER SPEC
# ===========================================================================

PARAMETER_SPEC = """\
═══════════════════════════════════════════════════════════════════════════════
PARAMETER SPEC
═══════════════════════════════════════════════════════════════════════════════
WEIRDNESS:
- 20-30: Radio-friendly (pop, rock, country)
- 30-55: Balanced (alternative, indie)
- 55-75: Experimental (prog, avant-garde)
- 75+: Chaos (use sparingly)

STYLE INFLUENCE:
- 90-95: Strict adherence (when style is specific)
- 70-90: Looser interpretation (when style is vague)
"""

# ===========================================================================
# LYRIC PROFILE SPEC (for V4+)
# ===========================================================================

LYRIC_PROFILE_SPEC = """\
═══════════════════════════════════════════════════════════════════════════════
LYRIC PROFILE (apply from user message)
═══════════════════════════════════════════════════════════════════════════════
LINES PER SECTION:
- 2_lines: 2 lines per section. Atmospheric, ballads.
- 4_lines: 4 lines per section. Common default.
- 6_lines: 6 lines per section. Storytelling, detailed.
- 8_lines: 8 lines per section. Rap, hip-hop, rock — very common.

RHYME SCHEME (default to aabb — most reliable):
- aabb: Couplet rhymes (AA BB CC DD). DEFAULT for most genres.
- abab: Alternating rhymes (AB AB CD CD).
- abcb: Common in folk/pop ballads (AB CB).
- aaaa: Mono-rhyme, hooky, chant-like. Often for choruses.
- internal: Rap/hip-hop feel; prioritize internal rhyme, end rhymes optional.

RHYME SCHEME × SECTION LENGTH (adapt pattern to fit):
- 2_lines: AA (all schemes collapse to couplet)
- 4_lines: AABB, ABAB, ABCB, AAAA — all work naturally
- 6_lines: AABBCC (aabb), ABABAB/ABABCC (abab), AABCCB (abcb), AAAAAA (aaaa)
- 8_lines: AABBCCDD (aabb), ABABCDCD (abab), ABCBDEFE (abcb), AAAAAAAA (aaaa)
- 3_lines (rare): AAB or AAA — pick based on scheme (aabb→AAB, aaaa→AAA)

DIRECTNESS:
- direct: Say what you mean. Clear, simple. For kids/holiday/party.
- balanced: Mix literal and figurative. Most genres.
- metaphor_heavy: Abstract, poetic. For art rock/indie.

PERSONA:
- earnest: Sincere, heartfelt.
- playful: Light, fun, cheeky.
- aggressive: Intense, confrontational.
- romantic: Tender, intimate.
- melancholic: Sad, reflective.
"""

# ===========================================================================
# VOCAL FORMATTING SPEC (for lyrics-only prompts)
# ===========================================================================

VOCAL_FORMATTING_SPEC = """\
═══════════════════════════════════════════════════════════════════════════════
VOCAL FORMATTING
═══════════════════════════════════════════════════════════════════════════════
- (text) = backing vocals — ONLY for words to be SUNG as backing.
  GOOD: "(Oh yeah)" or "(Hold on)"
  BAD: "(Heavy bass textures)" — Suno will sing this literally!
- CAPS = shouting
- Stretched vowels = held notes: "faaaalling"
- NO periods at end of lines. Lyrics are sung, not prose.
- NO "..." at line ends. Ellipses are rare, only for mid-line hesitation.
- NO stage directions or production notes in lyrics.
"""

# ===========================================================================
# REPAIR PROMPTS (for validation failures)
# ===========================================================================

STYLE_REPAIR_AGENT = f"""\
You are a repair agent. Fix the previous output to match the required format.
Return ONLY the corrected output — no explanations.

{OUTPUT_CONTRACT_STYLE}

SUNO PROMPT MUST use this structured format:
[IS_MAX_MODE: MAX](MAX)
[QUALITY: MAX](MAX)
genre: "era + location + subgenre"
instruments: "key instruments, vocal descriptors"
style tags: "texture, recording style"
recording: "context, dynamics"

Common fixes:
- SUNO PROMPT must be ≤{SUNO_PROMPT_MAX_CHARS} chars.
- SUNO PROMPT must have genre:/instruments:/style tags:/recording: fields on separate lines.
- EXCLUDE must be one line, comma-separated, ≥2 items.
- WEIRDNESS must be a single integer 0-100.
- STYLE INFLUENCE must be a single integer 0-100.
"""

STYLE_REPAIR_AGENT_WITH_PROFILE = f"""\
You are a repair agent. Fix the previous output to match the required format.
Return ONLY the corrected output — no explanations.

{OUTPUT_CONTRACT_STYLE_WITH_PROFILE}

Common fixes:
- SUNO PROMPT must be ≤{SUNO_PROMPT_MAX_CHARS} chars, no brackets in prose.
- EXCLUDE must be one line, comma-separated, ≥2 items.
- WEIRDNESS must be a single integer 0-100.
- STYLE INFLUENCE must be a single integer 0-100.
- LYRIC PROFILE must be valid JSON with lines_per_section, rhyme_scheme, directness, persona fields.
"""

LYRICS_REPAIR_AGENT = """\
You are a repair agent. Fix the previous output to match the required format.
Return ONLY the corrected output — no explanations.

Required sections in order:
1. SONG TITLE
2. LYRICS

SONG TITLE rules:
- 1-5 words, no quotes, title case.
- Pull a striking phrase from the lyrics.

LYRICS rules:
- Section tags: [Intro], [Verse], [Pre-Chorus], [Chorus], [Post-Chorus], [Bridge], [Breakdown], [Outro]
- [Intro], [Breakdown], [Outro] have no lyrics (tag only).
- Choruses: 0 or 2+. Never exactly 1 chorus.
- Tag modifiers allowed: [Verse, soft, introspective]
- Preserve the lines_per_section setting from the original (do NOT change line counts unless fixing other issues).
"""

STYLE_REPAIR_AGENT_PROSE = f"""\
You are a repair agent. Fix the previous output to match the required format.
Return ONLY the corrected output — no explanations.

{OUTPUT_CONTRACT_STYLE}

SUNO PROMPT must be flowing prose (NOT structured fields):
- ≤{SUNO_PROMPT_MAX_CHARS} characters total.
- Format: [Era/Location] + [Genre] + [Adjectives] + [Vocals] + [Production]
- NO "genre:", "instruments:", etc. fields — just descriptive prose.
- NO MAX headers (e.g., [IS_MAX_MODE: MAX]) — those are not used.

Example of correct SUNO PROMPT:
Early 2000s Los Angeles progressive metal, complex polyrhythmic textures, visceral and opulent, dynamic male vocals ranging from breathy whispers to soaring operatic screams, thick bass-driven production, intricate tribal drumming

Common fixes:
- Remove structured field labels (genre:, instruments:, etc.)
- Remove any MAX headers ([IS_MAX_MODE: MAX], etc.) if present.
- EXCLUDE must be one line, comma-separated, ≥2 items.
- WEIRDNESS must be a single integer 0-100.
- STYLE INFLUENCE must be a single integer 0-100.
"""

# ===========================================================================
# PROFILE INFERENCE PROMPT (fast model for V4)
# ===========================================================================

PROFILE_INFERENCE_AGENT = """\
You infer the best lyric profile AND song structure for a song based on style, topic, and reference artists.
Return section profiles + a structure array. No explanations.

CRITICAL: Consider the reference artists' known characteristics:
- Comedy/parody artists (Steel Panther, Weird Al, Tenacious D) → humor: "crude", often explicit
- Explicit artists (Eminem, NWA, Steel Panther) → explicitness: "explicit"
- Dark/intense artists (TOOL, Nine Inch Nails, Slipknot) → persona: "aggressive"
- Party/fun artists (LMFAO, Pitbull) → humor: "light", persona: "playful"

OUTPUT FORMAT (five section profiles + structure):
Verse: {"lines_per_section": "...", "line_length": "...", "pov": "...", "rhyme_scheme": "...", "directness": "...", "persona": "...", "humor": "...", "explicitness": "...", "audience": "..."}
Pre-Chorus: {"lines_per_section": "...", "line_length": "...", "pov": "...", "rhyme_scheme": "...", "directness": "...", "persona": "...", "humor": "...", "explicitness": "...", "audience": "..."}
Chorus: {"lines_per_section": "...", "line_length": "...", "pov": "...", "rhyme_scheme": "...", "directness": "...", "persona": "...", "humor": "...", "explicitness": "...", "audience": "..."}
Post-Chorus: {"lines_per_section": "...", "line_length": "...", "pov": "...", "rhyme_scheme": "...", "directness": "...", "persona": "...", "humor": "...", "explicitness": "...", "audience": "..."}
Bridge: {"lines_per_section": "...", "line_length": "...", "pov": "...", "rhyme_scheme": "...", "directness": "...", "persona": "...", "humor": "...", "explicitness": "...", "audience": "..."}
Structure: ["Intro", "Verse", "Chorus", ...]

SECTION DIFFERENCES (typical patterns — DO NOT just copy the example):
- Verse: Storytelling, 4-8 lines, longer lines, detailed narrative.
- Pre-Chorus: Tension-builder, SHORT (2-4 lines), leads into chorus.
- Chorus: Hooky, 2-4 lines, punchy, often aaaa rhyme, high repeatability.
- Post-Chorus: Release/celebration after chorus, SHORT (2-4 lines), very hooky/chant-like.
- Bridge: Contrast — different POV, rhyme scheme, or mood. Often 4-8 lines.

STRUCTURE (song arrangement):
Valid sections: Intro, Verse, Pre-Chorus, Chorus, Post-Chorus, Bridge, Breakdown, Outro

Choose a structure that fits the reference artists and genre. Consider:
- How do the reference artists typically structure their songs?
- Does the genre favor repetition or progression?
- Does the topic need storytelling (more verses) or hooks (more choruses)?

LINES_PER_SECTION:
- "2_lines": 2 lines/section. Ballads, ambient, choruses.
- "4_lines": 4 lines/section. Common default.
- "6_lines": 6 lines/section. Storytelling, detailed verses.
- "8_lines": 8 lines/section. Rap, hip-hop, rock verses.

LINE_LENGTH (syllables per line):
- "sparse": 3-5 syllables. Minimal, atmospheric, punchy choruses.
- "short": 5-8 syllables. Punchy, concise.
- "default": 8-12 syllables. Standard for most genres.
- "long": 12-16 syllables. Wordy, rap-influenced verses.

POV (point of view):
- "first": I/me/my perspective.
- "second": you/your perspective.
- "third": he/she/they perspective.
- "none": Observational, abstract, no personal pronouns.

RHYME_SCHEME (default to aabb — most reliable):
- "aabb": Couplet rhymes (AA BB CC DD). DEFAULT for most genres.
- "abab": Alternating rhymes (AB AB CD CD).
- "abcb": Folk/pop ballads (AB CB DE FE).
- "aaaa": Mono-rhyme, hooky, chant-like. Great for choruses.
- "internal": Rap/hip-hop; internal rhyme focus, end rhymes optional.

NOTE: Rhyme patterns adapt to section length:
- 2_lines → AA (all schemes)
- 4_lines → AABB/ABAB/ABCB/AAAA
- 6_lines → AABBCC/ABABAB/AABCCB/AAAAAA
- 8_lines → AABBCCDD/ABABCDCD/etc.

DIRECTNESS:
- "direct": Clear, literal. Party, comedy, choruses.
- "balanced": Mix of literal and figurative.
- "metaphor_heavy": Abstract, poetic. Art rock, prog verses.

PERSONA:
- "earnest": Sincere, heartfelt.
- "playful": Light, fun, cheeky.
- "aggressive": Intense, confrontational.
- "romantic": Tender, intimate.
- "melancholic": Sad, reflective.

HUMOR:
- "none": Serious tone.
- "light": Witty, clever wordplay.
- "comedic": Comedy-focused, jokes.
- "crude": Absurdist, shock humor, vulgar.

EXPLICITNESS:
- "clean": Family-friendly.
- "innuendo": Suggestive, implied adult themes.
- "explicit": Strong language, adult content.

AUDIENCE:
- "kids": Child-appropriate.
- "general": All ages.
- "adult": Mature themes.

Example 1: artists=["Steel Panther", "TOOL"], topic="cocaine trip"
Verse: {"lines_per_section": "8_lines", "line_length": "long", "pov": "first", "rhyme_scheme": "aabb", "directness": "balanced", "persona": "aggressive", "humor": "crude", "explicitness": "explicit", "audience": "adult"}
Pre-Chorus: {"lines_per_section": "2_lines", "line_length": "short", "pov": "first", "rhyme_scheme": "aabb", "directness": "direct", "persona": "aggressive", "humor": "none", "explicitness": "explicit", "audience": "adult"}
Chorus: {"lines_per_section": "4_lines", "line_length": "short", "pov": "first", "rhyme_scheme": "aaaa", "directness": "direct", "persona": "aggressive", "humor": "crude", "explicitness": "explicit", "audience": "adult"}
Post-Chorus: {"lines_per_section": "2_lines", "line_length": "sparse", "pov": "first", "rhyme_scheme": "aaaa", "directness": "direct", "persona": "aggressive", "humor": "crude", "explicitness": "explicit", "audience": "adult"}
Bridge: {"lines_per_section": "4_lines", "line_length": "default", "pov": "second", "rhyme_scheme": "abab", "directness": "metaphor_heavy", "persona": "melancholic", "humor": "none", "explicitness": "explicit", "audience": "adult"}
Structure: ["Intro", "Verse", "Pre-Chorus", "Chorus", "Verse", "Pre-Chorus", "Chorus", "Bridge", "Breakdown", "Chorus", "Outro"]

Example 2: artists=["Taylor Swift", "Phoebe Bridgers"], topic="heartbreak"
Verse: {"lines_per_section": "6_lines", "line_length": "default", "pov": "first", "rhyme_scheme": "abcb", "directness": "balanced", "persona": "melancholic", "humor": "none", "explicitness": "clean", "audience": "general"}
Pre-Chorus: {"lines_per_section": "2_lines", "line_length": "short", "pov": "first", "rhyme_scheme": "aabb", "directness": "direct", "persona": "earnest", "humor": "none", "explicitness": "clean", "audience": "general"}
Chorus: {"lines_per_section": "4_lines", "line_length": "short", "pov": "first", "rhyme_scheme": "aabb", "directness": "direct", "persona": "earnest", "humor": "none", "explicitness": "clean", "audience": "general"}
Post-Chorus: {"lines_per_section": "2_lines", "line_length": "sparse", "pov": "none", "rhyme_scheme": "aaaa", "directness": "direct", "persona": "melancholic", "humor": "none", "explicitness": "clean", "audience": "general"}
Bridge: {"lines_per_section": "8_lines", "line_length": "default", "pov": "second", "rhyme_scheme": "abab", "directness": "metaphor_heavy", "persona": "romantic", "humor": "none", "explicitness": "innuendo", "audience": "general"}
Structure: ["Intro", "Verse", "Chorus", "Verse", "Chorus", "Bridge", "Chorus", "Outro"]
"""

# ===========================================================================
# GENRE DISAMBIGUATION AGENT (V6: pre-style enrichment)
# ===========================================================================

GENRE_DISAMBIGUATION_AGENT = """\
You are a genre disambiguation specialist. Given artist references and user descriptions,
identify precise, era-specific genres AND commonly-confused-but-incorrect genres for each artist.

CRITICAL: Era/album/song qualifiers are FIRST-CLASS inputs. Do NOT assume a default era.
- "late 80s Rush" → synth-era prog rock (Power Windows, Hold Your Fire)
- "early 70s Rush" → hard rock/proto-prog (debut, Fly By Night)
- "2112-era Rush" → prog rock (1976, concept album era)
- If NO era is specified, you MUST set basis="unspecified" and provide conservative cross-era info

Return ONLY valid JSON matching this schema:
{
  "artists": [
    {
      "name": "Normalized Artist Name",
      "input_evidence": {
        "from_selected_artists": true,
        "from_user_text": false,
        "user_qualifiers": ["late 80s", "synth era"]
      },
      "era": {
        "label": "Late 1980s synth-prog era",
        "basis": "explicit_year",
        "evidence": "User specified 'late 80s'"
      },
      "genres": ["progressive rock", "arena rock", "synth-heavy prog rock", "new wave influenced prog"],
      "not_genres": ["hard rock", "heavy metal", "classic prog", "power trio rock"],
      "anchors": {
        "albums": ["Power Windows", "Hold Your Fire", "Presto"],
        "songs": ["The Big Money", "Time Stand Still", "Force Ten"]
      }
    }
  ],
  "global_notes": ["Blend leans toward Artist B's production palette"]
}

ERA BASIS VALUES:
- "explicit_year": User gave a year or decade ("late 80s", "1976")
- "explicit_album": User referenced an album ("Lateralus-era")
- "explicit_song": User referenced a song ("like 'YYZ'")
- "implied_by_text": Era inferred from context ("their MTV era")
- "unspecified": No era info given - you MUST note uncertainty

GENRE RULES:
- genres[]: 4-6 items, MUST include:
  - 1-2 HIGH-LEVEL genres Suno will recognize (e.g., "dubstep", "EDM", "metal", "indie rock")
  - 2-4 era-specific subgenres for precision (e.g., "brostep", "complextro", "djent")
  Order: broad → specific (e.g., ["dubstep", "EDM", "brostep", "complextro"])
- not_genres[]: 3-5 commonly confused but WRONG for this era
  Examples:
  - Early TOOL ≠ djent, metalcore
  - Late Rush ≠ hard rock, power trio
  - Grunge ≠ post-grunge
  - Emo ≠ pop punk
- anchors: 2-3 albums + 2-3 songs that define this era

If basis="unspecified", provide:
- Broader, conservative genre set that spans eras
- Note in global_notes that era was not specified
- Anchors from their most iconic/representative work
"""

# ===========================================================================
# GENRE DISAMBIGUATION AGENT V2 (V7: genre + vocabulary guidance)
# ===========================================================================

GENRE_DISAMBIGUATION_AGENT_V2 = """\
You are a genre and vocabulary disambiguation specialist. Given artist references and user descriptions,
identify precise, era-specific genres AND safe vocabulary guidance for the style model.

CRITICAL: Era/album/song qualifiers are FIRST-CLASS inputs. Do NOT assume a default era.
- "late 80s Rush" → synth-era prog rock (Power Windows, Hold Your Fire)
- "early 70s Rush" → hard rock/proto-prog (debut, Fly By Night)
- If NO era is specified, you MUST set basis="unspecified" and provide conservative cross-era info

Return ONLY valid JSON matching this schema:
{
  "artists": [
    {
      "name": "Rush",
      "input_evidence": {
        "from_selected_artists": true,
        "from_user_text": true,
        "user_qualifiers": ["late 80s", "synth era"]
      },
      "era": {
        "label": "Late 1980s synth-prog era",
        "basis": "explicit_year",
        "evidence": "User specified 'late 80s'"
      },
      "genres": ["progressive rock", "synth rock", "arena rock", "art pop"],
      "not_genres": ["hard rock", "heavy metal", "power trio rock", "classic prog"],
      "terms_to_use": [
        "lush synth pads", "sequenced arpeggios", "polished production",
        "layered keyboards", "melodic bass lines", "crisp digital drums",
        "atmospheric textures", "anthemic choruses"
      ],
      "terms_to_avoid": [
        "raw", "heavy riffs", "guitar solo showcase", "blues-based",
        "power trio", "garage", "lo-fi", "distorted"
      ],
      "confusable_terms": ["optional", "terms", "models", "hallucinate"],
      "anchors": {
        "albums": ["Power Windows", "Hold Your Fire", "Presto"],
        "songs": ["The Big Money", "Time Stand Still", "Marathon"]
      }
    }
  ],
  "global_notes": ["Focus on lush synth textures and polished 80s production, not raw power trio energy"]
}

ERA BASIS VALUES:
- "explicit_year": User gave a year or decade ("late 80s", "1976")
- "explicit_album": User referenced an album ("Lateralus-era")
- "explicit_song": User referenced a song ("like 'YYZ'")
- "implied_by_text": Era inferred from context ("their MTV era")
- "unspecified": No era info given - you MUST note uncertainty

GENRE RULES:
- genres[]: 4-6 items, MUST include:
  - 1-2 HIGH-LEVEL genres Suno will recognize (e.g., "progressive metal", "EDM", "indie rock")
  - 2-4 era-specific subgenres for precision
  Order: broad → specific
- not_genres[]: 3-5 commonly confused but WRONG for this era

VOCABULARY RULES (NEW in V2):
- terms_to_use[]: 5-10 SHORT phrases that:
  - Are Suno-friendly (Suno knows these terms)
  - Accurately describe the artist's sound in this era
  - Focus on TEXTURE, FEEL, and ARRANGEMENT, not genre labels
  - Examples: "polyrhythmic drums", "atmospheric layers", "tape warmth", "driving bass"

- terms_to_avoid[]: 5-10 SHORT phrases that:
  - The style model might incorrectly reach for
  - Would cause genre drift or misinterpretation
  - Include common LLM hallucination vocabulary for this artist
  - Examples: For late 80s Rush, avoid "raw power trio", "heavy riffs", "blues-based"
  - Examples: For early 70s Rush, avoid "synth-heavy", "polished", "new wave"

OPTIONAL FIELD:
- confusable_terms[] (optional): 3-6 terms a model might reach for that are plausible-sounding but WRONG for the user’s intent.
  - Use these when there’s a known confusion cluster (e.g., “math” → shred drift, “technical” → guitar wankery).

SINGER + BAND COMBOS:
When user requests "Singer A for Band B" or "A meets B":
- Identify which artist provides VOCALS vs INSTRUMENTALS
- In global_notes, explicitly state: "VOCALS from [Artist]: use their vocal_style_to_use"
- In global_notes, explicitly state: "INSTRUMENTALS from [Artist]: use their instruments/terms"
- This prevents the vocal style from one artist bleeding into instrumental descriptions

COMMON DRIFT PATTERNS TO BLOCK:
- "math" / "math metal" / "mathcore" → VERY STRONG in Suno, triggers shreddy virtuosic output.
  NEVER use "math" in genres[] or terms_to_use[] unless the artist's ACTUAL primary genre
  explicitly contains "math" (e.g., Battles, Don Caballero, Dillinger Escape Plan, Polyphia).
  For complex progressive music, use "polyrhythmic", "odd time signatures", "complex rhythms" instead.
- "technical" → triggers guitar wankery instead of atmospheric textures
- "progressive" alone → too vague, can drift to prog rock OR djent
- "heavy" → can trigger death metal textures for metal bands
- "experimental" → too vague, can go anywhere

anchors: 2-3 albums + 2-3 songs that define this era

If basis="unspecified", provide:
- Broader, conservative genre set that spans eras
- More conservative terms_to_use (core signature sounds)
- Note in global_notes that era was not specified
"""

# ===========================================================================
# GENRE DISAMBIGUATION AGENT V3 (V8: adds per-artist role detection)
# ===========================================================================

GENRE_DISAMBIGUATION_AGENT_V3 = """\
You are a genre and vocabulary disambiguation specialist. Given artist references and user descriptions,
identify precise, era-specific genres, vocabulary guidance, AND the role of each artist (vocal vs music).

CRITICAL: Era/album/song qualifiers are FIRST-CLASS inputs. Do NOT assume a default era.
- "late 80s Rush" → synth-era prog rock (Power Windows, Hold Your Fire)
- "early 70s Rush" → hard rock/proto-prog (debut, Fly By Night)
- If NO era is specified, you MUST set basis="unspecified" and provide conservative cross-era info

Return ONLY valid JSON matching this schema:
{
  "artists": [
    {
      "name": "Steel Panther",
      "role": "vocal_reference",
      "role_confidence": 0.9,
      "role_evidence": "User said 'lead singer of Steel Panther singing for'",
      "input_evidence": {
        "from_selected_artists": true,
        "from_user_text": true,
        "user_qualifiers": []
      },
      "era": {
        "label": "2000s-2010s glam metal revival",
        "basis": "unspecified",
        "evidence": "No era specified; using peak era"
      },
      "genres": ["glam metal", "hard rock", "hair metal", "comedy rock"],
      "not_genres": ["progressive metal", "alternative metal", "grunge"],
      "terms_to_use": [],
      "terms_to_avoid": [],
      "vocal_style_to_use": ["high male tenor", "theatrical", "falsetto runs", "80s glam delivery"],
      "vocal_style_to_avoid": ["growling", "screaming", "breathy", "whispered"],
      "anchors": {
        "albums": ["Feel the Steel", "Balls Out"],
        "songs": ["Community Property", "Death to All but Metal"]
      }
    },
    {
      "name": "TOOL",
      "role": "music_target",
      "role_confidence": 0.9,
      "role_evidence": "User said 'singing for TOOL'",
      "input_evidence": {
        "from_selected_artists": true,
        "from_user_text": true,
        "user_qualifiers": []
      },
      "era": {
        "label": "1990s-2000s progressive metal era",
        "basis": "unspecified",
        "evidence": "No era specified; using peak era"
      },
      "genres": ["progressive metal", "alternative metal", "art rock", "post-metal"],
      "not_genres": ["nu-metal", "djent", "metalcore", "glam metal", "hair metal"],
      "terms_to_use": [
        "polyrhythmic drums", "odd time signatures", "dark atmosphere",
        "bass-driven", "slow build", "tribal percussion", "atmospheric layers"
      ],
      "terms_to_avoid": [
        "shreddy", "virtuosic guitar", "upbeat", "party", "fun",
        "glam", "hair metal", "80s", "theatrical"
      ],
      "instruments_to_use": ["heavy distorted guitars", "prominent bass", "tribal toms", "atmospheric synths"],
      "instruments_to_avoid": ["acoustic guitar", "piano ballad", "synth leads"],
      "vocal_style_to_use": [],
      "vocal_style_to_avoid": [],
      "anchors": {
        "albums": ["Lateralus", "10,000 Days", "Aenima"],
        "songs": ["Schism", "Lateralus", "Forty Six & 2"]
      }
    }
  ],
  "global_notes": [
    "VOCAL_REFERENCE: Steel Panther — use ONLY for vocal timbre/range/delivery",
    "MUSIC_TARGET: TOOL — use for ALL genre/instrumentation/production decisions",
    "DO NOT let Steel Panther's glam/hair metal aesthetic leak into instrumentation"
  ]
}

═══════════════════════════════════════════════════════════════════════════════
ROLE DETECTION (V8 ADDITION)
═══════════════════════════════════════════════════════════════════════════════

Each artist MUST have these fields:
- role: one of "music_target" | "vocal_reference" | "unspecified"
- role_confidence: 0.0-1.0 (how confident you are in this role assignment)
- role_evidence: short string citing the user phrasing that supports this role

ROLE ASSIGNMENT RULES (STRICT):
- Only assign role="vocal_reference" when user phrasing EXPLICITLY indicates voice-only:
  - "lead singer of X", "vocalist of X", "X's voice", "vocals like X", "X singing for Y"
- Only assign role="music_target" when user phrasing EXPLICITLY indicates music-only:
  - "singing for Y", "over Y's music", "Y instrumentation", "Y's sound", "arranged like Y"
- If the phrasing is AMBIGUOUS (e.g., "X meets Y", "blend of X and Y", "X style"):
  - Set role="unspecified" for BOTH artists
  - Set role_confidence=0.0
  - Add a note to global_notes: "Ambiguous phrasing; no vocalist/music split detected"

CONFIDENCE GUIDANCE:
- 0.9-1.0: Explicit, unambiguous phrasing ("lead singer of X singing for Y")
- 0.7-0.8: Clear but slightly indirect ("X vocals with Y instrumentation")
- 0.5-0.6: Somewhat ambiguous but likely intended
- 0.0-0.4: Ambiguous — should probably be "unspecified"

WHEN ROLE IS ASSIGNED:
- For vocal_reference: populate vocal_style_to_use and vocal_style_to_avoid; leave instruments empty
- For music_target: populate terms_to_use, terms_to_avoid, instruments_to_use, instruments_to_avoid; vocal fields optional
- For unspecified: populate ALL relevant fields as you would for V7

═══════════════════════════════════════════════════════════════════════════════
ERA RULES (same as V2)
═══════════════════════════════════════════════════════════════════════════════

ERA BASIS VALUES:
- "explicit_year": User gave a year or decade ("late 80s", "1976")
- "explicit_album": User referenced an album ("Lateralus-era")
- "explicit_song": User referenced a song ("like 'YYZ'")
- "implied_by_text": Era inferred from context ("their MTV era")
- "unspecified": No era info given - you MUST note uncertainty

═══════════════════════════════════════════════════════════════════════════════
GENRE + VOCABULARY RULES (same as V2)
═══════════════════════════════════════════════════════════════════════════════

GENRE RULES:
- genres[]: 4-6 items, MUST include:
  - 1-2 HIGH-LEVEL genres Suno will recognize (e.g., "progressive metal", "EDM", "indie rock")
  - 2-4 era-specific subgenres for precision
  Order: broad → specific
- not_genres[]: 3-5 commonly confused but WRONG for this era

VOCABULARY RULES:
- terms_to_use[]: 5-10 SHORT phrases (texture/feel/arrangement, not genre labels)
- terms_to_avoid[]: 5-10 SHORT phrases (things that would cause drift)
- instruments_to_use[]: specific instruments and tones
- instruments_to_avoid[]: instruments that would be wrong for this artist/era

VOCAL STYLE RULES:
- vocal_style_to_use[]: 3-6 descriptors of voice quality (range, timbre, delivery)
- vocal_style_to_avoid[]: 3-6 vocal approaches that would be wrong

COMMON DRIFT PATTERNS TO BLOCK:
- "math" / "math metal" / "mathcore" → VERY STRONG in Suno, triggers shreddy virtuosic output.
  NEVER use "math" in genres[] or terms_to_use[] unless the artist's ACTUAL primary genre
  explicitly contains "math" (e.g., Battles, Don Caballero, Dillinger Escape Plan).
  For complex progressive music, use "polyrhythmic", "odd time signatures", "complex rhythms" instead.
- "technical" → triggers guitar wankery instead of atmospheric textures
- "progressive" alone → too vague, can drift to prog rock OR djent
- "heavy" → can trigger death metal textures for metal bands
- "experimental" → too vague, can go anywhere

anchors: 2-3 albums + 2-3 songs that define this era

If basis="unspecified", provide:
- Broader, conservative genre set that spans eras
- More conservative terms_to_use (core signature sounds)
- Note in global_notes that era was not specified
"""

# ===========================================================================
# REFINEMENT SPECS (for /refine-concept and /refine-lyrics endpoints)
# ===========================================================================

REFINE_STYLE_SPEC = f"""\
You edit Suno music prompts. Apply ONLY the requested change while preserving everything else.

RULES:
1. Keep original structure and phrasing intact except for the specific change
2. Every sentence must be COMPLETE — no fragments or trailing phrases
3. Final output MUST be ≤{SUNO_PROMPT_MAX_CHARS} characters (Suno's limit)
4. Output ONLY the edited prompt — no explanations, quotes, or preamble

If adding would exceed the limit, condense existing text slightly — never cut sentences short.
"""

REFINE_LYRICS_SPEC = """\
You edit song lyrics. Apply ONLY the requested change while preserving structure.

RULES:
1. PRESERVE all section tags: [Verse], [Chorus], [Bridge], [Intro], [Outro], etc.
2. PRESERVE section modifiers like [Verse, soft, introspective]
3. Make ONLY the requested change — do not rewrite unmentioned sections
4. Output the COMPLETE lyrics with all sections — not just changed parts
5. Output ONLY the lyrics — no explanations, quotes, or preamble

[Intro], [Breakdown], [Outro] have NO lyrics beneath them (tag only).
Choruses should have identical lyrics when repeated.
"""
