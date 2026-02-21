"""
Shared test fixtures for the backend test suite.
"""

import pytest

from app.config import Settings


@pytest.fixture
def test_settings() -> Settings:
    """Minimal Settings instance for tests (no real API keys needed)."""
    return Settings(spotify_client_id="test", openai_api_key="test")
