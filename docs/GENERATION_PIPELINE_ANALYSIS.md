# Generation Pipeline Performance Analysis

## Pipeline Architecture (V10 / v5_hybrid two-step path)

```
generate()
  ├── _build_context_pack()                    [~0ms, pure data]
  │
  ├── asyncio.gather (PARALLEL)
  │   │
  │   ├── STYLE BRANCH ────────────────────────────────────────────────
  │   │   ├── 1. genre_disambiguation        [LLM: gemini-3-flash-preview]  ~3-6s
  │   │   ├── 2. _decide_style_split_v8      [pure logic, ~0ms]
  │   │   ├── 3. _format_style_context_v8    [pure formatting, ~0ms]
  │   │   ├── 4. style.generate              [LLM: gemini-3-flash-preview]  ~5-12s
  │   │   ├── 5. style.parse + validate      [pure parse, ~0ms]
  │   │   ├── 6. style.repair (0-2x)         [LLM: gemini-3-flash-preview]  ~4-8s each
  │   │   └── 7. style.name_generate         [LLM: gemini-2.5-flash-lite]   ~2-4s  ← SEQUENTIAL after style
  │   │
  │   └── LYRICS BRANCH ──────────────────────────────────────────────
  │       ├── 1. lyrics.profile_infer         [LLM: gemini-3-flash-preview]  ~2-5s
  │       ├── 2. _format_lyrics_context_v4    [pure formatting, ~0ms]
  │       ├── 3. lyrics.generate              [LLM: gemini-3-flash-preview]  ~8-15s  ← SLOWEST CALL
  │       ├── 4. lyrics.parse + validate      [pure parse, ~0ms]
  │       └── 5. lyrics.repair (0-2x)         [LLM: gemini-3-flash-preview]  ~5-10s each
  │
  └── merge results + return                   [~0ms]
```

---

## Every LLM Call in the Pipeline

### Call 1: Genre Disambiguation (Style Branch, Sequential pre-step)

