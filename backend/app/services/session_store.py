"""
In-memory session store for MVP
In production, use Redis or a database
"""

import time
import asyncio
from typing import Optional
from threading import Lock


class SessionStore:
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
                "pkce": None
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
                    "state": state
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
        expires_in: int
    ):
        """Store OAuth tokens"""
        with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id].update({
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "token_expires_at": time.time() + expires_in - 60  # 1 min buffer
                })
    
    def update_access_token(self, session_id: str, access_token: str, expires_in: int):
        """Update access token after refresh"""
        with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id].update({
                    "access_token": access_token,
                    "token_expires_at": time.time() + expires_in - 60
                })
    
    def set_user_data(self, session_id: str, user_name: str, user_image: Optional[str]):
        """Store user profile data"""
        with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id].update({
                    "user_name": user_name,
                    "user_image": user_image
                })
    
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
                sid for sid, session in self._sessions.items()
                if current_time > session["expires_at"]
            ]
            for sid in expired:
                del self._sessions[sid]
            if expired:
                print(f"🧹 Cleaned up {len(expired)} expired sessions")
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
                print(f"⚠️  Session cleanup error: {e}")
    
    def start_cleanup_task(self):
        """Start the background cleanup task"""
        if not self._cleanup_running:
            self._cleanup_running = True
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            print("✓ Session cleanup task started")
    
    def stop_cleanup_task(self):
        """Stop the background cleanup task"""
        if self._cleanup_running:
            self._cleanup_running = False
            if self._cleanup_task:
                self._cleanup_task.cancel()
            print("✓ Session cleanup task stopped")
    
    def clear_all(self):
        """Clear all sessions (for shutdown)"""
        with self._lock:
            count = len(self._sessions)
            self._sessions.clear()
            if count > 0:
                print(f"🧹 Cleared {count} sessions on shutdown")


# Global session store instance
session_store = SessionStore()
