"""
Advanced generation routes using vibe-first methodology
"""

from fastapi import APIRouter, Request, HTTPException

from app.models_advanced import (
    AdvancedGenerateRequest,
    AdvancedGenerateResponse,
    GenerationMode
)
from app.services.spotify_client import SpotifyClient
from app.services.taste_analyzer import build_taste_profile
from app.services.advanced_prompt_builder import AdvancedPromptBuilder, MODE_PRESETS
from app.services.session_store import session_store
from app.models import SpotifyArtist, SpotifyTrack

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


@router.get("/modes")
async def get_modes():
    """Get available generation modes with descriptions"""
    return {
        "modes": {
            mode: {
                "description": preset["description"],
                "vibe_keywords": preset["vibe_keywords"]
            }
            for mode, preset in MODE_PRESETS.items()
        }
    }


@router.post("/advanced", response_model=AdvancedGenerateResponse)
async def generate_advanced(request: Request, body: AdvancedGenerateRequest):
    """
    Advanced vibe-first generation
    
    Implements:
    - Vibe-first intent (not genre-first)
    - Orthogonal control layers (vocals, rhythm, texture, structure)
    - Contrast-based iteration
    - Rule breaking permissions
    - Content themes as anchors
    - Lyric density matching intensity
    - Separated artifacts (lyrics vs prompt)
    """
    session = get_authenticated_session(request)
    
    # Create Spotify client and fetch data for taste profile
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
    
    # Generate using advanced builder
    builder = AdvancedPromptBuilder(taste_profile)
    result = builder.generate(body)
    
    return AdvancedGenerateResponse(**result)
