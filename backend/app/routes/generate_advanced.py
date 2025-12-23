"""
Minimal generation routes for the Suno formatter agent.
"""

from fastapi import APIRouter, Depends

from app.schemas.advanced import (
    AdvancedGenerateRequest,
    AdvancedGenerateResponse,
    LyricsOnlyRequest,
    LyricsOnlyResponse,
)
from app.deps import get_song_agent
from app.services.agent_prompt_graph import AgentPromptGraph
from app.prompts import LYRICS_ONLY_SYSTEM_PROMPT

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


@router.post("/lyrics-only", response_model=LyricsOnlyResponse)
async def generate_lyrics_only(
    body: LyricsOnlyRequest,
    agent: AgentPromptGraph = Depends(get_song_agent),
):
    """
    Generate new lyrics using a saved Suno prompt as style context.
    This is a simpler flow for reusing saved prompts with new lyric topics.
    """
    # Build context for lyrics-only generation
    context_text = f"""BEGIN_CONTEXT
suno_prompt: {body.suno_prompt}
lyrics_about: {body.lyrics_about}
END_CONTEXT"""

    # Use the agent's LLM client directly for a simpler call
    lyrics = await agent._call_llm(LYRICS_ONLY_SYSTEM_PROMPT, context_text)

    # Clean up the response (remove any accidental headers/prose)
    lyrics = lyrics.strip()

    return LyricsOnlyResponse(lyrics=lyrics)
