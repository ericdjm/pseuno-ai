# Columbus V1 — Agent Instructions

## Architecture

Columbus is a music generation app. The backend is a FastAPI service that calls LLMs to generate Suno-compatible style prompts and lyrics.

### Generation flow (default: two-step v5_hybrid)

The default prompt variant is `v5_hybrid` which runs **two parallel branches** via `asyncio.gather`:

1. **Style branch** → generates `suno_prompt`, `exclude`, `weirdness`, `style_influence`
2. **Lyrics branch** → infers a `LyricProfile` first, then generates `song_title` + `lyrics`

After both branches complete, a `style_name` LLM call summarizes the style.

**LLM call order** (non-instrumental): style → profile → lyrics → style_name (4 calls)
**LLM call order** (instrumental): style → title → style_name (3 calls)

### Key files

| File | What it does | Pitfalls |
|---|---|---|
| `backend/app/services/agent_prompt_graph.py` | Core generation engine (~3500 lines) | `_injected_llm` makes all branches share one FakeLLM in tests |
| `backend/app/prompts/specs.py` | Shared output contracts, repair prompts | Changes here affect ALL variants |
| `backend/app/prompts/variants/v5_hybrid.py` | Default two-step variant config | `uses_lyric_profile=True` triggers profile inference |
| `backend/app/schemas/advanced.py` | Request/response models, DebugTrace schema | `PromptVariant` literal must match registry |
| `backend/app/services/debug_trace.py` | DebugTracer builds span-based traces | `debug_info` is `DebugTrace` format, not flat dict |
| `backend/app/config.py` | Settings (env vars, defaults) | `agent_repair_enabled` exists but is NOT used in two-step code |

## Testing

### Running tests

```bash
cd backend && python -m pytest -v
```

**ALL tests must pass before committing.** Run the full suite, not just the file you changed.

### Testing patterns

- **FakeLLM**: Tests inject a `FakeLLM` with a list of string responses consumed in order. For two-step v5_hybrid, provide responses in this order: style, profile, lyrics, style_name (4 for non-instrumental, 3 for instrumental).
- **Always set `prompt_variant="v5_hybrid"`** in test requests — this matches the default behavior and ensures correct FakeLLM consumption order.
- **`debug_info`** is a `DebugTrace` dict with `version`, `summary` (variant, model, repairs, architecture), and `spans` list — NOT a flat dict with `repaired`/`agent_model` keys.
- **Shared helpers** are in `backend/tests/conftest.py` (`test_settings` fixture) and at the top of test files (`_valid_style_output`, `_valid_lyrics_output`, etc.).
- **Route tests** copy endpoint functions inline with mocked dependencies rather than importing FastAPI routers.
- **Pre-existing failures**: `test_artist_bank_routing.py` (event loop) and `test_v8_channel_split.py` are known broken — don't worry about those.

### Lint

```bash
cd backend && python -m ruff check app/ tests/
```

## Skills

Use these after making changes:
- `/test-quality` — assess generation quality by hitting real endpoints (after prompt/generation changes)
- `/test-perf` — benchmark endpoint latency
- `/test-frontend` — validate frontend builds and types
- `/debug-prod` — investigate production issues
- `/update-rules` — add new conventions to this file
