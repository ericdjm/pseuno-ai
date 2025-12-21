"""
Advanced generation routes using vibe-first methodology
"""

from fastapi import APIRouter, Request

from app.models_advanced import (
    AdvancedGenerateRequest,
    AdvancedGenerateResponse,
)
from app.services.advanced_prompt_builder import AdvancedPromptBuilder, MODE_PRESETS
from app.utils import get_authenticated_client, fetch_and_parse_spotify_data

router = APIRouter()


@router.get("/modes")
async def get_modes():
    """Get available generation modes with descriptions"""
    return {
        "modes": {
            mode: {
                "description": preset["description"],
                "vibe_keywords": preset["vibe_keywords"]
            }
            for mode, preset in MODE_PRESETS.items()
        }
    }


@router.post("/advanced", response_model=AdvancedGenerateResponse)
async def generate_advanced(request: Request, body: AdvancedGenerateRequest):
    """
    Advanced vibe-first generation
    
    Implements:
    - Vibe-first intent (not genre-first)
    - Orthogonal control layers (vocals, rhythm, texture, structure)
    - Contrast-based iteration
    - Rule breaking permissions
    - Content themes as anchors
    - Lyric density matching intensity
    - Separated artifacts (lyrics vs prompt)
    """
    client = get_authenticated_client(request)
    
    # Fetch and parse Spotify data for taste profile (uses parallel API calls)
    _, _, taste_profile = await fetch_and_parse_spotify_data(
        client, body.time_range
    )
    
    # Generate using advanced builder
    builder = AdvancedPromptBuilder(taste_profile)
    result = builder.generate(body)
    
    return AdvancedGenerateResponse(**result)
