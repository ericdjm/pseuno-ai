# Prompt Routing & Genre-Aware Lyrics: Analysis & Implementation Options

## Executive Summary

Three connected issues have been identified in the current generation pipeline:

1. **No prompt specificity routing** — Whether a user types "cool jazz song" or a 200-word detailed description, it goes through the same creative pipeline that transforms/rewrites the input, diluting highly specific prompts.
2. **No lyrics passthrough mode** — When a user provides complete lyrics, the system generates new lyrics instead of formatting the provided ones with section tags.
3. **No genre-aware lyrics density** — The lyrics profile system can infer `lines_per_section`, but lacks strong genre-to-density mapping. EDM gets full verse/chorus lyrics when it should get sparse, hook-driven content; rock appropriately gets full lyrics.

---

## Current Architecture (How It Works Today)

```
User Input
  ├── user_prompt (style description)
  └── lyrics_about (topic/theme)
         │
         ▼
┌─────────────────────────────────────────────┐
│         AgentPromptGraph.generate()         │
│                                             │
│  1. Build context_pack (user_prompt,        │
│     lyrics_about, artists, tags)            │
│                                             │
│  2. TWO-STEP PARALLEL:                      │
│     ├── Style Branch:                       │
│     │   genre_disambiguate → style LLM      │
│     │   → validate → repair loop            │
│     │                                       │
│     └── Lyrics Branch:                      │
│         profile_infer (fast model)          │
│         → lyrics LLM → validate → repair   │
│                                             │
│  3. Merge results → response               │
└─────────────────────────────────────────────┘
```

### Key Files

| File | Role |
|------|------|
| `services/agent_prompt_graph.py` (3188 lines) | Main generation engine (LangGraph) |
| `prompts/specs.py` (1265 lines) | All prompt templates, specs, contracts |
| `schemas/advanced.py` | Request/response models, lyric controls |
| `services/lyrics_topic_generator.py` | Trait-based lyrics topic bank selection |
| `services/lyrics_topic_banks.py` | Curated topic banks with trait vectors |
| `routes/generate_advanced.py` | `/advanced` and `/lyrics-only` endpoints |

### Current Input Handling

- **`user_prompt`** is always treated as a *style request* to be *transformed* — the system extracts "sonic DNA" from it, never copies verbatim. This is enforced by `POLICY` spec: "No copying user input verbatim."
- **`lyrics_about`** is always treated as a *topic/theme* to inspire LLM-generated lyrics — never used as literal lyrics. The `TASK_LYRICS` spec says: "Generate LYRICS about lyrics_about."
- **Profile inference** runs via a fast model (`gpt-4.1-nano`) to determine per-section profiles (lines_per_section, rhyme_scheme, etc.), but it doesn't have strong genre→density rules.

---

## Issue 1: Prompt Specificity Router (Style Prompt)

### Problem

A user who types *"dark, atmospheric post-rock with tremolo-picked guitars, crescendo structures building from delicate fingerpicked passages to overwhelming walls of distortion, with a GY!BE meets Explosions in the Sky feel, tape hiss, field recordings woven between movements, and a slow, deliberate 6/8 time signature"* gets the same creative transformation pipeline as *"cool jazz song"*.

For the detailed prompt, the current pipeline:
- Rewrites it through the style LLM (loses specificity)
- Runs genre disambiguation (unnecessary — user already disambiguated)
- May "hallucinate" different genre aspects
- Wastes an LLM call transforming already-excellent input

For the vague prompt, the current pipeline correctly:
- Enriches it with era, location, subculture
- Disambiguates genre references
- Adds production/vocal/texture details

### Option A: LLM-Based Router (Classifier Pre-Call)

Add a fast LLM call before generation that classifies prompt specificity.

**Flow:**
```
user_prompt → Fast LLM Classifier → { specificity: "high" | "medium" | "low" }
                                           │
                       ┌───────────────────┼───────────────────┐
                       ▼                   ▼                   ▼
                  HIGH: Passthrough    MEDIUM: Light Edit   LOW: Full Pipeline
                  (format only)        (enrich gaps)        (current behavior)
```

**Pros:**
- Most accurate classification — LLM understands nuance and intent
- Can detect subtleties (e.g., specific but wrong terms, specific but contradictory)
- Handles edge cases well (e.g., "a song that sounds like being underwater at midnight" — poetic but not musically specific)
- Can output a confidence score for gray-area cases

