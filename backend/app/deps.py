"""
Shared FastAPI dependencies.
"""

from typing import Generator, Optional

from fastapi import Depends, HTTPException, Request
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import User, _device_token
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


def get_device_user(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    Get the guest user from device_token cookie, if present.
    Does NOT create a user if token doesn't exist.
    Returns None if no valid device token.
    """
    device_token = request.cookies.get("device_token")
    if not device_token:
        return None

    user = db.scalar(select(User).where(User.device_token == device_token))
    return user


def get_or_create_device_user(
    request: Request,
    db: Session = Depends(get_db),
) -> tuple[User, bool]:
    """
    Get or create a guest user from device_token cookie.
    Returns (user, created) tuple where created=True if a new user was made.

    If no device_token cookie exists, creates a new guest user with a fresh token.
    The caller is responsible for setting the device_token cookie in the response.
    """
    device_token = request.cookies.get("device_token")

    if device_token:
        # Look up existing user by device token
        user = db.scalar(select(User).where(User.device_token == device_token))
        if user:
            return user, False

    # Create new guest user with new device token
    new_token = _device_token()
    user = User(device_token=new_token, is_guest=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, True


def get_song_agent(request: Request) -> AgentPromptGraph:
    """Return the startup-initialized LangGraph agent."""
    return request.app.state.song_agent


def get_http_client(request: Request) -> httpx.AsyncClient:
    """Return the shared HTTP client created at startup."""
    return request.app.state.http_client


def get_current_user_id(request: Request) -> str:
    """
    Require an authenticated Spotify session with a valid user_id.
    Returns the user_id string; raises 401 if not authenticated.
    Does NOT fall back to device token.
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


def get_current_user_id_optional(request: Request) -> Optional[str]:
    """
    Get user_id from Spotify session if available, else None.
    Does not raise exceptions.
    """
    session_id = request.cookies.get("session_id")
    if not session_id:
        return None

    session = session_store.get_session(session_id)
    if not session:
        return None

    return session.get("user_id")


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
