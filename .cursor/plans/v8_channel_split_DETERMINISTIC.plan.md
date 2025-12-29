## V8 Channel Split — Verbose, deterministic, interactive plan (with stop/commit gates)

### Why this doc exists

We’re fixing a specific failure mode: when a user asks for “Singer/voice of X over the music of Y”, the style model tends to leak X’s **genre/instrumentation/production** into the final Suno prompt. The V8 approach is:

- **Split** style guidance into two channels: **VOCAL_REFERENCE** vs **MUSIC_TARGET**
- **Enforce** a strict “no cross-contamination” contract in the style context
- **Be deterministic**: when in doubt, **do not split**

This plan is intentionally **interactive**: every small step ends in **STOP → manually confirm → commit to `main`** so we can correct course early.---

## Global invariants (non-negotiable)

- **Never guess roles**:
- If we can’t confidently identify *both* a vocalist reference and a music target, we do **no split**.
- **Deterministic precedence**:
- Prefer **schema-based role detection** (LLM outputs `role`) → fall back to **high-confidence regex** → else **none**.
- **No behavioral surprises**:
- V8 is **opt-in** until we validate it on known leakage prompts.
- **Manual checkpoints**:
- After each step: STOP, confirm the acceptance criteria, then commit.

---

## Deterministic conventions (use these everywhere)

### Artist name normalization (used for equality + matching)

**Goal**: determine whether two “artist names” are effectively the same string, without being clever.

- Normalize by:
- trimming whitespace
- lowercasing
- replacing `&` with `and`
- collapsing all whitespace runs to a single space
- stripping surrounding punctuation
- Do **not** attempt fuzzy matching in V8 (that can silently mis-route roles). If the strings don’t match after normalization, treat them as different.

### V8 constants (make them explicit in code)

- `V8_ROLE_CONFIDENCE_THRESHOLD = 0.7`
- `V8_REGEX_ENABLED = True` (so we can disable regex fallback without removing code)
- `V8_SPLIT_ENABLED_VARIANTS = {"v8_channel_split"}`

---

## Interactive TODO checklist (do these in order)

### Step 0 — Pre-flight sanity check (no code changes)

- [ ] **TODO**: Identify the exact MAX-header injection site and validation rule (anchors below) and confirm they match the plan.
- [ ] **STOP**: Confirm you agree with the implementation choice for V5 prose budgeting:
- Preferred: **retire** `SUNO_PROMPT_MAX_CHARS_V5_PROSE` and use `SUNO_PROMPT_MAX_CHARS`
- Minimal churn: keep constant but set to 500 (not preferred)
- [ ] **COMMIT**: *No commit* (this is a read-only step).

#### Code anchors (confirmed in repo)

- **MAX header prepending**: `backend/app/services/agent_prompt_graph.py` `_generate_parallel_two_step()` block for:
- `v5_hybrid`, `v6_genre_disambiguation`, `v7_genre_term_disambiguation`
- **Validation rule to remove/replace**: `backend/app/services/agent_prompt_graph.py` `_validate_style_output()` currently flags:
- “SUNO PROMPT has MAX headers but missing structured format …”
- **V5 prose cap constant**: `backend/app/constants.py` has `SUNO_PROMPT_MAX_CHARS_V5_PROSE = 400`
- **V5 prose spec text**: `backend/app/prompts/specs.py` `SUNO_PROMPT_SPEC_V5` says:
- “≤{SUNO_PROMPT_MAX_CHARS_V5_PROSE} (headers added automatically)”
- **Variant docs impacted**:
- `backend/app/prompts/variants/v5_hybrid.py`
- `backend/app/prompts/variants/v6_genre_disambiguation.py`
- `backend/app/prompts/variants/v7_genre_term_disambiguation.py`

---

## Phase 0 — Remove MAX headers for V5+ (global behavior change; many things can break)

### Phase 0 objective

Make **all V5+ variants** (currently V5/V6/V7, and future V8+) use the full **500 characters** and never auto-prepend MAX headers after style generation.This phase is split into multiple small commits on purpose.

### Step 0.1 — Remove MAX-header prepend in `_generate_parallel_two_step()`

