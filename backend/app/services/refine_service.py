"""
Refinement service for editing existing Suno prompts and lyrics.

This service handles targeted edits to generated outputs while preserving
the original structure and intent. Uses the same LLM calling patterns
as agent_prompt_graph.py for consistency.

Design principles:
- Targeted edits: Change only what's requested, preserve everything else
- Spec-driven: Uses composable specs from app.prompts.specs
- Architecture-aligned: Same LLM abstraction as the main generation pipeline
"""

import asyncio
import logging
from typing import Optional

from app.config import Settings
from app.constants import SUNO_PROMPT_MAX_CHARS
from app.prompts.specs import (
    REFINE_STYLE_SPEC,
    REFINE_LYRICS_SPEC,
    VOCAL_FORMATTING_SPEC,
)

logger = logging.getLogger(__name__)

# Gemini models that require the google-genai SDK
GEMINI_MODELS = {
    "gemini-3-flash-preview",
    "gemini-3-pro-preview",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
}


# =============================================================================
# PUBLIC API
# =============================================================================


async def refine_style_prompt(
    current_prompt: str,
    change_request: str,
    settings: Settings,
) -> str:
    """
    Refine an existing Suno style prompt based on user feedback.

    Args:
        current_prompt: The current Suno prompt text
        change_request: What the user wants to change
        settings: App settings (contains llm_model, api keys, etc.)

    Returns:
        The refined prompt as a string (≤500 chars, complete sentences)
    """
    model = settings.llm_model
    is_gemini = model in GEMINI_MODELS or model.startswith("gemini-")

    # Compose system prompt from specs
    system_prompt = _build_style_refine_prompt()

    # Clear user message format
    user_message = f"""CURRENT PROMPT:
{current_prompt}

REQUESTED CHANGE:
{change_request}"""

    if is_gemini:
        refined = await _call_gemini(
            system_prompt=system_prompt,
            user_message=user_message,
            model=model,
            api_key=settings.gemini_api_key,
            temperature=0.3,
            max_output_tokens=800,
        )
    else:
        refined = await _call_openai(
            system_prompt=system_prompt,
            user_message=user_message,
            model=model,
            api_key=settings.openai_api_key,
            temperature=0.3,
            max_tokens=800,
        )

    # Clean up common LLM artifacts
    refined = _clean_llm_output(refined)

    # Enforce Suno's character limit with smart truncation
    if len(refined) > SUNO_PROMPT_MAX_CHARS:
        refined = _truncate_at_sentence(refined, SUNO_PROMPT_MAX_CHARS)

    logger.info(f"Refined style prompt: {len(current_prompt)} -> {len(refined)} chars")
    return refined


async def refine_lyrics(
    current_lyrics: str,
    change_request: str,
    settings: Settings,
) -> str:
    """
    Refine lyrics based on user feedback while preserving structure markers.

    Args:
        current_lyrics: The current lyrics with structure tags
        change_request: What the user wants to change
        settings: App settings (contains llm_model, api keys, etc.)

    Returns:
        The refined lyrics as a string with structure preserved
    """
    model = settings.llm_model
    is_gemini = model in GEMINI_MODELS or model.startswith("gemini-")

    # Compose system prompt from specs
    system_prompt = _build_lyrics_refine_prompt()

    user_message = f"""CURRENT LYRICS:
{current_lyrics}

REQUESTED CHANGE:
{change_request}"""

    if is_gemini:
        refined = await _call_gemini(
            system_prompt=system_prompt,
            user_message=user_message,
            model=model,
            api_key=settings.gemini_api_key,
            temperature=0.5,
            max_output_tokens=2000,
        )
    else:
        refined = await _call_openai(
            system_prompt=system_prompt,
            user_message=user_message,
            model=model,
            api_key=settings.openai_api_key,
            temperature=0.5,
            max_tokens=2000,
        )

    # Clean up common LLM artifacts
    refined = _clean_llm_output(refined)

    # Enforce max length at line boundary
    if len(refined) > 3000:
        refined = refined[:3000].rsplit("\n", 1)[0]

    logger.info(f"Refined lyrics: {len(current_lyrics)} -> {len(refined)} chars")
    return refined


# =============================================================================
# PROMPT COMPOSITION (uses specs from app.prompts.specs)
# =============================================================================


