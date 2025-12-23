"""
Spotify OAuth Authentication Routes
Implements Authorization Code with PKCE flow
"""

import httpx
from fastapi import APIRouter, Depends, Request, Response, HTTPException
from fastapi.responses import RedirectResponse

from app.config import get_settings
from app.deps import get_http_client
from app.services.spotify_oauth import create_spotify_login, handle_spotify_callback
from app.services.session_store import session_store

router = APIRouter()


@router.get("/spotify/login")
async def spotify_login(response: Response):
    """
    Initiate Spotify OAuth login with PKCE
    Returns the authorization URL and sets session cookie
    """
    settings = get_settings()

    if not settings.spotify_client_id:
        raise HTTPException(status_code=500, detail="Spotify client ID not configured")

    auth_url, session_id = create_spotify_login(settings)
    
    # Set session cookie with environment-dependent security settings
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        secure=settings.session_cookie_secure,  # True in production
        samesite=settings.session_cookie_samesite,
        max_age=settings.session_max_age
    )
    
    return {"auth_url": auth_url}


@router.get("/spotify/callback")
async def spotify_callback(
    request: Request,
    code: str = None,
    state: str = None,
    error: str = None,
    http_client: httpx.AsyncClient = Depends(get_http_client),
):
    """
    Handle Spotify OAuth callback
    Exchanges authorization code for tokens.
    If user has a device_token (guest account), merges their prompts.
    """
    settings = get_settings()
    session_id = request.cookies.get("session_id")
    device_token = request.cookies.get("device_token")

    redirect_url = await handle_spotify_callback(
        settings=settings,
        http_client=http_client,
        session_id=session_id,
        code=code,
        state=state,
        error=error,
        device_token=device_token,
    )
    return RedirectResponse(url=redirect_url)


@router.get("/status")
async def auth_status(request: Request):
    """Check authentication status"""
    session_id = request.cookies.get("session_id")
    
    if not session_id:
        return {"authenticated": False}
    
    session = session_store.get_session(session_id)
    if not session or not session.get("access_token"):
        return {"authenticated": False}
    
    return {
        "authenticated": True,
        "user_name": session.get("user_name"),
        "user_image": session.get("user_image")
    }


@router.post("/logout")
async def logout(request: Request, response: Response):
    """Clear session and logout"""
    session_id = request.cookies.get("session_id")
    
    if session_id:
        session_store.delete_session(session_id)
    
    response.delete_cookie(key="session_id")
    
    return {"message": "Logged out successfully"}
