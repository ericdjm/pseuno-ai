# PostHog Runbook (Pseuno AI)

Copy/paste this into Notion. This is the operational guide for **debugging analytics**, **rolling out new events/properties**, and **keeping dashboards accurate** using our automation (smoke events, dashboard scripts, Playwright “truth tests”).

---

## Principles (don’t skip)

- **Track decisions, not trivia**: prefer “state change” events (generate succeeded, output used, delete style) over noisy micro-events.
- **Keep properties low-cardinality**: booleans, small enums, small buckets. Avoid raw prompt text, full tag lists as *breakdowns*, full error strings.
- **No sensitive text in properties**: don’t send lyrics/prompt/email.
- **Dev/prod in one PostHog project**: everything must be filterable by `environment`.

---

## What we standardize on (event contract conventions)

### Required “core” properties

These should be present on almost all frontend events (either explicitly or via shared helpers):

- `environment`: `dev|prod|unknown` (super property)
- `auth_state`: `guest|spotify`
- `flow`: `auth|generate|style_create|library|…` (small set)
- `page`: `new_song|song_view|…`
- `client_session_id` (frontend helper)
- `client_time_ms` (frontend helper)

### Required properties for outcomes

- **Any `*_failed` event** must include:
  - `error_type` (low-cardinality string like `NetworkError`, `TimeoutError`, `validation_failed`, `updates_not_persisted`)
- **Any `*_succeeded` event with latency** should include:
  - `duration_ms` (number)

### Causality / attribution properties (high leverage)

Use these to answer “did this output come from *this* generation?” without guessing with time windows:

- `flow_id`: correlates a single user journey (randomize → generate → output, or refine attempt)
- `origin_mode` on value-use events: `generated|loaded|new`
- `origin_action` on value-use events: `generate|style_refine|lyrics_ai_edit|unknown`
- `prompt_generation_id` when available (ties UI generation to backend result)

---

## Daily debugging workflow (fast triage)

### Step 0 — sanity checks (90 seconds)

- **Correct PostHog project**: ensure you’re in `Pseuno` (not “Default project”).
- **Environment filter**:
  - investigating prod → add filter `environment = prod`
  - investigating dev noise → add filter `environment = dev`
- **Indexing delay**: new event names/properties can take minutes to appear in dropdowns / breakdown selectors.

### Step 1 — determine the failure class

- **Nothing in Live Events**:
  - events can still be ingesting; Live Events is not a ground truth source
  - use Events list + query validation (below)
- **Events exist, but dashboards empty**:
  - dashboard filters wrong (usually `environment`)
  - event renamed without backfill/compat
  - property not being sent (instrumentation bug)
- **Breakdown property not selectable**:
  - property not indexed yet; trigger more events and wait
  - property is high-cardinality or wrong type

### Step 2 — confirm “are we sending?”

Pick one:

- **Frontend**: open DevTools → Network → look for PostHog `/e/` or `/capture/` calls returning `200`.
- **Backend**: check backend logs (we fire-and-forget; failures won’t block requests).

### Step 3 — confirm “is PostHog ingesting?”

Use our smoke script (most reliable, because it creates a unique `seed_id`):

```bash
cd /Users/calder/pseuno-ai
set -a && source backend/.env && set +a
python3 scripts/posthog_smoke_events.py
```

- Output includes `seed_id=...`
- It will poll PostHog query API; **indexing delay is normal**

If the smoke script says ingest is ok, but UI looks wrong, it’s almost always **filters** or **indexing delay**.

---

## Rolling out a new event or property (the correct way)

This is the repeatable workflow to avoid “we shipped metrics but they’re wrong.”

### 1) Add the event/property in code

- **Frontend events** live behind helpers in `frontend/src/analytics.ts`
  - Add a typed tracker function or extend an existing one.
  - Prefer adding derived/bucketed properties (enums/buckets), not raw text.
- **Backend events** use `backend/app/services/posthog_capture.py`
  - Keep `error_type` low-cardinality (map exceptions → stable labels).

### 2) Decide property strategy (avoid cardinality traps)

**Good patterns**
- Buckets: `tags_count_bucket: 0|1|2|3|4+`
- Curated buckets: `tag_buckets: ['electronic','hip-hop','other']`
- Booleans: `personalize_enabled`, `instrumental_intended`

**Be careful**
- Raw arrays like `tags_selected` are OK for **HogQL queries**, but not great for breakdowns.
- Raw user-entered strings are usually a mistake for analytics.

### 3) Update smoke events so PostHog “learns” the new schema

Edit:
- `scripts/posthog_smoke_events.py`

Run:

```bash
cd /Users/calder/pseuno-ai
set -a && source backend/.env && set +a
python3 scripts/posthog_smoke_events.py
```

