# PostHog in Pseuno AI (Decisions + Phased Rollout)

This doc is for future contributors/agents. It summarizes **why** we’re using PostHog, **what** we’re tracking, and **how** we plan to roll it out incrementally so each feature proves value (or gets cut).

## Why PostHog (single vendor)

We chose **PostHog-only** (hosted) to minimize ops while still getting:
- **Analytics**: funnels/paths/retention to understand user flow
- **Feature flags**: safe incremental rollouts and A/B tests
- Optional later: **session replay**, **error tracking**, **surveys**, **LLM analytics**

We are intentionally rolling out in phases to avoid “instrument everything” and to stay within free-tier limits.

## What this app does (core flows)

Pseuno AI has two user modes:
- **Guest**: identity via `device_token` cookie (created on first generation), frictionless exploration
- **Spotify-authenticated**: login via OAuth, profile fetch, personalized tag recommendations, more iteration

Key product loops:
- **Generate** a new song prompt (NewSongView)
- **Refine** style/lyrics (often forks a style prompt and copies threads)
- **Manage library** (style prompts + lyrics threads): select, rename, reorder, delete, favorite

The best analytics questions map to these flows:
- **Activation**: can users generate successfully the first time?
- **Iteration**: do they refine, create new variations, favorite, come back?
- **Friction**: where do they drop off (auth, long waits, failures)?
- **Model UX**: how long do requests take and how often do they fail?

## Principles (to stay useful + cheap)

- **Track decisions, not trivia**: prefer “state change” events over noisy events.
- **Low-cardinality properties only**: do not attach raw prompt text, full errors, user IDs in event properties unless explicitly needed.
- **Privacy-first by default**:
  - Don’t send raw lyrics, prompts, or emails as properties.
  - When/if enabling session replay: mask inputs by default.
- **One phase at a time**: do not implement later phases “because it’s available.”

## Identity strategy (guest → Spotify)

- Guests use PostHog anonymous `distinct_id`.
- When Spotify-authenticated:
  - Call `posthog.identify(spotifyUserId)` as soon as auth status is known.
  - Optionally call `posthog.alias(spotifyUserId)` on first login if we want to stitch pre-login activity to the user.

Avoid raw emails. If user properties are needed, keep them minimal (e.g., `auth_state`, `has_spotify`).

## Environment variables

Frontend (Vite requires `VITE_` prefix):
- `VITE_POSTHOG_KEY`: PostHog project API key (safe for browser; starts with `phc_...`)
- `VITE_POSTHOG_HOST`: PostHog API host (e.g. `https://us.i.posthog.com`)
- `VITE_APP_ENV`: `dev` or `prod` (used for environment tagging in events)

**Where configured**:
- Dev: `docker-compose.dev.yml` under `frontend.environment`
- Prod: set in your hosting provider's env var UI

## Dev vs prod in a single project

PostHog free tier only allows **one project**, so we use a single project for both dev and prod. To distinguish environments:

- Set `VITE_APP_ENV=dev` locally (already in docker-compose)
- Set `VITE_APP_ENV=prod` in production hosting
- During PostHog init, register it as a **super property** so it attaches to every event automatically:
  ```javascript
  posthog.register({ environment: import.meta.env.VITE_APP_ENV || 'unknown' })
  ```
- In PostHog UI, filter any dashboard/funnel/insight by `environment = prod` to see only production data

This keeps dev noise out of production analytics without needing a separate project.

## Frontend SDK setup

The PostHog JS SDK (`posthog-js`) is installed as a frontend dependency.

**Where initialized**: `frontend/src/main.tsx` (runs once at app bootstrap)

**Key init options**:
- `person_profiles: 'identified_only'` — only create profiles for identified users (privacy-friendly)
- `capture_pageview: true` — auto-capture pageviews
- `posthog.register({ environment })` — attach environment to all events

