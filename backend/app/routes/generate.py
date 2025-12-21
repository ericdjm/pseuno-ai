"""
Prompt and Lyrics Generation Routes
"""

from fastapi import APIRouter, Request, HTTPException

from app.models import GenerateRequest, GenerateResponse
from app.services.prompt_builder import PromptBuilder
from app.config import get_settings
from app.utils import get_authenticated_client, fetch_and_parse_spotify_data

router = APIRouter()


@router.post("", response_model=GenerateResponse)
async def generate_prompt(request: Request, body: GenerateRequest):
    """
    Generate Suno AI prompt and lyrics based on user's taste profile
    
    Parameters:
    - time_range: short_term | medium_term | long_term
    - theme: Optional theme or story idea
    - energy: 0-100 (calm to energetic)
    - rhythm_complexity: 0-100 (simple to complex)
    - darkness: 0-100 (light/happy to dark/melancholic)
    - extra_notes: Additional instructions
    - preset: Optional genre preset override
    """
    settings = get_settings()
    client = get_authenticated_client(request)
    
    # Fetch and parse Spotify data (uses parallel API calls)
    _, _, taste_profile = await fetch_and_parse_spotify_data(
        client, body.time_range
    )
    
    # Generate prompt and lyrics
    builder = PromptBuilder(taste_profile)
    
    result = builder.generate(
        theme=body.theme,
        energy=body.energy,
        rhythm_complexity=body.rhythm_complexity,
        darkness=body.darkness,
        extra_notes=body.extra_notes,
        preset=body.preset
    )
    
    # Include debug info only in dev mode
    debug_profile = taste_profile if settings.debug else None
    
    return GenerateResponse(
        concept_title=result["concept_title"],
        suno_prompt=result["suno_prompt"],
        lyrics=result["lyrics"],
        debug_profile=debug_profile
    )
