## NOTION AI CONVERSION PROMPT

Copy the prompt below, then copy everything after the `---` line into Notion, select all, and run Notion AI with this prompt:

```
Convert this markdown document to proper Notion formatting. Follow these exact steps:

STEP 0 - CLEANUP:
- Use "Randomize Features" as the Notion page title with the 🎲 emoji as the page icon
- Delete the "# Randomize Features" line from the body content
- Delete the Notion AI Conversation Prompt section

STEP 1 - DOCUMENT STRUCTURE (top to bottom):
The document should start with:
1. Callout block (the line starting with "> 💡...")
2. Horizontal divider (---)
3. Table of Contents (the /toc line)
4. Horizontal divider (---)
5. Then all the toggle headings and content

STEP 2 - CALLOUT:
Convert the line "> 💡 [summary]..." to a Callout block.
Keep the 💡 emoji as the callout icon. Make it blue.

STEP 3 - TOGGLE HEADINGS:
Find all lines that start with "## " (list them all):
- ## Overview
- ## Style Prompt Randomizer
- ## Lyrics Topic Randomizer
- ## Async Style Classification
- ## How They Connect
- ## Key Files

Convert each one to a Toggle Heading 2 (the kind you create with ▶## or by converting a heading to toggle).
The content under each heading should be inside the toggle.

STEP 4 - CODE BLOCKS:
DO NOT MODIFY any code blocks. They contain ASCII art diagrams with special characters like:
┌ ─ ┐ │ └ ┘ ▼ ▶ ├ ┤ ┬ ┴ ┼ ═ ║ ╔ ╗ ╚ ╝
These must remain exactly as they are, in monospace code blocks.

STEP 5 - TABLE:
If there are markdown tables with | characters, convert them to Notion simple tables.

STEP 6 - PRESERVE EVERYTHING ELSE:
- Keep all bullet points as bullet points
- Keep all bold text (**text**) as bold
- Keep all inline code (`code`) as inline code
- Do NOT summarize, shorten, or remove any content
- Do NOT add any new content or explanations
```

---

# Randomize Features

/toc

> 💡 Two "Surprise Me" dice buttons help users generate creative style prompts and lyrics topics. The style prompt influences lyrics topic selection through async classification.

---

## Overview

```
╔═══════════════════════════════════════════════════════════════════════════╗
║                           NEW SONG VIEW                                   ║
╠═══════════════════════════════════════════════════════════════════════════╣
║                                                                           ║
║  ┌─────────────────────────────────────────────────────────────────────┐  ║
║  │  📝 STYLE SECTION                                        🎲 Dice   │  ║
║  ├─────────────────────────────────────────────────────────────────────┤  ║
║  │                                                                     │  ║
║  │  "Dreamy synth-pop with shoegaze influences..."                     │  ║
║  │                                                                     │  ║
║  │  Tags: [indie rock] [dreamy] [synth-pop] [shoegaze]                │  ║
║  │                                                                     │  ║
║  └─────────────────────────────────────────────────────────────────────┘  ║
║                                                                           ║
║  ┌─────────────────────────────────────────────────────────────────────┐  ║
║  │  🎤 LYRICS SECTION                                       🎲 Dice   │  ║
║  ├─────────────────────────────────────────────────────────────────────┤  ║
║  │                                                                     │  ║
║  │  "The way nostalgia hits different at 3am, when the city           │  ║
║  │   is quiet and your thoughts are loud..."                          │  ║
║  │                                                                     │  ║
║  └─────────────────────────────────────────────────────────────────────┘  ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝
```

| Button | Location | What it generates |
|--------|----------|-------------------|
| 🎲 **Style Dice** | Style section header | 1-2 sentence style concept from tags |
| 🎲 **Lyrics Dice** | Lyrics section header | Themed lyric prompt from curated banks |

## Style Prompt Randomizer