**Adding or updating PostHog dependencies**:
1. Edit `frontend/package.json`
2. Run `npm install` in `frontend/` to update `package-lock.json`
3. Commit both `package.json` and `package-lock.json`
4. Rebuild Docker container: `docker-compose -f docker-compose.dev.yml up --build frontend`

This ensures `npm ci` in Docker builds installs the exact same versions everywhere.

## Phased rollout (prove value or cut)

### Phase 0 — Plumbing + governance
**Goal**: events flow in dev/prod.
- Add PostHog SDK init (frontend).
- Add `VITE_POSTHOG_KEY` / `VITE_POSTHOG_HOST` / `VITE_APP_ENV`.
- Create an “event contract” (names + properties + rules).

**Prove value**:
- Live Events show `pageview` + one custom event within 60 seconds.

### Phase 1 — Analytics for core journey (highest ROI)
**Goal**: identify activation drop-off, understand how users interact, measure friction.

**Event taxonomy** (defined in `frontend/src/analytics.ts`):

**Auth events**:
- `auth_login_clicked` — user clicked Spotify login
- `auth_login_succeeded` / `auth_login_failed` — login outcome
- `auth_status_loaded` — app checked auth state (props: `authenticated`)
- `auth_logout` — user logged out

**Generation flow**:
- `generate_clicked` — user clicked generate (props: `has_lyrics_input`, `has_style_input`, `personalize_enabled`, plus `instrumental_intended` + `instrumental_intent_signal`)
- `generate_succeeded` / `generate_failed` — outcome (props: `duration_ms`, plus `has_lyrics`, `instrumental_intended` + `instrumental_intent_signal`)
- `generate_wait_notice_shown` — slow-loading message shown

**Style creation**:
- `randomize_style_clicked` — user clicked "Surprise me" (props: `personalize_enabled`, `manual_tags_count`)
- `randomize_style_succeeded` / `randomize_style_failed` — outcome (props: `duration_ms`, `auto_picked_count`, `error_type`)
- `randomize_lyrics_clicked` — user clicked lyrics dice button (props: `has_style_input`, plus `page` and `randomize_context`)
- `randomize_lyrics_succeeded` / `randomize_lyrics_failed` — outcome (props: `duration_ms`, `error_type`, plus `page` and `randomize_context`)
- `personalize_toggled` — user toggled Spotify personalization (props: `is_enabled`)
- `tag_added` — user added a tag (props: `source: recommended|auto_picked`)
- `tag_removed` — user removed a tag

**Style refine (AI)**:
- `style_refine_started` / `style_refine_succeeded` / `style_refine_failed` — style changes (forks a new style)
  - Core props: `duration_ms`, `created_new_style`
  - “What changed” props on `style_refine_succeeded`: `changed_suno_prompt`, `changed_exclude`, `changed_weirdness`, `changed_style_influence`, `changed_lyrics`, `changed_title`, `changed_fields_count_bucket`
  - Persistence guard: `updates_persisted` (we treat `updates_persisted=false` as a failure in the UI + analytics)

**Lyrics AI edits**:
- `lyrics_ai_edit_started` / `lyrics_ai_edit_succeeded` / `lyrics_ai_edit_failed` — AI edits of lyrics (in-place)
  - Core props: `duration_ms`
  - “What changed” props on `lyrics_ai_edit_succeeded`: `changed_*` + `changed_fields_count_bucket`
  - Persistence guard: `updates_persisted`

**Legacy (compat)**:
- `refine_started` / `refine_succeeded` / `refine_failed` — legacy umbrella events (prop: `refine_type: style|lyrics`)

**Library actions**:
- `style_selected` / `thread_selected` — navigating to existing content
- `favorite_toggled` — pin/unpin style (props: `is_favorite`)
- `new_lyrics_variation_clicked` — user started new song on existing style
- `draft_lyrics_generated` — user generated lyrics for new song (props: `duration_ms`, `has_lyrics_about_input`)
- `new_lyrics_in_style_started` / `new_lyrics_in_style_succeeded` / `new_lyrics_in_style_failed` — end-to-end “create new lyrics within an existing style” flow (draft composer)