- [ ] **TODO**: Edit `backend/app/services/agent_prompt_graph.py`:
- Remove the entire “prepend MAX headers” block for V5/V6/V7.
- [ ] **Acceptance criteria**:
- No code path prepends [`IS_MAX_MODE: MAX`](MAX) to the returned `suno_prompt`. (Search for the literal string [`IS_MAX_MODE: MAX`](MAX); it should not appear.)
- [ ] **STOP**: Manually re-read the function and confirm no other location prepends headers.
- [ ] **COMMIT to main**: `chore: remove MAX header prepending for V5+`

### Step 0.2 — Retire V5 prose cap constant (or set to 500) and update V5 prose spec

- [ ] **TODO**: Update `backend/app/constants.py`:
- Preferred: remove/retire `SUNO_PROMPT_MAX_CHARS_V5_PROSE` and use `SUNO_PROMPT_MAX_CHARS` everywhere.
- [ ] **TODO**: Update `backend/app/prompts/specs.py`:
- Change `SUNO_PROMPT_SPEC_V5` to enforce `≤{SUNO_PROMPT_MAX_CHARS}`.
- Remove “headers added automatically”.
- [ ] **Acceptance criteria**:
- V5 prose spec no longer implies any post-processing header injection.
- There is exactly one Suno prompt character budget for prose outputs: 500.
- [ ] **STOP**: Ensure no other specs/variants still claim “400 chars because MAX headers”.
- [ ] **COMMIT to main**: `docs/spec: unify V5 prose prompt cap to 500`

### Step 0.3 — Replace validation rule to match new reality (no “structured format” requirement)

- [ ] **TODO**: Update `backend/app/services/agent_prompt_graph.py` `_validate_style_output()`:
- Remove “MAX headers but missing structured format” logic.
- Replace with: if Suno prompt contains `"[IS_MAX_MODE"` (case-insensitive), it is invalid and must be repaired to remove MAX headers.
- Do **not** enforce structured `genre:/instruments:` fields for prose variants.
- [ ] **Acceptance criteria**:
- Prose prompts are valid without structured fields.
- MAX headers are rejected universally post-Phase-0.
- [ ] **STOP**: Re-check that V2 structured variants aren’t unintentionally harmed.
- [ ] **COMMIT to main**: `fix: update style validation after MAX header removal`

### Step 0.4 — Fix variant docs/comments that now lie

- [ ] **TODO**: Update docs/comments in:
- `backend/app/prompts/variants/v5_hybrid.py`
- `backend/app/prompts/variants/v6_genre_disambiguation.py`
- `backend/app/prompts/variants/v7_genre_term_disambiguation.py`
- Remove references to “prepend MAX headers” and “400 char limit because headers”.
- [ ] **Acceptance criteria**:
- No variant doc claims headers are added automatically.
- [ ] **STOP**: Grep for “prepend MAX headers” / “headers added after” and confirm it’s cleaned up.
- [ ] **COMMIT to main**: `docs: remove outdated MAX-header references in V5–V7 docs`

### Step 0.5 — Manual validation checkpoint (required)

- [ ] **TODO**: Manually generate once each using:
- `v5_hybrid`
- `v6_genre_disambiguation`
- `v7_genre_term_disambiguation`
- [ ] **Acceptance criteria**:
- Returned `suno_prompt` contains **no** `[IS_MAX_MODE: MAX]` lines
- `suno_prompt` can reach close to **500** characters
- No DebugTrace validation errors tied to MAX headers
- [ ] **STOP**: If anything looks off, fix before moving to Phase 1.
- [ ] **COMMIT to main**: `test: verify V5–V7 generations after MAX-header removal`

---

## Phase 1 — Introduce V8 as a new opt-in variant (no split behavior yet)

### Step 1.1 — Add backend variant file `v8_channel_split` (scaffolding only)

- [ ] **TODO**: Create `backend/app/prompts/variants/v8_channel_split.py`:
- Clone structure from `v7_genre_term_disambiguation.py`.
- Register as `id="v8_channel_split"`.
- `is_default=False`.
- For now, it can still point to V7’s genre disambiguation prompt until Phase 2 (we will swap to V3 later).
- [ ] **Acceptance criteria**:
- `/generate/prompt-variants` includes `v8_channel_split`.
- [ ] **STOP**: Confirm V8 is visible but not default.
- [ ] **COMMIT to main**: `feat: add v8_channel_split variant scaffold (opt-in)`

### Step 1.2 — Update API types (backend + frontend)

