"""
Unified refinement service for multi-field edits.

This service handles a single user instruction that can update multiple fields:
- Suno prompt (style)
- Lyrics
- Exclude
- Title
- Weirdness

It uses an LLM "planner" to decide which fields to modify, then executes
the edits using existing refinement primitives for style/lyrics.
"""

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.config import Settings
from app.prompts.specs import (
    WEIRDNESS_RANGES,
    TITLE_RULES,
    EXCLUDE_GUIDELINES,
)
from app.schemas.unified_refine import PlannerOutput, UnifiedRefineRequest
from app.services.debug_trace import DebugTracer
from app.services.refine_service import refine_lyrics, refine_style_prompt

logger = logging.getLogger(__name__)

# Gemini models that require the google-genai SDK
GEMINI_MODELS = {
    "gemini-3-flash-preview",
    "gemini-3-pro-preview",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
}

# Timeout for planner LLM call
PLANNER_TIMEOUT_SECONDS = 30


# =============================================================================
# PUBLIC API
# =============================================================================


async def refine_all(
    request: UnifiedRefineRequest,
    settings: Settings,
) -> Tuple[dict, List[str], Optional[str], Dict[str, Any]]:
    """
    Apply multi-field edits based on user instruction.

    Returns:
        Tuple of (updated_snapshot, changed_fields, assistant_message, debug_info)
    """
    # Initialize tracer for this refinement
    tracer = DebugTracer(
        variant="refine",
        model=settings.llm_model,
        architecture="unified_refine",
    )

    # Step 1: Call planner to decide what to change
    with tracer.span("refine.planner", "llm_call", model=settings.llm_model) as span:
        plan = await _call_planner(request, settings)
        span.set_meta("edit_style", plan.edit_style)
        span.set_meta("edit_lyrics", plan.edit_lyrics)
        span.set_meta("has_exclude_update", plan.exclude_update is not None)
        span.set_meta("has_title_update", plan.title_update is not None)
        span.set_meta("has_weirdness_update", plan.weirdness_update is not None)
        span.set_artifact("change_request", request.change_request)
        # Show the planner's decisions
        if plan.style_change_request:
            span.set_artifact("style_instruction", plan.style_change_request)
        if plan.lyrics_change_request:
            span.set_artifact("lyrics_instruction", plan.lyrics_change_request)
        if plan.exclude_update:
            span.set_artifact(
                "exclude_update",
                f"{plan.exclude_update.mode}: {plan.exclude_update.value}",
            )
        if plan.title_update:
            span.set_artifact("title_update", plan.title_update)
        if plan.weirdness_update is not None:
            span.set_meta("weirdness_update", plan.weirdness_update)

    # Step 2: Execute the plan
    updated_snapshot = {
        "suno_prompt": request.suno_prompt,
        "lyrics": request.lyrics,
        "exclude": request.exclude,
        "title": request.title,
        "weirdness": request.weirdness,
    }
    changed_fields: List[str] = []

    # Execute style and lyrics edits IN PARALLEL with tracing
    style_span_data: Dict[str, Any] = {}
    lyrics_span_data: Dict[str, Any] = {}

    async def do_style_refine():
        if not (plan.edit_style and plan.style_change_request):
            return None
        logger.info(f"Planner style_change_request: '{plan.style_change_request}'")
        style_span_data["change_request"] = plan.style_change_request
        style_span_data["input_chars"] = len(request.suno_prompt)
        style_span_data["before"] = request.suno_prompt  # For debug trace
        try:
            new_prompt = await refine_style_prompt(
                current_prompt=request.suno_prompt,
                change_request=plan.style_change_request,
                settings=settings,
            )
            delta = len(new_prompt) - len(request.suno_prompt)
            logger.info(
                f"Style refine result: {len(request.suno_prompt)} -> {len(new_prompt)} chars ({delta:+d})"
            )
            style_span_data["output_chars"] = len(new_prompt)
            style_span_data["delta"] = delta
            style_span_data["success"] = True
            style_span_data["after"] = new_prompt  # For debug trace
            return new_prompt
        except Exception as e:
            logger.warning(f"Style refinement failed: {e}")
            style_span_data["error"] = str(e)
            style_span_data["success"] = False
            return None

    async def do_lyrics_refine():
        if not (plan.edit_lyrics and plan.lyrics_change_request):
            return None
        logger.info(f"Planner lyrics_change_request: '{plan.lyrics_change_request}'")
        lyrics_span_data["change_request"] = plan.lyrics_change_request
        lyrics_span_data["input_chars"] = len(request.lyrics)
        lyrics_span_data["before"] = request.lyrics  # For debug trace
        try:
            new_lyrics = await refine_lyrics(
                current_lyrics=request.lyrics,
                change_request=plan.lyrics_change_request,
                settings=settings,
            )
            delta = len(new_lyrics) - len(request.lyrics)
            logger.info(
                f"Lyrics refine result: {len(request.lyrics)} -> {len(new_lyrics)} chars ({delta:+d})"
            )
            lyrics_span_data["output_chars"] = len(new_lyrics)
            lyrics_span_data["delta"] = delta
            lyrics_span_data["success"] = True
            lyrics_span_data["after"] = new_lyrics  # For debug trace
            return new_lyrics
        except Exception as e:
            logger.warning(f"Lyrics refinement failed: {e}")
            lyrics_span_data["error"] = str(e)
            lyrics_span_data["success"] = False
            return None

    # Run both in parallel and time them
    import time

    parallel_start = time.time()
    style_result, lyrics_result = await asyncio.gather(
        do_style_refine(),
        do_lyrics_refine(),
    )
    parallel_elapsed_ms = int((time.time() - parallel_start) * 1000)

    # Add spans for style and lyrics (they ran in parallel, so add after)
    if plan.edit_style and plan.style_change_request:
        # Extract artifacts from span data
        style_artifacts = {}
        if "before" in style_span_data:
            style_artifacts["before"] = style_span_data.pop("before")
        if "after" in style_span_data:
            style_artifacts["after"] = style_span_data.pop("after")
        tracer.add_span(
            name="refine.style",
            kind="llm_call",
            start_ms=tracer._elapsed_ms() - parallel_elapsed_ms,
            end_ms=tracer._elapsed_ms(),
            meta={
                "model": settings.llm_model,
                **style_span_data,
            },
            artifacts=style_artifacts if style_artifacts else None,
        )

    if plan.edit_lyrics and plan.lyrics_change_request:
        # Extract artifacts from span data
        lyrics_artifacts = {}
        if "before" in lyrics_span_data:
            lyrics_artifacts["before"] = lyrics_span_data.pop("before")
        if "after" in lyrics_span_data:
            lyrics_artifacts["after"] = lyrics_span_data.pop("after")
        tracer.add_span(
            name="refine.lyrics",
            kind="llm_call",
            start_ms=tracer._elapsed_ms() - parallel_elapsed_ms,
            end_ms=tracer._elapsed_ms(),
            meta={
                "model": settings.lyrics_refine_model,
                **lyrics_span_data,
            },
            artifacts=lyrics_artifacts if lyrics_artifacts else None,
        )

    # Apply results
    if style_result is not None and style_result != request.suno_prompt:
        updated_snapshot["suno_prompt"] = style_result
        changed_fields.append("suno_prompt")

    if lyrics_result is not None and lyrics_result != request.lyrics:
        updated_snapshot["lyrics"] = lyrics_result
        changed_fields.append("lyrics")

    # Apply exclude update if requested
    if plan.exclude_update:
        with tracer.span("refine.exclude", "other") as span:
            new_exclude = _apply_exclude_update(
                current=request.exclude,
                mode=plan.exclude_update.mode,
                value=plan.exclude_update.value,
            )
            span.set_meta("mode", plan.exclude_update.mode)
            span.set_meta("value", plan.exclude_update.value)
            if new_exclude != request.exclude:
                updated_snapshot["exclude"] = new_exclude
                changed_fields.append("exclude")
                span.set_meta("changed", True)
            else:
                span.set_meta("changed", False)

    # Apply title update if requested
    if plan.title_update is not None:
        with tracer.span("refine.title", "other") as span:
            new_title = plan.title_update.strip()[:120]
            span.set_meta("new_title", new_title)
            if new_title and new_title != request.title:
                updated_snapshot["title"] = new_title
                changed_fields.append("title")
                span.set_meta("changed", True)
            else:
                span.set_meta("changed", False)

    # Apply weirdness update if requested
    if plan.weirdness_update is not None:
        with tracer.span("refine.weirdness", "other") as span:
            new_weirdness = max(0, min(100, plan.weirdness_update))
            span.set_meta("new_weirdness", new_weirdness)
            if new_weirdness != request.weirdness:
                updated_snapshot["weirdness"] = new_weirdness
                changed_fields.append("weirdness")
                span.set_meta("changed", True)
            else:
                span.set_meta("changed", False)

    logger.info(f"Unified refine completed: changed_fields={changed_fields}")

    return updated_snapshot, changed_fields, plan.assistant_message, tracer.to_dict()