**Utility actions**:
- `copied_to_clipboard` — user copied content (props: `content_type: style_prompt|exclude|lyrics|title|suno_link`, `copy_context`, plus `exclude_present`/`exclude_count_bucket` for analysis)
- `suno_link_clicked` — user clicked "Open in Suno"
- `output_used` — canonical “user used output” event for clean funnels (props: `method`, plus `style_prompt_id`/`lyrics_thread_id`, optional `exclude_present`/`exclude_count_bucket`, and `origin_mode: generated|loaded|new`)

**Manual vs AI edits** (lets us answer “did they rename/edit manually or via AI?”):
- `style_title_changed` — style name changed (props: `source: manual|ai_generate|ai_refine`)
- `song_title_changed` — song name changed (props: `source: manual|ai_generate|ai_refine`)
- `lyrics_manual_edit_saved` — user manually edited lyrics text (props: `edit_size: small|medium|large`, `was_empty_before`)

**Delete + organize**:
- `style_deleted` — style deleted (props: `source: sidebar`)
- `song_deleted` — song deleted (props: `source: song_view|sidebar`, `remaining_songs_bucket: 0|1-2|3-5|6+`)
- `songs_reordered` — songs reordered within a style (props: `songs_count_bucket: 1-2|3-5|6+`, `move_direction: up|down`)

**Failure events** (for drop-off + reliability dashboards):
- `randomize_style_failed`, `randomize_lyrics_failed` — randomizer failures (props: `error_type`)
- `draft_lyrics_failed` — draft lyrics generation failed (props: `duration_ms`, `error_type`)
- `new_lyrics_in_style_failed` — end-to-end existing-style new lyrics flow failed (props: `duration_ms`, `error_type`)
- `lyrics_manual_edit_save_failed` — autosave failed (props: `error_type`)
- `song_title_change_failed`, `style_title_change_failed` — rename failures (props: `error_type`)
- `song_delete_failed`, `style_delete_failed` — delete failures (props: `source`, `error_type`)
- `songs_reorder_failed` — reorder persist failed (props: `error_type`)
- `copied_to_clipboard_failed` — clipboard blocked/failed (props: `content_type`, `error_type`)

## Backend telemetry (LLM + repair agent)

We emit backend-side PostHog events to measure **per-LLM-call latency** and how often we invoke the **repair agent**.

## Programmatic dashboards (API-driven)

If you want to **create dashboards/tiles via code** and validate they “actually work” (queries return data), use:

- `scripts/posthog_dashboards.py` (standard library only)

### Required env vars

- `POSTHOG_HOST` (default: `https://us.posthog.com`)
- `POSTHOG_PROJECT_ID` (numeric project id in PostHog)
- `POSTHOG_PERSONAL_API_KEY` (**personal** API key, not the public `phc_...` project key)

### Backend telemetry key env var

Backend capture accepts either:
- `POSTHOG_API_KEY` (**preferred**)
- `POSTHOG_PROJECT_API_KEY` (also supported)

### Required PostHog key scopes

- **Dashboard**: Write
- **Insight**: Write
- **Performing analytics queries / Query**: Read
- *(Optional)* **Project**: Read (for `list-projects`)

### Commands

List projects (to find `POSTHOG_PROJECT_ID`):

```bash
POSTHOG_HOST="https://us.posthog.com" \
POSTHOG_PERSONAL_API_KEY="***" \
python3 scripts/posthog_dashboards.py list-projects
```

Create/update Core Health dashboard and validate each tile via `/query/`:

```bash
POSTHOG_HOST="https://us.posthog.com" \
POSTHOG_PROJECT_ID="12345" \
POSTHOG_PERSONAL_API_KEY="***" \
python3 scripts/posthog_dashboards.py ensure-core-health
```

## PostHog Investigation Runbook (keep dashboards clean; debug fast)

This is the “what to do when something looks off” playbook. The dashboards are intentionally kept **low-noise**; use these steps to drill down quickly and consistently.