- [ ] **TODO**: Add `"v8_channel_split"` to:
- `backend/app/schemas/advanced.py` PromptVariant union
- `frontend/src/api.ts` PromptVariant union
- [ ] **Acceptance criteria**:
- Frontend compiles with the new union value
- Backend accepts requests specifying `prompt_variant="v8_channel_split"`
- [ ] **STOP**: Confirm no other code assumes variants stop at v7.
- [ ] **COMMIT to main**: `chore: plumb v8_channel_split through backend/frontend types`

### Step 1.3 — Manual checkpoint: V8 parity (no split yet)

- [ ] **TODO**: Manually run one generation using `v8_channel_split`.
- [ ] **Acceptance criteria**:
- Output looks similar to V7 (since we haven’t added split logic yet)
- No crashes / schema issues
- [ ] **STOP**: Do not proceed until V8 is stable as a variant entry.
- [ ] **COMMIT to main**: `test: confirm v8_channel_split baseline parity`

---

## Phase 2 — Deterministic split implementation (role schema → regex fallback → none)

### Glossary (used everywhere below)

- **MUSIC_TARGET**: the artist whose genre/instrumentation/arrangement/production we emulate
- **VOCAL_REFERENCE**: the artist whose vocal timbre/range/delivery we emulate (voice-only)
- **Split active**: we have exactly one of each, confidently

### Step 2.1 — Add a V8/V3 genre-disambiguation agent prompt (schema extension with roles)

- [ ] **TODO**: Add `GENRE_DISAMBIGUATION_AGENT_V3` to `backend/app/prompts/specs.py` derived from `..._V2` but with:
- per-artist fields:
- `role`: `"music_target" | "vocal_reference" | "unspecified"`
- `role_confidence`: 0.0–1.0
- `role_evidence`: short string
- hard rules:
- only set a non-`unspecified` role when explicitly supported by user text
- if ambiguous: `unspecified`
- do not infer gender/personnel (that’s V9+)
- [ ] **Acceptance criteria**:
- Prompt text explicitly documents when roles must be `unspecified`
- Schema example is included in the prompt so the model is guided
- [ ] **STOP**: Re-read the schema and ensure it’s additive (doesn’t break V7 parsing).
- [ ] **COMMIT to main**: `feat: add GENRE_DISAMBIGUATION_AGENT_V3 with role fields (V8)`

#### Example (for the prompt text)

Expected V3 JSON fragment for: “Lead singer of Steel Panther singing for TOOL”

- `Steel Panther`: role=`vocal_reference`
- `TOOL`: role=`music_target`

#### Concrete schema example (include something like this in the V3 prompt)

This is the shape we want, conceptually:

- `artists[].role` is only non-`unspecified` when the user phrasing supports it
- `role_confidence` is conservative (when in doubt: low confidence + `unspecified`)

### Step 2.2 — Wire V8 to use V3 (still no split formatting)

- [ ] **TODO**: Update `backend/app/prompts/variants/v8_channel_split.py`:
- Set `genre_disambiguation_agent=GENRE_DISAMBIGUATION_AGENT_V3`
- [ ] **Acceptance criteria**:
- V8 uses V3 prompt, V7 still uses V2
- [ ] **STOP**: Confirm no other variants unintentionally switched.
- [ ] **COMMIT to main**: `feat: wire v8_channel_split to genre disambiguation V3`

### Step 2.3 — Add V8 split plumbing in small, verifiable increments

This is the riskiest part; break it into multiple commits.

#### Step 2.3a — Add constants + normalization helper

- [ ] **TODO**: Add the constants listed above (threshold, regex enabled flag).
- [ ] **TODO**: Implement `_normalize_artist_name_v8(name: str) -> str`.
- [ ] **Acceptance criteria**:
- Helper is deterministic and covered by unit tests later.
- [ ] **STOP**: Confirm the helper does not attempt fuzzy matching.
- [ ] **COMMIT to main**: `feat: add v8 split constants + artist normalization helper`

#### Step 2.3b — Schema-based split decision (roles only; no regex yet)

- [ ] **TODO**: Implement `_decide_style_split_v8_from_roles(genre_data) -> SplitDecision`:
- Find exactly one `music_target` and one `vocal_reference`
- Require both confidences ≥ threshold
- Require normalized names differ
- Else return `split_active=False`
- [ ] **Acceptance criteria**:
- Ambiguity results in `split_active=False`
- [ ] **STOP**: Manually inspect DebugTrace artifacts from genre disambiguation to confirm roles appear when expected.
- [ ] **COMMIT to main**: `feat: implement v8 schema-based split decision (roles-only)`