### The Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│   USER SELECTS TAGS              USER CLICKS 🎲                        │
│                                                                         │
│   [indie rock] [trip-hop]   ──────────────▶   POST /generate/input-concept
│   [dreamy] [melancholic]                                                │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         BACKEND PROCESSING                              │
│                                                                         │
│   1. Collect genres from:                                               │
│      ├── User-selected tags (always included)                          │
│      └── Spotify taste pool (if personalized)                          │
│                                                                         │
│   2. Pick 1-5 genres (weighted toward fewer)                           │
│                                                                         │
│   3. Look up genre descriptors:                                        │
│      ┌─────────────────────────────────────────────────────────┐       │
│      │ "indie rock": {                                         │       │
│      │     texture: "jangly guitars and lo-fi warmth"          │       │
│      │     vibe: "intimate and understated"                    │       │
│      │     energy: "builds from quiet to anthemic"             │       │
│      │ }                                                       │       │
│      └─────────────────────────────────────────────────────────┘       │
│                                                                         │
│   4. Pick a template style and generate:                               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         TEMPLATE STYLES                                 │
│                                                                         │
│   ┌─────────────┐  "A blend of indie rock and trip-hop.                │
│   │ DESCRIPTIVE │   Jangly guitars and lo-fi warmth."                  │
│   └─────────────┘                                                       │
│                                                                         │
│   ┌─────────────┐  "Imagine indie rock through a                       │
│   │  EVOCATIVE  │   trip-hop lens."                                    │
│   └─────────────┘                                                       │
│                                                                         │
│   ┌─────────────┐  "Where indie rock crashes into trip-hop.            │
│   │   ACTION    │   Dark and atmospheric."                             │
│   └─────────────┘                                                       │
│                                                                         │
│   ┌─────────────┐  "Indie rock meets trip-hop.                         │
│   │   MINIMAL   │   Let it breathe."                                   │
│   └─────────────┘                                                       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│   RESULT: "Where indie rock crashes into trip-hop.                     │
│            Jangly guitars and lo-fi warmth."                           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Genre Taxonomy (185 genres across 11 categories)

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           GENRE CATEGORIES                               │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  🎸 CORE           pop, rock, hip-hop, r&b, electronic, jazz, folk...   │
│  🎹 ELECTRONIC     house, techno, synthwave, lo-fi, trance, dubstep...  │
│  🎤 HIP-HOP        trap, boom bap, drill, g-funk, crunk, grime...       │
│  🔊 ROCK           indie, grunge, shoegaze, post-punk, prog rock...     │
│  🤘 METAL          doom, black, death, djent, metalcore, power...       │
│  💫 POP            synth-pop, indie pop, art pop, k-pop, city pop...    │
│  🪕 ACOUSTIC       folk, americana, bluegrass, country, chamber folk... │
│  🎷 JAZZ           fusion, bebop, smooth jazz, acid jazz, swing...      │
│  💃 WORLD          reggaeton, afrobeat, flamenco, bossa nova, salsa...  │
│  ❤️ SOUL           neo-soul, quiet storm, motown, gospel, disco...      │
│  🌙 MOODS          dreamy, dark, ethereal, melancholic, euphoric...     │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

## Lyrics Topic Randomizer

