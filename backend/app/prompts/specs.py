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
    SUNO_PROMPT_MAX_CHARS_V5_PROSE,
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
- LYRIC PROFILE: JSON object with density, pacing, directness, persona fields.
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
- 4 lines per section (standard). Adjust based on density control.
- Reuse chorus lyrics across repetitions (same words).
- [Intro], [Breakdown], [Outro] have no lyrics (tag only).
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
- Output as JSON: {"density": "...", "pacing": "...", "directness": "...", "persona": "..."}
- density: "sparse" | "standard" | "dense" — based on genre (ballads=sparse, rap=dense)
- pacing: "slow" | "mid" | "fast" — based on tempo feel (AABB rhymes for slow, sparse rhymes for fast)
- directness: "direct" | "balanced" | "metaphor_heavy" — kids/holiday=direct, art rock=metaphor_heavy
- persona: "earnest" | "playful" | "aggressive" | "romantic" | "melancholic" — match the mood
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
- lyric_profile: Density, pacing, directness, persona, humor, explicitness.

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

# V5 Hybrid: prose with reduced limit (MAX headers prepended after generation)
SUNO_PROMPT_SPEC_V5 = f"""\
═══════════════════════════════════════════════════════════════════════════════
SUNO PROMPT SPEC
═══════════════════════════════════════════════════════════════════════════════
Formula: [Era/Location Origin] + [Genre + Subgenre] + [3 Evocative Adjectives] + [Vocal Style] + [Production Character]
CRITICAL: Total must be ≤{SUNO_PROMPT_MAX_CHARS_V5_PROSE} characters (headers added automatically).

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
DENSITY:
- sparse: 2 lines per section. Atmospheric, breathing room.
- standard: 4 lines per section. Normal for most genres.
- dense: 6-8 lines per section. Wordy, storytelling, rapid-fire.

PACING (affects rhyme scheme):
- slow: Rhyme every line (AABB). More syllables (10-14). Ballad feel.
- mid: Standard ABAB or ABCB rhyme. Balanced syllables (8-12).
- fast: Sparse rhymes, fewer syllables (6-10). Punchy, clipped.

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
- LYRIC PROFILE must be valid JSON with density, pacing, directness, persona fields.
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
- 4 lines per section (standard).
"""

STYLE_REPAIR_AGENT_PROSE = f"""\
You are a repair agent. Fix the previous output to match the required format.
Return ONLY the corrected output — no explanations.

{OUTPUT_CONTRACT_STYLE}

SUNO PROMPT must be flowing prose (NOT structured fields):
- ≤{SUNO_PROMPT_MAX_CHARS_V5_PROSE} characters total (headers added automatically).
- Format: [Era/Location] + [Genre] + [Adjectives] + [Vocals] + [Production]
- NO "genre:", "instruments:", etc. fields — just descriptive prose.

Example of correct SUNO PROMPT:
Early 2000s Los Angeles progressive metal, complex polyrhythmic textures, visceral and opulent, dynamic male vocals ranging from breathy whispers to soaring operatic screams, thick bass-driven production, intricate tribal drumming

Common fixes:
- Remove structured field labels (genre:, instruments:, etc.)
- Remove MAX headers — those will be added automatically.
- EXCLUDE must be one line, comma-separated, ≥2 items.
- WEIRDNESS must be a single integer 0-100.
- STYLE INFLUENCE must be a single integer 0-100.
"""

# ===========================================================================
# PROFILE INFERENCE PROMPT (fast model for V4)
# ===========================================================================

PROFILE_INFERENCE_AGENT = """\
You infer the best lyric profile for a song based on style, topic, and reference artists.
Return ONLY a JSON object — no explanations.

CRITICAL: Consider the reference artists' known characteristics:
- Comedy/parody artists (Steel Panther, Weird Al, Tenacious D) → humor: "heavy", often explicit
- Explicit artists (Eminem, NWA, Steel Panther) → explicitness: "explicit"
- Dark/intense artists (TOOL, Nine Inch Nails, Slipknot) → persona: "aggressive"
- Party/fun artists (LMFAO, Pitbull) → humor: "light", persona: "playful"

Output format (ALL 7 fields required):
{"density": "...", "pacing": "...", "directness": "...", "persona": "...", "humor": "...", "explicitness": "...", "audience": "..."}

DENSITY:
- "sparse": 2-3 lines/section. Ballads, ambient.
- "standard": 4 lines/section. Most genres.
- "dense": 6-8 lines/section. Rap, metal, storytelling.

PACING:
- "slow": AABB rhymes, 10-14 syllables. Ballads.
- "mid": ABAB rhymes, 8-12 syllables. Standard.
- "fast": Sparse rhymes, 6-10 syllables. Punk, thrash.

DIRECTNESS:
- "direct": Clear, literal. Party, comedy.
- "balanced": Mix of literal and figurative.
- "metaphor_heavy": Abstract, poetic. Art rock, prog.

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

Example: artists=["Steel Panther", "TOOL"], topic="cocaine trip"
Output: {"density": "dense", "pacing": "fast", "directness": "direct", "persona": "aggressive", "humor": "crude", "explicitness": "explicit", "audience": "adult"}
"""
