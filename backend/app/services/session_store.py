"""
Session store implementations.
Uses Redis when REDIS_URL is set, otherwise falls back to in-memory storage.
"""

import asyncio
import json
import logging
import time
from threading import Lock
from typing import Optional

from redis import Redis

from app.config import get_settings

logger = logging.getLogger(__name__)


class InMemorySessionStore:
    """Thread-safe in-memory session storage with TTL and automatic cleanup"""

    def __init__(self, session_ttl: int = 86400):
        self._sessions: dict[str, dict] = {}
        self._lock = Lock()
        self._session_ttl = session_ttl  # 24 hours default
        self._cleanup_task: Optional[asyncio.Task] = None
        self._cleanup_running = False

    def create_session(self, session_id: str) -> dict:
        """Create a new session"""
        with self._lock:
            self._sessions[session_id] = {
                "created_at": time.time(),
                "last_accessed": time.time(),
                "expires_at": time.time() + self._session_ttl,
                "access_token": None,
                "refresh_token": None,
                "token_expires_at": None,
                "user_name": None,
                "user_image": None,
                "pkce": None,
            }
            return self._sessions[session_id]

    def get_session(self, session_id: str) -> Optional[dict]:
        """Get session by ID, return None if expired"""
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                # Check if session expired
                if time.time() > session["expires_at"]:
                    del self._sessions[session_id]
                    return None
                # Update last accessed time
                session["last_accessed"] = time.time()
            return session

    def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False

    def set_pkce_data(self, session_id: str, code_verifier: str, state: str):
        """Store PKCE data for OAuth flow"""
        with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id]["pkce"] = {
                    "code_verifier": code_verifier,
                    "state": state,
                }

    def get_pkce_data(self, session_id: str) -> Optional[dict]:
        """Get PKCE data"""
        with self._lock:
            session = self._sessions.get(session_id)
            return session.get("pkce") if session else None

    def clear_pkce_data(self, session_id: str):
        """Clear PKCE data after successful auth"""
        with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id]["pkce"] = None

    def set_tokens(
        self,
        session_id: str,
        access_token: str,
        refresh_token: Optional[str],
        expires_in: int,
    ):
        """Store OAuth tokens"""
        with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id].update(
                    {
                        "access_token": access_token,
                        "refresh_token": refresh_token,
                        "token_expires_at": time.time() + expires_in - 60,  # 1 min buffer
                    }
                )

    def update_access_token(self, session_id: str, access_token: str, expires_in: int):
        """Update access token after refresh"""
        with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id].update(
                    {
                        "access_token": access_token,
                        "token_expires_at": time.time() + expires_in - 60,
                    }
                )

    def set_user_data(self, session_id: str, user_name: str, user_image: Optional[str]):
        """Store user profile data"""
        with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id].update(
                    {"user_name": user_name, "user_image": user_image}
                )

    def is_token_expired(self, session_id: str) -> bool:
        """Check if access token is expired"""
        with self._lock:
            session = self._sessions.get(session_id)
            if not session or not session.get("token_expires_at"):
                return True
            return time.time() >= session["token_expires_at"]

    def cleanup_expired_sessions(self):
        """Remove expired sessions"""
        with self._lock:
            current_time = time.time()
            expired = [
                sid
                for sid, session in self._sessions.items()
                if current_time > session["expires_at"]
            ]
            for sid in expired:
                del self._sessions[sid]
            if expired:
                logger.info("Cleaned up %s expired sessions", len(expired))
            return len(expired)

    async def _cleanup_loop(self):
        """Background task to cleanup expired sessions"""
        while self._cleanup_running:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes
                self.cleanup_expired_sessions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("Session cleanup error: %s", e)

    def start_cleanup_task(self):
        """Start the background cleanup task"""
        if not self._cleanup_running:
            self._cleanup_running = True
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Session cleanup task started")

    def stop_cleanup_task(self):
        """Stop the background cleanup task"""
        if self._cleanup_running:
            self._cleanup_running = False
            if self._cleanup_task:
                self._cleanup_task.cancel()
            logger.info("Session cleanup task stopped")

    def clear_all(self):
        """Clear all sessions (for shutdown)"""
        with self._lock:
            count = len(self._sessions)
            self._sessions.clear()
            if count > 0:
                logger.info("Cleared %s sessions on shutdown", count)