### The Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│   USER CLICKS 🎲 LYRICS DICE                                           │
│                                                                         │
│   Current context:                                                      │
│   ├── Tags: [hip-hop] [melancholic]                                    │
│   └── Style: "Dark trap with emo influences"                           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      STEP 1: INFER TRAITS                               │
│                                                                         │
│   Tags → Traits:                                                        │
│   ┌───────────────────────────────────────────────────────────────┐    │
│   │  "hip-hop"     →  hip_hop_friendly: 0.9, urban: 0.6          │    │
│   │  "melancholic" →  melancholic: 0.85, introspective: 0.5      │    │
│   └───────────────────────────────────────────────────────────────┘    │
│                                                                         │
│   Async Classifier (if cached):                                         │
│   ┌───────────────────────────────────────────────────────────────┐    │
│   │  "Dark trap with emo influences"                              │    │
│   │       →  dark: 0.7, hip_hop_friendly: 0.8, vulnerable: 0.6   │    │
│   └───────────────────────────────────────────────────────────────┘    │
│                                                                         │
│   Merged Traits:                                                        │
│   { hip_hop_friendly: 0.9, melancholic: 0.85, dark: 0.7,               │
│     vulnerable: 0.6, urban: 0.6, introspective: 0.5 }                  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      STEP 2: SCORE ALL BANKS                            │
│                                                                         │
│   55 Topic Banks scored against merged traits:                          │
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐  │
│   │  Bank                        │  Score  │  Probability           │  │
│   ├─────────────────────────────────────────────────────────────────┤  │
│   │  emo_rap_vulnerability       │  0.82   │  ████████████░░ 28%   │  │
│   │  confessional_heartbreak     │  0.71   │  ██████████░░░░ 22%   │  │
│   │  warm_numbness               │  0.65   │  ████████░░░░░░ 18%   │  │
│   │  urban_swagger               │  0.58   │  ██████░░░░░░░░ 14%   │  │
│   │  late_night_thoughts         │  0.52   │  █████░░░░░░░░░ 11%   │  │
│   │  ...                         │  ...    │  ...                  │  │
│   └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      STEP 3: SAMPLE BANK                                │
│                                                                         │
│   Top-K linear normalization → weighted random selection                │
│                                                                         │
│   🎯 Selected: "emo_rap_vulnerability"                                  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      STEP 4: SAMPLE PROMPT                              │
│                                                                         │
│   Bank: emo_rap_vulnerability (15 prompts)                              │
│                                                                         │
│   Filter out recent (last 30 used) → Pick random                        │
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐  │
│   │  "I keep joking about being okay because the truth is          │  │
│   │   too heavy to say out loud"                                    │  │
│   └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Topic Bank Examples

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         55 TOPIC BANKS                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  💔 HEARTBREAK & LONGING                                               │
│     "Reading our old texts like scripture, trying to find the          │
│      exact moment we started losing each other"                        │
│                                                                         │
│  🎉 PARTY & CELEBRATION                                                │
│     "That exact moment when the bass drops and everyone                │
│      loses their minds together"                                       │
│                                                                         │
│  🌌 CONSCIOUSNESS & METAPHYSICAL                                       │
│     "Spiraling through layers of self, each one revealing              │
│      a mask I did not know I was wearing"                              │
│                                                                         │
│  🌊 COASTAL MYSTICISM                                                  │
│     "Fog rolling in like a verdict, like the coast deciding            │
│      what I am allowed to see today"                                   │
│                                                                         │
│  🔥 REBELLION & DEFIANCE                                               │
│     "I am done asking permission, my life is not a                     │
│      committee decision"                                               │
│                                                                         │
│  🌿 WHIMSICAL NATURE                                                   │
│     "A porch light and a summer breeze, telling stories                │
│      to the fireflies like they are old friends"                       │
│                                                                         │
│  🤡 ABSURDIST COMEDY                                                   │
│     "My brain is a group chat with no moderator, and                   │
│      everyone is typing at once"                                       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Async Style Classification

