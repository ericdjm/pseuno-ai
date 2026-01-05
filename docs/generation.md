# Generation: Input Concept and Lyrics

This document explains how the input concept and lyrics generation flows work,
based on the current backend implementation.

## Generate Input Concept (`POST /generate/input-concept`)

Purpose: Create a short Suno-style concept (2-3 sentences) from genre influences.
The result is used as the `user_prompt` in `/generate/advanced`.

Request (`InputConceptRequest`):
- `genres`: list of genre strings (1-3 are randomly selected). If empty, fallback
  seed genres are used.
- `artists`: list of artist strings (passed through, not used in v1).
- `mood`: optional mood hint (used if provided; otherwise inferred).

Response (`InputConceptResponse`):
- `concept`: generated 2-3 sentence concept.
- `chosen_genres`: the randomly selected 1-3 genres.
- `genres`: the full genre list used for selection.
- `artists`: echoed back for future use.
- `mood`: the mood used (provided or inferred).

Flow:
1. `create_generator_with_providers(...)` builds:
   - `InputConceptGenerator`
   - `CompositeGenreInfluenceProvider` with `ManualInputGenreProvider`
2. `providers.get_influence_genres(...)` merges all provider genre lists.
3. `InputConceptGenerator.generate(...)`:
   - Falls back to `FallbackSeedGenreProvider` if the merged list is empty.
   - Randomly selects 1-3 genres from the list.
   - Calls `_generate_concept(...)` to build a 2-3 sentence template.
     - Uses `GENRE_DESCRIPTORS` when available.
     - Falls back to generic texture/vibe/energy templates if unknown.
4. The endpoint returns the generated concept plus the metadata above.

Relevant files:
- `backend/app/routes/generate_input_concept.py`
- `backend/app/services/input_concept_generator.py`
- `backend/app/services/artist_influence.py`

## Generate Lyrics Topic (`POST /generate/lyrics-topic`)

Purpose: Generate a short 1-2 sentence topic or theme that can be used as the
`lyrics_about` field for `/generate/advanced` or `/generate/lyrics-only`.

Request (`LyricsTopicRequest`):
- `genres`: optional list of genres for thematic influence.
- `moods`: optional list of mood tags (preferred over genres when provided).
- `style_prompt`: optional style prompt to align the topic with a musical vibe.

Response (`LyricsTopicResponse`):
- `topic`: the generated 1-2 sentence topic.
- `chosen_moods`: the moods that influenced the topic (seeded if none provided).
- `reasoning`: optional debug reasoning from the generator.

Flow:
1. The endpoint calls `generate_lyrics_topic(...)` with `genres`, `moods`, and
   `style_prompt`.
2. The generator picks or infers moods (from explicit moods or genre-to-mood
   mappings) and returns a short topic sentence or two.
3. The endpoint returns the topic plus the chosen moods and optional reasoning.

Relevant files:
- `backend/app/routes/generate_input_concept.py`
- `backend/app/services/lyrics_topic_generator.py`
- `backend/app/schemas/input_concept.py`

## Generate Lyrics

There are two paths: full generation (lyrics + Suno prompt) and lyrics-only.

### Full Generation (`POST /generate/advanced`)

Purpose: Generate lyrics plus Suno prompt artifacts, and auto-save the result.

Key request fields (`AdvancedGenerateRequest`):
- `user_prompt`: style/vibe prompt (often from `/generate/input-concept`).
- `lyrics_about`: topic/theme for the lyrics.
- Optional: `selected_artists`, `tags`, `lyric_controls`, `prompt_variant`,
  `model`/`style_model`/`lyrics_model`.

High-level flow:
1. `AgentPromptGraph.generate(...)` picks a prompt variant:
   - Request override -> settings -> default `v5_hybrid`.
2. Builds a per-request `GenerationContext`.
   - Single-step: one model, one prompt + repair prompt.
   - Two-step: separate style + lyrics prompts and models.
3. Single-step path:
   - build_context -> generate -> parse/validate -> (repair loop) -> finalize
4. Two-step path:
   - Runs style and lyrics branches in parallel.
   - Lyrics branch may infer a lyric profile (for V4+ variants).
   - Both branches can repair on validation failure.
   - Results are merged into the final response.
5. Instrumental short-circuit:
   - If `lyrics_about` is empty or contains phrases like "instrumental" or
     "no lyrics", the lyrics branch is skipped and lyrics are returned empty.
6. The route auto-saves the prompt to the database:
   - Uses Spotify user if logged in, otherwise creates or reuses a guest via
     device cookie.
   - Returns `prompt_id` if saved successfully.

Response (`AdvancedGenerateResponse`) includes:
- `concept_title`, `lyrics`, `suno_prompt`
- `exclude`, `weirdness`, `style_influence`
- `generation_id`, optional `debug_info`, and `auto_tags`

Relevant files:
- `backend/app/routes/generate_advanced.py`
- `backend/app/services/agent_prompt_graph.py`
- `backend/app/prompts.py`
- `backend/app/schemas/advanced.py`

### Lyrics-Only (`POST /generate/lyrics-only`)

Purpose: Generate new lyrics using a saved Suno prompt as style context.

Request (`LyricsOnlyRequest`):
- `suno_prompt`: the saved Suno prompt for style guidance.
- `lyrics_about`: topic/theme for the new lyrics.

Flow:
1. `_is_instrumental_lyrics_request(...)` checks for instrumental intent.
   - If true, returns `song_title="Instrumental"` and empty lyrics.
2. Builds a small context block with `suno_prompt` and `lyrics_about`.
3. Calls the LLM directly with `LYRICS_SYSTEM_PROMPT`.
4. Parses output sections with `_extract_sections(...)`:
   - `SONG TITLE` and `LYRICS` headers are extracted.
   - Fallback: if no headers, use raw output and default title `Untitled`.

Response (`LyricsOnlyResponse`):
- `song_title`
- `lyrics`

Relevant files:
- `backend/app/routes/generate_advanced.py`
- `backend/app/schemas/advanced.py`
- `backend/app/prompts.py`