| Property | Value |
|---|---|
| **Function** | `_run_genre_disambiguation()` |
| **Location** | [agent_prompt_graph.py](backend/app/services/agent_prompt_graph.py#L830) |
| **Model** | `gemini-3-flash-preview` (settings.genre_disambiguation_model) |
| **System prompt** | `GENRE_DISAMBIGUATION_AGENT_V3` — **7,287 chars, ~1,821 tokens** |
| **User prompt** | ~200-400 chars (artist names + tags + style request) |
| **Total input** | ~1,900 tokens |
| **Parallel?** | **No — sequential blocker for style.generate** |
| **Retry** | 1 retry on 504/DEADLINE_EXCEEDED (Gemini client built-in) |
| **Repair loop** | No |
| **Est. latency** | 3-6s |

### Call 2: Style Generate (Style Branch, main call)

| Property | Value |
|---|---|
| **Function** | `_run_style_branch()` → `_call_llm()` |
| **Location** | [agent_prompt_graph.py](backend/app/services/agent_prompt_graph.py#L1489) |
| **Model** | `gemini-3-flash-preview` (settings.style_model) |
| **System prompt** | STYLE_AGENT (assembled) — **5,802 chars, ~1,450 tokens** |
| **User prompt** | ~500-2,000 chars (context pack + genre data + V8 split blocks) |
| **Total input** | ~1,600-2,000 tokens |
| **Parallel?** | **No — waits for genre_disambiguation to complete first** |
| **Retry** | 1 retry on timeout (OpenAI client), 1 retry on 504 (Gemini client) |
| **Repair loop** | Up to 2 repairs (settings.agent_max_repairs=2) |
| **Est. latency** | 5-12s (+ 4-8s per repair) |

### Call 3: Style Repair (Style Branch, conditional)

| Property | Value |
|---|---|
| **Function** | `_run_style_branch()` repair loop → `_call_llm()` |
| **Location** | [agent_prompt_graph.py](backend/app/services/agent_prompt_graph.py#L1525) |
| **Model** | `gemini-3-flash-preview` (same as style) |
| **System prompt** | `STYLE_REPAIR_AGENT_PROSE` — **1,505 chars, ~376 tokens** |
| **User prompt** | Previous output + issues list (~500-1,500 chars) |
| **Total input** | ~600-800 tokens |
| **Parallel?** | No — sequential within style branch |
| **Max calls** | 2 (settings.agent_max_repairs) |
| **Est. latency** | 4-8s per attempt |

### Call 4: Style Name Generate (Style Branch, sequential after style)

| Property | Value |
|---|---|
| **Function** | `_generate_style_name()` |
| **Location** | [agent_prompt_graph.py](backend/app/services/agent_prompt_graph.py#L3125) |
| **Model** | `gemini-2.5-flash-lite` (settings.title_generation_model) |
| **System prompt** | Short inline prompt — **~100 chars** |
| **User prompt** | ~400-600 chars (genres + artists + instructions) |
| **Total input** | ~200 tokens |
| **Parallel?** | **No — runs AFTER style branch completes, inside the style branch** |
| **Repair loop** | No |
| **Est. latency** | 2-4s |

### Call 5: Profile Inference (Lyrics Branch, sequential pre-step)

| Property | Value |
|---|---|
| **Function** | `_infer_lyric_profile()` |
| **Location** | [agent_prompt_graph.py](backend/app/services/agent_prompt_graph.py#L1810) |
| **Model** | `gemini-3-flash-preview` (settings.profile_inference_model) |
| **System prompt** | `PROFILE_INFERENCE_AGENT` — **6,986 chars, ~1,746 tokens** |
| **User prompt** | ~200-400 chars (style, topic, artists, tags) |
| **Total input** | ~1,850 tokens |
| **Parallel?** | **No — sequential blocker for lyrics.generate** |
| **Repair loop** | No |
| **Est. latency** | 2-5s |

### Call 6: Lyrics Generate (Lyrics Branch, main call)

| Property | Value |
|---|---|
| **Function** | `_run_lyrics_branch()` → `_call_llm()` |
| **Location** | [agent_prompt_graph.py](backend/app/services/agent_prompt_graph.py#L1696) |
| **Model** | `gemini-3-flash-preview` (settings.lyrics_model) |
| **System prompt** | LYRICS_AGENT (assembled) — **6,290 chars, ~1,572 tokens** |
| **User prompt** | ~800-1,500 chars (context pack + per-section lyric profiles) |
| **Total input** | ~1,800-2,000 tokens |
| **Parallel?** | **No — waits for profile_infer to complete first** |
| **Retry** | 1 retry on timeout/504 |
| **Repair loop** | Up to 2 repairs |
| **Est. latency** | **8-15s** (generates multi-section lyrics — highest output token count) |

### Call 7: Lyrics Repair (Lyrics Branch, conditional)

| Property | Value |
|---|---|
| **Function** | `_run_lyrics_branch()` repair loop → `_call_llm()` |
| **Location** | [agent_prompt_graph.py](backend/app/services/agent_prompt_graph.py#L1738) |
| **Model** | `gemini-3-flash-preview` |
| **System prompt** | `LYRICS_REPAIR_AGENT` — **672 chars, ~168 tokens** |
| **User prompt** | Previous output + issues (~1,000-3,000 chars) |
| **Total input** | ~1,000 tokens |
| **Parallel?** | No — sequential within lyrics branch |
| **Max calls** | 2 |
| **Est. latency** | 5-10s per attempt |

---

## Critical Path Analysis

### Best case (no repairs):

```
                 ┌─── genre_disamb (4s) ──► style.generate (8s) ──► style_name (3s) ───┐
PARALLEL gather  │                                                      TOTAL: ~15s     │ = max(15s, 12s) = ~15s
                 └─── profile_infer (3s) ──► lyrics.generate (12s) ────────────────────┘
                                                                        TOTAL: ~15s (but usually shorter)
```

**Best-case wall-clock: ~15s**

### Typical case (no repairs, some variance):

- Style branch: 4s (genre) + 8s (style) + 3s (name) = **~15s**
- Lyrics branch: 3s (profile) + 12s (lyrics) = **~15s**
- **Typical wall-clock: ~15-18s**

### Worst case (2 repairs on each branch):

- Style branch: 4s + 8s + 6s + 6s + 3s = **~27s**
- Lyrics branch: 3s + 12s + 8s + 8s = **~31s**
- **Worst-case wall-clock: ~31s**

### Why lyrics can take 30-40s:

1. Profile inference adds 2-5s sequential overhead before lyrics generation starts
2. lyrics.generate produces the most output tokens (full multi-section song lyrics = 300-600 tokens)
3. If repair triggers (missing section tags, empty title), each repair is another 5-10s
4. All models are `gemini-3-flash-preview` — if the API is slow/cold, each call compounds

---

## Identified Inefficiencies

### 1. **Gemini `_sync_generate` runs sync code in thread executor** (CRITICAL)

**Location:** [GeminiChatClient.ainvoke()](backend/app/services/agent_prompt_graph.py#L320-L331)

```python
async def ainvoke(self, messages, temperature=None):
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None, self._sync_generate, messages, temperature
    )
```

The Gemini SDK's `generate_content()` is called synchronously in the default thread executor. This means:
- **Every concurrent Gemini call consumes a thread** from the default ThreadPoolExecutor (which defaults to `min(32, os.cpu_count() + 4)` threads)
- With 5+ concurrent LLM calls per request, thread pool contention becomes an issue under load
- The `time.sleep(2)` retry backoff at [line 398](backend/app/services/agent_prompt_graph.py#L398) **blocks the thread** during retry
- The `google-genai` SDK has an async client (`client.aio.models.generate_content`) — this should use it

### 2. **`_generate_style_name` is sequential AFTER style branch** (HIGH)

**Location:** [_run_style_branch()](backend/app/services/agent_prompt_graph.py#L1588-L1598)

The style name generation happens AFTER the style branch completes (genre disambig → style generate → validate → repair → **then** style name). This adds 2-4s to the style branch's critical path.

**It could run in parallel with lyrics.generate** since it only needs genre_data (which is available after genre disambiguation, not after style generation).

### 3. **`PROFILE_INFERENCE_AGENT` prompt is massively oversized** (HIGH)

**Size:** 6,986 chars, ~1,746 tokens

This is a simple structured-output task (return 5 JSON objects + a structure array), but the prompt contains:
- Two detailed multi-line examples (~50% of the prompt)
- Exhaustive documentation of every field value and its meaning
- Redundant rhyme scheme documentation (already in the lyrics agent prompt)

The user message is only ~200-400 chars. The system prompt is **17x larger than the input**. This inflates TTFT (time-to-first-token) for a call that returns ~200-300 tokens.

**Recommendation:** Cut to ~1,500-2,000 chars. Remove examples, condense field docs since the model already has this knowledge.

### 4. **`GENRE_DISAMBIGUATION_AGENT_V3` prompt is oversized** (HIGH)

**Size:** 7,287 chars, ~1,821 tokens

Contains a massive example JSON response for Steel Panther + TOOL (~2,500 chars), plus extensive role detection documentation. Much of this is redundant given the model's capabilities.

**Recommendation:** Cut to ~3,000-4,000 chars. Remove the full example, condense rules.

### 5. **Genre disambiguation is a sequential blocker for the style branch** (MEDIUM)

**Location:** [_run_style_branch()](backend/app/services/agent_prompt_graph.py#L1458-L1460)

Genre disambiguation MUST complete before style generation can start, adding 3-6s to the style branch. Meanwhile, it gives data useful for both style context AND style name generation.

**Consider:** Running genre disambiguation in parallel with profile inference as a separate pre-gather step, then feeding results into both branches.

### 6. **All 5+ calls use the same model (`gemini-3-flash-preview`)** (MEDIUM)

Genre disambiguation, profile inference, style generation, and lyrics generation all default to `gemini-3-flash-preview`. The profile inference and genre disambiguation tasks are simple structured-output tasks that could use a cheaper/faster model like `gemini-2.5-flash-lite` (already used for title/style name generation).

### 7. **PostHog `capture_background` import inside hot path** (LOW)

**Locations:** [L1530](backend/app/services/agent_prompt_graph.py#L1530), [L1741](backend/app/services/agent_prompt_graph.py#L1741)

```python
from app.services.posthog_capture import capture_background
```

This `from` import is inside the repair loop body. While Python caches module imports, doing it inside the loop adds a small dict lookup per iteration. Move to top-level import.

### 8. **`_get_or_create_llm` creates a dataclass inside the method** (LOW)

**Location:** [_get_or_create_llm()](backend/app/services/agent_prompt_graph.py#L638-L654)

Every time a new model client is created, a new `ModelSettings` dataclass is defined. This is a one-time overhead per model, but the dataclass definition inside the method is unusual.

---

## Suggested Optimizations (ordered by impact)

### Optimization 1: Use async Gemini client (est. -0s latency, but fixes concurrency)

**Location:** [GeminiChatClient](backend/app/services/agent_prompt_graph.py#L307-L404)

Replace `run_in_executor` + sync `generate_content` with the async API:

```python
async def ainvoke(self, messages, temperature=None):
    client = self._get_client()
    # Use async API directly
    response = await client.aio.models.generate_content(
        model=self.model,
        contents=contents,
        config=config,
    )
```

This eliminates thread pool contention and allows true async concurrency.

### Optimization 2: Run style_name in parallel, not sequential (est. -2-4s)

**Location:** [_run_style_branch()](backend/app/services/agent_prompt_graph.py#L1588-L1598)

Move style name generation out of `_run_style_branch` and into the main `_generate_parallel_two_step` method. Run it in parallel with lyrics generation since it only needs genre_data.

### Optimization 3: Run genre_disambig + profile_infer in parallel pre-step (est. -2-4s)

**Current:**
```
PARALLEL:
  Style: genre_disambig (4s) → style.generate (8s) → style_name (3s)   = 15s
  Lyrics: profile_infer (3s) → lyrics.generate (12s)                     = 15s
```

**Proposed:**
```
PRE-STEP (parallel): genre_disambig + profile_infer                     = max(4s, 3s) = 4s
MAIN (parallel):
  Style: style.generate (8s)                                            = 8s
  Lyrics: lyrics.generate (12s)                                         = 12s
POST (parallel with nothing):
  style_name (3s)                                                       = could overlap
```

**Total: 4s + 12s = ~16s → saves ~3s** from overlapping genre_disambig and profile_infer.

### Optimization 4: Shrink profile inference prompt (est. -0.5-1s TTFT)

**Location:** [PROFILE_INFERENCE_AGENT in specs.py](backend/app/prompts/specs.py#L782-L893)

Cut from ~1,746 tokens to ~800 tokens by:
- Removing the 2 full examples (each ~500 chars)
- Condensing field documentation to one-liners
- Removing redundant rhyme scheme adaptation docs

### Optimization 5: Shrink genre disambiguation prompt (est. -0.5-1s TTFT)

**Location:** [GENRE_DISAMBIGUATION_AGENT_V3 in specs.py](backend/app/prompts/specs.py#L1074-L1264)

Cut from ~1,821 tokens to ~1,000 tokens by:
- Removing the full Steel Panther + TOOL example (~2,500 chars)
- Condensing to a minimal schema + 2-3 one-line examples

### Optimization 6: Use a faster model for profile inference + genre disambiguation

Both tasks produce structured JSON and don't need creative capability. Switch from `gemini-3-flash-preview` to `gemini-2.5-flash-lite` or `gpt-4.1-nano`:

**Location:** [config.py](backend/app/config.py#L82-L88)

```python
profile_inference_model: str = Field(
    default="gemini-2.5-flash-lite",  # was gemini-3-flash-preview
)
genre_disambiguation_model: str = Field(
    default="gemini-2.5-flash-lite",  # was gemini-3-flash-preview
)
```

### Summary: Combined estimated improvement

| Optimization | Est. savings | Effort |
|---|---|---|
| Async Gemini client | Concurrency fix | Medium |
| Parallel style_name | 2-4s | Low |
| Pre-step parallel (genre+profile) | 2-3s | Medium |
| Shrink profile prompt | 0.5-1s | Low |
| Shrink genre prompt | 0.5-1s | Low |
| Faster models for pre-steps | 1-2s | Config change |
| **Combined best-case** | **~6-10s** | |

Current typical: ~15-18s → **Optimized: ~8-12s** (for no-repair path)
