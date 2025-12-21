"""
In-memory session store for MVP
In production, use Redis or a database
"""

import time
from typing import Optional
from threading import Lock


class SessionStore:
    """Thread-safe in-memory session storage"""
    
    def __init__(self):
        self._sessions: dict[str, dict] = {}
        self._lock = Lock()
    
    def create_session(self, session_id: str) -> dict:
        """Create a new session"""
        with self._lock:
            self._sessions[session_id] = {
                "created_at": time.time(),
                "access_token": None,
                "refresh_token": None,
                "token_expires_at": None,
                "user_name": None,
                "user_image": None,
                "pkce": None
            }
            return self._sessions[session_id]
    
    def get_session(self, session_id: str) -> Optional[dict]:
        """Get session by ID"""
        with self._lock:
            return self._sessions.get(session_id)
    
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
    
    def clear_all(self):
        """Clear all sessions (for shutdown)"""
        with self._lock:
            self._sessions.clear()


# Global session store instance
session_store = SessionStore()