def _build_style_refine_prompt() -> str:
    """
    Build the system prompt for style refinement.

    Composes from:
    - REFINE_STYLE_SPEC: Core refinement instructions
    - SUNO_PROMPT_SPEC_V10: Suno-friendly language guidance (partial)
    """
    # Extract just the language guidance section from V10
    language_guidance = """
LANGUAGE GUIDANCE (Suno-friendly terms):
- GOOD: "warm", "crisp", "punchy", "lush", "raw", "polished", "gritty"
- AVOID: "brick-wall compression", "sidechain", "parallel processing", "dithering"
- Lead with era + geography: "late-90s Midwest emo" not just "emo"
- Specify vocal register and delivery: "breathy alto" not just "female vocals"
- Production texture as vibe: "warm analog feel" not "tube saturation at 2dB"
"""

    return f"""{REFINE_STYLE_SPEC}
{language_guidance}"""


def _build_lyrics_refine_prompt() -> str:
    """
    Build the system prompt for lyrics refinement.

    Composes from:
    - REFINE_LYRICS_SPEC: Core refinement instructions
    - VOCAL_FORMATTING_SPEC: Proper vocal formatting rules
    """
    return f"""{REFINE_LYRICS_SPEC}

{VOCAL_FORMATTING_SPEC}"""


# =============================================================================
# LLM CALL HELPERS (matching agent_prompt_graph.py pattern)
# =============================================================================


# Timeout for LLM calls (seconds)
LLM_TIMEOUT_SECONDS = 60


async def _call_gemini(
    system_prompt: str,
    user_message: str,
    model: str,
    api_key: Optional[str],
    temperature: float,
    max_output_tokens: int,
) -> str:
    """Call Gemini API with timeout."""
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is required for Gemini models")

    from google import genai
    from google.genai import types

    def _sync_generate():
        from google.genai import errors as genai_errors

        # Set HTTP timeout on the client
        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=LLM_TIMEOUT_SECONDS * 1000),  # ms
        )
        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            system_instruction=system_prompt,
        )
        try:
            response = client.models.generate_content(
                model=model,
                contents=[
                    types.Content(
                        role="user", parts=[types.Part.from_text(text=user_message)]
                    )
                ],
                config=config,
            )
            # Log for debugging
            if response.candidates:
                candidate = response.candidates[0]
                logger.debug(f"Gemini finish_reason: {candidate.finish_reason}")
            return response.text if response.text else ""
        except genai_errors.ServerError as e:
            # Handle Gemini-side timeouts (504 DEADLINE_EXCEEDED)
            logger.warning(f"Gemini server error: {e}")
            raise RuntimeError("AI service timed out. Please try again.")
        except genai_errors.APIError as e:
            logger.warning(f"Gemini API error: {e}")
            raise RuntimeError(f"AI service error: {e}")

    try:
        # Also wrap with asyncio timeout as a safety net
        result = await asyncio.wait_for(
            asyncio.to_thread(_sync_generate),
            timeout=LLM_TIMEOUT_SECONDS + 5,  # Give HTTP timeout a chance first
        )
        return result.strip()
    except asyncio.TimeoutError:
        logger.warning(f"Gemini call timed out after {LLM_TIMEOUT_SECONDS}s")
        raise RuntimeError("AI service timed out. Please try again.")


async def _call_openai(
    system_prompt: str,
    user_message: str,
    model: str,
    api_key: Optional[str],
    temperature: float,
    max_tokens: int,
) -> str:
    """Call OpenAI API using httpx."""
    import httpx

    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for OpenAI models")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=httpx.Timeout(LLM_TIMEOUT_SECONDS)) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()


# =============================================================================
# OUTPUT PROCESSING
# =============================================================================


def _clean_llm_output(text: str) -> str:
    """Remove common LLM artifacts from output."""
    text = text.strip()
    # Remove surrounding quotes if present
    if (text.startswith('"') and text.endswith('"')) or (
        text.startswith("'") and text.endswith("'")
    ):
        text = text[1:-1].strip()
    # Remove markdown code blocks if present
    if text.startswith("```") and text.endswith("```"):
        lines = text.split("\n")
        inner = "\n".join(lines[1:-1]).strip()
        # Only use inner content if it's non-empty
        if inner:
            text = inner
    return text


def _truncate_at_sentence(text: str, max_chars: int) -> str:
    """Truncate text at a sentence boundary, never mid-sentence."""
    if len(text) <= max_chars:
        return text

    truncated = text[:max_chars]

    # Find last sentence-ending punctuation followed by space or end
    last_end = -1
    for i in range(len(truncated) - 1, -1, -1):
        if truncated[i] in ".!?":
            # Check if it's end of string or followed by space
            if i == len(truncated) - 1 or truncated[i + 1] == " ":
                last_end = i
                break

    if last_end > max_chars // 2:  # Only use if we preserve enough content
        return truncated[: last_end + 1]

    # Fallback: truncate at word boundary, clean trailing punctuation, add period
    truncated = truncated.rsplit(" ", 1)[0].rstrip(",;:-")
    if not truncated.endswith((".", "!", "?")):
        truncated += "."
    return truncated