class RedisSessionStore:
    """Redis-backed session storage with TTL"""

    def __init__(
        self,
        redis_url: str,
        session_ttl: int = 86400,
        key_prefix: str = "pseuno:session:",
    ):
        self._redis = Redis.from_url(redis_url, decode_responses=True)
        self._session_ttl = session_ttl
        self._key_prefix = key_prefix

    def _key(self, session_id: str) -> str:
        return f"{self._key_prefix}{session_id}"

    def _encode_session(self, session: dict) -> dict:
        encoded: dict[str, str] = {}
        for key, value in session.items():
            if value is None:
                encoded[key] = ""
            elif isinstance(value, dict):
                encoded[key] = json.dumps(value)
            else:
                encoded[key] = str(value)
        return encoded

    def _decode_session(self, data: dict[str, str]) -> dict:
        def to_optional(value: Optional[str]) -> Optional[str]:
            if value is None or value == "":
                return None
            return value

        def to_float(value: Optional[str]) -> Optional[float]:
            if value is None or value == "":
                return None
            try:
                return float(value)
            except ValueError:
                return None

        session = {
            "created_at": to_float(data.get("created_at")),
            "last_accessed": to_float(data.get("last_accessed")),
            "expires_at": to_float(data.get("expires_at")),
            "access_token": to_optional(data.get("access_token")),
            "refresh_token": to_optional(data.get("refresh_token")),
            "token_expires_at": to_float(data.get("token_expires_at")),
            "user_name": to_optional(data.get("user_name")),
            "user_image": to_optional(data.get("user_image")),
            "pkce": None,
        }

        pkce_raw = data.get("pkce")
        if pkce_raw:
            try:
                session["pkce"] = json.loads(pkce_raw)
            except json.JSONDecodeError:
                session["pkce"] = None

        return session

    def create_session(self, session_id: str) -> dict:
        """Create a new session"""
        now = time.time()
        session = {
            "created_at": now,
            "last_accessed": now,
            "expires_at": now + self._session_ttl,
            "access_token": None,
            "refresh_token": None,
            "token_expires_at": None,
            "user_name": None,
            "user_image": None,
            "pkce": None,
        }
        key = self._key(session_id)
        pipeline = self._redis.pipeline()
        pipeline.hset(key, mapping=self._encode_session(session))
        pipeline.expire(key, self._session_ttl)
        pipeline.execute()
        return session

    def get_session(self, session_id: str) -> Optional[dict]:
        """Get session by ID, return None if expired"""
        key = self._key(session_id)
        data = self._redis.hgetall(key)
        if not data:
            return None

        session = self._decode_session(data)
        expires_at = session.get("expires_at")
        if expires_at and time.time() > expires_at:
            self._redis.delete(key)
            return None

        self._redis.hset(key, "last_accessed", str(time.time()))
        return session

    def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        return self._redis.delete(self._key(session_id)) > 0

    def set_pkce_data(self, session_id: str, code_verifier: str, state: str):
        """Store PKCE data for OAuth flow"""
        key = self._key(session_id)
        self._redis.hset(
            key,
            "pkce",
            json.dumps({"code_verifier": code_verifier, "state": state}),
        )

    def get_pkce_data(self, session_id: str) -> Optional[dict]:
        """Get PKCE data"""
        key = self._key(session_id)
        data = self._redis.hget(key, "pkce")
        if not data:
            return None
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return None

    def clear_pkce_data(self, session_id: str):
        """Clear PKCE data after successful auth"""
        self._redis.hdel(self._key(session_id), "pkce")

    def set_tokens(
        self,
        session_id: str,
        access_token: str,
        refresh_token: Optional[str],
        expires_in: int,
    ):
        """Store OAuth tokens"""
        token_expires_at = time.time() + expires_in - 60
        self._redis.hset(
            self._key(session_id),
            mapping={
                "access_token": access_token,
                "refresh_token": refresh_token or "",
                "token_expires_at": str(token_expires_at),
            },
        )

    def update_access_token(self, session_id: str, access_token: str, expires_in: int):
        """Update access token after refresh"""
        token_expires_at = time.time() + expires_in - 60
        self._redis.hset(
            self._key(session_id),
            mapping={
                "access_token": access_token,
                "token_expires_at": str(token_expires_at),
            },
        )

    def set_user_data(self, session_id: str, user_name: str, user_image: Optional[str]):
        """Store user profile data"""
        self._redis.hset(
            self._key(session_id),
            mapping={
                "user_name": user_name,
                "user_image": user_image or "",
            },
        )

    def is_token_expired(self, session_id: str) -> bool:
        """Check if access token is expired"""
        value = self._redis.hget(self._key(session_id), "token_expires_at")
        if not value:
            return True
        try:
            return time.time() >= float(value)
        except ValueError:
            return True

    def cleanup_expired_sessions(self):
        """Redis handles TTL expiration automatically"""
        return 0

    def start_cleanup_task(self):
        """No-op for Redis-backed store"""
        return None

    def stop_cleanup_task(self):
        """No-op for Redis-backed store"""
        return None

    def clear_all(self):
        """Clear all sessions for this app prefix"""
        keys = list(self._redis.scan_iter(match=f"{self._key_prefix}*"))
        if keys:
            self._redis.delete(*keys)


def create_session_store():
    settings = get_settings()
    if not settings.debug and not settings.redis_url:
        raise ValueError(
            "REDIS_URL must be set in production for session storage"
        )
    if settings.redis_url:
        return RedisSessionStore(
            settings.redis_url,
            session_ttl=settings.session_max_age,
        )
    return InMemorySessionStore(session_ttl=settings.session_max_age)


session_store = create_session_store()
