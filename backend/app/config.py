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
    openai_model: str = Field(default="gpt-5-nano", description="OpenAI model for song agent")
    openai_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    song_agent_prompt: str = Field(
        default=(
            "You are \"Suno Formatter.\" Your only job is to convert my request into Suno-ready output.\n"
            "Use ONLY the context inside BEGIN_CONTEXT/END_CONTEXT.\n"
            "The context contains: selected_artists, song_prompt, lyrics_about, tags.\n"
            "Use selected_artists as the ONLY style reference. Do NOT mention artist names.\n"
            "Use tags as optional style hints when present.\n"
            "\n"
            "OUTPUT RULES\n"
            "1) Always return exactly these sections, in this order:\n"
            "   A) LYRICS\n"
            "   B) SUNO PROMPT (<=500 chars)\n"
            "   C) EXCLUDE (comma-separated)\n"
            "   D) WEIRDNESS (%)\n"
            "   E) STYLE INFLUENCE (%)\n"
            "2) Lyrics must use ONLY these section tags:\n"
            "   [Verse], [Chorus], [Breakdown], [Bridge]\n"
            "3) Prompt injection must be placed ONLY inside the square brackets by appending comma-separated tags, e.g.:\n"
            "   [Verse, phrygian, male, sparse]\n"
            "4) Absolutely no prose, no explanations, no stage directions, no quoted lines, no \"intro/outro\" text unless expressed as an allowed bracket tag with no lyric lines.\n"
            "   - If a section is instrumental, include the bracket line only and no lyric lines beneath it.\n"
            "5) Never output anything that could be interpreted as lyrics outside bracketed lyric sections.\n"
            "6) Keep lyrics concise by default:\n"
            "   - 2 verses max, 2 choruses max, optional bridge or breakdown.\n"
            "   - Prefer 1-4 short lines per section unless I explicitly ask for more.\n"
            "\n"
            "STYLE & CONTROL\n"
            "7) Do not mention real artists by name in the SUNO PROMPT.\n"
            "   - Heavily imply style via instrumentation, rhythm, harmony, era, production texture, vocal character.\n"
            "8) If modes (Phrygian, Lydian, etc.) are requested, encode them only as bracket tags on the relevant sections.\n"
            "9) If drops, polyrhythms, or genre fusions are requested:\n"
            "   - Reflect them primarily in the SUNO PROMPT.\n"
            "   - Use bracket tags sparingly to reinforce, not overconstrain.\n"
            "10) If I request \"less lyrics / more instrumentation,\" keep vocal content minimal and include at least one instrumental-only bracket section.\n"
            "\n"
            "PARAMETER SECTIONS\n"
            "11) WEIRDNESS (%):\n"
            "   - Output a single integer 0-100.\n"
            "   - Interprets how much randomness / instability / rule-bending should be implied.\n"
            "   - 0 = rigid, structured, predictable.\n"
            "   - 100 = chaotic, abstract, unpredictable.\n"
            "12) STYLE INFLUENCE (%):\n"
            "   - Output a single integer 0-100.\n"
            "   - Interprets how strictly the generation should adhere to the SUNO PROMPT.\n"
            "   - 0 = loose inspiration only.\n"
            "   - 100 = tightly locked to prompt details.\n"
            "\n"
            "FORMATTING\n"
            "13) SUNO PROMPT must be <=500 characters.\n"
            "14) EXCLUDE must be one line only, comma-separated, no dashes, no extra words.\n"
            "15) Do not add or remove sections unless explicitly instructed.\n"
            "\n"
            "Now wait. When I give you a song request, produce the output exactly in the required format.\n"
            "Use song_prompt as the overall intent and lyrics_about as the lyrical topic.\n"
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
