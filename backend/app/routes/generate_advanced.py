"""
Minimal generation routes for the Suno formatter agent.
"""

from fastapi import APIRouter

from app.models_advanced import (
    AdvancedGenerateRequest,
    AdvancedGenerateResponse,
)
from app.services.agent_prompt_builder import AgentPromptBuilder
from app.config import get_settings
router = APIRouter()

@router.post("/advanced", response_model=AdvancedGenerateResponse)
async def generate_advanced(body: AdvancedGenerateRequest):
    """
    Minimal Suno formatter generation (no auth required).
    """
    # Generate using LangChain agent
    settings = get_settings()
    builder = AgentPromptBuilder(settings)
    result = await builder.generate(body)
    
    return AdvancedGenerateResponse(**result)
