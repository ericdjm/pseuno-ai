"""
Shared FastAPI dependencies.
"""

from fastapi import Depends, HTTPException, Request
import httpx

from app.services.agent_prompt_graph import AgentPromptGraph
from app.services.session_store import session_store
from app.services.spotify_client import SpotifyClient


def get_song_agent(request: Request) -> AgentPromptGraph:
    """Return the startup-initialized LangGraph agent."""
    return request.app.state.song_agent


def get_http_client(request: Request) -> httpx.AsyncClient:
    """Return the shared HTTP client created at startup."""
    return request.app.state.http_client


def get_spotify_client(
    request: Request,
    http_client: httpx.AsyncClient = Depends(get_http_client),
) -> SpotifyClient:
    """Return an authenticated Spotify client from the current session."""
    session_id = request.cookies.get("session_id")

    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session = session_store.get_session(session_id)

    if not session or not session.get("access_token"):
        raise HTTPException(status_code=401, detail="Session expired or invalid")

    return SpotifyClient(
        access_token=session["access_token"],
        refresh_token=session.get("refresh_token"),
        session_id=session_id,
        http_client=http_client,
    )
