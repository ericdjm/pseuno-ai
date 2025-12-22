"""
Spotify OAuth flow helpers.
"""

import base64
import hashlib
import logging
import secrets
from typing import Optional, Tuple
from urllib.parse import urlencode

import httpx

from app.config import Settings
from app.services.session_store import session_store

logger = logging.getLogger(__name__)

# Spotify OAuth endpoints
SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_USER_URL = "https://api.spotify.com/v1/me"

# Required scopes
SCOPES = "user-top-read user-read-email"


def _generate_code_verifier() -> str:
    """Generate a random code verifier for PKCE."""
    return secrets.token_urlsafe(64)[:128]


def _generate_code_challenge(verifier: str) -> str:
    """Generate code challenge from verifier using S256 method."""
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def create_spotify_login(settings: Settings) -> Tuple[str, str]:
    """Return (auth_url, session_id) for the PKCE login flow."""
    if not settings.spotify_client_id:
        raise ValueError("Spotify client ID not configured")

    code_verifier = _generate_code_verifier()
    code_challenge = _generate_code_challenge(code_verifier)
    state = secrets.token_urlsafe(32)

    session_id = secrets.token_urlsafe(32)
    session_store.create_session(session_id)
    session_store.set_pkce_data(session_id, code_verifier, state)

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
    return auth_url, session_id


async def handle_spotify_callback(
    *,
    settings: Settings,
    http_client: httpx.AsyncClient,
    session_id: Optional[str],
    code: Optional[str],
    state: Optional[str],
    error: Optional[str],
) -> str:
    """Process the callback and return a redirect URL."""
    frontend_url = settings.frontend_origin

    if error:
        logger.warning("Spotify OAuth error received")
        return f"{frontend_url}?error={error}"

    if not code or not state:
        logger.warning("Spotify OAuth missing code or state")
        return f"{frontend_url}?error=missing_params"

    if not session_id:
        logger.warning("Spotify OAuth missing session")
        return f"{frontend_url}?error=no_session"

    pkce_data = session_store.get_pkce_data(session_id)
    if not pkce_data or pkce_data.get("state") != state:
        logger.warning("Spotify OAuth invalid state")
        return f"{frontend_url}?error=invalid_state"

    code_verifier = pkce_data.get("code_verifier")

    try:
        token_response = await http_client.post(
            SPOTIFY_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.spotify_redirect_uri,
                "client_id": settings.spotify_client_id,
                "code_verifier": code_verifier,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        if token_response.status_code != 200:
            try:
                error_detail = token_response.json().get(
                    "error_description", "token_exchange_failed"
                )
            except ValueError:
                error_detail = "token_exchange_failed"
            logger.warning("Spotify OAuth token exchange failed")
            return f"{frontend_url}?error={error_detail}"

        try:
            tokens = token_response.json()
        except ValueError:
            logger.warning("Spotify OAuth token response was not valid JSON")
            return f"{frontend_url}?error=token_exchange_failed"

        session_store.set_tokens(
            session_id,
            access_token=tokens["access_token"],
            refresh_token=tokens.get("refresh_token"),
            expires_in=tokens.get("expires_in", 3600),
        )

        user_response = await http_client.get(
            SPOTIFY_USER_URL,
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )

        if user_response.status_code == 200:
            user_data = user_response.json()
            session_store.set_user_data(
                session_id,
                user_name=user_data.get("display_name", "User"),
                user_image=user_data.get("images", [{}])[0].get("url")
                if user_data.get("images")
                else None,
            )

        session_store.clear_pkce_data(session_id)
    except httpx.TimeoutException:
        logger.warning("Spotify OAuth request timed out")
        return f"{frontend_url}?error=request_timeout"
    except httpx.RequestError:
        logger.warning("Spotify OAuth request failed")
        return f"{frontend_url}?error=request_failed"
    except Exception:
        logger.exception("Spotify OAuth unexpected error")
        return f"{frontend_url}?error=unknown_error"

    return f"{frontend_url}?success=true"
