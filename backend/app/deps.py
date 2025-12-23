"""
Shared FastAPI dependencies.
"""

from typing import Generator

from fastapi import Depends, HTTPException, Request
import httpx
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.services.agent_prompt_graph import AgentPromptGraph
from app.services.session_store import session_store
from app.services.spotify_client import SpotifyClient


def get_db() -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session, closing it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_song_agent(request: Request) -> AgentPromptGraph:
    """Return the startup-initialized LangGraph agent."""
    return request.app.state.song_agent


def get_http_client(request: Request) -> httpx.AsyncClient:
    """Return the shared HTTP client created at startup."""
    return request.app.state.http_client


def get_current_user_id(request: Request) -> str:
    """
    Require an authenticated session with a valid user_id.
    Returns the user_id string; raises 401 if not authenticated.
    """
    session_id = request.cookies.get("session_id")

    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session = session_store.get_session(session_id)

    if not session:
        raise HTTPException(status_code=401, detail="Session expired or invalid")

    user_id = session.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=401, detail="User not linked. Please log in again."
        )

    return user_id


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
