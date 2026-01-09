"""
Minimal generation routes for the Suno formatter agent.
"""

import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import LyricsThread, SunoPrompt
from app.deps import (
    get_db,
    get_current_user_id_optional,
    get_or_create_device_user,
    get_song_agent,
)
from app.prompts import (
    LYRICS_SYSTEM_PROMPT,
    AVAILABLE_MODELS,
    list_variants,
)
from app.schemas.advanced import (
    AdvancedGenerateRequest,
    AdvancedGenerateResponse,
    LyricsOnlyRequest,
    LyricsOnlyResponse,
)
from app.services.agent_prompt_graph import AgentPromptGraph

logger = logging.getLogger(__name__)

# Cookie settings for device token (1 year expiry)
DEVICE_TOKEN_MAX_AGE = 365 * 24 * 60 * 60  # 1 year in seconds

router = APIRouter()


class PromptVariantInfo(BaseModel):
    """Info about an available prompt variant."""

    id: str
    description: str
    is_default: bool = False
    prompt_length: int = 0  # Total length of system prompts in characters
    prompt_lengths: List[int] = []  # Individual lengths per LLM call
    prompt_lengths_breakdown: Dict[str, int] = (
        {}
    )  # Semantic breakdown: style/combined, lyrics, repair, total


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
            prompt_lengths_breakdown=v.prompt_lengths_breakdown,
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


def _derive_prompt_title(suno_prompt: str, auto_tags: List[str]) -> str:
    """
    Derive a default title for a saved prompt from the suno_prompt and auto_tags.

    Creates a short, descriptive title like "Synthwave • 80s • Dreamy" from tags,
    or falls back to the first 50 chars of the suno_prompt.
    """
    if auto_tags:
        # Use top 3 tags joined with bullet
        return " • ".join(tag.title() for tag in auto_tags[:3])

    # Fallback: first line or first 50 chars of suno_prompt
    first_line = suno_prompt.split("\n")[0].strip()
    if len(first_line) > 50:
        return first_line[:47] + "..."
    return first_line or "Untitled"


@router.post("/advanced", response_model=AdvancedGenerateResponse)
async def generate_advanced(
    body: AdvancedGenerateRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    agent: AgentPromptGraph = Depends(get_song_agent),
):
    """
    Suno formatter generation with automatic prompt history saving.

    - Works for both Spotify-authenticated users and guests (via device token).
    - If guest and no device_token cookie, creates a new guest user and sets cookie.
    - All successful generations are automatically saved to prompt history.
    """
    from fastapi import HTTPException

    settings = get_settings()

    # Reuse the startup-initialized agent to avoid per-request graph compilation.
    result = await agent.generate(body)

    # Handle agent errors
    if not result.get("success", True):
        error_msg = result.get("error", "Generation failed")
        raise HTTPException(status_code=500, detail=error_msg)

    # === Auto-save prompt to history ===
    prompt_id: Optional[int] = None
    try:
        # Resolve user: Spotify session OR device token (create guest if needed)
        spotify_user_id = get_current_user_id_optional(request)

        if spotify_user_id:
            user_id = spotify_user_id
        else:
            # Fall back to device token (create guest user if needed)
            user, created = get_or_create_device_user(request, db)
            user_id = user.id

            if created:
                # Set device_token cookie for new guest users
                response.set_cookie(
                    key="device_token",
                    value=user.device_token,
                    httponly=True,
                    secure=settings.session_cookie_secure,
                    samesite=settings.session_cookie_samesite,
                    max_age=DEVICE_TOKEN_MAX_AGE,
                )

        # Create the prompt history record (StylePrompt)
        auto_tags = result.get("auto_tags", [])
        # Use LLM-generated style_name if available, fallback to tag-derived title
        style_name = result.get("style_name", "").strip()
        prompt_title = style_name or _derive_prompt_title(
            result["suno_prompt"], auto_tags
        )
        prompt = SunoPrompt(
            owner_user_id=user_id,
            parent_prompt_id=None,  # Fresh generation has no parent
            source_action="generate",
            suno_prompt=result["suno_prompt"],
            lyrics=result.get("lyrics", ""),
            exclude=result.get("exclude", ""),
            weirdness=result.get("weirdness", 50),
            style_influence=result.get("style_influence", 50),
            title=prompt_title,
            is_favorite=False,
            auto_tags=auto_tags,
            generation_id=result.get("generation_id"),
        )
        db.add(prompt)
        db.flush()  # Get the ID before creating thread
        prompt_id = prompt.id

        # Create initial LyricsThread (song) for this StylePrompt
        # Always create a thread, even for instrumental songs (empty lyrics)
        lyrics_text = result.get("lyrics", "")
        # Use the actual song title (concept_title) for the thread, not the style prompt title
        song_title = result.get("concept_title") or prompt_title
        thread = LyricsThread(
            style_prompt_id=prompt.id,
            parent_thread_id=None,
            title=song_title,
            lyrics_text=lyrics_text,
            source_action="generate_initial",
        )
        db.add(thread)

        db.commit()
        logger.info("Auto-saved prompt id=%d for user=%s", prompt_id, user_id)

    except Exception as e:
        # Don't fail the request if auto-save fails - just log it
        logger.warning("Failed to auto-save prompt: %s", e)
        db.rollback()

    # Build response with prompt_id
    return AdvancedGenerateResponse(
        concept_title=result["concept_title"],
        lyrics=result.get("lyrics", ""),
        suno_prompt=result["suno_prompt"],
        exclude=result.get("exclude", ""),
        weirdness=result.get("weirdness", 50),
        style_influence=result.get("style_influence", 50),
        generation_id=result["generation_id"],
        prompt_id=prompt_id,
        is_favorite=False,
        auto_tags=result.get("auto_tags", []),
        debug_info=result.get("debug_info"),
    )


def _is_instrumental_lyrics_request(lyrics_about: str) -> bool:
    """
    Check if a lyrics-only request is for instrumental (should skip lyrics generation).

    Returns True when:
    - lyrics_about is empty or whitespace-only, OR
    - lyrics_about contains "instrumental" / "no lyrics" / "no vocals" phrases
    """
    text = (lyrics_about or "").strip().lower()

    # Empty → instrumental
    if not text:
        return True

    # Keyword detection
    instrumental_phrases = [
        "instrumental",
        "no lyrics",
        "no vocal",
        "no vocals",
        "without lyrics",
        "without vocals",
    ]
    for phrase in instrumental_phrases:
        if phrase in text:
            return True

    return False


@router.post("/lyrics-only", response_model=LyricsOnlyResponse)
async def generate_lyrics_only(
    body: LyricsOnlyRequest,
    agent: AgentPromptGraph = Depends(get_song_agent),
):
    """
    Generate new lyrics using a saved Suno prompt as style context.
    This is a simpler flow for reusing saved prompts with new lyric topics.

    For instrumental requests (blank/keyword lyrics_about), returns empty lyrics
    without making any LLM calls.
    """
    # Short-circuit for instrumental requests
    if _is_instrumental_lyrics_request(body.lyrics_about):
        return LyricsOnlyResponse(song_title="Instrumental", lyrics="")

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
