"""
Configuration management
"""

import secrets
from functools import lru_cache
from typing import Optional

from pydantic import ConfigDict, Field, model_validator
from pydantic_settings import BaseSettings

from app.prompts import SONG_AGENT_SYSTEM_PROMPT


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Spotify OAuth (optional)
    spotify_client_id: Optional[str] = Field(
        default=None,
        description="Spotify Client ID (optional; enables Spotify login/profile)",
    )
    spotify_redirect_uri: str = "http://127.0.0.1:8000/auth/spotify/callback"

    # App settings
    frontend_origin: str = "http://127.0.0.1:5173"
    debug: bool = True
    secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(32))

    # Security settings
    session_cookie_secure: bool = Field(
        default=False, description="Use secure cookies (HTTPS only)"
    )
    session_cookie_samesite: str = Field(default="lax", pattern="^(strict|lax|none)$")
    session_max_age: int = Field(
        default=86400, description="Session cookie max age in seconds (24h)"
    )

    # Rate limiting
    rate_limit_requests: int = 100
    rate_limit_window: int = 60

    # Request timeouts
    http_timeout: int = 30

    # OpenAI / LangChain settings
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    openai_model: str = Field(
        default="gpt-5-nano", description="OpenAI model for song agent"
    )
    openai_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    song_agent_prompt: str = Field(
        default=SONG_AGENT_SYSTEM_PROMPT,
        description="System prompt for the song agent",
    )

    # Agent repair settings (will eventually be managed via Redis)
    agent_repair_enabled: bool = Field(
        default=True,
        description="Enable automatic repair of invalid agent outputs",
    )
    agent_max_repairs: int = Field(
        default=2,
        ge=0,
        le=10,
        description="Maximum repair attempts before falling back (0 = no repairs)",
    )

    @model_validator(mode="after")
    def validate_secret_key_in_production(self) -> "Settings":
        """Warn if using default secret key in production"""
        if (
            not self.debug
            and self.secret_key == "change-this-in-production-use-a-real-secret"
        ):
            raise ValueError("Must set SECRET_KEY environment variable in production")
        return self

    @model_validator(mode="after")
    def set_secure_cookie_in_production(self) -> "Settings":
        """Auto-enable secure cookies in production"""
        if not self.debug and not self.session_cookie_secure:
            object.__setattr__(self, "session_cookie_secure", True)
        return self


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


def validate_settings():
    """Validate settings on startup"""
    settings = get_settings()

    if not settings.spotify_client_id:
        print(
            "⚠️  SPOTIFY_CLIENT_ID not set; Spotify auth/profile endpoints will be unavailable"
        )

    if not settings.debug:
        print("⚠️  Running in PRODUCTION mode")
        if settings.secret_key == "change-this-in-production-use-a-real-secret":
            raise ValueError("SECRET_KEY must be set in production")
        if not settings.session_cookie_secure:
            print("⚠️  WARNING: Secure cookies not enabled in production!")
    else:
        print("🔧 Running in DEBUG mode")

    print("✓ Settings validated successfully")
    return settings
