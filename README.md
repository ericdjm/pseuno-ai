# Pseuno AI

Generate Suno-compatible prompts and original lyrics from natural language descriptions, with optional Spotify taste personalization.

**Live at [pseuno.com](https://pseuno.com)**

## Features

- **AI Song Generation** — Describe a vibe, get a complete Suno prompt + original lyrics in seconds
- **Split Parallel Generation** — Style and lyrics branches run concurrently for ~2x speed
- **Spotify Integration** — Optionally connect Spotify to personalize results with your listening history
- **Lyric Controls** — Fine-tune audience, directness, humor, explicitness, persona, rhyme scheme, and more
- **Prompt Library** — Auto-saved history with favorites, tags, and shareable links
- **Lyrics Threads** — Generate variations on a saved style prompt with new lyrics
- **Prompt Refinement** — Iterate on generated prompts with targeted edits
- **Guest Mode** — Full generation without any login (device-token tracking)
- **Instrumental Support** — Generates creative titles when no lyrics are requested

## Tech Stack

**Backend:**
- Python 3.11+ / FastAPI / Uvicorn
- Pydantic v2 (validation)
- SQLAlchemy + Alembic (database + migrations)
- Google Gemini + OpenAI (LLM providers)
- httpx (async HTTP)

**Frontend:**
- React 18 / TypeScript / Vite
- Chakra UI

**Infrastructure:**
- PostgreSQL (production) / SQLite (development)
- Redis (sessions, rate limiting — production)
- Docker Compose (dev + prod)

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- A Google Gemini API key (`GEMINI_API_KEY`)
- Optional: Spotify Developer credentials

### Docker (recommended)

```bash
git clone https://github.com/ericdjm/pseuno-ai.git
cd pseuno-ai

# Create .env in repo root with at minimum:
#   GEMINI_API_KEY=your-key-here

docker compose -f docker-compose.dev.yml up --build
```

Or use the Makefile shortcut:

```bash
make dev
```

Frontend: http://localhost:5173 | Backend: http://localhost:8000 | API Docs: http://localhost:8000/docs

### Manual Setup

**Backend:**

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Edit with your GEMINI_API_KEY
alembic upgrade head   # Apply database migrations
uvicorn app.main:app --reload --port 8000
```

**Frontend:**

```bash
cd frontend
npm install
echo "VITE_API_BASE=http://localhost:8000" > .env.local
npm run dev
```

## Usage

1. Open http://localhost:5173 (or [pseuno.com](https://pseuno.com) for production)
2. Describe the style you want (e.g. "cinematic synthwave chase scene")
3. Add a lyrics topic (e.g. "a neon city at midnight") — or leave blank for instrumental
4. Optionally connect Spotify, select reference artists, or add tags
5. Adjust lyric controls (audience, rhyme scheme, persona, etc.)
6. Click generate — style and lyrics are produced in parallel
7. Copy the Suno prompt + lyrics into Suno AI

**API usage (no UI):**

```bash
curl -X POST https://pseuno.com/generate/advanced \
  -H "Content-Type: application/json" \
  -d '{
    "user_prompt": "Cinematic synthwave chase scene",
    "lyrics_about": "a neon city at midnight",
    "tags": ["retro", "driving", "noir"]
  }'
```

## API Endpoints

### Generation

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/generate/advanced` | Full generation (style + lyrics + auto-save) |
| POST | `/generate/style` | Style-only generation (parallel split) |
| POST | `/generate/lyrics` | Lyrics-only generation (parallel split) |
| POST | `/generate/save-result` | Save merged split results to DB |
| POST | `/generate/lyrics-only` | New lyrics for an existing style prompt |
| GET | `/generate/prompt-variants` | List available prompt variants |
| GET | `/generate/models` | List available LLM models |

### Prompts & Library

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/prompts/` | List saved prompts |
| GET | `/prompts/{id}` | Get a saved prompt |
| PATCH | `/prompts/{id}` | Update prompt (title, favorite, notes) |
| DELETE | `/prompts/{id}` | Delete a saved prompt |

### Lyrics Threads

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/lyrics-threads/{prompt_id}` | List threads for a prompt |
| POST | `/lyrics-threads/` | Create a new lyrics thread |
| PATCH | `/lyrics-threads/{id}` | Update a thread |

### Refinement

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/refine/` | Refine a generated prompt |

### Auth & Spotify

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/auth/spotify/login` | Get Spotify auth URL |
| GET | `/auth/spotify/callback` | OAuth PKCE callback |
| GET | `/auth/status` | Check auth status |
| POST | `/auth/logout` | Clear session |
| GET | `/spotify/profile` | Taste profile (requires Spotify) |

### System

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |

## Environment Variables

### Backend (.env)

| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_API_KEY` | Google Gemini API key | **Required** |
| `OPENAI_API_KEY` | OpenAI API key (for GPT models) | Optional |
| `STYLE_MODEL` | Model for style generation | `gemini-3-flash-preview` |
| `LYRICS_MODEL` | Model for lyrics generation | `gemini-2.5-flash` |
| `PROFILE_INFERENCE_MODEL` | Model for lyric profile inference | `gemini-3-flash-preview` |
| `GENRE_DISAMBIGUATION_MODEL` | Model for genre pre-step | `gemini-3-flash-preview` |
| `TITLE_GENERATION_MODEL` | Model for instrumental titles | `gemini-2.5-flash-lite` |
| `LLM_MODEL` | Default model (single-step variants) | `gpt-4.1` |
| `LLM_TEMPERATURE` | Generation temperature | `0.7` |
| `LLM_ROLE_CONFIGS_JSON` | Per-role tuning overrides (JSON) | `{}` |
| `PROMPT_VARIANT` | Default prompt variant | `v10_suno_friendly` |
| `AGENT_MAX_REPAIRS` | Max repair attempts per branch | `2` |
| `DATABASE_URL` | SQLAlchemy DB URL | `sqlite:///./pseuno.db` |
| `REDIS_URL` | Redis URL (required in production) | Optional |
| `SPOTIFY_CLIENT_ID` | Spotify Client ID | Optional |
| `SPOTIFY_REDIRECT_URI` | OAuth callback URL | `http://localhost:8000/auth/spotify/callback` |
| `FRONTEND_ORIGIN` | Frontend URL for CORS | `http://localhost:5173` |
| `SECRET_KEY` | Session secret key | Auto-generated |
| `DEBUG` | Enable debug mode | `true` |
| `HTTP_TIMEOUT` | LLM request timeout (seconds) | `120` |