If you need to validate properties for a `seed_id`:
- `scripts/posthog_validate_seed.py` (useful when indexing delay makes the UI confusing)

### 4) Update dashboards programmatically

We manage dashboards via:
- `scripts/posthog_dashboards.py`

Run:

```bash
cd /Users/calder/pseuno-ai
set -a && source backend/.env && set +a
python3 -u scripts/posthog_dashboards.py ensure-all
```

Notes:
- This script also runs each query via `/query/` so you catch broken tiles early.
- If you get throttled (`HTTP 429`), wait and rerun later (hosted PostHog rate limits).

### 5) Add/extend Playwright telemetry truth tests (frontend)

Purpose: verify **UI actions → PostHog events** deterministically (no PostHog ingestion dependency).

- Tests live in `frontend/tests/e2e/`
- Helpers in `frontend/tests/e2e/posthog_helpers.ts`

Run:

```bash
cd /Users/calder/pseuno-ai/frontend
npm run test:e2e
```

What to add in tests:
- For each new event, assert:
  - event name is captured
  - required props are present (`auth_state`, `flow`, `page`, `flow_id` when applicable)
  - outcome events include `duration_ms` / `error_type` as appropriate

---

## How to build new dashboard tiles (the repeatable playbook)

### A) Prefer automation-first

If the tile is “core and repeatable,” implement it in:
- `scripts/posthog_dashboards.py` (so it stays consistent across environments and future refactors)

### B) Validate “does it work?”

Before you trust a tile:

1. Send smoke events (so the event exists, and so you can filter by `seed_id`).
2. Run `ensure-all` to create/update the tile and verify `/query/` returns data.
3. In PostHog UI, apply:
   - `environment = prod` (for prod dashboards)
   - exclude smoke noise if needed (`seed_id is not set`)

### C) When you need raw array visualizations (tags, etc.)

PostHog doesn’t “nicely” visualize arrays via standard breakdowns. Use **HogQL** tiles:

- Unnest arrays with `arrayJoin(...)`
- Create top-N tables/bars (e.g., top 15 tags)

We already support saving HogQL insights in the automation by using a `DataVisualizationNode`.

---

## Common PostHog gotchas (and the fix)

### “Live Events shows nothing”

- Live Events is not reliable ground truth.
- Confirm with:
  - Network `200` responses to capture endpoints
  - smoke script + query polling
  - Events list filtered by `environment`

### “I can filter by a property but can’t use it as breakdown”

- Indexing delay (wait + send more events)
- Property type mismatch (string vs number vs bool)

### “Dashboards show JSON instead of charts”

- Saved insight query node is wrong.
- Our automation wraps normal insights in `InsightVizNode` (charts) and uses `DataVisualizationNode` for HogQL.

### “We renamed events and now dashboards are empty”

- Keep **compat series** temporarily (query both old and new events) until enough new data exists.
- Example approach: query legacy `refine_*` with `refine_type` alongside new `style_refine_*`/`lyrics_ai_edit_*`.

### “Rate limit / throttled (HTTP 429)”

- Hosted PostHog throttles API calls.
- Wait and rerun `ensure-all`. Avoid tight loops.

---

## Repo map (where to change what)

### Frontend

- PostHog init: `frontend/src/main.tsx`
- Event helpers: `frontend/src/analytics.ts`
- New song flow: `frontend/src/components/NewSongView.tsx`
- Working prompt + refine + output: `frontend/src/components/WorkingPromptPanel.tsx`
- Library sidebar actions: `frontend/src/components/PromptLibrarySidebar.tsx`

### Backend

- PostHog capture helper: `backend/app/services/posthog_capture.py`
- FastAPI lifespan shutdown hook: `backend/app/main.py`

### Automation

- Create/update dashboards: `scripts/posthog_dashboards.py`
- Send smoke events: `scripts/posthog_smoke_events.py`
- Validate a seed’s schema: `scripts/posthog_validate_seed.py`
- Audit dashboards for data presence: `scripts/posthog_audit_dashboards.py`
- Playwright telemetry truth tests: `frontend/tests/e2e/*`

---

## Environment variables (quick reference)

### Frontend (Vite)

- `VITE_POSTHOG_KEY` (public project key, `phc_...`)
- `VITE_POSTHOG_HOST` (ingest host, e.g. `https://us.i.posthog.com`)
- `VITE_APP_ENV` (`dev|prod`)

### Backend

- `POSTHOG_HOST` (API host, e.g. `https://us.posthog.com`)
- `POSTHOG_PROJECT_ID` (numeric project id)
- `POSTHOG_PERSONAL_API_KEY` (private personal key; used by automation scripts)
- `POSTHOG_API_KEY` or `POSTHOG_PROJECT_API_KEY` (project key for backend event capture)