**Cons:**
- Adds latency (~200-400ms even with a fast model like `gpt-4.1-nano`)
- Adds cost per request
- One more LLM call that can fail  
- Potential for the classifier itself to misjudge (a third of requests may be "medium" — hardest to route correctly)
- Complexity: now 3 possible paths to maintain and test

### Option B: Heuristic Scoring (No LLM)

Score prompt specificity using deterministic heuristics.

**Scoring signals:**
- **Length**: >100 chars → +0.3, >200 chars → +0.5
- **Technical vocabulary**: "tremolo", "fingerpicked", "polyrhythmic", "808", "reverb", "BPM" → +0.1 each
- **Era/time references**: "90s", "late 70s", "2010s" → +0.2
- **Production terms**: "lo-fi", "tape hiss", "analog", "lush pads" → +0.1
- **Genre depth**: ≥2 subgenre-level terms → +0.2
- **Artist references already in `selected_artists`**: if >0 and prompt reiterates → prompt is doing the LLM's job
- **Threshold**: score > 0.7 → "high" (passthrough), 0.4-0.7 → "medium", <0.4 → "low"

**Pros:**
- Zero latency added
- Zero cost
- Fully deterministic/testable — easy to write unit tests for edge cases
- No failure modes (pure Python)
- Can be tuned with real user data over time

**Cons:**
- Brittle — can't understand *meaning*, only surface features
- A long but vague prompt ("I want a really really really amazing incredible cool song with lots of really great vibes and incredible energy") scores high on length but is actually low-specificity
- Requires ongoing vocabulary list maintenance
- Misses creative/poetic prompts that are highly specific in *intent* but don't use technical terms
- Hard to get the threshold right without extensive testing

### Option C: Hybrid (Heuristic Fast-Path + LLM Fallback)

Use heuristics first. If score is clearly high (>0.85) or clearly low (<0.25), route directly. For the ambiguous middle zone, call the fast LLM classifier.

**Pros:**
- Best of both: fast for clear cases, accurate for ambiguous ones
- Saves LLM cost on ~60-70% of requests (assuming most are clearly vague or clearly specific)
- Graceful degradation — if LLM fails, fall back to heuristic score

**Cons:**
- Most complex to implement and maintain
- Two systems to tune (heuristic thresholds + LLM prompt)
- Inconsistent behavior: same-feeling prompts might take different paths depending on whether they hit the middle zone

### Recommendation

**Option B (Heuristic Scoring)** for v1, with a migration path to Option C if needed. Reasons:
- Zero latency/cost impact — important given this runs on every request
- The distinction between "very detailed" and "very vague" is usually obvious from surface features
- The "medium" case (which is hardest) can default to the current pipeline safely
- Can ship and iterate quickly with real user data
- Add PostHog tracking of scores to inform whether LLM classifier is needed later

---

## Issue 2: Lyrics Passthrough Mode

### Problem

When a user provides **complete lyrics** in the `lyrics_about` field (e.g., a full poem, song they wrote, or copied lyrics), the system:
1. Treats it as a *topic* and generates completely new lyrics *about* that topic
2. Ignores the actual words the user wrote
3. The user has no way to say "use THESE exact lyrics, just add section tags"

### What "Passthrough" Should Do

Take user-provided complete lyrics and:
1. Preserve the exact words/lines
2. Add appropriate section structure: `[Verse]`, `[Chorus]`, `[Bridge]`, etc.
3. Identify repeated sections (choruses) automatically
4. Add section tag modifiers where appropriate (e.g., `[Verse, soft, building]`)
5. Generate a `SONG TITLE` from the lyrics
6. Optional: light formatting (remove extraneous blank lines, normalize capitalization)

### Option A: LLM-Based Lyrics Classifier + Formatter

Add an LLM call to classify `lyrics_about` as `full_lyrics | topic | hybrid`, then route.

**Classifier prompt:**
```
Classify this text:
- "full_lyrics": Complete song lyrics (multiple stanzas/verses, rhyming patterns, 8+ lines)
- "topic": A short topic/theme description (1-3 sentences describing what the song should be about)
- "hybrid": Partial lyrics mixed with instructions (e.g., "verse about X, chorus: line line line")

Text: "{lyrics_about}"
```

**Formatter prompt (for full_lyrics):**
```
Add section tags to these lyrics. Do NOT change any words.
Identify repeated sections as [Chorus].
Output: SONG TITLE + formatted LYRICS with section tags.
```

