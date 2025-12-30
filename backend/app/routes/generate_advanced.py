"""
Minimal generation routes for the Suno formatter agent.
"""

import random
import re
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.schemas.advanced import (
    AdvancedGenerateRequest,
    AdvancedGenerateResponse,
    LyricsOnlyRequest,
    LyricsOnlyResponse,
    SpotifySunoPromptRequest,
    SpotifySunoPromptResponse,
    SpotifySunoPromptContext,
)
from app.constants import SUNO_PROMPT_MAX_CHARS
from app.deps import get_song_agent, get_spotify_client
from app.services.agent_prompt_graph import AgentPromptGraph
from app.schemas.spotify import SpotifyArtist
from app.services.spotify_client import SpotifyClient, SpotifyClientError
from app.prompts import (
    LYRICS_SYSTEM_PROMPT,
    SPOTIFY_SUNO_PROMPT_SYSTEM_PROMPT,
    SPOTIFY_SUNO_PROMPT_REWRITE_PROMPT,
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


@router.post("/spotify-suno-prompt", response_model=SpotifySunoPromptResponse)
async def generate_spotify_suno_prompt(
    body: SpotifySunoPromptRequest,
    client: SpotifyClient = Depends(get_spotify_client),
    agent: AgentPromptGraph = Depends(get_song_agent),
):
    """
    Generate a Suno prompt from Spotify taste data (auth required).
    """
    previous_generation = (body.suno_prompt or "").strip()
    change_request = (body.change_request or "").strip()

    top_artists = await _fetch_top_artists(client, body.time_range)

    selected_artists = body.artists or _select_random_artists(top_artists, count=2)
    if not selected_artists:
        raise HTTPException(
            status_code=400, detail="No Spotify artists available for prompt generation"
        )

    context_text = _format_spotify_prompt_context(
        selected_artists=selected_artists,
        time_range=body.time_range,
        previous_generation=previous_generation or None,
        change_request=change_request or None,
    )

    suno_prompt = await _generate_spotify_suno_prompt(
        agent=agent,
        context_text=context_text,
        selected_artists=selected_artists,
    )

    context = SpotifySunoPromptContext(
        time_range=body.time_range,
        top_artists=top_artists,
        previous_generation=previous_generation or None,
        change_request=change_request or None,
    )

    return SpotifySunoPromptResponse(
        suno_prompt=suno_prompt,
        selected_artists=selected_artists,
        context=context,
    )


def _first_non_empty_line(text: str) -> str:
    """Extract the first non-empty line from text."""
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return ""


def _select_random_artists(top_artists, count: int = 2) -> list[str]:
    names = [artist.name for artist in top_artists if artist.name]
    unique = []
    seen = set()
    for name in names:
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(name)
    if not unique:
        return []
    if len(unique) <= count:
        return unique
    return random.sample(unique, count)


async def _fetch_top_artists(
    client: SpotifyClient,
    time_range: str,
    limit: int = 20,
) -> list[SpotifyArtist]:
    try:
        top_artists_data = await client.get_top_artists(
            time_range=time_range, limit=limit
        )
    except SpotifyClientError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch Spotify data: {exc}",
        ) from exc

    return [
        SpotifyArtist(
            name=artist["name"],
            genres=artist.get("genres", []),
            popularity=artist.get("popularity", 0),
            image_url=artist["images"][0]["url"] if artist.get("images") else None,
            spotify_url=artist.get("external_urls", {}).get("spotify"),
        )
        for artist in top_artists_data.get("items", [])
    ]


def _format_spotify_prompt_context(
    selected_artists,
    time_range: str,
    previous_generation: str | None,
    change_request: str | None,
) -> str:
    lines = [
        "SPOTIFY_TASTE_CONTEXT",
        f"time_range: {time_range}",
        f"selected_artists: {selected_artists}",
    ]
    if previous_generation:
        lines.append(f"previous_generation: {previous_generation}")
    if change_request:
        lines.append(f"change_request: {change_request}")
    return "\n".join(lines)


async def _generate_spotify_suno_prompt(
    agent: AgentPromptGraph,
    context_text: str,
    selected_artists: list[str],
) -> str:
    raw = await agent._call_llm(SPOTIFY_SUNO_PROMPT_SYSTEM_PROMPT, context_text)
    prompt = _extract_suno_prompt(agent, raw)

    prompt = await _repair_suno_prompt(agent, prompt, selected_artists)
    return prompt


def _extract_suno_prompt(agent: AgentPromptGraph, raw: str) -> str:
    _, sections = agent._extract_sections(raw)
    if "SUNO PROMPT" in sections:
        text = sections["SUNO PROMPT"]
    else:
        text = raw
    return _clean_prompt_text(text)


def _clean_prompt_text(text: str) -> str:
    cleaned = (text or "").strip()
    if cleaned.lower().startswith("suno prompt"):
        parts = cleaned.split(":", 1)
        cleaned = parts[1] if len(parts) == 2 else cleaned[len("suno prompt") :]
    cleaned = cleaned.strip().strip('"').strip("'").strip()
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


async def _repair_suno_prompt(
    agent: AgentPromptGraph,
    prompt: str,
    selected_artists: list[str],
) -> str:
    cleaned = _clean_prompt_text(prompt)

    if len(cleaned) > SUNO_PROMPT_MAX_CHARS:
        cleaned = await _rewrite_prompt(
            agent,
            cleaned,
            instruction=f"Shorten to <= {SUNO_PROMPT_MAX_CHARS} chars.",
            selected_artists=selected_artists,
        )

    leaked = agent._find_artist_leaks(cleaned, selected_artists)
    if leaked:
        cleaned = agent._scrub_artist_names(cleaned, selected_artists)

    leaked = agent._find_artist_leaks(cleaned, selected_artists)
    if leaked:
        cleaned = await _rewrite_prompt(
            agent,
            cleaned,
            instruction=f"Remove artist names: {', '.join(leaked)}.",
            selected_artists=selected_artists,
        )

    cleaned = _clean_prompt_text(cleaned)
    if len(cleaned) > SUNO_PROMPT_MAX_CHARS:
        cleaned = cleaned[:SUNO_PROMPT_MAX_CHARS].rstrip(" ,.;")

    cleaned = agent._scrub_artist_names(cleaned, selected_artists)
    return cleaned


async def _rewrite_prompt(
    agent: AgentPromptGraph,
    prompt: str,
    instruction: str,
    selected_artists: list[str],
) -> str:
    user_prompt = "\n".join(
        [
            instruction,
            f"Do not include artist names: {selected_artists}",
            "PROMPT:",
            prompt,
        ]
    )
    raw = await agent._call_llm(SPOTIFY_SUNO_PROMPT_REWRITE_PROMPT, user_prompt)
    return _extract_suno_prompt(agent, raw)
