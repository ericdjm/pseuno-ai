"""
Spotify OAuth flow helpers.
"""

import base64
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from sqlalchemy import update

from app.config import Settings
from app.db.models import ExternalAccount, SunoPrompt, User
from app.db.session import SessionLocal
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
    device_token: Optional[str] = None,
) -> str:
    """
    Process the callback and return a redirect URL.

    If device_token is provided, merges any guest user prompts into the
    Spotify-linked user account.
    """
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
            try:
                user_data = user_response.json()
            except ValueError:
                logger.warning("Spotify user profile JSON parsing failed")
            else:
                user_name = user_data.get("display_name", "User")
                user_image = (
                    user_data.get("images", [{}])[0].get("url")
                    if user_data.get("images")
                    else None
                )
                user_id = _upsert_spotify_account(
                    tokens, user_data, device_token=device_token
                )
                session_store.set_user_data(
                    session_id,
                    user_name=user_name,
                    user_image=user_image,
                    user_id=user_id,
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


def _upsert_spotify_account(
    tokens: dict,
    user_data: dict,
    device_token: Optional[str] = None,
) -> Optional[str]:
    """
    Create or update a Spotify-linked user account.

    If device_token is provided and belongs to a guest user, merges their
    saved prompts into the Spotify user and removes the guest user.
    """
    provider_user_id = user_data.get("id")
    if not provider_user_id:
        return None

    token_expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=max(tokens.get("expires_in", 3600) - 60, 0)
    )
    user_image = (
        user_data.get("images", [{}])[0].get("url") if user_data.get("images") else None
    )

    db = SessionLocal()
    try:
        account = db.scalar(
            select(ExternalAccount).where(
                ExternalAccount.provider == "spotify",
                ExternalAccount.provider_user_id == provider_user_id,
            )
        )
        if account:
            # Existing Spotify user - update tokens
            account.access_token = tokens.get("access_token")
            if tokens.get("refresh_token") is not None:
                account.refresh_token = tokens.get("refresh_token")
            account.token_expires_at = token_expires_at
            account.scopes = SCOPES
            account.display_name = user_data.get("display_name")
            account.email = user_data.get("email")
            account.profile_image_url = user_image
            user = account.user
        else:
            # New Spotify user
            user = User(is_guest=False)
            account = ExternalAccount(
                user=user,
                provider="spotify",
                provider_user_id=provider_user_id,
                email=user_data.get("email"),
                display_name=user_data.get("display_name"),
                profile_image_url=user_image,
                access_token=tokens.get("access_token"),
                refresh_token=tokens.get("refresh_token"),
                token_expires_at=token_expires_at,
                scopes=SCOPES,
            )
            db.add(user)
            db.add(account)

        # Mark user as non-guest since they've linked Spotify
        user.is_guest = False

        db.flush()  # Ensure user.id is available

        # Merge guest prompts if device_token provided
        if device_token:
            guest_user = db.scalar(
                select(User).where(
                    User.device_token == device_token,
                    User.is_guest == True,  # noqa: E712
                    User.id != user.id,  # Don't match self
                )
            )
            if guest_user:
                # Transfer prompts from guest to Spotify user
                prompt_count = _merge_guest_prompts(db, guest_user.id, user.id)
                if prompt_count > 0:
                    logger.info(
                        "Merged %d prompts from guest %s to user %s",
                        prompt_count,
                        guest_user.id,
                        user.id,
                    )
                # Delete the guest user (cascade will clean up, but prompts are moved)
                db.delete(guest_user)

        db.commit()
        db.refresh(user)
        return user.id
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Failed to persist Spotify account")
        return None
    finally:
        db.close()


def _merge_guest_prompts(db, guest_user_id: str, target_user_id: str) -> int:
    """
    Transfer all prompts from guest user to target user.
    Returns the number of prompts transferred.
    """
    result = db.execute(
        update(SunoPrompt)
        .where(SunoPrompt.owner_user_id == guest_user_id)
        .values(owner_user_id=target_user_id)
    )
    return result.rowcount
