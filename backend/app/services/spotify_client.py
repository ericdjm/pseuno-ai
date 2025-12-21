"""
Spotify API Client
Handles authenticated requests to Spotify Web API
"""

import time
from typing import Optional
import httpx

from app.config import get_settings
from app.services.session_store import session_store

SPOTIFY_API_BASE = "https://api.spotify.com/v1"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"


class SpotifyClient:
    """Async Spotify API client with automatic token refresh"""
    
    def __init__(
        self,
        access_token: str,
        refresh_token: Optional[str] = None,
        session_id: Optional[str] = None
    ):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.session_id = session_id
    
    async def _ensure_valid_token(self):
        """Refresh access token if expired"""
        if not self.session_id or not self.refresh_token:
            return
        
        if session_store.is_token_expired(self.session_id):
            await self._refresh_access_token()
    
    async def _refresh_access_token(self):
        """Refresh the access token using refresh token"""
        settings = get_settings()
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                SPOTIFY_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token,
                    "client_id": settings.spotify_client_id,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code == 200:
                tokens = response.json()
                self.access_token = tokens["access_token"]
                
                # Update session store
                session_store.update_access_token(
                    self.session_id,
                    tokens["access_token"],
                    tokens.get("expires_in", 3600)
                )
                
                # Update refresh token if new one provided
                if tokens.get("refresh_token"):
                    self.refresh_token = tokens["refresh_token"]
    
    async def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        """Make authenticated request to Spotify API"""
        await self._ensure_valid_token()
        
        url = f"{SPOTIFY_API_BASE}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            **kwargs.pop("headers", {})
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method,
                url,
                headers=headers,
                **kwargs
            )
            
            if response.status_code == 401:
                # Token might have just expired, try refresh
                await self._refresh_access_token()
                headers["Authorization"] = f"Bearer {self.access_token}"
                response = await client.request(
                    method,
                    url,
                    headers=headers,
                    **kwargs
                )
            
            response.raise_for_status()
            return response.json()
    
    async def get_top_artists(
        self,
        time_range: str = "medium_term",
        limit: int = 20
    ) -> dict:
        """
        Get user's top artists
        
        Args:
            time_range: short_term (~4 weeks), medium_term (~6 months), long_term (years)
            limit: Number of items to return (max 50)
        """
        return await self._request(
            "GET",
            "/me/top/artists",
            params={"time_range": time_range, "limit": min(limit, 50)}
        )
    
    async def get_top_tracks(
        self,
        time_range: str = "medium_term",
        limit: int = 30
    ) -> dict:
        """
        Get user's top tracks
        
        Args:
            time_range: short_term (~4 weeks), medium_term (~6 months), long_term (years)
            limit: Number of items to return (max 50)
        """
        return await self._request(
            "GET",
            "/me/top/tracks",
            params={"time_range": time_range, "limit": min(limit, 50)}
        )
    
    async def get_current_user(self) -> dict:
        """Get current user's profile"""
        return await self._request("GET", "/me")
