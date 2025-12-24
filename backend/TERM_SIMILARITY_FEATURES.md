# Term Similarity System — Future Features

This document outlines the user-facing and product features unlocked by the term similarity architecture (Phase 0–2). Each feature maps to the primitives now in place: canonical terms, aliasing, provenance-tagged signals, and time-decayed co-occurrence.

---

## 1. Prompt Builder "Chips" UX

**Description**: Show `artists_used`, `tags_used`, and `terms_extracted` as editable chips in the frontend. Users can remove/add terms before saving, giving them explicit control over what's associated with a prompt.

**Enables**:
- User-curated term sets per prompt
- Higher-trust signals for similarity (user explicitly approved these terms)
- Better UX for power users who want fine-grained control

**Maps to**:
- `AdvancedGenerateResponse.artists_used` / `tags_used` / `terms_extracted`
- `PromptTermLink` table (links terms to saved prompts with `source` tag)

---

## 2. Saved Prompt Organization

**Description**: Filter and search saved prompts by canonical terms. E.g., "show me all my prompts tagged with `prog` + `upbeat`".

**Enables**:
- Library UX for users with many saved prompts
- Discovery of prompts by mood/genre/era
- "Similar prompts" suggestions

**Maps to**:
- `prompt_term_links` table
- `Term.canonical` for consistent filtering

---

## 3. Explainable Similarity

**Description**: For any suggested term in `/terms/similar`, show provenance: "suggested because you saved prompts with X" or "Spotify taste indicates Y".

**Enables**:
- User trust in recommendations
- Debugging why certain terms appear
- Transparency over "black box" recommendations

**Maps to**:
- `SimilarTermResult.provenance` field
- `TermEvent.event_type` (query, select, save_prompt, spotify_seed, model_extracted)
- `PromptTermLink.source` (user, model_extracted, spotify)

---

## 4. Term Compare ("Shared vs. Differing")

**Description**: `POST /terms/compare([Rush, Meshuggah])` returns:
- **Shared facets**: `prog`, `complex_rhythms`, `instrumental_prowess`
- **Differing facets**: Rush → `classic_rock`, `canadian`; Meshuggah → `djent`, `metal`

**Enables**:
- Discovery of what makes artists/genres similar or different
- Educational UX for users exploring new styles
- "If you like X, try Y because they share Z" recommendations

**Maps to**:
- `GET /terms/similar/{term}` co-occurrence logic
- `POST /terms/compare` endpoint

---

## 5. Trend Surfacing (Over Time)

**Description**: Show global or per-user trending terms using time-decayed event weights. E.g., "this week, `synth_pop` is trending".

**Enables**:
- Discovery of emerging styles
- Social proof ("others are exploring X")
- Seasonal or event-driven recommendations

**Maps to**:
- `term_events.created_at` + time decay function
- Aggregation over `TermEvent` table

---

## 6. Personalization

**Description**: Re-rank similarity results based on per-user history:
- Spotify taste features (e.g., if user's top genre is "indie", boost indie-adjacent terms)
- Saved prompts (if user saves many `lo_fi` prompts, boost `lo_fi` in recommendations)
- Explicit feedback (user clicks "not relevant" on a term)

**Enables**:
- Tailored recommendations per user
- "More like this" that learns from behavior
- Reduced noise in suggestions

**Maps to**:
- `term_events.user_id`
- Future: `user_term_weights` table (per-user preference vectors)
- Future: Spotify integration via `ExternalAccount.access_token`

---

## 7. Curation Tools

**Description**: Admin UI to manage the term registry:
- Merge duplicate terms (e.g., `classic_rock` and `classicrock`)
- Split overly broad terms (e.g., `rock` into `hard_rock`, `soft_rock`, `prog_rock`)
- Pin/ban terms from suggestions
- Correct wrong associations

**Enables**:
- Data quality control
- Expert curation of taxonomy
- Handling edge cases and typos at scale

**Maps to**:
- `Term` and `TermAlias` tables
- Future: admin endpoints for bulk operations

---

## 8. Evaluation Harness

**Description**: A small "gold set" of expected term similarities:
- Input: `classic_rock`
- Expected similar: `70s_rock`, `guitar_driven`, `arena_rock`, etc.
- Expected NOT similar: `hip_hop`, `electronic`, `country`

Run periodically to catch regressions when models or data change.

**Enables**:
- Confidence that similarity is working as expected
- Alerts when model changes break expectations
- Versioned snapshots for reproducibility

**Maps to**:
- Test fixtures in `backend/tests/`
- Future: `similarity_snapshot_id` for versioned results

---

## Implementation Status

| Feature | Status | Dependencies |
|---------|--------|--------------|
| Chips UX | Ready for frontend | `terms_extracted` in response |
| Saved Prompt Org | Backend ready | `prompt_term_links` table |
| Explainable Similarity | Implemented | `provenance` in `/terms/similar` |
| Term Compare | Implemented | `POST /terms/compare` |
| Trend Surfacing | Backend ready | Time decay on `term_events` |
| Personalization | Phase 4 | `user_id` on events + Spotify |
| Curation Tools | Phase 4+ | Admin UI needed |
| Evaluation Harness | Future | Test fixtures needed |

---

## Data Flow Summary

```
User Input (artists, tags)
        ↓
AgentPromptGraph.generate()
        ↓
Model Output (TERMS section)
        ↓
normalize_term() + dedupe
        ↓
AdvancedGenerateResponse
  ├── artists_used (deterministic)
  ├── tags_used (normalized)
  └── terms_extracted (model output, may be empty)
        ↓
On Save Prompt → PromptTermLink records
        ↓
/terms/similar uses co-occurrence
        ↓
Explainable, time-decayed recommendations
```