# =============================================================================
# PLANNER
# =============================================================================


PLANNER_SYSTEM_PROMPT = f"""You route user edit requests to the right fields. Output JSON only.

FIELDS:
- suno_prompt: Style description (≤500 chars)
- lyrics: Song lyrics with [Verse], [Chorus], etc.
- exclude: Terms to avoid (comma-separated)
- title: Song title
- weirdness: 0-100 (experimental level)

ROUTING RULES:
- Lyrics/verse/chorus/rhyme/words → edit_lyrics=true
- Sound/style/vibe/production/instruments → edit_style=true
- "avoid X" / "no X" → exclude_update
- Title mention → title_update
- "more experimental" → increase weirdness; "more mainstream" → decrease

IMPORTANT - VOCAL CHANGES:
When user mentions adding vocals (backing vocals, harmonies, choir, etc.):
1. edit_style=true with instruction like "add female backing vocals" (tells Suno what voice to use)
2. edit_lyrics=true with instruction to add vocal notation like "(Oh)" (tells Suno when to sing it)
Both are needed - style defines the voice, lyrics define the words.

=== FIELD-SPECIFIC RULES ===

WEIRDNESS:
{WEIRDNESS_RANGES}
When adjusting weirdness, consider the genre context.

TITLE:
{TITLE_RULES}

EXCLUDE:
{EXCLUDE_GUIDELINES}

=== OUTPUT INSTRUCTIONS ===

CRITICAL: style_change_request and lyrics_change_request must be SHORT INSTRUCTIONS (≤50 chars), NOT the actual content.

GOOD examples:
- style_change_request: "add subtle synth pads"
- lyrics_change_request: "change rhyme scheme to AABB"

BAD examples (DO NOT DO THIS):
- style_change_request: "Late 90s rock with guitars..." (this is CONTENT, not instruction)

OUTPUT (JSON only):
{{
  "edit_style": boolean,
  "style_change_request": "short instruction" or null,
  "edit_lyrics": boolean,
  "lyrics_change_request": "short instruction" or null,
  "exclude_update": {{"mode": "append"|"remove_terms", "value": "terms"}} or null,
  "title_update": "new title" or null,
  "weirdness_update": number or null,
  "assistant_message": "brief response to user" or null
}}"""


