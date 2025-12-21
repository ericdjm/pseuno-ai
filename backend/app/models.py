"""
Pydantic models for request/response schemas
"""

from typing import Optional
from pydantic import BaseModel, Field


# === Spotify Models ===

class SpotifyArtist(BaseModel):
    """Spotify artist data"""
    name: str
    genres: list[str] = []
    popularity: int = 0
    image_url: Optional[str] = None
    spotify_url: Optional[str] = None


class SpotifyTrack(BaseModel):
    """Spotify track data"""
    name: str
    artists: list[str]
    album_name: str
    album_image_url: Optional[str] = None
    popularity: int = 0
    spotify_url: Optional[str] = None


class TasteProfile(BaseModel):
    """Derived taste profile from Spotify data"""
    top_genres: list[str] = Field(description="Ranked list of top genres")
    mood_tags: list[str] = Field(description="Mood descriptors derived from taste")
    summary_sentence: str = Field(description="1-2 sentence taste summary")
    banned_references: list[str] = Field(description="Artist names to avoid in prompts")


class SpotifyProfileResponse(BaseModel):
    """Full Spotify profile response"""
    top_artists: list[SpotifyArtist]
    top_tracks: list[SpotifyTrack]
    taste_profile: TasteProfile
    time_range: str


# === Generation Models ===

class GenerateRequest(BaseModel):
    """Request body for prompt generation"""
    time_range: str = Field(default="medium_term", pattern="^(short_term|medium_term|long_term)$")
    theme: Optional[str] = Field(default=None, max_length=200)
    energy: int = Field(default=50, ge=0, le=100)
    rhythm_complexity: int = Field(default=50, ge=0, le=100)
    darkness: int = Field(default=50, ge=0, le=100)
    extra_notes: Optional[str] = Field(default=None, max_length=500)
    preset: Optional[str] = Field(default=None, description="Genre preset override")


class GenerateResponse(BaseModel):
    """Response from prompt generation"""
    concept_title: str = Field(description="Short title for the concept")
    suno_prompt: str = Field(description="Structured prompt for Suno AI", max_length=700)
    lyrics: str = Field(description="Original lyrics with section tags", max_length=1800)
    debug_profile: Optional[TasteProfile] = Field(default=None, description="Debug info (dev only)")


# === Auth Models ===

class LoginResponse(BaseModel):
    """Response from login endpoint"""
    auth_url: str


class AuthStatusResponse(BaseModel):
    """Response for auth status check"""
    authenticated: bool
    user_name: Optional[str] = None
    user_image: Optional[str] = None