### 0) First sanity checks (before you trust any chart)
- **Correct project**: make sure you’re on the `Pseuno` project (not “Default project”).
- **Environment filter**: if you’re investigating production, add `environment = prod`.
- **Indexing delay**: new events/properties can take a bit to appear in dropdowns / breakdown menus.

### 1) Triage: is it reliability, performance, or value?
Start on `Core Health (Exec)`:
- If **`generate_failed` spikes** → go to “Failures”.
- If **latency p95 spikes** → go to “Latency”.
- If **`output_used` drops** but generates are stable → likely a UX/value-extraction issue → go to “Output / Export Behavior”.

### 2) Failures (where are users dropping?)
Use these standard breakdowns/filters:
- **Breakdown**: `auth_state` to see if it’s guest-only vs Spotify-only.
- **Breakdown**: `error_type` (keep `error_type` low-cardinality; don’t rely on raw exception strings).
- **Filter out test noise**:
  - If you’re running smoke scripts, exclude `seed_id is set` (or `seed_id != *` depending on UI).

Then pivot to the relevant dashboard:
- Generate failures → `Core Health (Exec)` + `Backend LLM + Repair (Obs)` (if backend failures rose too)
- Clipboard failures → `Output / Export Behavior`
- Edit/refine failures → `Iteration (Refine + Manual Edit)`
- Library failures (delete/reorder/new lyrics in style) → `Library Engagement`

### 3) Proving causality: “did output_used come from THIS generation?”
Prefer using correlation properties instead of time-window guessing:
- **`flow_id`**: links a single draft flow (randomize → generate → output usage) or a refine/edit attempt.
- **`origin_action`** on `output_used` / `suno_link_clicked` / clipboard events:
  - `generate` vs `style_refine` vs `lyrics_ai_edit` vs `unknown`
- **`origin_mode`**:
  - `generated` means value usage happened from the currently generated draft
  - `loaded` means user loaded an older style/song and used output from there

Practical drill-down:
- From an `output_used` trend, add filter `origin_mode = generated` to measure “direct from generation”.
- If you want “direct from refine”, filter `origin_action = style_refine` (or `lyrics_ai_edit`).

### 4) Prompt quality / tags deep-dive (keep it out of exec)
Use `Prompt Quality (Tags)` when you’re investigating:
- which tag buckets create the most successful generations
- which tag buckets lead to the most `output_used`
- whether randomizers are being used (`used_randomize_style` / `used_randomize_lyrics`)

Important: we intentionally **do not** send raw user tags as properties (too high-cardinality). We bucket into a curated set + `other`.

### 5) Backend/LLM debugging loop
Use `Backend LLM + Repair (Obs)`:
- **Failures**: breakdown by `operation` + `error_type`
- **Latency**: p95 by `operation`
- **Repairs**: watch `repair_agent_invoked`/`validated` and `fixed`

### 6) When the UI lies (common PostHog quirks)
- **Live events missing**: events may still be ingesting—use the Events table and query endpoints, and check filters.
- **Property exists but not breakdown option yet**: indexing delay; wait or trigger events again.
- **Dashboards look like JSON**: saved insight payload needs an `InsightVizNode` wrapper (handled by `scripts/posthog_dashboards.py`).

## E2E “telemetry truth” tests (Playwright)

To verify that real UI actions emit the correct PostHog events + required properties (without relying on PostHog’s ingestion/batching), we ship a Playwright test that:
- stubs backend API responses (deterministic; no LLM calls)
- wraps `window.posthog.capture` (dev-only exposure) to record emitted events

Run:

```bash
cd frontend
npm run test:e2e
```

### Environment variables (backend)
- `POSTHOG_API_KEY`: PostHog project API key (same project as frontend)
- `POSTHOG_HOST`: PostHog host (e.g. `https://us.i.posthog.com`)
- `APP_ENV`: `dev|prod` (used as `environment` property)

Configured in `docker-compose.dev.yml` under `backend.environment`.

### Events