async def _call_planner(
    request: UnifiedRefineRequest,
    settings: Settings,
) -> PlannerOutput:
    """Call LLM to plan which fields to edit."""
    model = settings.llm_model
    is_gemini = model in GEMINI_MODELS or model.startswith("gemini-")

    # Build target-aware context
    target_context = ""
    if request.refine_target == "style":
        target_context = """
IMPORTANT: This is a STYLE-ONLY refinement.
- You MAY edit: suno_prompt (style), exclude, weirdness
- You MUST NOT edit: lyrics, title
- Set edit_lyrics=false, lyrics_change_request=null, title_update=null"""
    elif request.refine_target == "lyrics":
        target_context = """
IMPORTANT: This is a LYRICS-ONLY refinement.
- You MAY edit: lyrics, title
- You MUST NOT edit: suno_prompt (style), exclude, weirdness
- Set edit_style=false, style_change_request=null, exclude_update=null, weirdness_update=null"""

    user_message = f"""CURRENT STATE:
- Title: {request.title}
- Weirdness: {request.weirdness}
- Exclude: {request.exclude or "(none)"}
- Suno Prompt: {request.suno_prompt}
- Lyrics:
{request.lyrics or "(instrumental - no lyrics)"}
{target_context}
USER REQUEST:
{request.change_request}"""

    if is_gemini:
        raw_output = await _call_gemini_planner(
            system_prompt=PLANNER_SYSTEM_PROMPT,
            user_message=user_message,
            model=model,
            api_key=settings.gemini_api_key,
        )
    else:
        raw_output = await _call_openai_planner(
            system_prompt=PLANNER_SYSTEM_PROMPT,
            user_message=user_message,
            model=model,
            api_key=settings.openai_api_key,
        )

    # Parse JSON output
    plan = _parse_planner_output(raw_output)

    # Enforce target constraints (in case LLM didn't follow instructions)
    if request.refine_target == "style":
        # Force no lyrics/title changes
        plan.edit_lyrics = False
        plan.lyrics_change_request = None
        plan.title_update = None
    elif request.refine_target == "lyrics":
        # Force no style/exclude/weirdness changes
        plan.edit_style = False
        plan.style_change_request = None
        plan.exclude_update = None
        plan.weirdness_update = None

    logger.info(
        f"Planner plan (target={request.refine_target}): edit_style={plan.edit_style}, "
        f"edit_lyrics={plan.edit_lyrics}, exclude_update={plan.exclude_update}, "
        f"title_update={plan.title_update is not None}, weirdness_update={plan.weirdness_update}"
    )
    return plan


