# Generation Timeout Audit & Fixes

## Problem

In production, users are intermittently getting **HTTP 500 errors** when generating songs. The backend logs show:

```
504 DEADLINE_EXCEEDED. {'error': {'code': 504, 'message': 'Deadline expired
before operation could complete.', 'status': 'DEADLINE_EXCEEDED'}}
```

---

## Root Cause: Google's Servers, Not Our Code

When you hit "generate," our backend fires off LLM calls to **Google Gemini** (`gemini-3-flash-preview`). Google's API has its own internal deadline — roughly 60 seconds. If their model hasn't finished generating a response within that window, **Google kills the request on their end** and sends back a `504 DEADLINE_EXCEEDED` error.

Our timeout increase from 60s → 120s (applied 2026-02-18) only controls how long **our client is willing to wait**. But Google kills it at ~60s on their side regardless. So bumping our timeout helped with cases where *our* client was giving up too early, but it doesn't fix the cases where Google itself is the one timing out.

### Is it a model issue? Yes, partially.

We're using `gemini-3-flash-preview` — a **preview model**. Three things matter:

1. **Preview models have lower reliability guarantees.** Google's preview/experimental models run on less provisioned infrastructure. They're more likely to hit capacity issues, cold starts, and deadline exceeded errors compared to GA (generally available) models.

2. **Flash models are supposed to be fast** — that's the whole point of "flash" vs "pro." But `gemini-3-flash-preview` is a pre-release version. Google may be tuning capacity, and it can have unpredictable latency spikes.

3. **Our prompts are large.** The style generation spec alone is massive (~1265 lines in `specs.py`). Large input = more processing time for the model. When Google's servers are under load, a large prompt is more likely to exceed their deadline.

### Why it doesn't happen every time

The 504 is **intermittent**. Most requests complete fine in 5-8 seconds. But when Google's servers are congested (high traffic periods, capacity rebalancing, etc.), the same request that normally takes 3 seconds might take 60+ seconds and get killed.

---

## The Pipeline & Where Time Goes

Each generation makes **up to 6 LLM calls**, arranged like this:

```
STYLE BRANCH (sequential)          LYRICS BRANCH (sequential)
─────────────────────────          ──────────────────────────
① genre_disambiguate  ~1-2s       ③ profile_infer    ~1-2s
        ↓                                  ↓
② style.generate      ~2-4s       ④ lyrics.generate   ~3-6s
        ↓                                  ↓
   [repair × 0-2]     ~2-4s ea       [repair × 0-2]   ~3-6s ea
        ↓
⑤ name_generate       ~0.5-1s
```

The two branches run **in parallel** (good), but within each branch, calls are **sequential** (each must wait for the previous one). So:

| Scenario | Critical Path | Total Wall Time |
|----------|--------------|-----------------|
| **Best case** (no repairs) | max(style ~5s, lyrics ~6s) | **~6-8s** |
| **Typical** (some slow calls) | max(style ~7s, lyrics ~8s) | **~8-12s** |
| **Worst case** (max repairs) | max(style ~13s, lyrics ~16s) | **~16-20s** |
| **Failure case** (Gemini overloaded) | Everything 3-5x slower | **~30-60s+ → 504** |

### LLM Call Details

| # | Call | Purpose | Model (default) | Parallel? | Retry? | Est. Latency |
|---|------|---------|-----------------|-----------|--------|-------------|
| ① | `genre_disambiguate` | Extract genres, era, instruments from artists | `gemini-3-flash-preview` | Sequential before ② | Best-effort (swallows errors) | ~1-2s |
| ② | `style.generate` | Generate SUNO PROMPT, EXCLUDE, WEIRDNESS, STYLE INFLUENCE | `gemini-3-flash-preview` | Parallel with lyrics branch | Repair loop: up to 2 retries | ~2-4s |
| ③ | `profile_infer` | Infer per-section lyric profiles (rhyme, line length, etc.) | `gemini-3-flash-preview` | Parallel with style branch | None | ~1-2s |
| ④ | `lyrics.generate` | Generate SONG TITLE + LYRICS with section tags | `gemini-3-flash-preview` | Parallel with style branch | Repair loop: up to 2 retries | ~3-6s |
| ⑤ | `name_generate` | Generate creative fusion genre name | `gemini-2.5-flash-lite` | Sequential after ② | None (failure returns empty) | ~0.5-1s |
| ⑥ | `style_classifier` | Classify style for lyrics topic routing | `gpt-4o-mini` | **Background** (non-blocking) | 10s timeout | ~0.5-1s |

### The Timeout Stack

| Layer | Current Value | Behavior |
|-------|--------------|----------|
| Gemini server-side deadline | ~60s (Google-controlled) | Returns 504 DEADLINE_EXCEEDED |
| `GeminiChatClient` HTTP timeout | 120s (`http_timeout × 1000` ms) | Our client's max wait |
| `refine_service` LLM timeout | 120s | For refine calls |
| Gunicorn worker timeout | 180s | Kills the whole worker if request takes >180s |
| nginx `proxy_read_timeout` | 120s | Returns 504 to browser if backend doesn't respond |