### Why Async?

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│   PROBLEM: Artist names can't be matched with keywords                  │
│                                                                         │
│   ┌──────────────────────────┐    ┌──────────────────────────┐         │
│   │  "Something like Tool"   │ ─▶ │  ???                     │         │
│   └──────────────────────────┘    └──────────────────────────┘         │
│                                                                         │
│   Keyword matching knows nothing about Tool's lyrics!                   │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   SOLUTION: LLM Classification (async, ~1-2s)                          │
│                                                                         │
│   ┌──────────────────────────┐    ┌──────────────────────────┐         │
│   │  "Something like Tool"   │ ─▶ │  spiritual: 0.9          │         │
│   └──────────────────────────┘    │  prog_metal_friendly: 0.8│         │
│                                   │  introspective: 0.75     │         │
│                                   │  surreal: 0.7            │         │
│                                   └──────────────────────────┘         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Async Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│  USER TYPES STYLE PROMPT                                                │
│                                                                         │
│  [S][o][m][e][t][h][i][n][g][ ][l][i][k][e][ ][T][o][o][l]...          │
│                                                                         │
│                              │                                          │
│                              ▼ (1s debounce)                           │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  ASYNC: POST /generate/classify-style                             │ │
│  │                                                                   │ │
│  │  Runs in parallel:                                                │ │
│  │  ├── LLM Classifier (Gemini Flash)                               │ │
│  │  └── Embedding Similarity (text-embedding-004)                   │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                              │                                          │
│                              ▼ (~1-2s later)                           │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  CACHED IN FRONTEND STATE                                         │ │
│  │                                                                   │ │
│  │  traits: { spiritual: 0.9, prog_metal_friendly: 0.8, ... }       │ │
│  │  bank_similarities: { consciousness_metaphysical: 0.72, ... }    │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

                              ▼ (later, user clicks lyrics 🎲)

┌─────────────────────────────────────────────────────────────────────────┐
│  LYRICS RANDOMIZER USES CACHED RESULTS                                  │
│                                                                         │
│  POST /generate/lyrics-topic                                            │
│    + trait_overrides: { spiritual: 0.9, ... }    ◀── from cache        │
│    + bank_similarities: { consciousness: 0.72 }  ◀── from cache        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Specificity Weighting

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    INFLUENCE SPECIFICITY                                │
│                                                                         │
│   More specific = More influence on bank selection                      │
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐  │
│   │                                                                 │  │
│   │  "Radiohead"        ████████████████████  1.5x (artist)        │  │
│   │                                                                 │  │
│   │  "post-punk"        ████████████████░░░░  1.2x (subgenre)      │  │
│   │                                                                 │  │
│   │  "rock"             ████████████░░░░░░░░  1.0x (genre)         │  │
│   │                                                                 │  │
│   │  "dreamy"           ████████░░░░░░░░░░░░  0.8x (descriptor)    │  │
│   │                                                                 │  │
│   └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## How They Connect

```
╔═════════════════════════════════════════════════════════════════════════╗
║                      COMPLETE DATA FLOW                                 ║
╚═════════════════════════════════════════════════════════════════════════╝

     ┌─────────────────────────────────────────────────────────────────┐
     │                        STYLE SECTION                            │
     │                                                                 │
     │   Tags: [indie rock] [trip-hop] [dreamy]                       │
     │                                                                 │
     │   Style Prompt: "Something like Massive Attack meets           │
     │                  Radiohead, atmospheric and cinematic"         │
     │                                                                 │
     └─────────────────────────────────────────────────────────────────┘
                │                                    │
                │                                    │
     ┌──────────┴──────────┐              ┌─────────┴─────────┐
     │                     │              │                   │
     ▼                     ▼              ▼                   │
┌─────────┐         ┌───────────┐   ┌───────────┐            │
│  Tags   │         │   Style   │   │   Async   │            │
│         │         │  Dice 🎲  │   │ Classifier│            │
└────┬────┘         └─────┬─────┘   └─────┬─────┘            │
     │                    │               │                   │
     │                    ▼               ▼                   │
     │              ┌───────────┐   ┌───────────┐            │
     │              │  Concept  │   │  Cached   │            │
     │              │ Generated │   │  Traits   │            │
     │              └───────────┘   └─────┬─────┘            │
     │                                    │                   │
     │                                    │                   │
     └────────────────────┬───────────────┘                   │
                          │                                   │
                          ▼                                   │
     ┌─────────────────────────────────────────────────────────────────┐
     │                       LYRICS SECTION                            │
     │                                                                 │
     │   User clicks 🎲                                               │
     │                                                                 │
     │   ┌─────────────────────────────────────────────────────────┐  │
     │   │  /generate/lyrics-topic                                 │  │
     │   │                                                         │  │
     │   │  Inputs:                                                │  │
     │   │  ├── tags: ["indie rock", "trip-hop", "dreamy"]        │  │
     │   │  ├── trait_overrides: {melancholic: 0.8, ...}   ◀ cache│  │
     │   │  └── bank_similarities: {coastal: 0.7, ...}     ◀ cache│  │
     │   └─────────────────────────────────────────────────────────┘  │
     │                          │                                      │
     │                          ▼                                      │
     │   ┌─────────────────────────────────────────────────────────┐  │
     │   │  BLENDING                                               │  │
     │   │                                                         │  │
     │   │  If tags present:  70% traits + 30% embeddings          │  │
     │   │  If no tags:       100% embeddings                      │  │
     │   └─────────────────────────────────────────────────────────┘  │
     │                          │                                      │
     │                          ▼                                      │
     │   ┌─────────────────────────────────────────────────────────┐  │
     │   │  OUTPUT                                                 │  │
     │   │                                                         │  │
     │   │  "Fog rolling in like a verdict, like the coast         │  │
     │   │   deciding what I am allowed to see today"              │  │
     │   │                                                         │  │
     │   │  Bank: coastal_mysticism                                │  │
     │   └─────────────────────────────────────────────────────────┘  │
     │                                                                 │
     └─────────────────────────────────────────────────────────────────┘
```

