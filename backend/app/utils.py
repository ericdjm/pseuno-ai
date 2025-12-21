"""
Utility functions to reduce code duplication
"""

import asyncio
from typing import List
from fastapi import Request, HTTPException

from app.models import SpotifyArtist, SpotifyTrack, TasteProfile
from app.services.spotify_client import SpotifyClient
from app.services.taste_analyzer import build_taste_profile
from app.services.session_store import session_store


def get_authenticated_client(request: Request) -> SpotifyClient:
    """
    Get an authenticated Spotify client from session.
    Raises HTTPException if not authenticated.
    """
    session_id = request.cookies.get("session_id")
    
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    session = session_store.get_session(session_id)
    
    if not session or not session.get("access_token"):
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    
    return SpotifyClient(
        access_token=session["access_token"],
        refresh_token=session.get("refresh_token"),
        session_id=session_id
    )


async def fetch_and_parse_spotify_data(
    client: SpotifyClient,
    time_range: str,
    artist_limit: int = 20,
    track_limit: int = 30
) -> tuple[List[SpotifyArtist], List[SpotifyTrack], TasteProfile]:
    """
    Fetch top artists and tracks in parallel, parse them, and build taste profile.
    
    Args:
        client: Authenticated Spotify client
        time_range: Time range for data (short_term, medium_term, long_term)
        artist_limit: Number of artists to fetch
        track_limit: Number of tracks to fetch
    
    Returns:
        Tuple of (top_artists, top_tracks, taste_profile)
    
    Raises:
        HTTPException: If Spotify API call fails
    """
    try:
        # Fetch artists and tracks in parallel for better performance
        top_artists_data, top_tracks_data = await asyncio.gather(
            client.get_top_artists(time_range=time_range, limit=artist_limit),
            client.get_top_tracks(time_range=time_range, limit=track_limit)
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch Spotify data: {str(e)}"
        )
    
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
    
    return top_artists, top_tracks, taste_profile