- `llm_call`
  - **Purpose**: latency + reliability per internal LLM step
  - **Properties**:
    - `operation` (examples): `song.generate`, `song.repair`, `style.generate`, `style.repair`, `lyrics.generate`, `lyrics.repair`, `lyrics.profile_infer`, `style.genre_disambiguate`, `title.generate`, `style.name_generate`, `refine.planner`, `refine.call`
    - `provider`: `openai|gemini`
    - `model`
    - `duration_ms`
    - `status`: `succeeded|failed`
    - `error_type` (when failed)
    - `variant_id` (when applicable)
    - `architecture`: `single_step|two_step|unified_refine|refine_service`
    - `is_repair` + `repair_kind` + `attempt` (for repair loops)

- `repair_agent_invoked`
  - **Purpose**: how often repair is called and *why*
  - **Properties**:
    - `repair_kind`: `song|style|lyrics`
    - `attempt`
    - `issues_count`
    - `issue_category` (low-cardinality, derived from validation issues)
    - `variant_id`, `architecture`, `model`

- `repair_agent_validated`
  - **Purpose**: did the repair fix validation?
  - **Properties**:
    - `repair_kind`, `attempt`
    - `fixed` (bool)
    - `pre_issues_count` / `pre_issue_category`
    - `post_issues_count` / `post_issue_category`
    - `variant_id`, `architecture`

**Core properties** (low-cardinality, attached to most events):
- `auth_state`: `guest|spotify`
- `page`: `new_song|song_view`
- `flow`: `auth|generate|refine|library`
- `environment`: `dev|prod` (auto-attached via super property)
- `duration_ms`: user-perceived wait time for generate/refine

**Dashboards to build**:
- Funnel: `page_view(new_song) → generate_clicked → generate_succeeded`
- Funnel: `auth_login_clicked → auth_login_succeeded → generate_succeeded`
- Trend: `generate_failed` rate
- Distribution: `duration_ms` (generate/refine)

**Prove value**:
- Within a day of traffic, we can answer “where do users drop?” and “how long do they wait?”

### Phase 2 — Feature flags + experiments
**Goal**: ship safely and measure impact.

Good first flags for this app:
- `new_song_default_personalize_on`
- `show_advanced_controls_default`
- `new_song_tag_recs_layout`
- `refine_wait_message_threshold`

**Prove value**:
- Ship one change behind a flag, measure effect on conversion/time-to-first-success.

### Phase 3 — Error tracking (only if needed)
**Goal**: quantify breakage users experience.
- Frontend: use PostHog error tracking if it’s actionable.
- Backend: prefer **structured events** like `api_error` for key endpoints with `status_code` and `error_type`.

**Prove value**:
- Error tracking reduces time-to-detection and correlates to user drop-off.

### Phase 4 — Session replay (only when events can’t answer)
**Goal**: solve a specific UX mystery (drop-off you can’t explain with events).
- Mask inputs by default.
- Sample aggressively.

**Prove value**:
- Watching replays leads directly to concrete fixes.

### Phase 5+ (optional): LLM analytics, surveys, data warehouse
- **LLM analytics**: add only if you’re actively improving latency/failure.
- **Surveys**: add only when you have enough traffic and a hypothesis.
- **Data warehouse**: defer until you truly need joins with external business data.

## Where integrations should live (repo)

- Frontend init: `frontend/src/main.tsx`
- Key UI flows:
  - `frontend/src/App.tsx` (auth state transitions, routing between views)
  - `frontend/src/components/NewSongView.tsx` (generate flow + wait notice)
  - `frontend/src/components/WorkingPromptPanel.tsx` (refine + library actions)
- Backend endpoints:
  - `backend/app/routes/generate_advanced.py`
  - `backend/app/routes/refine.py`
  - `backend/app/routes/auth.py`
  - `backend/app/routes/spotify.py`

## Implementation plan reference

See the plan file: `/Users/calder/.cursor/plans/posthog-only_monitoring_05bddcd7.plan.md`


