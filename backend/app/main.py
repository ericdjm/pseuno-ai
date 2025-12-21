"""
Pseuno AI - FastAPI Backend
Spotify-powered music taste analyzer and prompt generator for Suno AI
"""

import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routes import auth, spotify, generate, generate_advanced
from app.services.session_store import session_store

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    # Startup
    print("🎵 Pseuno AI starting up...")
    yield
    # Shutdown
    print("🎵 Pseuno AI shutting down...")
    session_store.clear_all()

app = FastAPI(
    title="Pseuno AI",
    description="Generate personalized Suno AI prompts based on your Spotify taste",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Configuration
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://127.0.0.1:5173")

# Allow both 127.0.0.1 and localhost for development
allowed_origins = [FRONTEND_ORIGIN]
if "127.0.0.1" in FRONTEND_ORIGIN:
    allowed_origins.append(FRONTEND_ORIGIN.replace("127.0.0.1", "localhost"))
elif "localhost" in FRONTEND_ORIGIN:
    allowed_origins.append(FRONTEND_ORIGIN.replace("localhost", "127.0.0.1"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Rate limiting middleware (simple in-memory counter)
rate_limit_store: dict[str, dict] = {}
RATE_LIMIT_REQUESTS = 100
RATE_LIMIT_WINDOW = 60  # seconds

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Simple rate limiting per session"""
    import time
    
    session_id = request.cookies.get("session_id", request.client.host if request.client else "unknown")
    current_time = time.time()
    
    if session_id not in rate_limit_store:
        rate_limit_store[session_id] = {"count": 0, "window_start": current_time}
    
    session_rate = rate_limit_store[session_id]
    
    # Reset window if expired
    if current_time - session_rate["window_start"] > RATE_LIMIT_WINDOW:
        session_rate["count"] = 0
        session_rate["window_start"] = current_time
    
    session_rate["count"] += 1
    
    if session_rate["count"] > RATE_LIMIT_REQUESTS:
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please slow down."}
        )
    
    response = await call_next(request)
    return response

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(spotify.router, prefix="/spotify", tags=["Spotify"])
app.include_router(generate.router, prefix="/generate", tags=["Generation"])
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
