"""
Async style classifier for lyrics topic routing.

Analyzes style_prompt (artist names, style descriptions) using a fast LLM
to extract trait weights. Results are cached for subsequent requests.

This runs asynchronously - the frontend fires it when user types,
and uses cached results when generating lyrics topics.
"""

import asyncio
import json
import logging
import re
import time
from typing import Any, Dict, Optional

from app.config import get_settings
from app.services.lyrics_topic_traits import TRAIT_DEFINITIONS

logger = logging.getLogger(__name__)

# Timeout for classifier LLM calls
# Note: Gemini enforces a minimum per-request deadline; 5s is rejected.
CLASSIFIER_TIMEOUT_SECONDS = 12

# Trait names we ask the LLM to score
CLASSIFIABLE_TRAITS = [
    "emotional_intensity",
    "melancholic",
    "uplifting",
    "dark",
    "playful",
    "romantic",
    "confessional",
    "introspective",
    "empowering",
    "urban",
    "pastoral",
    "coastal",
    "braggadocio",
    "vulnerable",
    "aggressive",
    "surreal",
    "narrative",
    "party",
    "political",
    "spiritual",
    "absurdist",
    "hip_hop_friendly",
    "rock_friendly",
    "electronic_friendly",
    "folk_friendly",
    "pop_friendly",
    "metal_friendly",
    "rnb_friendly",
    "prog_rock_friendly",
    "prog_metal_friendly",
]

CLASSIFIER_SYSTEM_PROMPT = f"""\
You are a music style analyzer. Given a style description (which may include artist names, \
genre descriptions, or vibes), output trait scores from 0.0 to 1.0.

If the input includes an artist name, infer likely lyrical traits from cultural knowledge.
When uncertain, still make a reasonable guess (don't return an empty object).
Return 3-8 traits in most cases.

Traits to consider:
{chr(10).join(f"- {t}: {TRAIT_DEFINITIONS.get(t, '')}" for t in CLASSIFIABLE_TRAITS)}

IMPORTANT:
- For artist names, think about their ACTUAL lyrical themes (not just genre)
- "Red Hot Chili Peppers" = coastal (0.8), playful (0.6), funk vibes, California imagery
- "Tool" = spiritual (0.9), prog_metal_friendly (0.9), introspective (0.8), surreal (0.7)
- "Taylor Swift" = confessional (0.8), narrative (0.7), romantic (0.7)
- "Kendrick Lamar" = political (0.7), introspective (0.8), hip_hop_friendly (0.9), narrative (0.7)

Output ONLY valid JSON object mapping trait names to float scores. Example:
{{"dark": 0.7, "introspective": 0.8, "metal_friendly": 0.6}}
"""