**The bottleneck is Google's ~60s server-side deadline**, not our timeout configs.

---

## Fixes

### Fix 1: Retry on Gemini 504 ✅ IMPLEMENTED

**What it does:** When Google returns a 504 DEADLINE_EXCEEDED, instead of immediately failing and showing the user an error, we wait 1-2 seconds and try the same call again.

**Why it works:** The 504 is usually a transient capacity issue. The next request often succeeds because it may land on a different server, or capacity has freed up. The OpenAI client (`OpenAIChatClient`) already does this — it retries once on `ReadTimeout`. But the Gemini client (`GeminiChatClient`) had **zero retry logic**. One failure = generation dead.

**Effect on generation:**
- Failed generations that return 500 → now succeed after a brief retry
- Adds ~1-2s delay only when there's a failure (no impact on successful requests)
- Doesn't help if Google is consistently overloaded (both attempts would fail)

**Files changed:** `backend/app/services/agent_prompt_graph.py` — `GeminiChatClient._sync_generate()`

---

### Fix 2: Trim prompt sizes (NOT YET IMPLEMENTED)

**What it does:** Our prompts are very large — the system instructions for style generation include the full spec with all rules, examples, validation criteria, etc. Shorter prompts mean fewer tokens for the model to process, which means faster responses.

**Why it matters:** LLM response time is roughly proportional to input + output tokens. A prompt that's 3,000 tokens will generally get a response faster than one that's 8,000 tokens. When Google's servers are under load, the difference between "finishes in 45s" and "finishes in 65s" (past their deadline) can be entirely due to prompt size.

**Effect on generation:** Faster responses across the board. Every request benefits, not just the failing ones. But requires careful editing to not lose important instructions.

**Files to change:** `backend/app/prompts/specs.py`

---

### Fix 3: Use a faster/lighter model for genre disambiguation (NOT YET IMPLEMENTED)

**What it does:** Genre disambiguation (call ①) currently uses `gemini-3-flash-preview` — the same model as the main style generation. But genre disambiguation is a simpler task (just extracting genre info from artist names). Using `gemini-2.5-flash-lite` (which we already use for title generation) would be faster and cheaper.

**Why it matters:** Genre disambiguation runs **sequentially before** style generation. If it takes 3s instead of 1s, that's 2 extra seconds before the main style call even starts. Every second matters when you're racing against a 60s deadline.

**Effect on generation:** Saves ~0.5-1s on every generation. Small but compounds with the other fixes. Reduces the chance of the style branch hitting the deadline.

**Files to change:** `backend/app/config.py` — `genre_disambiguation_model` default

---

### Fix 4: Make genre disambiguation non-blocking (NOT YET IMPLEMENTED)

**What it does:** Right now the pipeline is: `genre_disambiguate → wait for result → use result in style generation`. This means if genre disambiguation is slow (or fails), it delays everything.

Instead, we could start genre disambiguation and style generation at the same time. If genre disambig finishes fast, its result enriches the style call. If it's slow, we skip it and the style branch runs without it (it's already marked as "best-effort" — failures are swallowed).

**Effect on generation:** Removes ~1-2s from the critical path on every request. The style branch would start immediately instead of waiting. Genre enrichment would still apply most of the time (when it finishes before style does).

**Files to change:** `backend/app/services/agent_prompt_graph.py` — `_run_style_branch()`

---

### Fix 5: Increase Google's server-side timeout hint (NOT YET IMPLEMENTED)

**What it does:** The Google SDK lets you pass a timeout parameter that *hints* to their servers how long you want them to keep trying. Right now we set it to `http_timeout * 1000` (120,000ms) as our client-side timeout, but Google may impose their own shorter internal deadline regardless.

**Why it might not work:** Google controls their server-side deadlines. For preview/flash models, they may cap it regardless of what we request. This is worth trying but not guaranteed.

**Effect on generation:** Potentially allows Google to spend more time on complex prompts instead of cutting them off at 60s. Zero impact on fast requests.

**Files to change:** `backend/app/services/agent_prompt_graph.py` — `GeminiChatClient`

---

## Fix Priority

| Fix | Impact | Effort | Risk |
|-----|--------|--------|------|
| **1. Retry on 504** | Highest — turns failures into successes | Easy (done) | Low — only fires on failure |
| **2. Trim prompts** | High — faster across the board | Medium — careful editing needed | Medium — could lose quality |
| **3. Lighter disambig model** | Low-Medium — saves 0.5-1s | Easy — config change | Low |
| **4. Non-blocking disambig** | Medium — saves 1-2s on critical path | Medium — restructure async flow | Low-Medium |
| **5. Server-side timeout hint** | Uncertain — Google may ignore | Easy | Low |

### Longer-term consideration

If `gemini-3-flash-preview` continues to have 504 issues, consider switching to `gemini-2.5-flash` (GA model, already used for lyrics refine) or waiting for `gemini-3-flash` GA release. Preview models have weaker SLAs.
