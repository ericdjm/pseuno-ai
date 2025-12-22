"""
Minimal generation routes for the Suno formatter agent.
"""

from fastapi import APIRouter, Depends

from app.schemas.advanced import (
    AdvancedGenerateRequest,
    AdvancedGenerateResponse,
)
from app.deps import get_song_agent
from app.services.agent_prompt_graph import AgentPromptGraph

router = APIRouter()

@router.post("/advanced", response_model=AdvancedGenerateResponse)
async def generate_advanced(
    body: AdvancedGenerateRequest,
    agent: AgentPromptGraph = Depends(get_song_agent),
):
    """
    Minimal Suno formatter generation (no auth required).
    """
    # Reuse the startup-initialized agent to avoid per-request graph compilation.
    result = await agent.generate(body)

    return AdvancedGenerateResponse(**result)
