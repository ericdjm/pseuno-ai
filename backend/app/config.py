"""
Configuration management
"""

import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Spotify OAuth
    spotify_client_id: str = ""
    spotify_redirect_uri: str = "http://127.0.0.1:8000/auth/spotify/callback"
    
    # App settings
    frontend_origin: str = "http://127.0.0.1:5173"
    debug: bool = True
    secret_key: str = "change-this-in-production-use-a-real-secret"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