#### Step 2.3c — Regex fallback (high-confidence patterns only; gated by flag)

- [ ] **TODO**: Implement `_decide_style_split_v8_from_regex(style_request) -> SplitDecision` (used only if roles don’t produce a confident split and `V8_REGEX_ENABLED` is true).
- [ ] **Regex patterns (ordered, high-confidence only)**:
- `lead singer of X ... (singing|vocals) ... (for|over|with) Y`
- `vocals (like|by) X ... (over|with) Y (instrumentation|music|track)`
- `X-style vocals ... (music|composition|arranged) (like|as) Y`
- `instrumentation (of|like) Y ... vocals (by|like) X`
- [ ] **Hard failure rules**:
- If regex matches but yields only one side: fail → no split.
- If regex yields multiple candidates per side: fail → no split.
- [ ] **Acceptance criteria**:
- Regex never produces a split unless it found both sides and exactly one pair.
- [ ] **STOP**: Run a few edge cases (“X meets Y”, “Blend X and Y”) and confirm it stays no-split.
- [ ] **COMMIT to main**: `feat: add v8 regex fallback for split decision (high-confidence only)`

#### Step 2.3d — Unify decision function + add DebugTrace span

- [ ] **TODO**: Implement:
- `self._decide_style_split_v8(style_request, selected_artists, genre_data) -> SplitDecision`
- precedence: roles → regex → none
- emit DebugTrace span `style.split` capturing:
- `split_active`, `music_target_artist`, `vocal_reference_artist`, `source`, `role_confidence`
- [ ] **Acceptance criteria**:
- DebugTrace always includes the `style.split` span for V8 runs
- `source` is one of: `role_schema`, `regex`, `none`
- [ ] **STOP**: Manually inspect one V8 run and confirm split metadata looks correct.
- [ ] **COMMIT to main**: `feat: add v8 split decision orchestration + debug trace span`

### Step 2.4 — Implement V8 style context formatter (enforces anti-leakage contract)

- [ ] **TODO**: Add `_format_style_context_v8(...)` in `agent_prompt_graph.py` and use it in `_run_style_branch()` when `ctx.variant_id == "v8_channel_split"`.
- [ ] **When split is active, the user message MUST include**:
- A **MUSIC_TARGET** block and a **VOCAL_REFERENCE** block
- A hard rule: “genre/instruments/arrangement/production MUST come from MUSIC_TARGET only”
- A hard rule: “VOCAL_REFERENCE is voice-only; do not borrow genre/instrumentation/production”
- [ ] **Acceptance criteria**:
- DebugTrace `style.generate` shows the final style context with the two blocks
- If split inactive, the context falls back to the existing V6/V7 style context format
- [ ] **STOP**: Run the known failure prompt and manually verify the blocks are correct.
- [ ] **COMMIT to main**: `feat: v8 style context formatter with MUSIC_TARGET vs VOCAL_REFERENCE contract`

#### Concrete expected style context example (Steel Panther vocals → TOOL music)

This is intentionally verbose; the style model should not be able to misinterpret which side controls what:

```text
Generate SUNO PROMPT, EXCLUDE, WEIRDNESS, and STYLE INFLUENCE for:
  style_request: Lead singer of Steel Panther singing for TOOL
  reference_artists: ["Steel Panther", "TOOL"]
  tags: []

═══════════════════════════════════════════════════════════════════════════════
MUSIC_TARGET (AUTHORITATIVE for genre / instrumentation / arrangement / production)
═══════════════════════════════════════════════════════════════════════════════
ARTIST: TOOL
USE FOR: genre, instruments, arrangement, dynamics, production texture
DO NOT USE FOR: vocal timbre/range/delivery

GENRE / VOCAB / INSTRUMENT GUIDANCE (do not copy verbatim; translate into Suno-friendly prose):
  GENRE_TARGETS: ...
  GENRE_AVOID: ...
  VOCAB_TO_USE: ...
  VOCAB_TO_AVOID: ...
  INSTRUMENTS_TO_USE: ...
  INSTRUMENTS_TO_AVOID: ...

HARD RULE: All non-vocal musical content MUST be derived from MUSIC_TARGET only.

═══════════════════════════════════════════════════════════════════════════════
VOCAL_REFERENCE (VOICE-ONLY: timbre / register / delivery)
═══════════════════════════════════════════════════════════════════════════════
ARTIST: Steel Panther
USE FOR: vocal timbre/tone, vocal register, delivery style
DO NOT USE FOR: genre, instrumentation, arrangement, production aesthetic

VOCAL GUIDANCE (voice-only; do not introduce band/genre facts):
  VOCAL_STYLE_TO_USE: ...
  VOCAL_STYLE_TO_AVOID: ...

HARD RULE: Do NOT borrow genre/instruments/production from VOCAL_REFERENCE.
```



