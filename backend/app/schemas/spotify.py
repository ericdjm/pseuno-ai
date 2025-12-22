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


# === Auth Models ===

class LoginResponse(BaseModel):
    """Response from login endpoint"""
    auth_url: str


class AuthStatusResponse(BaseModel):
    """Response for auth status check"""
    authenticated: bool
    user_name: Optional[str] = None
    user_image: Optional[str] = None
