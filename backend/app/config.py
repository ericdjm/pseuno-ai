"""
Configuration management
"""

import os
import secrets
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field, validator
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Spotify OAuth (required)
    spotify_client_id: str = Field(..., min_length=1, description="Spotify Client ID (required)")
    spotify_redirect_uri: str = "http://127.0.0.1:8000/auth/spotify/callback"
    
    # App settings
    frontend_origin: str = "http://127.0.0.1:5173"
    debug: bool = True
    secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    
    # Security settings
    session_cookie_secure: bool = Field(default=False, description="Use secure cookies (HTTPS only)")
    session_cookie_samesite: str = Field(default="lax", pattern="^(strict|lax|none)$")
    session_max_age: int = Field(default=86400, description="Session cookie max age in seconds (24h)")
    
    # Rate limiting
    rate_limit_requests: int = 100
    rate_limit_window: int = 60
    
    # Request timeouts
    http_timeout: int = 30

    # OpenAI / LangChain settings
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    openai_model: str = Field(default="gpt-4.1", description="OpenAI model for song agent")
    openai_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    song_agent_prompt: str = Field(
        default=(
            "You are a song generation agent. Use ONLY the context inside BEGIN_CONTEXT/END_CONTEXT. "
            "Use all provided context sections when relevant. Generate:\n"
            "1) concept_title (<= 50 chars)\n"
            "2) suno_prompt (<= 700 chars, machine-facing, include style, mood, instrumentation, vocals, "
            "tempo feel, and structure hints)\n"
            "3) lyrics (<= 1800 chars, include [Verse], [Chorus], [Bridge], [Outro] tags)\n"
            "Use selected artists/genres/vibes as influence but do NOT mention artist names. "
            "Avoid any names in banned_references. Respect generation_controls if present. "
            "Return JSON only, matching the requested schema exactly."
        ),
        description="System prompt for the song agent"
    )
    
    @validator("secret_key")
    def validate_secret_key(cls, v, values):
        """Warn if using default secret key in production"""
        if not values.get("debug") and v == "change-this-in-production-use-a-real-secret":
            raise ValueError("Must set SECRET_KEY environment variable in production")
        return v
    
    @validator("session_cookie_secure")
    def set_secure_cookie_in_production(cls, v, values):
        """Auto-enable secure cookies in production"""
        if not values.get("debug") and not v:
            return True
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


def validate_settings():
    """Validate settings on startup"""
    settings = get_settings()
    
    if not settings.spotify_client_id:
        raise ValueError("SPOTIFY_CLIENT_ID environment variable is required")
    
    if not settings.debug:
        print("⚠️  Running in PRODUCTION mode")
        if settings.secret_key == "change-this-in-production-use-a-real-secret":
            raise ValueError("SECRET_KEY must be set in production")
        if not settings.session_cookie_secure:
            print("⚠️  WARNING: Secure cookies not enabled in production!")
    else:
        print("🔧 Running in DEBUG mode")
    
    print(f"✓ Settings validated successfully")
    return settings