### Step 2.5 — Role-aware genre guidance routing (do not reuse `_format_genre_context_section()` for V8)

- [ ] **TODO**: For V8 only, inject genre guidance into the correct block:
- MUSIC_TARGET gets full V7-style guidance (genres/not_genres/terms/instruments)
- VOCAL_REFERENCE gets only vocal guidance fields (vocal_style_to_use / avoid)
- [ ] **Acceptance criteria**:
- VOCAL_REFERENCE block does not include instruments/genre lists even if present in genre_data
- MUSIC_TARGET block is rich and actionable
- [ ] **STOP**: Inspect DebugTrace style context and confirm the routing is correct.
- [ ] **COMMIT to main**: `feat: route genre guidance by role into V8 split blocks`

### Step 2.6 — Manual checkpoint: leakage regression test (interactive)

- [ ] **TODO**: Manually test these prompts using `v8_channel_split`:
- “Lead singer of Steel Panther singing for TOOL”
- “Flipturn vocals with Richy Mitch & The Coal Miners instrumentation”
- [ ] **Acceptance criteria**:
- DebugTrace shows correct split and correct block routing
- Generated Suno prompt does not drift instrumentation/genre toward the vocalist band
- [ ] **STOP**: If leakage persists, adjust contract wording (not heuristics first).
- [ ] **COMMIT to main**: `test: validate v8 channel split on leakage prompts`

---

## Phase 3 — Test fixtures + automated checks (so future changes don’t regress V8)

### Step 3.1 — Add prompt_lab fixtures (manual runs only)

- [ ] **TODO**: Add `backend/prompt_lab/test_cases/test_cases_v8_channel_split.json` with:
- at least 6 cases:
    - singer-for-band phrasing
    - vocals-over-instrumentation phrasing
    - ambiguous “X meets Y” (expects no split)
    - vocalist+vocalist (expects no split)
    - multi-vocalist reference (expects no split)
    - same-artist both sides (expects no split)
- [ ] **STOP**: Do not run `prompt_lab.py` automatically; run manually when you want.
- [ ] **COMMIT to main**: `testdata: add prompt_lab cases for v8 channel split`

### Step 3.2 — Add pytest unit tests for the deterministic pieces

- [ ] **TODO**: Add `backend/tests/test_v8_channel_split.py`:
- normalization tests
- decision tree tests (schema-based, regex fallback, none)
- formatter output tests (contains required prohibitions when split is active)
- [ ] **Acceptance criteria**:
- Tests are deterministic (no network, no LLM calls)
- [ ] **STOP**: Run tests and ensure green.
- [ ] **COMMIT to main**: `test: add deterministic unit tests for v8 split decision + formatting`

### Step 3.3 — Final interactive checkpoint (decide rollout)

- [ ] **TODO**: Decide whether to keep V8 opt-in or set it as default.
- [ ] **STOP**: If making default, do it in its own commit.
- [ ] **COMMIT to main** (optional): `chore: set v8_channel_split as default variant`

---

## Optional follow-ups (explicitly out of scope for V8)

### V11 — “Comprehensive EXCLUDE” variant (A/B)

- Saved prompts currently cap `exclude` at `SUNO_EXCLUDE_MAX_CHARS = 100` (`backend/app/constants.py`) and schema enforcement exists (see `backend/app/schemas/prompts.py`).
- So a “long EXCLUDE” variant must choose one:
- **Allow saving long excludes** (global schema + DB constraints if any)
- **Truncate on save** (plan must specify truncation + user messaging)

### V9 — MusicBrainz grounding (separate PR)

Keep as a later variant (e.g., `v9_musicbrainz_grounded`) that:

- looks up vocalist metadata best-effort
- caches in Postgres