### Staleness Handling

```
┌─────────────────────────────────────────────────────────────────────────┐
│  WHAT HAPPENS WHEN STYLE PROMPT CHANGES?                                │
│                                                                         │
│  1. User edits style prompt                                             │
│     ┌──────────────────────────────────────────────────────────────┐   │
│     │  "Massive Attack meets Radiohead" → "Taylor Swift country"   │   │
│     └──────────────────────────────────────────────────────────────┘   │
│                                       │                                 │
│                                       ▼                                 │
│  2. Frontend immediately clears cache                                   │
│     ┌──────────────────────────────────────────────────────────────┐   │
│     │  cachedTraits = null                                         │   │
│     │  cachedBankSimilarities = null                               │   │
│     └──────────────────────────────────────────────────────────────┘   │
│                                       │                                 │
│                                       ▼                                 │
│  3. Async re-classification fires (1s debounce)                        │
│     ┌──────────────────────────────────────────────────────────────┐   │
│     │  POST /generate/classify-style                               │   │
│     │  { style_prompt: "Taylor Swift country" }                    │   │
│     └──────────────────────────────────────────────────────────────┘   │
│                                       │                                 │
│                                       ▼                                 │
│  4. If user clicks lyrics 🎲 before cache is ready:                    │
│     → Falls back to keyword heuristics (fast, less accurate)           │
│                                                                         │
│  5. Once cache is ready, subsequent clicks use new traits              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Key Files

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           CODEBASE MAP                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  BACKEND                                                                │
│  ├── services/                                                          │
│  │   ├── input_concept_generator.py   📝 Style template generation     │
│  │   ├── lyrics_topic_generator.py    🎯 Bank selection + sampling     │
│  │   ├── lyrics_topic_banks.py        📚 55 banks, 825 prompts         │
│  │   ├── lyrics_topic_traits.py       🏷️  Trait definitions + mappings │
│  │   ├── style_classifier.py          🤖 LLM-based style analysis      │
│  │   └── bank_embeddings.py           📐 Embedding similarity          │
│  │                                                                      │
│  └── routes/                                                            │
│      └── generate_input_concept.py    🔌 API endpoints                  │
│                                                                         │
│  FRONTEND                                                               │
│  └── components/                                                        │
│      ├── NewSongView.tsx              🎨 Randomizer UI + caching        │
│      └── LyricsTopicDebugPanel.tsx    🔍 Debug overlay (dev only)       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```
