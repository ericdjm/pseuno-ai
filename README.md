# Pseuno AI

Generate personalized Suno AI prompts based on your Spotify listening history.

![Pseuno AI](https://img.shields.io/badge/Pseuno-AI-1DB954?style=for-the-badge&logo=spotify&logoColor=white)

## Features

- 🎵 **Spotify Integration**: Connect your Spotify account to analyze your music taste
- 🎨 **Taste Analysis**: Automatically detects your top genres, artists, and mood preferences
- ✨ **Custom Prompts**: Generate Suno AI prompts tailored to your unique listening history
- 📝 **Original Lyrics**: Get auto-generated lyrics with proper [Verse]/[Chorus]/[Bridge] tags
- 🎛️ **Fine-tune Controls**: Adjust energy, rhythm complexity, and darkness levels
- 🔗 **Share Results**: Create shareable links to your generated prompts

## Tech Stack

**Backend:**
- FastAPI (Python 3.11+)
- Uvicorn (ASGI server)
- Pydantic v2 (validation)
- httpx (async HTTP client)

**Frontend:**
- React 18
- Vite
- TypeScript
- Chakra UI

## Prerequisites

- Python 3.11+
- Node.js 18+
- A Spotify Developer account

## Spotify App Setup

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Click "Create App"
3. Fill in the details:
   - **App name**: Pseuno AI (or your choice)
   - **App description**: Personalized music prompt generator
   - **Redirect URI**: `http://localhost:8000/auth/spotify/callback`
4. Check the Web API checkbox
5. Save and note your **Client ID** (you don't need the Client Secret for PKCE flow)

## Installation

### Clone the repository

```bash
git clone https://github.com/ericdjm/pseuno-ai.git
cd pseuno-ai
```

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file and edit it
cp .env.example .env
```

Edit `.env` with your Spotify credentials:

```env
SPOTIFY_CLIENT_ID=your_spotify_client_id_here
SPOTIFY_REDIRECT_URI=http://localhost:8000/auth/spotify/callback
FRONTEND_ORIGIN=http://localhost:5173
DEBUG=true
SECRET_KEY=your-random-secret-key
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# (Optional) Create environment file for API URL
echo "VITE_API_BASE=http://localhost:8000" > .env.local
```

## Running the App

### Start the Backend

```bash
cd backend
source venv/bin/activate  # On Windows: venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```

The API will be available at http://localhost:8000

- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

### Start the Frontend

```bash
cd frontend
npm run dev
```

The app will be available at http://localhost:5173

## Usage

1. Open http://localhost:5173 in your browser
2. Click "Login with Spotify"
3. Authorize the app to read your top artists and tracks
4. Select a time range (Last 4 Weeks / Last 6 Months / All Time)
5. Adjust the sliders (Energy, Rhythm Complexity, Darkness)
6. Optionally add a theme or story idea
7. Click "Generate Prompt + Lyrics"
8. Copy the prompt to use in Suno AI!

## Running Tests

```bash
cd backend
source venv/bin/activate
pytest
```

## Project Structure

```
pseuno-ai/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, CORS, middleware
│   │   ├── config.py            # Settings management
│   │   ├── models.py            # Pydantic schemas
│   │   ├── routes/
│   │   │   ├── auth.py          # Spotify OAuth (PKCE)
│   │   │   ├── spotify.py       # Profile/taste endpoints
│   │   │   └── generate.py      # Prompt generation
│   │   └── services/
│   │       ├── session_store.py # In-memory session storage
│   │       ├── spotify_client.py # Spotify API client
│   │       ├── taste_analyzer.py # Taste profile builder
│   │       └── prompt_builder.py # Prompt/lyrics generator
│   ├── tests/
│   │   ├── test_taste_analyzer.py
│   │   └── test_prompt_builder.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── main.tsx             # Entry point, Chakra theme
│   │   ├── App.tsx              # Main app component
│   │   ├── api.ts               # API layer
│   │   ├── types.ts             # TypeScript types
│   │   ├── hooks.ts             # Custom hooks
│   │   └── components/
│   │       ├── TasteDisplay.tsx
│   │       ├── GenerationControls.tsx
│   │       ├── ResultsDisplay.tsx
│   │       └── PrivacyNote.tsx
│   ├── package.json
│   └── vite.config.ts
├── .gitignore
└── README.md
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/auth/spotify/login` | Get Spotify auth URL |
| GET | `/auth/spotify/callback` | OAuth callback |
| GET | `/auth/status` | Check auth status |
| POST | `/auth/logout` | Clear session |
| GET | `/spotify/profile` | Get taste profile |
| POST | `/generate` | Generate prompt + lyrics |

## Environment Variables

### Backend (.env)

| Variable | Description | Default |
|----------|-------------|---------|
| `SPOTIFY_CLIENT_ID` | Your Spotify app's Client ID | Required |
| `SPOTIFY_REDIRECT_URI` | OAuth callback URL | `http://localhost:8000/auth/spotify/callback` |
| `FRONTEND_ORIGIN` | Frontend URL for CORS | `http://localhost:5173` |
| `DEBUG` | Enable debug mode | `true` |
| `SECRET_KEY` | Session secret key | Required for production |

### Frontend (.env.local)

| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_API_BASE` | Backend API URL | `http://localhost:8000` |

## Future Improvements

- [ ] Wire prompt generation to an LLM (OpenAI, Claude, etc.)
- [ ] Add persistent session storage (Redis)
- [ ] Deploy to cloud (Vercel + Railway/Fly.io)
- [ ] Add more genre presets
- [ ] Implement prompt history
- [ ] Add audio preview integration

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