**Pros:**
- Most flexible — handles edge cases (partial lyrics, lyrics-with-instructions, etc.)
- LLM excels at detecting structure in free-form text
- Can handle the "hybrid" case where user gives some lyrics and some instructions
- Naturally handles identifying which segments are choruses vs verses vs bridges

**Cons:**
- Adds ~300-500ms for classification call
- Risk of the formatter LLM "improving" or modifying lyrics despite instructions (LLMs love to edit)
- Two LLM calls for the passthrough path (classify + format) vs one for regular path
- If the formatter changes even one word, user trust is broken

### Option B: Heuristic Lyrics Detection + LLM Formatter

Detect full lyrics via heuristics, then use LLM only for section tag placement.

**Detection heuristics:**
- **Line count**: ≥8 non-blank lines → likely lyrics
- **Line length consistency**: lyrics lines are typically 4-15 words; descriptions are longer sentences
- **Rhyme detection**: Basic end-word rhyme matching (last word similarity across line pairs)
- **Existing section tags**: Already has `[Verse]`, `[Chorus]` → definitely lyrics
- **No question marks / imperative verbs**: Lyrics rarely say "make it" or "should be"
- **Absence of meta-language**: No "about", "something like", "vibe of", "style of"

**Pros:**
- Fast detection (no LLM for classification step)
- Clear, testable rules
- Only one LLM call (for formatting) instead of two