### Frontend (.env.local)

| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_API_BASE` | Backend API URL | `http://localhost:8000` |

## Prompt Variants

The generation pipeline supports swappable prompt configurations (variants) for A/B testing.

| Variant | Architecture | Description |
|---------|-------------|-------------|
| `v1_baseline` | single-step | Initial baseline |
| `v2_max_mode` | single-step | Advanced single-step |
| `v3_two_step` | two-step | Basic style/lyrics split |
| `v4_lyric_profile` | two-step | + lyric profile inference |
| `v5_hybrid` | two-step | Hybrid approach |
| `v6_genre_disambiguation` | two-step | + genre pre-step |
| `v7_genre_term_disambiguation` | two-step | Enhanced genre terms |
| `v8_channel_split` | two-step | Vocalist/music split |
| `v9_comprehensive_exclude` | two-step | Comprehensive avoid list |
| **`v10_suno_friendly`** | two-step | **Default** — musical descriptors over technical terms |

Pass `prompt_variant` in any generation request to override the default.

## Prompt Lab

Prompt Lab is a CLI tool for benchmarking prompts across models.

```bash
cd backend
source venv/bin/activate

# Compare variants
python prompt_lab/prompt_lab.py --prompts prompt_lab/prompts/v11_production.txt prompt_lab/prompts/v14_protocol.txt

# Test with specific models
python prompt_lab/prompt_lab.py --prompts prompt_lab/prompts/v14_protocol.txt \
    --models gemini-3-flash-preview

# Speed benchmarks
python prompt_lab/speed_bench.py

# Save results
python prompt_lab/prompt_lab.py --prompts prompt_lab/prompts/v14_protocol.txt \
    --output prompt_lab/results/
```

## Database Migrations

Managed with Alembic. Keep migration history linear (single head).

```bash
cd backend
source venv/bin/activate
alembic upgrade head                              # Apply pending migrations
alembic revision --autogenerate -m "description"  # Create new migration
alembic upgrade head                              # Apply new migration
```

Docker:

```bash
docker compose -f docker-compose.dev.yml exec backend alembic upgrade head
```

## Project Structure

```
pseuno-ai/
├── backend/
│   ├── app/
│   │   ├── main.py                          # FastAPI app, CORS, lifespan
│   │   ├── config.py                        # Settings + ModelRoleConfig
│   │   ├── constants.py                     # Validation limits
│   │   ├── deps.py                          # FastAPI dependency injection
│   │   ├── db/
│   │   │   ├── models.py                    # SQLAlchemy models
│   │   │   ├── session.py                   # DB session
│   │   │   └── migrations/                  # Alembic migrations
│   │   ├── routes/
│   │   │   ├── auth.py                      # Spotify OAuth (PKCE)
│   │   │   ├── spotify.py                   # Profile/taste endpoints
│   │   │   ├── generate_advanced.py         # Generation endpoints (full + split)
│   │   │   ├── generate_input_concept.py    # Input concept generation
│   │   │   ├── refine.py                    # Prompt refinement
│   │   │   ├── prompts.py                   # Saved prompts CRUD
│   │   │   └── lyrics_threads.py            # Song variations/threads
│   │   ├── schemas/
│   │   │   ├── advanced.py                  # Generation request/response models
│   │   │   ├── lyrics_threads.py            # Thread schemas
│   │   │   └── unified_refine.py            # Refinement schemas
│   │   ├── services/
│   │   │   ├── agent_prompt_graph.py        # Core LLM agent (generation pipeline)
│   │   │   ├── debug_trace.py               # Span-based debug tracer
│   │   │   ├── style_classifier.py          # Gemini-based style classification
│   │   │   ├── lyrics_topic_generator.py    # Topic routing for variations
│   │   │   ├── spotify_client.py            # Spotify API client
│   │   │   ├── taste_analyzer.py            # Taste profile builder
│   │   │   └── refine_service.py            # Prompt refinement logic
│   │   └── prompts/
│   │       ├── registry.py                  # Variant registration system
│   │       ├── specs.py                     # Reusable prompt components
│   │       └── variants/                    # v1 through v10
│   ├── prompt_lab/                          # Benchmarking CLI
│   │   ├── prompt_lab.py
│   │   ├── speed_bench.py
│   │   └── experiments.py
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx                          # Main app
│   │   ├── api.ts                           # API client
│   │   ├── types.ts                         # TypeScript types
│   │   ├── hooks.ts                         # Custom hooks
│   │   └── components/
│   │       ├── NewSongView.tsx              # Main generation UI
│   │       ├── AdvancedGenerationControls.tsx
│   │       ├── AdvancedResultsDisplay.tsx
│   │       ├── PromptLibrarySidebar.tsx
│   │       └── WorkingPromptPanel.tsx
│   ├── package.json
│   └── vite.config.ts
├── docker-compose.dev.yml
├── docker-compose.prod.yml
├── Makefile
└── README.md
```

## Running Tests

```bash
cd backend
source venv/bin/activate
pytest
```

## License

MIT
