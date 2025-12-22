"""
Pseuno AI - FastAPI Backend
Spotify-powered music taste analyzer and prompt generator for Suno AI
"""

import inspect
import logging
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routes import auth, spotify, generate_advanced
from app.services.agent_prompt_graph import AgentPromptGraph
from app.services.session_store import session_store
from app.config import get_settings, validate_settings

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    # Startup
    print("🎵 Pseuno AI starting up...")
    settings = validate_settings()  # Validate configuration on startup
    logging.basicConfig(
        level=logging.DEBUG if settings.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # Build the LangGraph agent once; compiling per request is expensive.
    app.state.song_agent = AgentPromptGraph(settings)
    print("AgentPromptGraph initialized")
    session_store.start_cleanup_task()  # Start session cleanup
    yield
    # Shutdown
    print("🎵 Pseuno AI shutting down...")
    session_store.stop_cleanup_task()
    session_store.clear_all()
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
    lifespan=lifespan
)

# CORS Configuration
settings = get_settings()

# In development, allow both 127.0.0.1 and localhost
# In production, use exact origin only
allowed_origins = [settings.frontend_origin]
if settings.debug:
    if "127.0.0.1" in settings.frontend_origin:
        allowed_origins.append(settings.frontend_origin.replace("127.0.0.1", "localhost"))
    elif "localhost" in settings.frontend_origin:
        allowed_origins.append(settings.frontend_origin.replace("localhost", "127.0.0.1"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    max_age=3600,  # Cache preflight requests for 1 hour
)

# Rate limiting middleware with automatic cleanup
import time
from collections import OrderedDict

class RateLimiter:
    """Rate limiter with LRU cleanup to prevent memory leaks"""
    def __init__(self, max_size: int = 10000):
        self.store: OrderedDict[str, dict] = OrderedDict()
        self.max_size = max_size
    
    def check_rate_limit(self, key: str, limit: int, window: int) -> bool:
        """Check if rate limit exceeded. Returns True if limit exceeded."""
        current_time = time.time()
        
        # Cleanup old entries if store is too large
        if len(self.store) > self.max_size:
            # Remove oldest 20% entries
            for _ in range(self.max_size // 5):
                self.store.popitem(last=False)
        
        if key not in self.store:
            self.store[key] = {"count": 1, "window_start": current_time}
            return False
        
        rate_data = self.store[key]
        
        # Reset window if expired
        if current_time - rate_data["window_start"] > window:
            rate_data["count"] = 1
            rate_data["window_start"] = current_time
            return False
        
        rate_data["count"] += 1
        
        # Move to end (LRU)
        self.store.move_to_end(key)
        
        return rate_data["count"] > limit

rate_limiter = RateLimiter()

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Rate limiting per session/IP with memory leak prevention"""
    # Use session_id if available, fallback to IP
    session_id = request.cookies.get("session_id")
    client_ip = request.client.host if request.client else "unknown"
    rate_key = session_id if session_id else f"ip:{client_ip}"
    
    if rate_limiter.check_rate_limit(
        rate_key,
        settings.rate_limit_requests,
        settings.rate_limit_window
    ):
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please slow down."},
            headers={"Retry-After": str(settings.rate_limit_window)}
        )
    
    response = await call_next(request)
    return response

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(spotify.router, prefix="/spotify", tags=["Spotify"])
app.include_router(generate_advanced.router, prefix="/generate", tags=["Advanced Generation"])

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "pseuno-ai",
        "version": "1.0.0"
    }

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to Pseuno AI API",
        "docs": "/docs",
        "health": "/health"
    }