**Cons:**
- Can misclassify prose poems (long, line-broken text that isn't lyrics)
- Heuristics need tuning — 8 lines of haiku vs 8 lines of lyrics look very different
- Rhyme detection is unreliable for free-verse or rap lyrics

### Option C: Explicit User Signal (UI Toggle)

Add a UI toggle or mode selector: "I'm providing lyrics" vs "I'm providing a topic."

**Pros:**
- 100% accurate — user declares their intent
- Zero detection errors
- Zero added latency or cost
- Simplest backend implementation
- User feels in control

**Cons:**
- Adds UI complexity (another button/toggle)
- Users may not understand the distinction or forget to toggle
- Breaks the "it just works" magic — forces user to think about system internals
- Most users probably don't provide full lyrics (feature is niche), so the toggle adds clutter for the majority

### Option D: Hybrid (Heuristic Detection + User Override)

Auto-detect with heuristics, show a confirmation banner: "It looks like you typed full lyrics. Want us to keep your exact words and just add section structure? [Yes] [No, generate new lyrics from this topic]"

**Pros:**
- Best UX: auto-detects intent, but lets user correct if wrong
- No wasted LLM calls for detection
- User stays in control for edge cases
- Educates users about the feature naturally

**Cons:**
- Requires frontend work (banner/confirmation UI)
- Adds a step to the flow (user must confirm)
- Heuristics still need to be reasonably good to avoid annoying false positives
- Mobile UX for confirmation banners can be clunky

### Recommendation

**Option D (Heuristic Detection + User Override)** is the best UX, but **Option B (Heuristic Detection + LLM Formatter)** is the fastest to ship. 

For v1: Use Option B with conservative heuristics (high bar for "full lyrics" detection — minimize false positives). The formatter LLM prompt must be very strict about not modifying words. Add PostHog tracking for when passthrough fires to measure accuracy.

For v2: Add the confirmation banner (Option D) once you have data on detection accuracy.

### Formatter Prompt Design (Critical)

The LLM formatter for passthrough mode must be extremely constrained:

```
You are a lyrics structure formatter. You MUST NOT change any words.

Rules:
1. Output every line EXACTLY as given — same words, same spelling, same order
2. Add section tags: [Verse], [Chorus], [Pre-Chorus], [Bridge], [Intro], [Outro]
3. If a group of lines repeats, tag all instances as [Chorus]
4. Add [Intro] before first section if opening lines feel atmospheric/short
5. Add tag modifiers based on tone: [Verse, soft], [Chorus, powerful, anthemic]
6. Generate a SONG TITLE from a striking phrase in the lyrics
7. VERIFICATION: Every line from the input MUST appear in your output

Input lyrics:
{user_lyrics}
```

---

## Issue 3: Genre-Aware Lyrics Density

### Problem

The profile inference system (`PROFILE_INFERENCE_AGENT`) *can* infer `lines_per_section` and structure, but it lacks strong guidance about genre-specific lyrics conventions. Result:

| Genre | Current Behavior | Expected Behavior |
|-------|-----------------|-------------------|
| Rock/Alt Rock | Full lyrics (Verse-Chorus-Verse-Chorus-Bridge-Chorus) ✅ | Same ✅ |
| Hip-Hop/Rap | 8-line verses, internal rhyme ✅ | Same ✅ |
| EDM/House/Techno | Full verse-chorus lyrics ❌ | Sparse hooks, short phrases, mostly instrumental sections |
| Ambient/Drone | Full verse-chorus lyrics ❌ | Minimal or no lyrics, atmospheric tags only |
| Classical/Orchestral | Full verse-chorus lyrics ❌ | Should often be instrumental |
| DnB/Dubstep | Full verse-chorus lyrics ❌ | Short vocal hooks, mostly instrumental |
| Shoegaze | Standard lyrics ⚠️ | Ethereal, buried-vocal feel — fewer, sparser lines |
| Country/Folk | Standard 4-line verses ⚠️ | Storytelling: 6-8 line verses, narrative structure |

### Root Cause

The profile inference prompt (`PROFILE_INFERENCE_AGENT`) has examples for rock/metal and pop, but no examples for electronic genres. The `LINES_PER_SECTION` documentation mentions:
- `2_lines`: "Atmospheric, ballads"
- `4_lines`: "Common default"
- `8_lines`: "Rap, hip-hop, rock"

But there's no guidance like: "EDM → 2_lines sparse choruses, heavy instrumental sections, minimal verse text."

The system also doesn't have a concept of **section density** — how many sections should *have lyrics at all* vs being instrumental `[Breakdown]` or `[Drop]` tags.

### Option A: Genre-Density Lookup Table (Hardcoded)

Add a deterministic genre→lyrics density mapping.

```python
GENRE_LYRICS_DENSITY = {
    # genre_pattern: (lines_per_section, structure_bias, vocal_density)
    "edm|electronic|house|techno|trance": {
        "lines_per_section": "2_lines",
        "line_length": "sparse",
        "vocal_density": "sparse",  # new concept
        "structure": ["Intro", "Verse", "Chorus", "Breakdown", "Chorus", "Outro"],
        "notes": "Short hooks, repetitive phrases, mostly instrumental sections"
    },
    "dnb|drum and bass|dubstep|bass music": {
        "lines_per_section": "2_lines",
        "line_length": "short",
        "vocal_density": "minimal",
        "structure": ["Intro", "Verse", "Breakdown", "Chorus", "Breakdown", "Chorus", "Outro"],
        "notes": "MC-style short vocal phrases, heavy drops"
    },
    "ambient|drone|atmospheric": {
        "lines_per_section": "2_lines",
        "line_length": "sparse",
        "vocal_density": "near_instrumental",
        "structure": ["Intro", "Verse", "Breakdown", "Outro"],
        "notes": "Ethereal, minimal words, mostly texture"
    },
    "rock|alt rock|indie rock|punk": {
        "lines_per_section": "4_lines",
        "line_length": "default",
        "vocal_density": "full",
        "structure": ["Intro", "Verse", "Pre-Chorus", "Chorus", "Verse", "Chorus", "Bridge", "Chorus", "Outro"],
        "notes": "Full lyric treatment standard"
    },
    "hip-hop|rap|trap": {
        "lines_per_section": "8_lines",
        "line_length": "long",
        "vocal_density": "dense",
        "structure": ["Intro", "Verse", "Chorus", "Verse", "Chorus", "Verse", "Chorus", "Outro"],
        "notes": "Dense rhyming, long verses"
    },
    "shoegaze|dream pop": {
        "lines_per_section": "2_lines",
        "line_length": "short",
        "vocal_density": "sparse",
        "structure": ["Intro", "Verse", "Chorus", "Verse", "Chorus", "Outro"],
        "notes": "Vocals buried in mix, impressionistic"
    },
    "country|folk|americana": {
        "lines_per_section": "6_lines",
        "line_length": "default",
        "vocal_density": "full",
        "structure": ["Intro", "Verse", "Chorus", "Verse", "Chorus", "Bridge", "Chorus", "Outro"],
        "notes": "Storytelling, narrative arc"
    }
}
```

**Pros:**
- Instant, zero cost, zero latency
- Deterministic and testable
- Easy to tune per genre with real listening tests
- Can be used as a *hint* to the profile inference LLM (not a hard override)

**Cons:**
- Requires manual curation for every genre/subgenre
- Rigid — can't handle genre blends (e.g., "EDM rock" — which density?)
- Genre detection from user prompt may be unreliable
- Doesn't account for artist-specific conventions within a genre

### Option B: Enhance Profile Inference Prompt

Augment the existing `PROFILE_INFERENCE_AGENT` prompt with explicit genre→density examples.

**Add to the prompt:**
```
GENRE-SPECIFIC DENSITY GUIDELINES:

EDM / House / Techno / Trance:
- Verse: 2_lines, sparse, short hooky phrases. NOT full storytelling.
- Chorus: 2_lines, sparse or short. Repetitive hooks ("Feel the bass", "Take me higher")
- HEAVY use of [Breakdown], [Drop] (instrumental-only sections)
- Structure leans: Intro → Verse → Chorus → Breakdown → Chorus → Drop → Outro
- Overall: 60-70% instrumental, 30-40% vocal

DnB / Dubstep / Bass Music:
- Even sparser than EDM. MC-style vocal bursts.
- 2_lines sparse, often just a hook phrase per section
- Structure: Intro → Verse → Drop → Verse → Drop → Outro
- Overall: 70-80% instrumental

Ambient / Drone / Atmospheric:
- Near-instrumental. 0-2 sung sections total.
- If any vocals: 2_lines, sparse, ethereal and abstract
- Consider choosing "instrumental" structure with just [Intro] [Breakdown] [Outro]

Shoegaze / Dream Pop:
- 2_lines per section, short/sparse line length
- Vocals should feel "buried" — keep words minimal and impressionistic
- More [Breakdown] sections than typical rock

Rock / Alt Rock / Punk / Metal:
- Full lyrics. 4_lines default, 6-8_lines for storytelling genres.
- Standard verse-chorus-bridge structure works great.

Hip-Hop / Rap:
- Dense. 8_lines verses, long line length, internal rhyme.
- Choruses can be shorter/hookier (4_lines, short).

Country / Folk / Singer-Songwriter:
- Storytelling-heavy. 6_lines verses, default line length.
- Narrative arc matters. Bridge often reveals twist.
```

**Pros:**
- No new system/code — just update an existing prompt
- LLM can blend guidelines with context (e.g., "EDM-rock hybrid" gets intermediate density)
- LLM can consider artist-specific conventions too
- Cheapest change — just text editing

**Cons:**
- LLM compliance is not guaranteed — it may still generate full lyrics for EDM
- Prompt is already long — adding more text increases context cost and may dilute other instructions
- Harder to test/verify — LLM outputs are non-deterministic
- No hard guardrails — if the LLM ignores the guidelines, there's no safety net

### Option C: Hybrid (Lookup Table as Hard Constraints + LLM for Nuance)

Use the lookup table to set hard *constraints* (max lines, required instrumental sections), then let the LLM fill in the nuance.

**Flow:**
```
Genre detected from tags/artists/prompt
        │
        ▼
Lookup table → { max_lines_per_section: 2, min_breakdowns: 2, vocal_density: "sparse" }
        │
        ▼
Profile Inference LLM (receives constraints as hard rules)
        │
        ▼  
Lyrics LLM (constrained profile applied)
        │
        ▼
Post-validation: reject if total lyric lines > max for genre
```

**Pros:**
- Hard constraints prevent the worst violations (EDM with 8-line verses)
- LLM still handles nuance within constraints
- Testable: unit tests can verify constraints are applied
- Post-validation adds a safety net

**Cons:**
- Most complex to implement
- Genre blends are still tricky (which table entry wins?)
- Post-validation rejection wastes an LLM call if it fails
- May over-constrain edge cases (e.g., vocal-heavy EDM acts like La Roux or Robyn)

### Option D: New "Vocal Density" Lyric Control

Extend `LyricControls` with a new `vocal_density` field that the profile inference model sets:

```python
LyricVocalDensity = Literal[
    "auto",
    "instrumental",    # No vocals at all
    "near_instrumental",  # 1-2 short vocal moments
    "sparse",          # Short hooks and phrases, mostly instrumental
    "standard",        # Normal verse-chorus-bridge
    "dense",           # Lots of lyrics (rap, storytelling folk)
]
```

The lyrics generation prompt would then interpret this control:
- `sparse` → Add more `[Breakdown]`, `[Drop]` sections; keep vocal sections to 2 lines
- `dense` → 8-line verses, long lines, minimize instrumental sections

**Pros:**
- Clean, extensible schema change
- User can override (e.g., force "dense" for an EDM song if they want it)
- Profile inference LLM just needs to output one more field
- Fits existing lyric controls pattern

**Cons:**
- Still relies on LLM to output the right density value  
- Need to update all lyrics prompt specs to use the new control
- Requires schema migration for API compatibility

### Recommendation

**Option B (Enhanced Profile Inference Prompt)** for v1 — simplest change with highest impact. The profile inference model already runs; we just need better genre→density guidance in its prompt.

**Option D (Vocal Density Control)** for v2 — adds proper schema support, user overrides, and structured control.

Key insight: The existing `lines_per_section` control is necessary but insufficient. EDM needs *fewer sections with lyrics* (more `[Breakdown]`/`[Drop]` tags), not just fewer lines per section. The structure array from profile inference is the right lever — the prompt just needs better genre guidance.

---

## Implementation Priority & Effort Estimates

| Issue | Recommended Approach | Effort | Impact | Risk |
|-------|---------------------|--------|--------|------|
| 1. Prompt Router | Heuristic Scoring (Option B) | 2-3 days | High — prevents creative dilution of specific prompts | Low — deterministic, testable, no new LLM calls |
| 3. Genre Density | Enhanced Profile Prompt (Option B) | 0.5-1 day | High — fixes the most visible EDM/electronic issue | Low — text-only change, no code changes |
| 2. Lyrics Passthrough | Heuristic Detection + LLM Formatter (Option B) | 3-4 days | Medium — niche feature but high value for power users | Medium — LLM formatter must not modify lyrics |

**Suggested order:** Issue 3 → Issue 1 → Issue 2

Issue 3 is the fastest win (just updating the profile inference prompt text). Issue 1 is highest impact but needs more code. Issue 2 is the most complex and serves a smaller user segment.

---

## Appendix: Architecture Touchpoints

### For Prompt Router (Issue 1)

Files to modify:
- `services/agent_prompt_graph.py` → Add `_classify_prompt_specificity()` method, add routing in `generate()`
- `prompts/specs.py` → Add `PASSTHROUGH_STYLE_SPEC` (minimal formatting prompt for high-specificity)
- `schemas/advanced.py` → Optionally add `prompt_specificity` to response for debugging

### For Lyrics Passthrough (Issue 2)

Files to modify:
- `services/agent_prompt_graph.py` → Add `_classify_lyrics_input()`, `_format_user_lyrics()`, new branch in `_run_lyrics_branch()`
- `prompts/specs.py` → Add `LYRICS_FORMATTER_PROMPT` (section tag placement only)
- `schemas/advanced.py` → Add `lyrics_mode: "generated" | "formatted"` to response

### For Genre Density (Issue 3)

Files to modify:
- `prompts/specs.py` → Expand `PROFILE_INFERENCE_AGENT` with genre-density guidelines
- Optionally: `schemas/advanced.py` → Add `vocal_density` to `LyricControls` (v2)

---

## Open Questions

1. **What happens in the "medium" specificity zone?** For prompts that are somewhat specific but not fully (e.g., "90s grunge, raw and heavy"), do we enrich or passthrough? Current recommendation: enrich for medium, passthrough only for clearly high-specificity.

2. **Should passthrough mode still run genre disambiguation?** If the user provided a detailed prompt, do we still need to classify artists? Recommendation: skip genre disambiguation for high-specificity prompts (it's redundant).

3. **How do we handle genres that are "lyric-optional"?** Some EDM songs have full vocals (La Roux, Robyn), some have none. Should the user's `lyrics_about` content influence density? If they write a full topic, maybe they want more lyrics even for EDM. Recommendation: if `lyrics_about` is detailed, bias toward more lyrics even for EDM.

4. **Should passthrough lyrics also affect style generation?** If a user provides full lyrics, should the style branch analyze the lyrics to infer mood/genre? This could create a fully user-driven flow: lyrics in → style inferred → Suno prompt generated. Interesting but out of scope for v1.

5. **Section tag vocabulary for EDM**: Suno may not understand `[Drop]`. Need to test whether `[Breakdown, heavy bass drop]` or `[Instrumental, drop]` works better. The existing tag list uses `[Breakdown]` which is close enough for v1.