async def _call_gemini_classifier(
    system_prompt: str,
    user_message: str,
) -> str:
    """Call Gemini for style classification, matching codebase pattern."""
    settings = get_settings()
    api_key = settings.gemini_api_key
    model = settings.profile_inference_model  # gemini-2.0-flash

    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is required for style classification")

    from google import genai
    from google.genai import types

    def _sync_generate():
        from google.genai import errors as genai_errors

        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=CLASSIFIER_TIMEOUT_SECONDS * 1000),
        )
        config = types.GenerateContentConfig(
            temperature=0.3,  # Low for consistent classification
            max_output_tokens=512,
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
            logger.warning(f"Gemini server error in classifier: {e}")
            raise RuntimeError("AI service timed out. Please try again.")
        except genai_errors.APIError as e:
            logger.warning(f"Gemini API error in classifier: {e}")
            raise RuntimeError(f"AI service error: {e}")

    # Run in executor to avoid blocking
    loop = asyncio.get_event_loop()
    result = await asyncio.wait_for(
        loop.run_in_executor(None, _sync_generate),
        timeout=CLASSIFIER_TIMEOUT_SECONDS,
    )
    return result


def _parse_traits_response(text: str) -> Dict[str, float]:
    """Parse LLM response into trait dict, with fallback handling."""
    # Try to extract JSON from response
    text = text.strip()
    
    # Handle markdown code blocks
    if "```" in text:
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            text = match.group(1)
    
    # Try direct JSON parse
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            # Validate and clamp values
            result = {}
            for k, v in data.items():
                if k in CLASSIFIABLE_TRAITS:
                    try:
                        score = float(v)
                        if 0.0 <= score <= 1.0:
                            result[k] = score
                    except (ValueError, TypeError):
                        pass
            return result
    except json.JSONDecodeError:
        pass
    
    # Fallback: try to extract key-value pairs
    result = {}
    for trait in CLASSIFIABLE_TRAITS:
        # Look for patterns like "trait": 0.7 or trait: 0.7
        pattern = rf'["\']?{trait}["\']?\s*:\s*([\d.]+)'
        match = re.search(pattern, text)
        if match:
            try:
                score = float(match.group(1))
                if 0.0 <= score <= 1.0:
                    result[trait] = score
            except ValueError:
                pass
    
    return result


async def classify_style_prompt(
    style_prompt: str,
    timeout_seconds: float = 3.0,
    include_embeddings: bool = True,
) -> Dict[str, Any]:
    """
    Classify a style prompt into trait weights using LLM + embedding similarity.
    
    Args:
        style_prompt: User's style description (e.g., "Red Hot Chili Peppers funk rock")
        timeout_seconds: Max time to wait for LLM response
        include_embeddings: Whether to also compute embedding-based bank similarities
        
    Returns:
        Dict with:
            - traits: Dict[str, float] of trait weights from LLM
            - bank_similarities: Dict[str, float] of bank similarity scores (if include_embeddings)
            - latency_ms: How long the call took
            - success: Whether classification succeeded
            - raw_response: The raw LLM response (for debugging)
    """
    from app.services.posthog_capture import capture_background
    
    if not style_prompt or len(style_prompt.strip()) < 3:
        return {
            "traits": {},
            "bank_similarities": {},
            "latency_ms": 0,
            "success": False,
            "error": "Style prompt too short",
        }
    
    start = time.time()
    
    user_prompt = f"Analyze this style/artist description and output trait scores:\n\n{style_prompt}"
    
    async def get_llm_traits():
        try:
            raw = await _call_gemini_classifier(CLASSIFIER_SYSTEM_PROMPT, user_prompt)
            return _parse_traits_response(raw), raw
        except Exception as e:
            logger.warning(f"LLM classification failed: {e}")
            return {}, ""
    
    async def get_bank_similarities():
        if not include_embeddings:
            return {}
        try:
            from app.services.bank_embeddings import compute_bank_similarities
            return await compute_bank_similarities(style_prompt, top_k=10)
        except Exception as e:
            logger.warning(f"Embedding similarity failed: {e}")
            return {}
    
    try:
        # Run both in parallel for speed
        traits_result, bank_sims = await asyncio.gather(
            get_llm_traits(),
            get_bank_similarities(),
        )
        
        traits, raw = traits_result
        latency_ms = int((time.time() - start) * 1000)
        
        # Track in PostHog
        capture_background(
            "style_classifier.completed",
            distinct_id="backend",
            properties={
                "latency_ms": latency_ms,
                "num_traits": len(traits),
                "num_bank_sims": len(bank_sims),
                "style_prompt_length": len(style_prompt),
                "top_traits": sorted(traits.items(), key=lambda x: -x[1])[:5],
                "top_bank": list(bank_sims.keys())[0] if bank_sims else None,
            },
        )
        
        logger.info(
            f"Style classifier completed in {latency_ms}ms, "
            f"found {len(traits)} traits, {len(bank_sims)} bank similarities"
        )
        
        return {
            "traits": traits,
            "bank_similarities": bank_sims,
            "latency_ms": latency_ms,
            "success": True,
            "raw_response": raw[:500],  # Truncate for logging
        }
        
    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        
        capture_background(
            "style_classifier.failed",
            distinct_id="backend",
            properties={
                "latency_ms": latency_ms,
                "error_type": e.__class__.__name__,
                "style_prompt_length": len(style_prompt),
            },
        )
        
        logger.warning(f"Style classifier failed: {e}")
        
        return {
            "traits": {},
            "bank_similarities": {},
            "latency_ms": latency_ms,
            "success": False,
            "error": str(e),
        }
