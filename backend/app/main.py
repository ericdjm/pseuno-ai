"""
Pseuno AI - FastAPI Backend
Spotify-powered music taste analyzer and prompt generator for Suno AI
"""

import inspect
import logging
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx

from app.routes import auth, spotify, generate_advanced, prompts
from app.services.agent_prompt_graph import AgentPromptGraph
from app.services.rate_limiter import create_rate_limiter
from app.services.session_store import session_store
from app.services.spotify_client import SpotifyClientError
from app.config import get_settings, validate_settings

load_dotenv()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    # Startup
    settings = get_settings()
    logging.basicConfig(
        level=logging.DEBUG if settings.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger.info("Pseuno AI starting up...")
    validate_settings()  # Validate configuration on startup
    # Shared HTTP client for outbound requests.
    app.state.http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(settings.http_timeout),
    )
    app.state.rate_limiter = create_rate_limiter(settings)
    # Build the LangGraph agent once; compiling per request is expensive.
    app.state.song_agent = AgentPromptGraph(settings)
    logger.info("AgentPromptGraph initialized")
    session_store.start_cleanup_task()  # Start session cleanup
    yield
    # Shutdown
    logger.info("Pseuno AI shutting down...")
    session_store.stop_cleanup_task()
    session_store.clear_all()
    http_client = getattr(app.state, "http_client", None)
    if http_client is not None:
        await http_client.aclose()
    agent = getattr(app.state, "song_agent", None)
    if agent is not None:
        close_fn = getattr(agent, "aclose", None) or getattr(agent, "close", None)
        if close_fn:
            result = close_fn()
            if inspect.isawaitable(result):
                await result
        llm = getattr(agent, "llm", None)
        if llm is not None:
            llm_close = getattr(llm, "aclose", None) or getattr(llm, "close", None)
            if llm_close:
                result = llm_close()
                if inspect.isawaitable(result):
                    await result


app = FastAPI(
    title="Pseuno AI",
    description="Generate personalized Suno AI prompts based on your Spotify taste",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(SpotifyClientError)
async def spotify_client_error_handler(request: Request, exc: SpotifyClientError):
    logger.warning("Spotify client error: %s", exc)
    return JSONResponse(status_code=502, content={"detail": str(exc)})


settings = get_settings()


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Rate limiting per session/IP with memory leak prevention"""
    # Use session_id if available, fallback to IP
    session_id = request.cookies.get("session_id")
    client_ip = request.client.host if request.client else "unknown"
    rate_key = session_id if session_id else f"ip:{client_ip}"

    rate_limiter = request.app.state.rate_limiter
    if rate_limiter.check_rate_limit(
        rate_key, settings.rate_limit_requests, settings.rate_limit_window
    ):
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please slow down."},
            headers={"Retry-After": str(settings.rate_limit_window)},
        )

    response = await call_next(request)
    return response


# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(spotify.router, prefix="/spotify", tags=["Spotify"])
app.include_router(
    generate_advanced.router, prefix="/generate", tags=["Advanced Generation"]
)
app.include_router(prompts.router, prefix="/prompts", tags=["Saved Prompts"])

# CORS Configuration (must be OUTERMOST so even early middleware returns get CORS headers)
# In development, allow both 127.0.0.1 and localhost; in production, use exact origin only.
allowed_origins = [settings.frontend_origin]
if settings.debug:
    if "127.0.0.1" in settings.frontend_origin:
        allowed_origins.append(
            settings.frontend_origin.replace("127.0.0.1", "localhost")
        )
    elif "localhost" in settings.frontend_origin:
        allowed_origins.append(
            settings.frontend_origin.replace("localhost", "127.0.0.1")
        )

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    max_age=3600,  # Cache preflight requests for 1 hour
)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "pseuno-ai", "version": "1.0.0"}


@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Welcome to Pseuno AI API", "docs": "/docs", "health": "/health"}
