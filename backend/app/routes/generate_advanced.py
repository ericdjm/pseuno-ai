"""
Minimal generation routes for the Suno formatter agent.
"""

from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.schemas.advanced import (
    AdvancedGenerateRequest,
    AdvancedGenerateResponse,
    LyricsOnlyRequest,
    LyricsOnlyResponse,
)
from app.deps import get_song_agent
from app.services.agent_prompt_graph import AgentPromptGraph
from app.prompts import (
    LYRICS_SYSTEM_PROMPT,
    AVAILABLE_MODELS,
    list_variants,
)
from app.config import get_settings

router = APIRouter()


class PromptVariantInfo(BaseModel):
    """Info about an available prompt variant."""

    id: str
    description: str
    is_default: bool = False
    prompt_length: int = 0  # Total length of system prompts in characters
    prompt_lengths: List[int] = []  # Individual lengths per LLM call


class PromptVariantsResponse(BaseModel):
    """List of available prompt variants for A/B testing."""

    variants: List[PromptVariantInfo]


@router.get("/prompt-variants", response_model=PromptVariantsResponse)
async def list_prompt_variants_endpoint():
    """
    List available prompt variants for A/B testing.
    """
    variants = [
        PromptVariantInfo(
            id=v.id,
            description=v.description,
            is_default=v.is_default,
            prompt_length=v.prompt_length,
            prompt_lengths=v.prompt_lengths,
        )
        for v in list_variants()
    ]
    return PromptVariantsResponse(variants=variants)


class ModelInfo(BaseModel):
    """Info about an available LLM model."""

    id: str
    name: str
    provider: str
    is_default: bool = False
    is_style_default: bool = False
    is_lyrics_default: bool = False


class ModelsResponse(BaseModel):
    """List of available LLM models."""

    models: List[ModelInfo]
    default_model: str
    default_style_model: str
    default_lyrics_model: str


@router.get("/models", response_model=ModelsResponse)
async def list_models():
    """
    List available LLM models for generation.
    """
    settings = get_settings()
    models = [
        ModelInfo(
            id=model["id"],
            name=model["name"],
            provider=model["provider"],
            is_default=(model["id"] == settings.llm_model),
            is_style_default=(model["id"] == settings.style_model),
            is_lyrics_default=(model["id"] == settings.lyrics_model),
        )
        for model in AVAILABLE_MODELS
    ]
    return ModelsResponse(
        models=models,
        default_model=settings.llm_model,
        default_style_model=settings.style_model,
        default_lyrics_model=settings.lyrics_model,
    )


@router.post("/advanced", response_model=AdvancedGenerateResponse)
async def generate_advanced(
    body: AdvancedGenerateRequest,
    agent: AgentPromptGraph = Depends(get_song_agent),
):
    """
    Minimal Suno formatter generation (no auth required).
    """
    from fastapi import HTTPException

    # Reuse the startup-initialized agent to avoid per-request graph compilation.
    result = await agent.generate(body)

    # Handle agent errors
    if not result.get("success", True):
        error_msg = result.get("error", "Generation failed")
        raise HTTPException(status_code=500, detail=error_msg)

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
