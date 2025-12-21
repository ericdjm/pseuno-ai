"""
Prompt and Lyrics Generation Routes
"""

import os
from fastapi import APIRouter, Request, HTTPException

from app.models import GenerateRequest, GenerateResponse
from app.services.spotify_client import SpotifyClient
from app.services.taste_analyzer import build_taste_profile
from app.services.prompt_builder import PromptBuilder
from app.services.session_store import session_store
from app.config import get_settings

router = APIRouter()


def get_authenticated_session(request: Request) -> dict:
    """Get authenticated session data"""
    session_id = request.cookies.get("session_id")
    
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    session = session_store.get_session(session_id)
    
    if not session or not session.get("access_token"):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    return session


@router.post("", response_model=GenerateResponse)
async def generate_prompt(request: Request, body: GenerateRequest):
    """
    Generate Suno AI prompt and lyrics based on user's taste profile
    
    Parameters:
    - time_range: short_term | medium_term | long_term
    - theme: Optional theme or story idea
    - energy: 0-100 (calm to energetic)
    - rhythm_complexity: 0-100 (simple to complex)
    - darkness: 0-100 (light/happy to dark/melancholic)
    - extra_notes: Additional instructions
    - preset: Optional genre preset override
    """
    session = get_authenticated_session(request)
    settings = get_settings()
    
    # Create Spotify client and fetch data
    client = SpotifyClient(
        access_token=session["access_token"],
        refresh_token=session.get("refresh_token"),
        session_id=request.cookies.get("session_id")
    )
    
    try:
        top_artists_data = await client.get_top_artists(time_range=body.time_range, limit=20)
        top_tracks_data = await client.get_top_tracks(time_range=body.time_range, limit=30)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch Spotify data: {str(e)}")
    
    # Parse data for taste analysis
    from app.models import SpotifyArtist, SpotifyTrack
    
    top_artists = [
        SpotifyArtist(
            name=artist["name"],
            genres=artist.get("genres", []),
            popularity=artist.get("popularity", 0),
            image_url=artist["images"][0]["url"] if artist.get("images") else None
        )
        for artist in top_artists_data.get("items", [])
    ]
    
    top_tracks = [
        SpotifyTrack(
            name=track["name"],
            artists=[a["name"] for a in track.get("artists", [])],
            album_name=track.get("album", {}).get("name", ""),
            album_image_url=track.get("album", {}).get("images", [{}])[0].get("url"),
            popularity=track.get("popularity", 0)
        )
        for track in top_tracks_data.get("items", [])
    ]
    
    # Build taste profile
    taste_profile = build_taste_profile(top_artists, top_tracks)
    
    # Generate prompt and lyrics
    builder = PromptBuilder(taste_profile)
    
    result = builder.generate(
        theme=body.theme,
        energy=body.energy,
        rhythm_complexity=body.rhythm_complexity,
        darkness=body.darkness,
        extra_notes=body.extra_notes,
        preset=body.preset
    )
    
    # Include debug info only in dev mode
    debug_profile = taste_profile if settings.debug else None
    
    return GenerateResponse(
        concept_title=result["concept_title"],
        suno_prompt=result["suno_prompt"],
        lyrics=result["lyrics"],
        debug_profile=debug_profile
    )
