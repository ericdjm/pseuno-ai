"""
Spotify Data Routes
Fetches and processes user's Spotify data
"""

from fastapi import APIRouter, Request, HTTPException, Query

from app.models import SpotifyProfileResponse, SpotifyArtist, SpotifyTrack
from app.services.spotify_client import SpotifyClient
from app.services.taste_analyzer import build_taste_profile
from app.services.session_store import session_store

router = APIRouter()


def get_authenticated_client(request: Request) -> SpotifyClient:
    """Get an authenticated Spotify client from session"""
    session_id = request.cookies.get("session_id")
    
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    session = session_store.get_session(session_id)
    
    if not session or not session.get("access_token"):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    return SpotifyClient(
        access_token=session["access_token"],
        refresh_token=session.get("refresh_token"),
        session_id=session_id
    )


@router.get("/profile", response_model=SpotifyProfileResponse)
async def get_profile(
    request: Request,
    time_range: str = Query(default="medium_term", pattern="^(short_term|medium_term|long_term)$")
):
    """
    Get user's Spotify profile with taste analysis
    
    Time ranges:
    - short_term: ~4 weeks
    - medium_term: ~6 months
    - long_term: Several years
    """
    client = get_authenticated_client(request)
    
    # Fetch top artists and tracks in parallel
    try:
        top_artists_data = await client.get_top_artists(time_range=time_range, limit=20)
        top_tracks_data = await client.get_top_tracks(time_range=time_range, limit=30)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch Spotify data: {str(e)}")
    
    # Parse artists
    top_artists = [
        SpotifyArtist(
            name=artist["name"],
            genres=artist.get("genres", []),
            popularity=artist.get("popularity", 0),
            image_url=artist["images"][0]["url"] if artist.get("images") else None,
            spotify_url=artist.get("external_urls", {}).get("spotify")
        )
        for artist in top_artists_data.get("items", [])
    ]
    
    # Parse tracks
    top_tracks = [
        SpotifyTrack(
            name=track["name"],
            artists=[a["name"] for a in track.get("artists", [])],
            album_name=track.get("album", {}).get("name", ""),
            album_image_url=track.get("album", {}).get("images", [{}])[0].get("url"),
            popularity=track.get("popularity", 0),
            spotify_url=track.get("external_urls", {}).get("spotify")
        )
        for track in top_tracks_data.get("items", [])
    ]
    
    # Build taste profile
    taste_profile = build_taste_profile(top_artists, top_tracks)
    
    return SpotifyProfileResponse(
        top_artists=top_artists,
        top_tracks=top_tracks,
        taste_profile=taste_profile,
        time_range=time_range
    )