def _parse_planner_output(raw: str) -> PlannerOutput:
    """Parse LLM JSON output into PlannerOutput with robust truncation handling."""
    # Clean up common issues
    raw = raw.strip()
    # Remove markdown code blocks if present
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        raw = raw.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse planner output: {e}")
        logger.debug(f"Raw output: {raw[:500]}")

        # Try to repair truncated JSON by extracting what we can with regex
        data = {}

        # Extract boolean fields
        edit_style_match = re.search(
            r'"edit_style"\s*:\s*(true|false)', raw, re.IGNORECASE
        )
        if edit_style_match:
            data["edit_style"] = edit_style_match.group(1).lower() == "true"

        edit_lyrics_match = re.search(
            r'"edit_lyrics"\s*:\s*(true|false)', raw, re.IGNORECASE
        )
        if edit_lyrics_match:
            data["edit_lyrics"] = edit_lyrics_match.group(1).lower() == "true"

        # Extract string fields (handle potential truncation)
        style_req_match = re.search(r'"style_change_request"\s*:\s*"([^"]*)"', raw)
        if style_req_match:
            data["style_change_request"] = style_req_match.group(1)

        lyrics_req_match = re.search(r'"lyrics_change_request"\s*:\s*"([^"]*)"', raw)
        if lyrics_req_match:
            data["lyrics_change_request"] = lyrics_req_match.group(1)

        # If we found change requests but no explicit edit flags, infer them
        if data.get("style_change_request") and "edit_style" not in data:
            data["edit_style"] = True
        if data.get("lyrics_change_request") and "edit_lyrics" not in data:
            data["edit_lyrics"] = True

        logger.info(f"Recovered partial plan from truncated JSON: {data}")

        if not data:
            return PlannerOutput()

    # Build ExcludeUpdate if present
    exclude_update = None
    if data.get("exclude_update"):
        from app.schemas.unified_refine import ExcludeUpdate

        eu = data["exclude_update"]
        if isinstance(eu, dict) and "mode" in eu and "value" in eu:
            exclude_update = ExcludeUpdate(mode=eu["mode"], value=eu["value"])

    return PlannerOutput(
        edit_style=data.get("edit_style", False),
        style_change_request=data.get("style_change_request"),
        edit_lyrics=data.get("edit_lyrics", False),
        lyrics_change_request=data.get("lyrics_change_request"),
        exclude_update=exclude_update,
        title_update=data.get("title_update"),
        weirdness_update=data.get("weirdness_update"),
        assistant_message=data.get("assistant_message"),
    )


# =============================================================================
# EXCLUDE LOGIC
# =============================================================================


def _apply_exclude_update(current: str, mode: str, value: str) -> str:
    """Apply an exclude update based on mode."""
    # Normalize current excludes to list
    current_terms = [t.strip() for t in current.split(",") if t.strip()]
    value_terms = [t.strip() for t in value.split(",") if t.strip()]

    if mode == "replace":
        result_terms = value_terms
    elif mode == "append":
        # Add new terms, avoid duplicates (case-insensitive)
        existing_lower = {t.lower() for t in current_terms}
        for term in value_terms:
            if term.lower() not in existing_lower:
                current_terms.append(term)
                existing_lower.add(term.lower())
        result_terms = current_terms
    elif mode == "remove_terms":
        # Remove matching terms (case-insensitive)
        remove_lower = {t.lower() for t in value_terms}
        result_terms = [t for t in current_terms if t.lower() not in remove_lower]
    else:
        logger.warning(f"Unknown exclude mode: {mode}")
        result_terms = current_terms

    return ", ".join(result_terms)


# =============================================================================
# LLM CALL HELPERS
# =============================================================================


async def _call_gemini_planner(
    system_prompt: str,
    user_message: str,
    model: str,
    api_key: Optional[str],
) -> str:
    """Call Gemini for planner."""
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is required for Gemini models")

    from google import genai
    from google.genai import types

    def _sync_generate():
        from google.genai import errors as genai_errors

        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=PLANNER_TIMEOUT_SECONDS * 1000),
        )
        config = types.GenerateContentConfig(
            temperature=0.2,  # Low for structured output
            max_output_tokens=2000,
            system_instruction=system_prompt,
            response_mime_type="application/json",  # Force JSON output
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
            return response.text if response.text else "{}"
        except genai_errors.ServerError as e:
            logger.warning(f"Gemini server error: {e}")
            raise RuntimeError("AI service timed out. Please try again.")
        except genai_errors.APIError as e:
            logger.warning(f"Gemini API error: {e}")
            raise RuntimeError(f"AI service error: {e}")

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_sync_generate),
            timeout=PLANNER_TIMEOUT_SECONDS + 5,
        )
        return result.strip()
    except asyncio.TimeoutError:
        logger.warning(
            f"Gemini planner call timed out after {PLANNER_TIMEOUT_SECONDS}s"
        )
        raise RuntimeError("AI service timed out. Please try again.")


async def _call_openai_planner(
    system_prompt: str,
    user_message: str,
    model: str,
    api_key: Optional[str],
) -> str:
    """Call OpenAI for planner."""
    import httpx

    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for OpenAI models")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.2,
        "max_tokens": 2000,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(PLANNER_TIMEOUT_SECONDS)
    ) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
