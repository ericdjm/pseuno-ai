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
from app.prompts import LYRICS_SYSTEM_PROMPT

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
    raw_output = await agent._call_llm(LYRICS_SYSTEM_PROMPT, context_text)

    # Parse the output to extract SONG TITLE and LYRICS sections
    # (The LLM returns section headers that must be stripped)
    _, sections = agent._extract_sections(raw_output)

    song_title = _first_non_empty_line(sections.get("SONG TITLE", ""))
    lyrics = sections.get("LYRICS", "").strip()

    # Fallback if parsing fails (raw output had no headers)
    if not lyrics:
        lyrics = raw_output.strip()
    if not song_title:
        song_title = "Untitled"

    return LyricsOnlyResponse(song_title=song_title, lyrics=lyrics)


def _first_non_empty_line(text: str) -> str:
    """Extract the first non-empty line from text."""
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return ""
