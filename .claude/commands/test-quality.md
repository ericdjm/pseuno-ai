# Test Quality

Assess generation quality by hitting real endpoints. Run this after prompt or generation changes.

## Prerequisites

1. Verify dev stack is up: `curl -s localhost:8000/health`
2. If not running, run `make dev-up` and wait for health check to pass.

## Steps

### 1. Generate 5 songs across varied genres

Call `POST localhost:8000/generate/advanced` with these inputs:

```bash
# Country
curl -s -X POST localhost:8000/generate/advanced \
  -H "Content-Type: application/json" \
  -d '{"user_prompt": "classic country with steel guitar and fiddle", "lyrics_about": "driving down a dirt road at sunset"}'

# Punk
curl -s -X POST localhost:8000/generate/advanced \
  -H "Content-Type: application/json" \
  -d '{"user_prompt": "fast aggressive punk rock", "lyrics_about": "being fed up with corporate greed"}'

# Hip-hop
curl -s -X POST localhost:8000/generate/advanced \
  -H "Content-Type: application/json" \
  -d '{"user_prompt": "boom bap hip hop with jazz samples", "lyrics_about": "growing up in the city"}'

# Folk
curl -s -X POST localhost:8000/generate/advanced \
  -H "Content-Type: application/json" \
  -d '{"user_prompt": "acoustic folk with fingerpicking", "lyrics_about": "a small town slowly disappearing"}'

# Electronic
curl -s -X POST localhost:8000/generate/advanced \
  -H "Content-Type: application/json" \
  -d '{"user_prompt": "dark synthwave with arpeggiated bass", "lyrics_about": "neon lights in an empty city"}'
```

Capture full JSON responses from each.

### 2. Assess vocabulary

Read the lyrics from each response. Check:
- **Banned/overused words**: silver, velvet, neon, shattered, whisper, shadows, echoes, crimson, golden, embers
- Flag if any of these appear in 3+ of the 5 songs
- Check that vocabulary feels genre-appropriate (country should sound different from punk)

### 3. Assess chorus quality

Parse `[Chorus]` sections from each song. Flag if any chorus has the same line repeated 3+ times consecutively.

### 4. Assess style names

Check that each response's `concept_title` / style name is:
- Short (under 30 characters)
- Descriptive, not a full style prompt sentence

### 5. Assess structure

For each song, verify:
- Section tags are present (`[Verse]`, `[Chorus]`, etc.)
- No stage directions in lyrics (e.g., "(softly)", "(guitar solo)")
- No periods at end of lines

### 6. Test refine

Take one generated song's full response and call refine. The refine endpoint requires the full current snapshot:
```bash
curl -s -X POST localhost:8000/generate/refine \
  -H "Content-Type: application/json" \
  -d '{
    "suno_prompt": "<suno_prompt from step 1>",
    "lyrics": "<lyrics from step 1>",
    "exclude": "<exclude from step 1>",
    "title": "<concept_title from step 1>",
    "weirdness": <weirdness from step 1>,
    "change_request": "make the chorus more upbeat and energetic",
    "refine_target": "lyrics"
  }'
```

Verify:
- `changed_fields` includes "lyrics"
- `changed_fields` does NOT include "suno_prompt"
- Completed in <30s

### 7. Report

Summarize findings: what passed, what failed, with specific examples of issues found.

### 8. Save results

Save the report to `benchmarks/quality-YYYY-MM-DD.md` (use today's date). Include the git branch/commit, per-song results for each check (vocabulary, chorus, style names, structure), and a summary. See `benchmarks/README.md` for the format.
