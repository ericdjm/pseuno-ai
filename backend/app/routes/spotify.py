"""
Spotify Data Routes
Fetches and processes user's Spotify data
"""

from fastapi import APIRouter, Request, Query

from app.models import SpotifyProfileResponse
from app.utils import get_authenticated_client, fetch_and_parse_spotify_data

router = APIRouter()


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
    
    # Fetch and parse data (uses parallel API calls internally)
    top_artists, top_tracks, taste_profile = await fetch_and_parse_spotify_data(
        client, time_range
    )
    
    return SpotifyProfileResponse(
        top_artists=top_artists,
        top_tracks=top_tracks,
        taste_profile=taste_profile,
        time_range=time_range
    )
