"""
Spotify API Client
Handles authenticated requests to Spotify Web API
"""

import asyncio
import logging
from typing import Optional
import httpx

from app.config import get_settings
from app.services.session_store import session_store

SPOTIFY_API_BASE = "https://api.spotify.com/v1"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"

logger = logging.getLogger(__name__)


class SpotifyClientError(Exception):
    """Base error for Spotify client failures."""


class SpotifyAuthError(SpotifyClientError):
    """Authentication/refresh failures."""


class SpotifyAPIError(SpotifyClientError):
    """Spotify API request failures."""


class SpotifyClient:
    """Async Spotify API client with automatic token refresh and race condition protection"""
    
    # Class-level lock to prevent concurrent token refreshes for the same session
    _refresh_locks: dict[str, asyncio.Lock] = {}
    _locks_lock = asyncio.Lock()
    
    def __init__(
        self,
        access_token: str,
        refresh_token: Optional[str] = None,
        session_id: Optional[str] = None,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.session_id = session_id
        self._settings = get_settings()
        self._http_client = http_client
        self._owns_client = http_client is None

    def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            timeout = httpx.Timeout(self._settings.http_timeout)
            self._http_client = httpx.AsyncClient(timeout=timeout)
            self._owns_client = True
        return self._http_client

    async def aclose(self):
        if self._http_client is not None and self._owns_client:
            await self._http_client.aclose()
    
    async def _get_refresh_lock(self) -> asyncio.Lock:
        """Get or create a lock for this session's token refresh"""
        if not self.session_id:
            # No session, create a temporary lock
            return asyncio.Lock()
        
        async with self._locks_lock:
            if self.session_id not in self._refresh_locks:
                self._refresh_locks[self.session_id] = asyncio.Lock()
            return self._refresh_locks[self.session_id]
    
    async def _ensure_valid_token(self):
        """Refresh access token if expired (with race condition protection)"""
        if not self.session_id or not self.refresh_token:
            return
        
        if session_store.is_token_expired(self.session_id):
            lock = await self._get_refresh_lock()
            async with lock:
                # Double-check after acquiring lock - another request might have refreshed
                if session_store.is_token_expired(self.session_id):
                    await self._refresh_access_token()
    
    async def _refresh_access_token(self):
        """Refresh the access token using refresh token"""
        settings = self._settings

        client = self._get_client()
        try:
            response = await client.post(
                SPOTIFY_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token,
                    "client_id": settings.spotify_client_id,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            if response.status_code == 200:
                tokens = response.json()
                self.access_token = tokens["access_token"]

                # Update session store
                session_store.update_access_token(
                    self.session_id,
                    tokens["access_token"],
                    tokens.get("expires_in", 3600),
                )

                # Update refresh token if new one provided
                if tokens.get("refresh_token"):
                    self.refresh_token = tokens["refresh_token"]
            else:
                raise SpotifyAuthError(
                    f"Token refresh failed: {response.status_code}"
                )
        except httpx.TimeoutException as exc:
            raise SpotifyAuthError("Token refresh timed out") from exc
        except httpx.RequestError as exc:
            raise SpotifyAuthError(f"Token refresh request failed: {exc}") from exc
    
    async def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        """Make authenticated request to Spotify API with timeout"""
        await self._ensure_valid_token()
        
        url = f"{SPOTIFY_API_BASE}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            **kwargs.pop("headers", {})
        }
        client = self._get_client()
        try:
            response = await client.request(
                method,
                url,
                headers=headers,
                **kwargs,
            )

            if response.status_code == 401:
                # Token might have just expired, try refresh once
                await self._refresh_access_token()
                headers["Authorization"] = f"Bearer {self.access_token}"
                response = await client.request(
                    method,
                    url,
                    headers=headers,
                    **kwargs,
                )

            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException as exc:
            raise SpotifyAPIError(
                f"Spotify API request timed out: {method} {endpoint}"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise SpotifyAPIError(
                f"Spotify API error: {exc.response.status_code} - {exc.response.text}"
            ) from exc
        except httpx.RequestError as exc:
            logger.warning("Spotify API request failed: %s %s", method, endpoint)
            raise SpotifyAPIError(
                f"Spotify API request failed: {method} {endpoint}"
            ) from exc
    
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
