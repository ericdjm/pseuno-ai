"""
Spotify OAuth Authentication Routes
Implements Authorization Code with PKCE flow
"""

import os
import secrets
import hashlib
import base64
from urllib.parse import urlencode

from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import RedirectResponse
import httpx

from app.config import get_settings
from app.services.session_store import session_store

router = APIRouter()

# Spotify OAuth endpoints
SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_USER_URL = "https://api.spotify.com/v1/me"

# Required scopes
SCOPES = "user-top-read user-read-email"


def generate_code_verifier() -> str:
    """Generate a random code verifier for PKCE"""
    return secrets.token_urlsafe(64)[:128]


def generate_code_challenge(verifier: str) -> str:
    """Generate code challenge from verifier using S256 method"""
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


@router.get("/spotify/login")
async def spotify_login(response: Response):
    """
    Initiate Spotify OAuth login with PKCE
    Returns the authorization URL and sets session cookie
    """
    settings = get_settings()
    
    if not settings.spotify_client_id:
        raise HTTPException(status_code=500, detail="Spotify client ID not configured")
    
    # Generate PKCE codes
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)
    
    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    
    # Create session and store PKCE data
    session_id = secrets.token_urlsafe(32)
    session_store.create_session(session_id)
    session_store.set_pkce_data(session_id, code_verifier, state)
    
    # Build authorization URL
    params = {
        "client_id": settings.spotify_client_id,
        "response_type": "code",
        "redirect_uri": settings.spotify_redirect_uri,
        "scope": SCOPES,
        "state": state,
        "code_challenge_method": "S256",
        "code_challenge": code_challenge,
    }
    
    auth_url = f"{SPOTIFY_AUTH_URL}?{urlencode(params)}"
    
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
    error: str = None
):
    """
    Handle Spotify OAuth callback
    Exchanges authorization code for tokens
    """
    settings = get_settings()
    frontend_url = settings.frontend_origin
    
    if error:
        return RedirectResponse(url=f"{frontend_url}?error={error}")
    
    if not code or not state:
        return RedirectResponse(url=f"{frontend_url}?error=missing_params")
    
    # Get session
    session_id = request.cookies.get("session_id")
    if not session_id:
        return RedirectResponse(url=f"{frontend_url}?error=no_session")
    
    # Verify state and get code verifier
    pkce_data = session_store.get_pkce_data(session_id)
    if not pkce_data or pkce_data.get("state") != state:
        return RedirectResponse(url=f"{frontend_url}?error=invalid_state")
    
    code_verifier = pkce_data.get("code_verifier")
    
    # Exchange code for tokens
    settings = get_settings()
    timeout = httpx.Timeout(settings.http_timeout)
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            token_response = await client.post(
                SPOTIFY_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": settings.spotify_redirect_uri,
                    "client_id": settings.spotify_client_id,
                    "code_verifier": code_verifier,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if token_response.status_code != 200:
                error_detail = token_response.json().get("error_description", "token_exchange_failed")
                print(f"⚠️  Token exchange failed: {error_detail}")
                return RedirectResponse(url=f"{frontend_url}?error={error_detail}")
            
            tokens = token_response.json()
            
            # Store tokens in session
            session_store.set_tokens(
                session_id,
                access_token=tokens["access_token"],
                refresh_token=tokens.get("refresh_token"),
                expires_in=tokens.get("expires_in", 3600)
            )
            
            # Fetch user profile
            user_response = await client.get(
                SPOTIFY_USER_URL,
                headers={"Authorization": f"Bearer {tokens['access_token']}"}
            )
            
            if user_response.status_code == 200:
                user_data = user_response.json()
                session_store.set_user_data(
                    session_id,
                    user_name=user_data.get("display_name", "User"),
                    user_image=user_data.get("images", [{}])[0].get("url") if user_data.get("images") else None
                )
            
            # Clear PKCE data
            session_store.clear_pkce_data(session_id)
            
    except httpx.TimeoutException:
        print("⚠️  Spotify API request timed out during OAuth callback")
        return RedirectResponse(url=f"{frontend_url}?error=request_timeout")
    except httpx.RequestError as e:
        print(f"⚠️  OAuth callback request failed: {str(e)}")
        return RedirectResponse(url=f"{frontend_url}?error=request_failed")
    except Exception as e:
        print(f"⚠️  Unexpected error during OAuth callback: {str(e)}")
        return RedirectResponse(url=f"{frontend_url}?error=unknown_error")
    
    return RedirectResponse(url=f"{frontend_url}?success=true")


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
