"""
LangGraph-based agent for Suno prompt + lyrics generation.
"""

import asyncio
import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple, TypedDict

import httpx
from langgraph.graph import END, StateGraph

from app.config import Settings
from app.constants import (
    V8_ROLE_CONFIDENCE_THRESHOLD,
    V8_REGEX_ENABLED,
    V8_SPLIT_ENABLED_VARIANTS,
)
from app.prompts import get_variant
from app.schemas.advanced import AdvancedGenerateRequest, LyricControls
from app.services.debug_trace import DebugTracer

logger = logging.getLogger(__name__)

# Gemini models that should use the Google Generative AI client
GEMINI_MODELS = frozenset(
    {
        "gemini-3-flash-preview",
        "gemini-3-pro-preview",
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-2.0-flash",
    }
)


@dataclass(frozen=True)
class _ParsedAgentOutput:
    order: Tuple[str, ...]
    sections: Dict[str, str]
    song_title: str
    lyrics: str
    suno_prompt: str
    exclude: str
    weirdness: int
    style_influence: int


@dataclass(frozen=True)
class _ParsedStyleOutput:
    """Output from the style agent (Step 1)."""

    suno_prompt: str
    exclude: str
    weirdness: int
    style_influence: int
    lyric_profile: Optional[Dict[str, str]]  # V4 only: LLM-generated profile
    raw: str


@dataclass
class GenerationContext:
    """
    Request-scoped context for a single generation.

    This avoids race conditions when the AgentPromptGraph singleton
    handles concurrent requests - each request gets its own context.
    """

    variant_id: str
    is_two_step: bool
    uses_lyric_profile: bool

    # Model configuration
    active_model: str  # Primary model (or style model for two-step)
    style_model: Optional[str] = None  # Two-step only
    lyrics_model: Optional[str] = None  # Two-step only

    # Prompts (set based on variant)
    song_prompt: Optional[str] = None  # Single-step
    repair_prompt: Optional[str] = None  # Single-step
    style_prompt: Optional[str] = None  # Two-step
    style_repair_prompt: Optional[str] = None  # Two-step
    lyrics_prompt: Optional[str] = None  # Two-step
    lyrics_repair_prompt: Optional[str] = None  # Two-step
    profile_inference_prompt: Optional[str] = None  # V4 onwards
    genre_disambiguation_prompt: Optional[str] = None  # V6 onwards


@dataclass(frozen=True)
class _ParsedLyricsOutput:
    """Output from the lyrics agent (Step 2)."""

    song_title: str
    lyrics: str
    raw: str


@dataclass(frozen=True)
class _LLMResponse:
    content: str


@dataclass
class SplitDecision:
    """
    V8 channel split decision result.

    Indicates whether style guidance should be split into VOCAL_REFERENCE vs MUSIC_TARGET,
    and if so, which artist plays which role.
    """

    split_active: bool
    music_target_artist: Optional[str] = None
    vocal_reference_artist: Optional[str] = None
    source: str = "none"  # "role_schema" | "regex" | "none"
    role_confidence: float = 0.0


def _normalize_artist_name_v8(name: str) -> str:
    """
    Normalize an artist name for comparison (V8 channel split).

    This is intentionally simple and deterministic:
    - trim whitespace
    - lowercase
    - replace & with 'and'
    - collapse whitespace runs to single space
    - strip surrounding punctuation

    Does NOT attempt fuzzy matching.
    """
    if not name:
        return ""
    normalized = name.strip().lower()
    normalized = normalized.replace("&", "and")
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = normalized.strip(".,!?;:'\"()-")
    return normalized


class OpenAIChatClient:
    """
    Minimal OpenAI-compatible client using HTTPX (Responses API).
    """

    def __init__(
        self,
        api_key: Optional[str],
        model: str,
        temperature: float,
        timeout: int,
    ) -> None:
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required to call the LLM.")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient()
        return self._client

    async def aclose(self):
        if self._client is not None:
            await self._client.aclose()

    async def ainvoke(
        self, messages: List[Dict[str, str]], temperature: Optional[float] = None
    ):
        payload = {
            "model": self.model,
            "input": self._format_messages(messages),
        }
        effective_temp = self.temperature if temperature is None else temperature
        if effective_temp is not None:
            payload["temperature"] = effective_temp
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        client = self._get_client()
        timeout = httpx.Timeout(self.timeout)

        try:
            try:
                response = await client.post(
                    "https://api.openai.com/v1/responses",
                    json=payload,
                    headers=headers,
                    timeout=timeout,
                )
            except httpx.ReadTimeout:
                # Retry once with a longer timeout to handle slow model responses.
                retry_timeout = httpx.Timeout(max(self.timeout * 2, self.timeout + 30))
                response = await client.post(
                    "https://api.openai.com/v1/responses",
                    json=payload,
                    headers=headers,
                    timeout=retry_timeout,
                )

            if response.status_code >= 400:
                # Some models do not support temperature; retry without it if needed.
                if self._is_unsupported_temperature(response):
                    payload.pop("temperature", None)
                    retry = await client.post(
                        "https://api.openai.com/v1/responses",
                        json=payload,
                        headers=headers,
                        timeout=timeout,
                    )
                    if retry.status_code >= 400:
                        raise RuntimeError(
                            f"OpenAI API error {retry.status_code}: {retry.text}"
                        )
                    data = retry.json()
                else:
                    raise RuntimeError(
                        f"OpenAI API error {response.status_code}: {response.text}"
                    )
            else:
                data = response.json()
        except httpx.ReadTimeout as e:
            # If we still timeout after retry, provide a helpful error
            raise RuntimeError(
                f"OpenAI API request timed out after {self.timeout}s. "
                f"Try increasing HTTP_TIMEOUT in your environment settings."
            ) from e

        content = self._extract_text(data)
        return _LLMResponse(content=content or "")

    def _is_unsupported_temperature(self, response: httpx.Response) -> bool:
        try:
            data = response.json()
        except ValueError:
            return "temperature" in response.text.lower()
        error = (data or {}).get("error", {})
        message = (error.get("message") or "").lower()
        param = (error.get("param") or "").lower()
        return "temperature" in message or param == "temperature"

    def _format_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        formatted: List[Dict[str, Any]] = []
        for message in messages:
            role = message.get("role", "user")
            text = message.get("content", "")
            formatted.append(
                {
                    "role": role,
                    "content": text,
                }
            )
        return formatted

    def _extract_text(self, data: Dict[str, Any]) -> str:
        # Responses API sometimes exposes a convenience field.
        output_text = data.get("output_text")
        if output_text:
            return output_text

        # Fallback: walk output messages and collect text chunks.
        parts: List[str] = []
        for item in data.get("output", []) or []:
            for content in item.get("content", []) or []:
                if content.get("type") in ("output_text", "text"):
                    text = content.get("text", "")
                    if text:
                        parts.append(text)
        if parts:
            return "\n".join(parts)

        # Last-resort: support chat-completions-like shapes.
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")


class GeminiChatClient:
    """
    Google Gemini API client using the google-genai SDK.
    """

    def __init__(
        self,
        api_key: Optional[str],
        model: str,
        temperature: float,
        timeout: int,
    ) -> None:
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is required to use Gemini models.")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.timeout = timeout
        self._client = None

    def _get_client(self):
        """Lazy-initialize the Gemini client."""
        if self._client is None:
            from google import genai
            from google.genai import types

            self._client = genai.Client(
                api_key=self.api_key,
                http_options=types.HttpOptions(timeout=self.timeout * 1000),  # ms
            )
        return self._client

    async def ainvoke(
        self, messages: List[Dict[str, str]], temperature: Optional[float] = None
    ):
        """
        Invoke the Gemini model with the given messages.
        Gemini uses a different format - we convert from OpenAI-style messages.
        """
        import asyncio

        # Run synchronous Gemini call in executor to avoid blocking
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, self._sync_generate, messages, temperature
        )
        return _LLMResponse(content=response or "")

    def _sync_generate(
        self, messages: List[Dict[str, str]], temperature: Optional[float]
    ) -> str:
        """Synchronous generation using the Gemini SDK."""
        from google.genai import types

        client = self._get_client()

        # Extract system instruction and user content
        system_instruction = None
        contents = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                system_instruction = content
            else:
                # Map roles: "user" -> "user", "assistant" -> "model"
                gemini_role = "model" if role == "assistant" else "user"
                contents.append(
                    types.Content(
                        role=gemini_role, parts=[types.Part.from_text(text=content)]
                    )
                )

        # Build generation config
        config = types.GenerateContentConfig(
            temperature=self.temperature if temperature is None else temperature,
            system_instruction=system_instruction,
        )

        response = client.models.generate_content(
            model=self.model,
            contents=contents,
            config=config,
        )

        # Extract text from response
        if response.text:
            return response.text
        return ""


class _AgentState(TypedDict, total=False):
    request: AdvancedGenerateRequest
    context_pack: Dict[str, Any]
    lyric_controls: Dict[str, Any]
    # Request-scoped context (avoids race conditions with concurrent requests)
    ctx: Any  # GenerationContext instance
    # Step 1: Style generation
    style_context: str
    style_output: _ParsedStyleOutput
    # Step 2: Lyrics generation
    lyrics_context: str
    lyrics_output: _ParsedLyricsOutput
    # Legacy fields for repair flow
    context_text: str
    raw_output: str
    parsed: _ParsedAgentOutput
    issues: List[str]
    repairs_left: int
    repaired: bool
    result: Dict[str, Any]
    # Debug tracer
    tracer: Any  # DebugTracer instance
    generation_debug: Dict[str, Any]


class AgentPromptGraph:
    """
    LangGraph agent that generates song artifacts using a minimal context pack.

    Supports two architectures:
    - V1/V2 (single-step): One LLM call generates all 6 sections with repair flow
    - V3 (two-step): Separate LLM calls for style and lyrics
    """

    def __init__(self, settings: Settings, llm: Optional[Any] = None):
        self.settings = settings
        self.llm = llm or self._create_llm_client(settings)
        # Track injected LLM for testing (so _get_or_create_llm can reuse it)
        self._injected_llm = llm
        # Build single-step graph at init time (two-step uses _generate_parallel_two_step)
        self._graph_single_step = self._build_single_step_graph()

    @staticmethod
    def _create_llm_client(settings: Settings):
        """Create the appropriate LLM client based on the model name."""
        model = settings.llm_model

        # Check if this is a Gemini model
        if model in GEMINI_MODELS or model.startswith("gemini-"):
            return GeminiChatClient(
                api_key=settings.gemini_api_key,
                model=model,
                temperature=settings.llm_temperature,
                timeout=settings.http_timeout,
            )

        # Default to OpenAI
        return OpenAIChatClient(
            api_key=settings.openai_api_key,
            model=model,
            temperature=settings.llm_temperature,
            timeout=settings.http_timeout,
        )

    @staticmethod
    def _is_instrumental_request(request: AdvancedGenerateRequest) -> bool:
        """
        Detect if a request is for instrumental music (no lyrics).

        Returns True when:
        - lyrics_about is empty or whitespace-only, OR
        - lyrics_about contains "instrumental" / "no lyrics" / "no vocals" phrases, OR
        - tags include "instrumental"
        """
        lyrics_about = (request.lyrics_about or "").strip().lower()

        # Empty lyrics_about → instrumental
        if not lyrics_about:
            return True

        # Keyword detection in lyrics_about
        instrumental_phrases = [
            "instrumental",
            "no lyrics",
            "no vocal",
            "no vocals",
            "without lyrics",
            "without vocals",
        ]
        for phrase in instrumental_phrases:
            if phrase in lyrics_about:
                return True

        # Check tags for "instrumental"
        tags = request.tags or []
        for tag in tags:
            if tag.strip().lower() == "instrumental":
                return True

        return False

    def _build_single_step_graph(self):
        """
        V1/V2 single-step generation graph:
        build_context → generate → parse_validate → [repair loop] → finalize

        One LLM call generates all 6 sections (title, lyrics, suno prompt,
        exclude, weirdness, style influence) with optional repair.
        """
        graph = StateGraph(_AgentState)

        graph.add_node("build_context", self._node_build_context_single)
        graph.add_node("generate", self._node_generate_single)
        graph.add_node("parse_validate", self._node_parse_validate)
        graph.add_node("repair", self._node_repair)
        graph.add_node("finalize", self._node_finalize_single)
        graph.add_node("error", self._node_error)

        graph.set_entry_point("build_context")
        graph.add_edge("build_context", "generate")
        graph.add_edge("generate", "parse_validate")
        graph.add_conditional_edges(
            "parse_validate",
            self._route_after_validation,
            {"finalize": "finalize", "repair": "repair", "error": "error"},
        )
        graph.add_edge("repair", "parse_validate")
        graph.add_edge("finalize", END)
        graph.add_edge("error", END)

        return graph.compile()

    async def generate(self, request: AdvancedGenerateRequest) -> Dict[str, Any]:
        logger.info("AgentPromptGraph.generate start")

        # Get variant - either from request, settings, or default to v5_hybrid
        request_variant = getattr(request, "prompt_variant", None)
        variant_id = request_variant or self.settings.prompt_variant or "v5_hybrid"

        try:
            variant = get_variant(variant_id)
        except ValueError:
            # Fall back to default if variant not found
            logger.warning("Unknown variant %s, falling back to v5_hybrid", variant_id)
            variant = get_variant("v5_hybrid")
            variant_id = "v5_hybrid"

        # Build request-scoped context to avoid race conditions with concurrent requests
        if variant.two_step:
            # Two-step: separate style and lyrics models
            request_style_model = getattr(request, "style_model", None)
            request_lyrics_model = getattr(request, "lyrics_model", None)
            style_model = request_style_model or self.settings.style_model
            lyrics_model = request_lyrics_model or self.settings.lyrics_model

            ctx = GenerationContext(
                variant_id=variant_id,
                is_two_step=True,
                uses_lyric_profile=variant.uses_lyric_profile,
                active_model=style_model,
                style_model=style_model,
                lyrics_model=lyrics_model,
                style_prompt=variant.style_agent,
                style_repair_prompt=variant.style_repair_agent,
                lyrics_prompt=variant.lyrics_agent,
                lyrics_repair_prompt=variant.lyrics_repair_agent,
                profile_inference_prompt=variant.profile_inference_agent,
                genre_disambiguation_prompt=variant.genre_disambiguation_agent,
            )
            logger.info(
                "Using two-step variant: %s (lyric_profile=%s, style=%s, lyrics=%s)",
                variant_id,
                ctx.uses_lyric_profile,
                ctx.style_model,
                ctx.lyrics_model,
            )
        else:
            # Single-step: single model
            request_model = getattr(request, "model", None)
            active_model = request_model or self.settings.llm_model

            ctx = GenerationContext(
                variant_id=variant_id,
                is_two_step=False,
                uses_lyric_profile=False,
                active_model=active_model,
                song_prompt=variant.song_agent,
                repair_prompt=variant.repair_agent,
            )
            logger.info(
                "Using single-step variant: %s (model=%s)", variant_id, active_model
            )

        # Select the appropriate execution path based on variant
        if ctx.is_two_step:
            # V3/V4: Parallel two-step generation
            result = await self._generate_parallel_two_step(request, ctx)
        else:
            # V1/V2: Single-step graph with repair loop
            # Create tracer for this generation
            tracer = DebugTracer(
                variant=ctx.variant_id,
                model=ctx.active_model,
                architecture="single_step",
            )
            state = await self._graph_single_step.ainvoke(
                {"request": request, "tracer": tracer, "ctx": ctx}
            )
            result = state["result"]
            # Attach trace to result
            result["debug_info"] = tracer.to_dict()

        logger.info("AgentPromptGraph.generate complete (two_step=%s)", ctx.is_two_step)
        return result

    def _get_or_create_llm(self, model: str):
        """Get or create an LLM client for the specified model."""
        # If a stub LLM was injected (for testing), always return it
        # This allows FakeLLM to be used for all model calls in tests
        if hasattr(self, "_injected_llm") and self._injected_llm:
            return self._injected_llm

        # Cache LLM clients by model name
        if not hasattr(self, "_llm_cache"):
            self._llm_cache = {}

        if model not in self._llm_cache:
            # Create a temporary settings-like object with the new model
            from dataclasses import dataclass

            @dataclass
            class ModelSettings:
                llm_model: str
                openai_api_key: str
                gemini_api_key: str
                llm_temperature: float
                http_timeout: int

            temp_settings = ModelSettings(
                llm_model=model,
                openai_api_key=self.settings.openai_api_key,
                gemini_api_key=self.settings.gemini_api_key,
                llm_temperature=self.settings.llm_temperature,
                http_timeout=self.settings.http_timeout,
            )
            self._llm_cache[model] = self._create_llm_client(temp_settings)
            logger.info("Created LLM client for model: %s", model)

        return self._llm_cache[model]

    def _get_fast_llm(self):
        """Get the fast LLM client for profile inference."""
        fast_model = self.settings.profile_inference_model
        return self._get_or_create_llm(fast_model)

    async def _generate_parallel_two_step(
        self, request: AdvancedGenerateRequest, ctx: GenerationContext
    ) -> Dict[str, Any]:
        """
        V3/V4 parallel two-step generation:

        [PARALLEL]
          ├── Style Branch: generate_style → validate → [repair loop]
          └── Lyrics Branch: [infer_profile] → generate_lyrics → validate → [repair loop]
        → merge results

        For instrumental requests, only the Style Branch runs (no lyrics/profile inference).

        This achieves ~2x latency improvement over sequential execution.
        """
        # Check if this is an instrumental request (skip lyrics branch entirely)
        is_instrumental = self._is_instrumental_request(request)

        logger.info(
            "Starting parallel two-step generation (style=%s, lyrics=%s, instrumental=%s)",
            ctx.style_model,
            ctx.lyrics_model,
            is_instrumental,
        )

        # Create tracer for this generation (show primary style model in summary)
        # Include fast models used: profile inference, genre disambiguation, or title gen
        fast_models = []
        if ctx.uses_lyric_profile and not is_instrumental:
            fast_models.append(self.settings.profile_inference_model)
        if is_instrumental:
            # Instrumental uses cheap/fast model for title generation
            fast_models.append(self.settings.title_generation_model)
        if ctx.genre_disambiguation_prompt:
            fast_models.append(self.settings.genre_disambiguation_model)
        fast_model_str = ", ".join(fast_models) if fast_models else None

        tracer = DebugTracer(
            variant=ctx.variant_id,
            model=f"{ctx.style_model}"
            + ("" if is_instrumental else f" / {ctx.lyrics_model}"),
            fast_model=fast_model_str,
            architecture="two_step",
        )

        # Build context pack first (shared by both branches)
        context_pack = self._build_context_pack(request)

        # =========================================================================
        # INSTRUMENTAL PATH: Style + title in parallel (skip lyrics branch)
        # =========================================================================
        if is_instrumental:
            logger.info("Instrumental mode: running style + title in parallel")

            # Record a span indicating lyrics was skipped
            with tracer.span("lyrics.skipped", "branch") as span:
                span.set_meta("reason", "instrumental_request")
                span.set_meta("lyrics_about", request.lyrics_about or "")

            # Run style and title generation in parallel
            style_task = self._run_style_branch(context_pack, tracer, ctx)
            title_task = self._generate_instrumental_title(request.user_prompt, tracer)

            style_result, concept_title = await asyncio.gather(
                style_task, title_task, return_exceptions=True
            )

            # Handle style branch failure
            if isinstance(style_result, Exception):
                logger.error("Style branch failed: %s", style_result)
                tracer.set_error(str(style_result))
                result = self._create_error_result(
                    "Style generation failed", str(style_result)
                )
                result["debug_info"] = tracer.to_dict()
                return result

            # Handle title generation failure (use fallback)
            if isinstance(concept_title, Exception):
                logger.warning("Title generation failed: %s", concept_title)
                concept_title = self._derive_title(request.user_prompt, "")

            suno_prompt = style_result["suno_prompt"]

            # Generate unique ID
            generation_id = hashlib.md5(
                f"{concept_title}{suno_prompt}{time.time()}".encode()
            ).hexdigest()[:12]

            logger.info(
                "Instrumental two-step complete in %dms",
                tracer._elapsed_ms(),
            )

            return {
                "concept_title": concept_title,
                "lyrics": "",  # No lyrics for instrumental
                "suno_prompt": suno_prompt,
                "exclude": style_result["exclude"],
                "weirdness": style_result["weirdness"],
                "style_influence": style_result["style_influence"],
                "generation_id": generation_id,
                "auto_tags": style_result.get("auto_tags", []),
                "debug_info": tracer.to_dict(),
            }

        # =========================================================================
        # STANDARD PATH: Parallel style + lyrics
        # =========================================================================
        lyric_controls_obj = getattr(request, "lyric_controls", None)
        # For two-step: only extract explicit user overrides (not defaults)
        # so LLM-inferred profile isn't overwritten by hardcoded defaults
        user_overrides = self._extract_user_overrides(lyric_controls_obj)

        # Run style and lyrics branches in parallel with separate models
        style_task = self._run_style_branch(context_pack, tracer, ctx)
        lyrics_task = self._run_lyrics_branch(context_pack, user_overrides, tracer, ctx)

        style_result, lyrics_result = await asyncio.gather(
            style_task, lyrics_task, return_exceptions=True
        )

        # Handle exceptions
        if isinstance(style_result, Exception):
            logger.error("Style branch failed: %s", style_result)
            tracer.set_error(str(style_result))
            result = self._create_error_result(
                "Style generation failed", str(style_result)
            )
            result["debug_info"] = tracer.to_dict()
            return result
        if isinstance(lyrics_result, Exception):
            logger.error("Lyrics branch failed: %s", lyrics_result)
            tracer.set_error(str(lyrics_result))
            result = self._create_error_result(
                "Lyrics generation failed", str(lyrics_result)
            )
            result["debug_info"] = tracer.to_dict()
            return result

        suno_prompt = style_result["suno_prompt"]

        # Generate unique ID for this generation
        generation_id = hashlib.md5(
            f"{lyrics_result['song_title']}{suno_prompt}{time.time()}".encode()
        ).hexdigest()[:12]

        logger.info(
            "Parallel two-step complete in %dms",
            tracer._elapsed_ms(),
        )

        return {
            "concept_title": lyrics_result["song_title"],
            "lyrics": lyrics_result["lyrics"],
            "suno_prompt": suno_prompt,
            "exclude": style_result["exclude"],
            "weirdness": style_result["weirdness"],
            "style_influence": style_result["style_influence"],
            "generation_id": generation_id,
            "auto_tags": style_result.get("auto_tags", []),
            "debug_info": tracer.to_dict(),
        }

    async def _run_genre_disambiguation(
        self,
        context_pack: Dict[str, Any],
        tracer: DebugTracer,
        ctx: GenerationContext,
    ) -> Optional[Dict[str, Any]]:
        """
        V6: Run genre disambiguation pre-call to enrich style context.
        Returns parsed JSON or None on failure (best-effort).
        """
        if not ctx.genre_disambiguation_prompt:
            return None

        genre_model = self.settings.genre_disambiguation_model
        logger.info("Genre disambiguation: starting (model=%s)", genre_model)

        # Build user message for genre disambiguation
        user_msg = (
            f"Analyze these artists for genre disambiguation:\n"
            f"  style_request: {context_pack.get('user_style_request', '')}\n"
            f"  selected_artists: {context_pack.get('selected_artists', [])}\n"
            f"  tags: {context_pack.get('tags', [])}\n\n"
            f"Return ONLY valid JSON matching the schema."
        )

        with tracer.span(
            "style.genre_disambiguate", "llm_call", model=genre_model
        ) as span:
            try:
                raw_output = await self._call_llm(
                    ctx.genre_disambiguation_prompt, user_msg, model=genre_model
                )
                span.set_meta(
                    "prompt_chars", len(ctx.genre_disambiguation_prompt) + len(user_msg)
                )
                span.set_meta("response_chars", len(raw_output))
                span.set_artifact("system_prompt", ctx.genre_disambiguation_prompt)
                span.set_artifact("user_message", user_msg)
                span.set_artifact("raw_response", raw_output)
            except Exception as e:
                logger.warning("Genre disambiguation LLM call failed: %s", e)
                span.set_meta("error", str(e))
                return None

        # Parse JSON with span
        with tracer.span("style.genre_disambiguate.parse", "parse") as parse_span:
            try:
                # Extract JSON from response (may be wrapped in markdown code block)
                json_match = re.search(r"```json\s*(.*?)\s*```", raw_output, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    # Try to find raw JSON
                    json_str = raw_output.strip()

                parsed = json.loads(json_str)
                parse_span.set_meta("valid", True)
                parse_span.set_meta("artist_count", len(parsed.get("artists", [])))

                logger.info(
                    "Genre disambiguation: parsed %d artists",
                    len(parsed.get("artists", [])),
                )
                return parsed
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("Genre disambiguation parse failed: %s", e)
                parse_span.set_meta("valid", False)
                parse_span.set_meta("error", str(e))
                return None

    def _format_genre_context_section(self, genre_data: Dict[str, Any]) -> str:
        """
        Format genre disambiguation data for injection into style context.

        V6: Basic genre/not_genres guidance
        V7: Enhanced with terms_to_use/terms_to_avoid + instruments
        """
        if not genre_data or not genre_data.get("artists"):
            return ""

        # Check if this is V7 (has terms_to_use/terms_to_avoid or instruments)
        has_vocab_guidance = any(
            artist.get("terms_to_use")
            or artist.get("terms_to_avoid")
            or artist.get("instruments_to_use")
            or artist.get("instruments_to_avoid")
            for artist in genre_data.get("artists", [])
        )

        if has_vocab_guidance:
            return self._format_genre_context_v7(genre_data)
        else:
            return self._format_genre_context_v6(genre_data)

    def _format_genre_context_v6(self, genre_data: Dict[str, Any]) -> str:
        """V6 format: basic genre disambiguation."""
        lines = [
            "",
            "GENRE DISAMBIGUATION (DO NOT COPY VERBATIM - use to guide genre accuracy):",
        ]

        for artist in genre_data.get("artists", []):
            name = artist.get("name", "Unknown")
            era = artist.get("era", {})
            era_label = era.get("label", "unspecified")
            era_basis = era.get("basis", "unspecified")

            lines.append(f"  {name} ({era_label}, basis={era_basis}):")
            lines.append(f"    genres: {artist.get('genres', [])}")
            lines.append(f"    NOT (commonly confused): {artist.get('not_genres', [])}")

            anchors = artist.get("anchors", {})
            if anchors.get("albums") or anchors.get("songs"):
                lines.append(
                    f"    anchors: albums={anchors.get('albums', [])}, "
                    f"songs={anchors.get('songs', [])}"
                )

        global_notes = genre_data.get("global_notes", [])
        if global_notes:
            lines.append(f"  Notes: {global_notes}")

        return "\n".join(lines)

    def _format_genre_context_v7(self, genre_data: Dict[str, Any]) -> str:
        """
        V7 format: enhanced genre + vocabulary + instrument guidance.

        Structured as actionable sections for the style model.
        """
        lines = [
            "",
            "═══════════════════════════════════════════════════════════════════════════════",
            "STYLE GUIDANCE (use this to inform SUNO PROMPT and EXCLUDE)",
            "═══════════════════════════════════════════════════════════════════════════════",
        ]

        for artist in genre_data.get("artists", []):
            name = artist.get("name", "Unknown")
            era = artist.get("era", {})
            era_label = era.get("label", "unspecified")

            lines.append("")
            lines.append(f"▶ {name} ({era_label})")

            # GENRE_TARGETS
            genres = artist.get("genres", [])
            not_genres = artist.get("not_genres", [])
            if genres:
                lines.append(f"  GENRE_TARGETS: {', '.join(genres)}")
            if not_genres:
                lines.append(f"  GENRE_AVOID: {', '.join(not_genres)}")

            # VOCAB_TO_USE
            terms_to_use = artist.get("terms_to_use", [])
            if terms_to_use:
                lines.append(f"  VOCAB_TO_USE: {', '.join(terms_to_use)}")

            # VOCAB_TO_AVOID
            terms_to_avoid = artist.get("terms_to_avoid", [])
            if terms_to_avoid:
                lines.append(f"  VOCAB_TO_AVOID: {', '.join(terms_to_avoid)}")

            # INSTRUMENTS_TO_USE
            instruments_to_use = artist.get("instruments_to_use", [])
            if instruments_to_use:
                lines.append(f"  INSTRUMENTS_TO_USE: {', '.join(instruments_to_use)}")

            # INSTRUMENTS_TO_AVOID
            instruments_to_avoid = artist.get("instruments_to_avoid", [])
            if instruments_to_avoid:
                lines.append(
                    f"  INSTRUMENTS_TO_AVOID: {', '.join(instruments_to_avoid)}"
                )

            # VOCAL_STYLE_TO_USE
            vocal_style_to_use = artist.get("vocal_style_to_use", [])
            if vocal_style_to_use:
                lines.append(f"  VOCAL_STYLE_TO_USE: {', '.join(vocal_style_to_use)}")

            # VOCAL_STYLE_TO_AVOID
            vocal_style_to_avoid = artist.get("vocal_style_to_avoid", [])
            if vocal_style_to_avoid:
                lines.append(
                    f"  VOCAL_STYLE_TO_AVOID: {', '.join(vocal_style_to_avoid)}"
                )

            # ANCHOR_REFERENCES
            anchors = artist.get("anchors", {})
            albums = anchors.get("albums", [])
            songs = anchors.get("songs", [])
            if albums or songs:
                anchor_str = []
                if albums:
                    anchor_str.append(f"albums: {', '.join(albums)}")
                if songs:
                    anchor_str.append(f"songs: {', '.join(songs)}")
                lines.append(f"  ANCHOR_REFERENCES: {'; '.join(anchor_str)}")

        # Global notes
        global_notes = genre_data.get("global_notes", [])
        if global_notes:
            lines.append("")
            lines.append(f"NOTES: {' '.join(global_notes)}")

        # Actionable instruction
        lines.append("")
        lines.append("INSTRUCTIONS:")
        lines.append("- Use VOCAB_TO_USE terms in your SUNO PROMPT for texture/feel")
        lines.append("- Use INSTRUMENTS_TO_USE in your instrument descriptions")
        lines.append("- Use VOCAL_STYLE_TO_USE for vocal descriptions")
        lines.append(
            "- Do NOT use VOCAB_TO_AVOID, INSTRUMENTS_TO_AVOID, or VOCAL_STYLE_TO_AVOID"
        )
        lines.append("- Treat GENRE_AVOID as hard negatives")

        return "\n".join(lines)

    def _extract_exclude_suggestions(self, genre_data: Dict[str, Any]) -> List[str]:
        """Extract terms_to_avoid from genre data for EXCLUDE guidance."""
        if not genre_data or not genre_data.get("artists"):
            return []

        suggestions = []
        for artist in genre_data.get("artists", []):
            terms_to_avoid = artist.get("terms_to_avoid", [])
            suggestions.extend(terms_to_avoid[:2])  # Take top 2 per artist
            instruments_to_avoid = artist.get("instruments_to_avoid", [])
            suggestions.extend(instruments_to_avoid[:1])  # Take top 1 per artist
            vocal_style_to_avoid = artist.get("vocal_style_to_avoid", [])
            suggestions.extend(vocal_style_to_avoid[:1])  # Take top 1 per artist

        return suggestions[:5]  # Cap at 5 total

    def _derive_auto_tags(self, genre_data: Optional[Dict[str, Any]]) -> List[str]:
        """
        Derive auto_tags from genre disambiguation data.

        Returns a list of 6-8 tags derived from:
        - Top genres across all artists (most common first)
        - Era labels (e.g., "90s", "2010s")
        - Key instruments (V7+)

        These tags are stored with the prompt for discovery/filtering.
        """
        if not genre_data or not genre_data.get("artists"):
            return []

        # Count genres across all artists
        genre_counts: Dict[str, int] = {}
        eras: List[str] = []
        instruments: List[str] = []

        for artist in genre_data.get("artists", []):
            # Count genres
            for genre in artist.get("genres", []):
                genre_lower = genre.lower().strip()
                if genre_lower:
                    genre_counts[genre_lower] = genre_counts.get(genre_lower, 0) + 1

            # Collect era labels
            era = artist.get("era", {})
            era_label = era.get("label", "")
            if era_label and era_label not in eras:
                eras.append(era_label)

            # Collect instruments (V7+)
            for inst in artist.get("instruments_to_use", [])[:2]:
                inst_lower = inst.lower().strip()
                if inst_lower and inst_lower not in instruments:
                    instruments.append(inst_lower)

        # Build tags: top 4 genres + 2 eras + 2 instruments
        sorted_genres = sorted(genre_counts.items(), key=lambda x: -x[1])
        tags: List[str] = []

        # Add top genres
        for genre, _ in sorted_genres[:4]:
            tags.append(genre)

        # Add era labels
        for era in eras[:2]:
            if era not in tags:
                tags.append(era)

        # Add instruments
        for inst in instruments[:2]:
            if inst not in tags:
                tags.append(inst)

        return tags[:8]  # Cap at 8 tags

    # =========================================================================
    # V8 Channel Split Logic
    # =========================================================================

    def _decide_style_split_v8_from_roles(
        self, genre_data: Optional[Dict[str, Any]]
    ) -> SplitDecision:
        """
        V8 Step 2.3b: Schema-based split decision using role fields from genre disambiguation.

        Returns a SplitDecision with split_active=True only if:
        - exactly one vocal_reference and one music_target are found
        - both have role_confidence >= V8_ROLE_CONFIDENCE_THRESHOLD
        - normalized names are different
        """
        if not genre_data or not genre_data.get("artists"):
            return SplitDecision(split_active=False, source="none")

        artists = genre_data.get("artists", [])

        vocal_refs = []
        music_targets = []

        for artist in artists:
            role = artist.get("role", "unspecified")
            confidence = artist.get("role_confidence", 0.0)
            name = artist.get("name", "")

            # Skip artists with empty names (defensive: matches regex path validation)
            if not name:
                continue

            if role == "vocal_reference" and confidence >= V8_ROLE_CONFIDENCE_THRESHOLD:
                vocal_refs.append((name, confidence))
            elif role == "music_target" and confidence >= V8_ROLE_CONFIDENCE_THRESHOLD:
                music_targets.append((name, confidence))

        # Must have exactly one of each
        if len(vocal_refs) != 1 or len(music_targets) != 1:
            return SplitDecision(split_active=False, source="none")

        vocal_name, vocal_conf = vocal_refs[0]
        music_name, music_conf = music_targets[0]

        # Names must differ after normalization
        if _normalize_artist_name_v8(vocal_name) == _normalize_artist_name_v8(
            music_name
        ):
            return SplitDecision(split_active=False, source="none")

        return SplitDecision(
            split_active=True,
            music_target_artist=music_name,
            vocal_reference_artist=vocal_name,
            source="role_schema",
            role_confidence=min(vocal_conf, music_conf),
        )

    def _decide_style_split_v8_from_regex(self, style_request: str) -> SplitDecision:
        """
        V8 Step 2.3c: Regex fallback for split detection.

        Only used if schema-based detection didn't produce a confident split.
        Uses high-confidence patterns only. If ambiguous, returns no split.
        """
        if not V8_REGEX_ENABLED or not style_request:
            return SplitDecision(split_active=False, source="none")

        # High-confidence patterns (ordered)
        # Pattern format: (regex, vocal_group_idx, music_group_idx)
        patterns = [
            # "lead singer of X singing/vocals for/over/with Y"
            (
                r"lead\s+singer\s+of\s+(.+?)\s+(?:singing|vocals?)\s+(?:for|over|with)\s+(.+?)(?:\s+(?:music|instrumentation|style|sound))?$",
                1,
                2,
            ),
            # "singer of X for Y"
            (r"singer\s+of\s+(.+?)\s+(?:for|singing\s+for)\s+(.+?)$", 1, 2),
            # "X vocals with/over Y instrumentation/music"
            (
                r"(.+?)\s+vocals?\s+(?:with|over|for)\s+(.+?)\s+(?:instrumentation|music|sound|arrangement)",
                1,
                2,
            ),
            # "vocals like/by X over/with Y"
            (
                r"vocals?\s+(?:like|by)\s+(.+?)\s+(?:over|with)\s+(.+?)(?:\s+(?:instrumentation|music))?$",
                1,
                2,
            ),
            # "X-style vocals ... music/arranged like Y"
            (
                r"(.+?)(?:-style)?\s+vocals?\s+.*?(?:music|composition|arranged)\s+(?:like|as)\s+(.+?)$",
                1,
                2,
            ),
            # "instrumentation of/like Y ... vocals by/like X"
            (
                r"instrumentation\s+(?:of|like)\s+(.+?)\s+.*?vocals?\s+(?:by|like)\s+(.+?)$",
                2,
                1,
            ),
        ]

        for pattern, vocal_idx, music_idx in patterns:
            match = re.search(pattern, style_request, re.IGNORECASE)
            if match:
                try:
                    vocal_artist = match.group(vocal_idx).strip()
                    music_artist = match.group(music_idx).strip()

                    # Both must be non-empty and different
                    if not vocal_artist or not music_artist:
                        continue
                    if _normalize_artist_name_v8(
                        vocal_artist
                    ) == _normalize_artist_name_v8(music_artist):
                        continue

                    return SplitDecision(
                        split_active=True,
                        music_target_artist=music_artist,
                        vocal_reference_artist=vocal_artist,
                        source="regex",
                        role_confidence=0.8,  # Regex matches are reasonably confident
                    )
                except (IndexError, AttributeError):
                    continue

        return SplitDecision(split_active=False, source="none")

    def _decide_style_split_v8(
        self,
        style_request: str,
        genre_data: Optional[Dict[str, Any]],
        tracer: DebugTracer,
    ) -> SplitDecision:
        """
        V8 Step 2.3d: Unified split decision with precedence.

        Precedence:
        1. Schema-based role detection (from genre disambiguation V3)
        2. Regex fallback (high-confidence patterns only)
        3. No split

        Emits a DebugTrace span with the decision.
        """
        # Try schema-based first
        decision = self._decide_style_split_v8_from_roles(genre_data)

        # If no split from roles, try regex
        if not decision.split_active:
            decision = self._decide_style_split_v8_from_regex(style_request)

        # Emit debug span
        with tracer.span("style.split", "parse") as span:
            span.set_meta("split_active", decision.split_active)
            span.set_meta("source", decision.source)
            span.set_meta("role_confidence", decision.role_confidence)
            if decision.split_active:
                span.set_meta("music_target_artist", decision.music_target_artist)
                span.set_meta("vocal_reference_artist", decision.vocal_reference_artist)
            span.set_artifact("style_request_original", style_request)

        return decision

    def _format_style_context_v8(
        self,
        context_pack: Dict[str, Any],
        split: SplitDecision,
        genre_data: Optional[Dict[str, Any]],
    ) -> str:
        """
        V8 Step 2.4: Format style context with explicit MUSIC_TARGET vs VOCAL_REFERENCE blocks.

        When split is active, enforces a strict anti-leakage contract:
        - MUSIC_TARGET is authoritative for genre/instrumentation/arrangement/production
        - VOCAL_REFERENCE is authoritative for vocal timbre/range/delivery ONLY
        """
        lines = [
            "Generate SUNO PROMPT, EXCLUDE, WEIRDNESS, and STYLE INFLUENCE for:",
            f"  style_request: {context_pack.get('user_style_request', '')}",
            f"  reference_artists: {context_pack.get('selected_artists', [])}",
            f"  tags: {context_pack.get('tags', [])}",
        ]

        if not split.split_active:
            # Fallback: use standard format with genre disambiguation
            if genre_data:
                genre_section = self._format_genre_context_section(genre_data)
                return "\n".join(lines) + genre_section
            return "\n".join(lines)

        # Split is active: build explicit MUSIC_TARGET and VOCAL_REFERENCE blocks

        # Find artist data in genre_data
        music_artist_data = None
        vocal_artist_data = None
        if genre_data and genre_data.get("artists"):
            for artist in genre_data["artists"]:
                artist_name = artist.get("name", "")
                if _normalize_artist_name_v8(artist_name) == _normalize_artist_name_v8(
                    split.music_target_artist or ""
                ):
                    music_artist_data = artist
                elif _normalize_artist_name_v8(
                    artist_name
                ) == _normalize_artist_name_v8(split.vocal_reference_artist or ""):
                    vocal_artist_data = artist

        # MUSIC_TARGET block
        lines.append("")
        lines.append(
            "═══════════════════════════════════════════════════════════════════════════════"
        )
        lines.append(
            "MUSIC_TARGET (AUTHORITATIVE for genre / instrumentation / arrangement / production)"
        )
        lines.append(
            "═══════════════════════════════════════════════════════════════════════════════"
        )
        lines.append(f"ARTIST: {split.music_target_artist}")
        lines.append(
            "USE FOR: genre, instruments, arrangement, dynamics, production texture"
        )
        lines.append("DO NOT USE FOR: vocal timbre/range/delivery")

        if music_artist_data:
            lines.append("")
            lines.append(
                "GENRE / VOCAB / INSTRUMENT GUIDANCE (do not copy verbatim; translate into Suno-friendly prose):"
            )

            # Era
            era = music_artist_data.get("era", {})
            if era.get("label"):
                lines.append(
                    f"  ERA: {era.get('label')} (basis: {era.get('basis', 'unspecified')})"
                )

            # Genres
            genres = music_artist_data.get("genres", [])
            if genres:
                lines.append(f"  GENRE_TARGETS: {', '.join(genres)}")
            not_genres = music_artist_data.get("not_genres", [])
            if not_genres:
                lines.append(f"  GENRE_AVOID: {', '.join(not_genres)}")

            # Terms
            terms_to_use = music_artist_data.get("terms_to_use", [])
            if terms_to_use:
                lines.append(f"  VOCAB_TO_USE: {', '.join(terms_to_use)}")
            terms_to_avoid = music_artist_data.get("terms_to_avoid", [])
            if terms_to_avoid:
                lines.append(f"  VOCAB_TO_AVOID: {', '.join(terms_to_avoid)}")

            # Instruments
            instruments_to_use = music_artist_data.get("instruments_to_use", [])
            if instruments_to_use:
                lines.append(f"  INSTRUMENTS_TO_USE: {', '.join(instruments_to_use)}")
            instruments_to_avoid = music_artist_data.get("instruments_to_avoid", [])
            if instruments_to_avoid:
                lines.append(
                    f"  INSTRUMENTS_TO_AVOID: {', '.join(instruments_to_avoid)}"
                )

        lines.append("")
        lines.append(
            "HARD RULE: All non-vocal musical content MUST be derived from MUSIC_TARGET only."
        )

        # VOCAL_REFERENCE block
        lines.append("")
        lines.append(
            "═══════════════════════════════════════════════════════════════════════════════"
        )
        lines.append("VOCAL_REFERENCE (VOICE-ONLY: timbre / register / delivery)")
        lines.append(
            "═══════════════════════════════════════════════════════════════════════════════"
        )
        lines.append(f"ARTIST: {split.vocal_reference_artist}")
        lines.append("USE FOR: vocal timbre/tone, vocal register, delivery style")
        lines.append(
            "DO NOT USE FOR: genre, instrumentation, arrangement, production aesthetic"
        )

        if vocal_artist_data:
            lines.append("")
            lines.append(
                "VOCAL GUIDANCE (voice-only; do not introduce band/genre facts):"
            )

            # Only include vocal-specific fields
            vocal_style_to_use = vocal_artist_data.get("vocal_style_to_use", [])
            if vocal_style_to_use:
                lines.append(f"  VOCAL_STYLE_TO_USE: {', '.join(vocal_style_to_use)}")
            vocal_style_to_avoid = vocal_artist_data.get("vocal_style_to_avoid", [])
            if vocal_style_to_avoid:
                lines.append(
                    f"  VOCAL_STYLE_TO_AVOID: {', '.join(vocal_style_to_avoid)}"
                )

        lines.append("")
        lines.append(
            "HARD RULE: Do NOT borrow genre/instruments/production from VOCAL_REFERENCE."
        )

        # Global notes from genre_data
        if genre_data and genre_data.get("global_notes"):
            lines.append("")
            lines.append(f"NOTES: {' '.join(genre_data['global_notes'])}")

        return "\n".join(lines)

    async def _run_style_branch(
        self,
        context_pack: Dict[str, Any],
        tracer: DebugTracer,
        ctx: GenerationContext,
    ) -> Dict[str, Any]:
        """
        Style branch: [genre_disambiguate] → generate_style → validate → [repair loop]
        """
        style_model = ctx.style_model
        logger.info("Style branch: starting (model=%s)", style_model)

        # V6+: Run genre disambiguation first (best-effort)
        genre_data = None
        if ctx.genre_disambiguation_prompt:
            genre_data = await self._run_genre_disambiguation(context_pack, tracer, ctx)

        # V8: Check for channel split if enabled
        split_decision = SplitDecision(split_active=False, source="none")
        if ctx.variant_id in V8_SPLIT_ENABLED_VARIANTS:
            style_request = context_pack.get("user_style_request", "")
            split_decision = self._decide_style_split_v8(
                style_request, genre_data, tracer
            )

        # Format context for style generation
        if ctx.variant_id in V8_SPLIT_ENABLED_VARIANTS:
            # V8: Use dedicated formatter that handles split and genre data together
            style_context = self._format_style_context_v8(
                context_pack, split_decision, genre_data
            )
        else:
            # V6/V7: Use standard formatter with genre section injected
            style_context = self._format_style_context(context_pack)
            if genre_data:
                genre_section = self._format_genre_context_section(genre_data)
                style_context = style_context + genre_section

        style_prompt = ctx.style_prompt

        # Generate style with span
        with tracer.span("style.generate", "llm_call", model=style_model) as span:
            raw_output = await self._call_llm(
                style_prompt, style_context, model=style_model
            )
            span.set_meta("prompt_chars", len(style_prompt) + len(style_context))
            span.set_meta("response_chars", len(raw_output))
            span.set_artifact("system_prompt", style_prompt)
            span.set_artifact("user_message", style_context)
            span.set_artifact("raw_response", raw_output)

        # Parse with span
        with tracer.span("style.parse", "parse") as span:
            style_output = self._parse_style_output(raw_output)
            span.set_meta("suno_prompt_chars", len(style_output.suno_prompt))

        # Validate with repair loop
        max_repairs = self.settings.agent_max_repairs
        for attempt in range(max_repairs + 1):
            with tracer.span(f"style.validate.{attempt}", "validate") as validate_span:
                issues = self._validate_style_output(style_output)
                validate_span.set_meta("issues", issues)
                validate_span.set_meta("valid", len(issues) == 0)

            if not issues:
                break

            if attempt < max_repairs:
                logger.info(
                    "Style branch: repair attempt %d/%d", attempt + 1, max_repairs
                )
                repair_prompt = ctx.style_repair_prompt
                repair_context = (
                    f"Fix this output:\n\n{style_output.raw}\n\nIssues: {issues}"
                )

                with tracer.span(
                    f"style.repair.{attempt + 1}",
                    "repair",
                    attempt=attempt + 1,
                    model=style_model,
                ) as repair_span:
                    repair_output = await self._call_llm(
                        repair_prompt, repair_context, model=style_model
                    )
                    repair_span.set_meta("issues", issues)
                    repair_span.set_meta(
                        "prompt_chars", len(repair_prompt) + len(repair_context)
                    )
                    repair_span.set_meta("response_chars", len(repair_output))
                    repair_span.set_artifact("system_prompt", repair_prompt)
                    repair_span.set_artifact("repair_context", repair_context)
                    repair_span.set_artifact("raw_response", repair_output)

                # Parse repaired output
                with tracer.span(f"style.parse.{attempt + 1}", "parse") as parse_span:
                    style_output = self._parse_style_output(repair_output)
                    parse_span.set_meta(
                        "suno_prompt_chars", len(style_output.suno_prompt)
                    )

                raw_output = repair_output
            else:
                logger.warning(
                    "Style branch: max repairs reached, proceeding with issues"
                )

        logger.info(
            "Style branch: complete (suno_prompt=%d chars)",
            len(style_output.suno_prompt),
        )

        # Derive auto_tags from genre disambiguation data
        auto_tags = self._derive_auto_tags(genre_data)

        return {
            "suno_prompt": style_output.suno_prompt,
            "exclude": style_output.exclude,
            "weirdness": style_output.weirdness,
            "style_influence": style_output.style_influence,
            "auto_tags": auto_tags,
        }

    async def _run_lyrics_branch(
        self,
        context_pack: Dict[str, Any],
        user_lyric_controls: Dict[str, str],
        tracer: DebugTracer,
        ctx: GenerationContext,
    ) -> Dict[str, Any]:
        """
        Lyrics branch: [infer_profile] → generate_lyrics → validate → [repair loop]

        For V4: First infers lyric profile using fast model, then generates lyrics.
        For V3: Skips profile inference, generates lyrics directly.
        """
        lyrics_model = ctx.lyrics_model
        logger.info(
            "Lyrics branch: starting (uses_profile=%s, model=%s)",
            ctx.uses_lyric_profile,
            lyrics_model,
        )

        lyric_profile = None
        if ctx.uses_lyric_profile:
            # V4: Infer lyric profile using fast model
            fast_model = self.settings.profile_inference_model
            with tracer.span(
                "lyrics.profile_infer", "profile_infer", model=fast_model
            ) as span:
                inferred_profile, profile_artifacts = await self._infer_lyric_profile(
                    context_pack, ctx
                )
                span.set_artifact(
                    "system_prompt", profile_artifacts.get("system_prompt", "")
                )
                span.set_artifact(
                    "user_message", profile_artifacts.get("user_message", "")
                )
                span.set_artifact(
                    "raw_response", profile_artifacts.get("raw_response", "")
                )

                logger.info("Lyrics branch: inferred profiles: %s", inferred_profile)

                # Merge explicit user overrides into all section profiles
                lyric_profile = {}
                for section in ["verse", "prechorus", "chorus", "postchorus", "bridge"]:
                    section_profile = inferred_profile.get(section, {}).copy()
                    for key, value in user_lyric_controls.items():
                        section_profile[key] = value
                    lyric_profile[section] = section_profile

                # Preserve structure from inferred profile
                if "structure" in inferred_profile:
                    lyric_profile["structure"] = inferred_profile["structure"]

                if user_lyric_controls:
                    logger.info(
                        "Lyrics branch: user overrides applied to all sections: %s",
                        user_lyric_controls,
                    )

                # Set both in span metadata for debug trace
                span.set_meta("inferred_profile", inferred_profile)
                span.set_meta("user_overrides", user_lyric_controls)
                span.set_meta("final_profile", lyric_profile)

            # Build lyrics context with per-section profiles
            lyrics_context = self._format_lyrics_context_v4_parallel(
                context_pack=context_pack,
                lyric_controls=lyric_profile,
            )
        else:
            # V3: No profile, use style_request for context
            lyrics_context = self._format_lyrics_context_simple_v3(context_pack)

        # Generate lyrics with span
        lyrics_prompt = ctx.lyrics_prompt
        with tracer.span("lyrics.generate", "llm_call", model=lyrics_model) as span:
            raw_output = await self._call_llm(
                lyrics_prompt, lyrics_context, model=lyrics_model
            )
            span.set_meta("prompt_chars", len(lyrics_prompt) + len(lyrics_context))
            span.set_meta("response_chars", len(raw_output))
            span.set_artifact("system_prompt", lyrics_prompt)
            span.set_artifact("user_message", lyrics_context)
            span.set_artifact("raw_response", raw_output)

        # Parse with span
        with tracer.span("lyrics.parse", "parse") as span:
            lyrics_output = self._parse_lyrics_output(raw_output)
            span.set_meta("title", lyrics_output.song_title)
            span.set_meta("lyrics_chars", len(lyrics_output.lyrics))

        # Validate with repair loop
        max_repairs = self.settings.agent_max_repairs
        for attempt in range(max_repairs + 1):
            with tracer.span(f"lyrics.validate.{attempt}", "validate") as validate_span:
                issues = self._validate_lyrics_output(lyrics_output)
                validate_span.set_meta("issues", issues)
                validate_span.set_meta("valid", len(issues) == 0)

            if not issues:
                break

            if attempt < max_repairs:
                logger.info(
                    "Lyrics branch: repair attempt %d/%d", attempt + 1, max_repairs
                )
                repair_prompt = ctx.lyrics_repair_prompt
                repair_context = (
                    f"Fix this output:\n\n{lyrics_output.raw}\n\nIssues: {issues}"
                )

                with tracer.span(
                    f"lyrics.repair.{attempt + 1}",
                    "repair",
                    attempt=attempt + 1,
                    model=lyrics_model,
                ) as repair_span:
                    repair_output = await self._call_llm(
                        repair_prompt, repair_context, model=lyrics_model
                    )
                    repair_span.set_meta("issues", issues)
                    repair_span.set_meta(
                        "prompt_chars", len(repair_prompt) + len(repair_context)
                    )
                    repair_span.set_meta("response_chars", len(repair_output))
                    repair_span.set_artifact("system_prompt", repair_prompt)
                    repair_span.set_artifact("repair_context", repair_context)
                    repair_span.set_artifact("raw_response", repair_output)

                # Parse repaired output
                with tracer.span(f"lyrics.parse.{attempt + 1}", "parse") as parse_span:
                    lyrics_output = self._parse_lyrics_output(repair_output)
                    parse_span.set_meta("title", lyrics_output.song_title)
                    parse_span.set_meta("lyrics_chars", len(lyrics_output.lyrics))

                raw_output = repair_output
            else:
                logger.warning(
                    "Lyrics branch: max repairs reached, proceeding with issues"
                )

        logger.info(
            "Lyrics branch: complete (title=%s)",
            lyrics_output.song_title[:30] if lyrics_output.song_title else "EMPTY",
        )
        return {
            "song_title": lyrics_output.song_title,
            "lyrics": lyrics_output.lyrics,
            "lyric_profile": lyric_profile,
        }

    async def _infer_lyric_profile(
        self, context_pack: Dict[str, Any], ctx: GenerationContext
    ) -> Tuple[Dict[str, str], Dict[str, Any]]:
        """
        Infer lyric profile using the fast model (gpt-4.1-nano).
        Returns a tuple of (profile_dict, debug_info).
        """
        fast_llm = self._get_fast_llm()
        profile_prompt = ctx.profile_inference_prompt

        # Build context for profile inference
        context = (
            f"style: {context_pack.get('user_style_request', '')}\n"
            f"topic: {context_pack.get('lyrics_about', '')}\n"
            f"artists: {context_pack.get('selected_artists', [])}\n"
            f"tags: {context_pack.get('tags', [])}"
        )

        debug = {
            "model": self.settings.profile_inference_model,
            "user_message": context,
            "system_prompt": profile_prompt,
        }

        logger.info(
            "Profile inference: calling fast model (%s)",
            self.settings.profile_inference_model,
        )

        messages = [
            {"role": "system", "content": profile_prompt},
            {"role": "user", "content": context},
        ]
        response = await fast_llm.ainvoke(messages)
        raw = response.content if hasattr(response, "content") else str(response)
        debug["raw_response"] = raw

        # Parse per-section JSON response (Verse/Chorus/Bridge)
        result = self._parse_per_section_profiles(raw)
        return result, debug

    def _get_default_section_profile(self) -> Dict[str, str]:
        """Return default profile for a section."""
        return {
            "lines_per_section": "4_lines",
            "line_length": "default",
            "pov": "none",
            "rhyme_scheme": "aabb",
            "directness": "balanced",
            "persona": "earnest",
            "humor": "none",
            "explicitness": "clean",
            "audience": "general",
        }

    def _parse_per_section_profiles(self, raw: str) -> Dict[str, Any]:
        """
        Parse per-section profiles and structure from inference output.

        Expected format:
        Verse: {...json...}
        Pre-Chorus: {...json...}
        Chorus: {...json...}
        Post-Chorus: {...json...}
        Bridge: {...json...}
        Structure: ["Intro", "Verse", "Chorus", ...]

        Returns dict with section profiles + 'structure' key.
        Falls back to defaults if parsing fails.
        """
        defaults = self._get_default_section_profile()
        result: Dict[str, Any] = {
            "verse": defaults.copy(),
            "prechorus": defaults.copy(),
            "chorus": defaults.copy(),
            "postchorus": defaults.copy(),
            "bridge": defaults.copy(),
            "structure": [
                "Intro",
                "Verse",
                "Chorus",
                "Verse",
                "Chorus",
                "Bridge",
                "Chorus",
                "Outro",
            ],
        }

        # Try to parse each section
        import re

        # Map internal keys to regex patterns (handle hyphenated formats)
        section_patterns = {
            "verse": r"verse",
            "prechorus": r"pre-?chorus",  # matches Pre-Chorus or PreChorus
            "chorus": r"(?<!pre-)(?<!post-)chorus",  # matches Chorus but not Pre-Chorus/Post-Chorus
            "postchorus": r"post-?chorus",  # matches Post-Chorus or PostChorus
            "bridge": r"bridge",
        }
        parsed_any_section = False
        for section, section_regex in section_patterns.items():
            # Match "Section: {...}" pattern (case-insensitive)
            # Use start-of-line to avoid partial matches
            pattern = rf"(?:^|\n)\s*{section_regex}\s*:\s*(\{{[^}}]+\}})"
            match = re.search(pattern, raw, re.IGNORECASE | re.MULTILINE)
            if match:
                try:
                    profile = json.loads(match.group(1))
                    # Merge with defaults to ensure all keys present
                    section_profile = defaults.copy()
                    for key in defaults:
                        if key in profile:
                            section_profile[key] = profile[key]
                    result[section] = section_profile
                    parsed_any_section = True
                except json.JSONDecodeError:
                    logger.warning(
                        "Profile inference: failed to parse %s JSON", section
                    )

        # If no sections found, try parsing as single JSON (backward compat)
        if not parsed_any_section:
            try:
                # Try to parse as single JSON
                text = raw.strip()
                if text.startswith("{"):
                    profile = json.loads(text)
                    section_profile = defaults.copy()
                    for key in defaults:
                        if key in profile:
                            section_profile[key] = profile[key]
                    # Apply to all sections
                    result["verse"] = section_profile.copy()
                    result["prechorus"] = section_profile.copy()
                    result["chorus"] = section_profile.copy()
                    result["postchorus"] = section_profile.copy()
                    result["bridge"] = section_profile.copy()
                    logger.info(
                        "Profile inference: parsed as single JSON (legacy format)"
                    )
            except json.JSONDecodeError:
                logger.warning(
                    "Profile inference: failed to parse any JSON, using defaults. Raw: %s",
                    raw[:100],
                )

        # Parse structure array
        structure_pattern = r"Structure\s*:\s*(\[[^\]]+\])"
        structure_match = re.search(structure_pattern, raw, re.IGNORECASE)
        if structure_match:
            try:
                structure = json.loads(structure_match.group(1))
                if isinstance(structure, list) and all(
                    isinstance(s, str) for s in structure
                ):
                    result["structure"] = structure
                    logger.info(
                        "Profile inference: parsed structure with %d sections",
                        len(structure),
                    )
            except json.JSONDecodeError:
                logger.warning("Profile inference: failed to parse structure array")

        return result

    def _format_lyrics_context_simple_v3(self, context_pack: Dict[str, Any]) -> str:
        """Format lyrics context for V3 (no profile, no suno_prompt)."""
        lines = [
            "Generate SONG TITLE and LYRICS for:",
            f"  style: {context_pack.get('user_style_request', '')}",
            f"  topic: {context_pack.get('lyrics_about', '')}",
            f"  artists: {context_pack.get('selected_artists', [])}",
            f"  tags: {context_pack.get('tags', [])}",
        ]
        return "\n".join(lines)

    # Syllable range mapping for line_length presets
    LINE_LENGTH_SYLLABLES = {
        "sparse": (3, 5),
        "short": (5, 8),
        "default": (8, 12),
        "long": (12, 16),
    }

    def _format_line_length_range(self, line_length: str) -> str:
        """Format line_length as 'preset (N-M syllables)'."""
        if line_length in self.LINE_LENGTH_SYLLABLES:
            lo, hi = self.LINE_LENGTH_SYLLABLES[line_length]
            return f"{line_length} ({lo}-{hi} syllables)"
        return line_length

    def _format_lyrics_context_v4_parallel(
        self, context_pack: Dict[str, Any], lyric_controls: Dict[str, Any]
    ) -> str:
        """Format lyrics context for V4 parallel mode (includes style info + per-section profiles)."""
        lines = [
            "Generate SONG TITLE and LYRICS for:",
            f"  style_request: {context_pack.get('user_style_request', '')}",
            f"  reference_artists: {context_pack.get('selected_artists', [])}",
            f"  lyrics_about: {context_pack.get('lyrics_about', '')}",
            f"  tags: {context_pack.get('tags', [])}",
            "",
        ]

        # Check if this is per-section format (has 'verse', 'chorus', 'bridge' keys)
        if "verse" in lyric_controls and isinstance(lyric_controls["verse"], dict):
            lines.append("LYRIC PROFILES (apply per section type):")
            for section in ["verse", "prechorus", "chorus", "postchorus", "bridge"]:
                section_profile = lyric_controls.get(section, {})
                line_length = section_profile.get("line_length", "default")
                label = {"prechorus": "PRE-CHORUS", "postchorus": "POST-CHORUS"}.get(
                    section, section.upper()
                )
                lines.append(f"  [{label}]")
                lines.append(
                    f"    lines_per_section: {section_profile.get('lines_per_section', '4_lines')}"
                )
                lines.append(
                    f"    line_length: {self._format_line_length_range(line_length)}"
                )
                lines.append(f"    pov: {section_profile.get('pov', 'none')}")
                lines.append(
                    f"    rhyme_scheme: {section_profile.get('rhyme_scheme', 'aabb')}"
                )
                lines.append(
                    f"    directness: {section_profile.get('directness', 'balanced')}"
                )
                lines.append(
                    f"    persona: {section_profile.get('persona', 'earnest')}"
                )
                lines.append(f"    humor: {section_profile.get('humor', 'none')}")
                lines.append(
                    f"    explicitness: {section_profile.get('explicitness', 'clean')}"
                )
                lines.append(
                    f"    audience: {section_profile.get('audience', 'general')}"
                )
            lines.append("")
            lines.append("Apply [VERSE] profile to [Verse] sections.")
            lines.append("Apply [PRE-CHORUS] profile to [Pre-Chorus] sections.")
            lines.append("Apply [CHORUS] profile to [Chorus] sections.")
            lines.append("Apply [POST-CHORUS] profile to [Post-Chorus] sections.")
            lines.append("Apply [BRIDGE] profile to [Bridge] sections.")

            # Add structure if present
            structure = lyric_controls.get("structure")
            if structure and isinstance(structure, list):
                lines.append("")
                lines.append(
                    f"SONG STRUCTURE (follow this arrangement): {json.dumps(structure)}"
                )
        else:
            # Legacy single-profile format (backward compat)
            line_length = lyric_controls.get("line_length", "default")
            lines.append("LYRIC PROFILE (apply these settings):")
            lines.append(
                f"  lines_per_section: {lyric_controls.get('lines_per_section', '4_lines')}"
            )
            lines.append(
                f"  line_length: {self._format_line_length_range(line_length)}"
            )
            lines.append(f"  pov: {lyric_controls.get('pov', 'none')}")
            lines.append(
                f"  rhyme_scheme: {lyric_controls.get('rhyme_scheme', 'aabb')}"
            )
            lines.append(
                f"  directness: {lyric_controls.get('directness', 'balanced')}"
            )
            lines.append(f"  persona: {lyric_controls.get('persona', 'earnest')}")
            lines.append(f"  audience: {lyric_controls.get('audience', 'general')}")
            lines.append(f"  humor: {lyric_controls.get('humor', 'none')}")
            lines.append(
                f"  explicitness: {lyric_controls.get('explicitness', 'clean')}"
            )

        return "\n".join(lines)

    def _validate_style_output(self, output: _ParsedStyleOutput) -> List[str]:
        """Validate style output, return list of issues."""
        issues = []
        if not output.suno_prompt:
            issues.append("SUNO PROMPT is empty")
        elif len(output.suno_prompt) > 500:
            issues.append(f"SUNO PROMPT too long ({len(output.suno_prompt)} > 500)")
        else:
            # MAX headers are no longer used; reject if present so repair can remove them
            prompt_lower = output.suno_prompt.lower()
            if "[is_max_mode" in prompt_lower:
                issues.append(
                    "SUNO PROMPT contains MAX headers ([IS_MAX_MODE: ...]) which are no longer used; remove them"
                )
        if not output.exclude:
            issues.append("EXCLUDE is empty")
        if output.weirdness < 0 or output.weirdness > 100:
            issues.append(f"WEIRDNESS out of range ({output.weirdness})")
        if output.style_influence < 0 or output.style_influence > 100:
            issues.append(f"STYLE INFLUENCE out of range ({output.style_influence})")
        return issues

    def _strip_lyrics_preamble(self, lyrics: str) -> str:
        """Strip any header preamble that might have been included in lyrics."""
        # Find first section tag - everything before it is preamble
        match = re.search(
            r"\[(?:Intro|Verse|Pre-Chorus|Chorus|Post-Chorus|Bridge|Breakdown|Outro)",
            lyrics,
            re.IGNORECASE,
        )
        if match:
            return lyrics[match.start() :].strip()
        return lyrics.strip()

    def _validate_lyrics_output(self, output: _ParsedLyricsOutput) -> List[str]:
        """Validate lyrics output, return list of issues."""
        issues = []
        if not output.song_title:
            issues.append("SONG TITLE is empty")
        if not output.lyrics:
            issues.append("LYRICS is empty")
        elif "[" not in output.lyrics:
            issues.append("LYRICS missing section tags")
        return issues

    def _create_error_result(self, error_type: str, details: str) -> Dict[str, Any]:
        """Create an error result dict. Caller should attach debug_info from tracer."""
        return {
            "success": False,
            "error": f"{error_type}: {details}",
            "concept_title": "Generation Error",
            "lyrics": f"Error: {error_type}",
            "suno_prompt": "",
            "exclude": "",
            "weirdness": 50,
            "style_influence": 50,
            "generation_id": hashlib.md5(f"error{time.time()}".encode()).hexdigest()[
                :12
            ],
            "auto_tags": [],
        }

    def _node_error(self, state: _AgentState) -> _AgentState:
        """Return an error result when style generation fails."""
        style_output = state.get("style_output")
        error_msg = "Style generation failed"
        if style_output:
            error_msg = "Style generation produced empty SUNO PROMPT"

        logger.warning("agent.error: %s", error_msg)

        # IMPORTANT: this must return a fully-shaped AdvancedGenerateResponse-compatible
        # payload (minus debug_info, which is attached by the caller), otherwise FastAPI
        # response_model validation will fail during serialization.
        result = self._create_error_result("StyleError", error_msg)
        result["style_raw"] = style_output.raw if style_output else ""

        return {
            **state,
            "result": {
                **result,
            },
        }

    def _resolve_lyric_controls(
        self, lyric_controls: Optional[LyricControls]
    ) -> Dict[str, Any]:
        """
        Resolve lyric controls to concrete values.
        'auto' values get sensible defaults (no LLM call needed).
        Used for V1/V2 single-step where there's no LLM inference.
        """
        defaults = {
            "audience": "general",
            "directness": "balanced",
            "humor": "none",
            "explicitness": "clean",
            "persona": "earnest",
            "lines_per_section": "4_lines",
            "line_length": "default",
            "pov": "none",
            "rhyme_scheme": "aabb",
        }

        if not lyric_controls:
            return defaults

        resolved = dict(defaults)
        if lyric_controls.audience != "auto":
            resolved["audience"] = lyric_controls.audience
        if lyric_controls.directness != "auto":
            resolved["directness"] = lyric_controls.directness
        if lyric_controls.humor != "auto":
            resolved["humor"] = lyric_controls.humor
        if lyric_controls.explicitness != "auto":
            resolved["explicitness"] = lyric_controls.explicitness
        if lyric_controls.persona != "auto":
            resolved["persona"] = lyric_controls.persona
        if lyric_controls.lines_per_section != "auto":
            resolved["lines_per_section"] = lyric_controls.lines_per_section
        if lyric_controls.line_length != "auto":
            resolved["line_length"] = lyric_controls.line_length
        if lyric_controls.pov != "auto":
            resolved["pov"] = lyric_controls.pov
        if lyric_controls.rhyme_scheme != "auto":
            resolved["rhyme_scheme"] = lyric_controls.rhyme_scheme

        return resolved

    def _extract_user_overrides(
        self, lyric_controls: Optional[LyricControls]
    ) -> Dict[str, str]:
        """
        Extract only explicitly-set (non-"auto") lyric control values.
        Returns a dict with only the fields the user explicitly set.
        Used for V4/V5 two-step where LLM infers profile and user overrides it.
        """
        if not lyric_controls:
            return {}

        overrides = {}
        if lyric_controls.audience and lyric_controls.audience != "auto":
            overrides["audience"] = lyric_controls.audience
        if lyric_controls.directness and lyric_controls.directness != "auto":
            overrides["directness"] = lyric_controls.directness
        if lyric_controls.humor and lyric_controls.humor != "auto":
            overrides["humor"] = lyric_controls.humor
        if lyric_controls.explicitness and lyric_controls.explicitness != "auto":
            overrides["explicitness"] = lyric_controls.explicitness
        if lyric_controls.persona and lyric_controls.persona != "auto":
            overrides["persona"] = lyric_controls.persona
        if (
            lyric_controls.lines_per_section
            and lyric_controls.lines_per_section != "auto"
        ):
            overrides["lines_per_section"] = lyric_controls.lines_per_section
        if lyric_controls.line_length and lyric_controls.line_length != "auto":
            overrides["line_length"] = lyric_controls.line_length
        if lyric_controls.pov and lyric_controls.pov != "auto":
            overrides["pov"] = lyric_controls.pov
        if lyric_controls.rhyme_scheme and lyric_controls.rhyme_scheme != "auto":
            overrides["rhyme_scheme"] = lyric_controls.rhyme_scheme

        return overrides

    def _format_style_context(self, context_pack: Dict[str, Any]) -> str:
        """Format context for V3 style agent (Step 1, no lyric profile)."""
        lines = [
            "Generate SUNO PROMPT, EXCLUDE, WEIRDNESS, and STYLE INFLUENCE for:",
            f"  style_request: {context_pack.get('user_style_request', '')}",
            f"  reference_artists: {context_pack.get('selected_artists', [])}",
            f"  tags: {context_pack.get('tags', [])}",
        ]
        return "\n".join(lines)

    def _format_style_context_with_profile(self, context_pack: Dict[str, Any]) -> str:
        """Format context for V4 style agent (Step 1, generates lyric profile)."""
        lines = [
            "Generate SUNO PROMPT, EXCLUDE, WEIRDNESS, STYLE INFLUENCE, and LYRIC PROFILE for:",
            f"  style_request: {context_pack.get('user_style_request', '')}",
            f"  lyrics_about: {context_pack.get('lyrics_about', '')}",
            f"  reference_artists: {context_pack.get('selected_artists', [])}",
            f"  tags: {context_pack.get('tags', [])}",
        ]
        return "\n".join(lines)

    def _format_lyrics_context_simple(
        self,
        suno_prompt: str,
        lyrics_about: str,
    ) -> str:
        """Format context for V3 lyrics agent (no lyric profile)."""
        lines = [
            "Generate SONG TITLE and LYRICS for:",
            f"  suno_prompt: {suno_prompt}",
            f"  lyrics_about: {lyrics_about}",
        ]
        return "\n".join(lines)

    def _format_lyrics_context_with_profile(
        self,
        suno_prompt: str,
        lyrics_about: str,
        lyric_controls: Dict[str, Any],
    ) -> str:
        """Format context for V4 lyrics agent (with lyric profile)."""
        lines = [
            "Generate SONG TITLE and LYRICS for:",
            f"  suno_prompt: {suno_prompt}",
            f"  lyrics_about: {lyrics_about}",
            "",
        ]

        # Check if this is per-section format (has 'verse', 'chorus', 'bridge' keys)
        if "verse" in lyric_controls and isinstance(lyric_controls["verse"], dict):
            lines.append("LYRIC PROFILES (apply per section type):")
            for section in ["verse", "prechorus", "chorus", "postchorus", "bridge"]:
                section_profile = lyric_controls.get(section, {})
                line_length = section_profile.get("line_length", "default")
                label = {"prechorus": "PRE-CHORUS", "postchorus": "POST-CHORUS"}.get(
                    section, section.upper()
                )
                lines.append(f"  [{label}]")
                lines.append(
                    f"    lines_per_section: {section_profile.get('lines_per_section', '4_lines')}"
                )
                lines.append(
                    f"    line_length: {self._format_line_length_range(line_length)}"
                )
                lines.append(f"    pov: {section_profile.get('pov', 'none')}")
                lines.append(
                    f"    rhyme_scheme: {section_profile.get('rhyme_scheme', 'aabb')}"
                )
                lines.append(
                    f"    directness: {section_profile.get('directness', 'balanced')}"
                )
                lines.append(
                    f"    persona: {section_profile.get('persona', 'earnest')}"
                )
                lines.append(f"    humor: {section_profile.get('humor', 'none')}")
                lines.append(
                    f"    explicitness: {section_profile.get('explicitness', 'clean')}"
                )
                lines.append(
                    f"    audience: {section_profile.get('audience', 'general')}"
                )
            lines.append("")
            lines.append("Apply [VERSE] profile to [Verse] sections.")
            lines.append("Apply [PRE-CHORUS] profile to [Pre-Chorus] sections.")
            lines.append("Apply [CHORUS] profile to [Chorus] sections.")
            lines.append("Apply [POST-CHORUS] profile to [Post-Chorus] sections.")
            lines.append("Apply [BRIDGE] profile to [Bridge] sections.")

            # Add structure if present
            structure = lyric_controls.get("structure")
            if structure and isinstance(structure, list):
                lines.append("")
                lines.append(
                    f"SONG STRUCTURE (follow this arrangement): {json.dumps(structure)}"
                )
        else:
            # Legacy single-profile format
            line_length = lyric_controls.get("line_length", "default")
            lines.append("LYRIC PROFILE (apply these settings):")
            lines.append(
                f"  lines_per_section: {lyric_controls.get('lines_per_section', '4_lines')}"
            )
            lines.append(
                f"  line_length: {self._format_line_length_range(line_length)}"
            )
            lines.append(f"  pov: {lyric_controls.get('pov', 'none')}")
            lines.append(
                f"  rhyme_scheme: {lyric_controls.get('rhyme_scheme', 'aabb')}"
            )
            lines.append(
                f"  directness: {lyric_controls.get('directness', 'balanced')}"
            )
            lines.append(f"  persona: {lyric_controls.get('persona', 'earnest')}")
            lines.append(f"  audience: {lyric_controls.get('audience', 'general')}")
            lines.append(f"  humor: {lyric_controls.get('humor', 'none')}")
            lines.append(
                f"  explicitness: {lyric_controls.get('explicitness', 'clean')}"
            )

        return "\n".join(lines)

    def _parse_style_output(self, raw: str) -> _ParsedStyleOutput:
        """Parse the style agent output."""
        _, sections = self._extract_sections(raw)

        suno_prompt = sections.get("SUNO PROMPT", "").strip()
        exclude = self._first_non_empty_line(sections.get("EXCLUDE", ""))
        weirdness = self._parse_percent(sections.get("WEIRDNESS", ""))
        style_influence = self._parse_percent(sections.get("STYLE INFLUENCE", ""))

        # Parse lyric profile if present (V4 only)
        lyric_profile = None
        lyric_profile_raw = sections.get("LYRIC PROFILE", "").strip()
        if lyric_profile_raw:
            lyric_profile = self._parse_lyric_profile_json(lyric_profile_raw)

        return _ParsedStyleOutput(
            suno_prompt=suno_prompt,
            exclude=exclude,
            weirdness=weirdness,
            style_influence=style_influence,
            lyric_profile=lyric_profile,
            raw=raw,
        )

    def _parse_lyric_profile_json(self, raw: str) -> Optional[Dict[str, str]]:
        """Parse lyric profile JSON from step 1 output."""
        try:
            # Try to find JSON in the raw text
            # It might be wrapped in markdown code blocks
            text = raw.strip()
            if text.startswith("```"):
                # Remove markdown code block
                lines = text.split("\n")
                text = "\n".join(
                    lines[1:-1] if lines[-1].startswith("```") else lines[1:]
                )

            profile = json.loads(text)
            valid_keys = {
                "lines_per_section",
                "line_length",
                "pov",
                "rhyme_scheme",
                "directness",
                "persona",
                "audience",
                "humor",
                "explicitness",
            }
            result = {k: v for k, v in profile.items() if k in valid_keys}
            # Ensure all profile fields are present with defaults
            result.setdefault("lines_per_section", "4_lines")
            result.setdefault("line_length", "default")
            result.setdefault("pov", "none")
            result.setdefault("rhyme_scheme", "aabb")
            result.setdefault("directness", "balanced")
            result.setdefault("persona", "earnest")
            result.setdefault("humor", "none")
            result.setdefault("explicitness", "clean")
            result.setdefault("audience", "general")
            return result
        except (json.JSONDecodeError, AttributeError):
            logger.warning("Failed to parse lyric profile JSON: %s", raw[:100])
            return None

    def _parse_lyrics_output(self, raw: str) -> _ParsedLyricsOutput:
        """Parse the lyrics agent output."""
        _, sections = self._extract_sections(raw)

        song_title = self._first_non_empty_line(sections.get("SONG TITLE", ""))
        lyrics_raw = sections.get("LYRICS", "").strip()
        # Strip any preamble - only count from first section tag
        lyrics = self._strip_lyrics_preamble(lyrics_raw)

        return _ParsedLyricsOutput(
            song_title=song_title,
            lyrics=lyrics,
            raw=raw,
        )

    # =========================================================================
    # SINGLE-STEP GRAPH NODES (V1/V2)
    # =========================================================================

    async def _node_build_context_single(self, state: _AgentState) -> _AgentState:
        """Build context for single-step generation (V1/V2)."""
        request = state["request"]
        context_pack = self._build_context_pack(request)
        context_text = self._format_context_text(context_pack)

        logger.info(
            "agent.build_context_single prepared (tags=%s, artists=%s)",
            len(context_pack.get("tags", [])),
            len(context_pack.get("selected_artists", [])),
        )
        return {
            **state,
            "context_pack": context_pack,
            "context_text": context_text,
            "repairs_left": self.settings.agent_max_repairs,
        }

    async def _node_generate_single(self, state: _AgentState) -> _AgentState:
        """Single LLM call to generate all 6 sections (V1/V2)."""
        ctx: GenerationContext = state.get("ctx")
        model = ctx.active_model if ctx else self.settings.llm_model
        logger.info("agent.generate_single calling LLM (model=%s)", model)

        tracer: DebugTracer = state.get("tracer")
        context_text = state["context_text"]
        system_prompt = ctx.song_prompt if ctx else self.settings.song_agent_prompt

        # Generate with span
        with tracer.span("song.generate", "llm_call", model=model) as span:
            raw = await self._call_llm(system_prompt, context_text, model=model)
            span.set_meta("prompt_chars", len(system_prompt) + len(context_text))
            span.set_meta("response_chars", len(raw))
            span.set_artifact("system_prompt", system_prompt)
            span.set_artifact("user_message", context_text)
            span.set_artifact("raw_response", raw)

        return {**state, "raw_output": raw}

    async def _node_parse_validate(self, state: _AgentState) -> _AgentState:
        """Parse and validate the single-step output."""
        tracer: DebugTracer = state.get("tracer")
        raw = state.get("raw_output", "")

        # Parse with span
        with tracer.span("song.parse", "parse") as span:
            parsed = self._parse_agent_output(raw)
            span.set_meta("title", parsed.song_title)
            span.set_meta("lyrics_chars", len(parsed.lyrics))
            span.set_meta("suno_prompt_chars", len(parsed.suno_prompt))

        # Validate with span
        with tracer.span("song.validate", "validate") as span:
            issues = self._validate_output(parsed, state["context_pack"])
            span.set_meta("issues", issues)
            span.set_meta("valid", len(issues) == 0)

        if issues:
            logger.info("agent.parse_validate found issues: %s", issues)
        else:
            logger.info("agent.parse_validate passed")

        return {**state, "parsed": parsed, "issues": issues}

    def _route_after_validation(self, state: _AgentState) -> str:
        """Route based on validation results."""
        issues = state.get("issues", [])
        repairs_left = state.get("repairs_left", 0)

        if not issues:
            return "finalize"
        if repairs_left > 0:
            return "repair"
        return "error"

    async def _node_repair(self, state: _AgentState) -> _AgentState:
        """Attempt to repair invalid output."""
        ctx: GenerationContext = state.get("ctx")
        tracer: DebugTracer = state.get("tracer")
        repairs_left = state.get("repairs_left", 0)
        max_repairs = self.settings.agent_max_repairs
        attempt = max_repairs - repairs_left + 1

        logger.info(
            "agent.repair attempting fix (attempt=%d, repairs_left=%d)",
            attempt,
            repairs_left,
        )

        issues = state.get("issues", [])
        raw_output = state.get("raw_output", "")
        context_text = state["context_text"]

        # Build repair prompt
        repair_prompt = ctx.repair_prompt if ctx else self.settings.repair_agent_prompt
        model = ctx.active_model if ctx else self.settings.llm_model
        user_message = f"""The following output has validation issues:

ORIGINAL OUTPUT:
{raw_output}

ISSUES:
{chr(10).join(f"- {i}" for i in issues)}

ORIGINAL REQUEST:
{context_text}

Please fix the issues and regenerate the complete output with all 6 sections.
"""

        # Repair with span
        with tracer.span(
            f"song.repair.{attempt}",
            "repair",
            attempt=attempt,
            model=model,
        ) as span:
            raw = await self._call_llm(repair_prompt, user_message, model=model)
            span.set_meta("issues", issues)
            span.set_meta("prompt_chars", len(repair_prompt) + len(user_message))
            span.set_meta("response_chars", len(raw))
            span.set_artifact("system_prompt", repair_prompt)
            span.set_artifact("repair_context", user_message)
            span.set_artifact("raw_response", raw)

        return {
            **state,
            "raw_output": raw,
            "repairs_left": repairs_left - 1,
            "repaired": True,
        }

    def _node_finalize_single(self, state: _AgentState) -> _AgentState:
        """Finalize single-step output into response format."""
        logger.info("agent.finalize_single assembling response")
        context_pack = state["context_pack"]
        parsed = state["parsed"]

        song_prompt = context_pack.get("user_style_request", "")
        lyrics_about = context_pack.get("lyrics_about", "")

        # Use LLM-generated title, fall back to derived if empty
        concept_title = parsed.song_title.strip() or self._derive_title(
            song_prompt, lyrics_about
        )
        suno_prompt = parsed.suno_prompt.strip() or song_prompt.strip()
        suno_prompt = self._trim_text(suno_prompt, 500)
        lyrics = parsed.lyrics.strip()
        exclude = parsed.exclude.strip()
        weirdness = self._clamp_percent(parsed.weirdness)
        style_influence = self._clamp_percent(parsed.style_influence)
        generation_id = self._create_generation_id(song_prompt, lyrics_about)

        # Result without debug_info - tracer will be attached in generate()
        # Single-step variants (V1/V2) don't run genre disambiguation, so no auto_tags
        result = {
            "concept_title": concept_title,
            "lyrics": lyrics,
            "suno_prompt": suno_prompt,
            "exclude": exclude,
            "weirdness": weirdness,
            "style_influence": style_influence,
            "generation_id": generation_id,
            "auto_tags": [],
        }
        return {**state, "result": result}

    def _format_context_text(self, context_pack: Dict[str, Any]) -> str:
        """Format context for single-step generation (V1/V2)."""
        lines = [
            "Generate a complete song with all 6 sections for:",
            f"  style_request: {context_pack.get('user_style_request', '')}",
            f"  lyrics_about: {context_pack.get('lyrics_about', '')}",
            f"  reference_artists: {context_pack.get('selected_artists', [])}",
            f"  tags: {context_pack.get('tags', [])}",
        ]
        return "\n".join(lines)

    # =========================================================================
    # SHARED UTILITIES
    # =========================================================================

    async def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        model: Optional[str] = None,
    ) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # Use specified model, active LLM, or fall back to default
        if model:
            llm = self._get_or_create_llm(model)
        else:
            llm = getattr(self, "_active_llm", self.llm)

        try:
            response = await llm.ainvoke(messages, temperature=temperature)
        except TypeError:
            # Compatibility with stubs or older clients without temperature kwarg.
            response = await llm.ainvoke(messages)

        return response.content or ""

    def _build_context_pack(self, request: AdvancedGenerateRequest) -> Dict[str, Any]:
        return {
            "selected_artists": request.selected_artists or [],
            "user_style_request": request.user_prompt or "",
            "lyrics_about": request.lyrics_about or "",
            "tags": request.tags or [],
        }

    def _parse_agent_output(self, text: str) -> _ParsedAgentOutput:
        order, sections = self._extract_sections(text)

        song_title = self._first_non_empty_line(sections.get("SONG TITLE", ""))
        lyrics = sections.get("LYRICS", "").strip()
        suno_prompt = sections.get("SUNO PROMPT", "").strip()
        exclude = self._first_non_empty_line(sections.get("EXCLUDE", ""))
        weirdness = self._parse_percent(sections.get("WEIRDNESS", ""))
        style_influence = self._parse_percent(sections.get("STYLE INFLUENCE", ""))

        return _ParsedAgentOutput(
            order=order,
            sections=sections,
            song_title=song_title,
            lyrics=lyrics,
            suno_prompt=suno_prompt,
            exclude=exclude,
            weirdness=weirdness,
            style_influence=style_influence,
        )

    def _extract_sections(self, text: str) -> Tuple[Tuple[str, ...], Dict[str, str]]:
        """
        Extracts the agent's labeled sections and preserves header order.
        Filters out --- separator lines that some models include.
        """
        sections: Dict[str, str] = {}
        order: List[str] = []
        current_key: Optional[str] = None
        buffer: list[str] = []

        for line in text.splitlines():
            # Skip separator lines (---, ===, etc.)
            stripped = line.strip()
            if stripped and all(c in "-=" for c in stripped):
                continue

            header = self._normalize_header(line)
            if header:
                if current_key is not None:
                    sections[current_key] = "\n".join(buffer).strip()
                current_key = header
                if header not in order:
                    order.append(header)
                buffer = []
                continue
            if current_key is not None:
                buffer.append(line)

        if current_key is not None:
            sections[current_key] = "\n".join(buffer).strip()

        return tuple(order), sections

    def _validate_output(
        self, parsed: _ParsedAgentOutput, context_pack: Dict[str, Any]
    ) -> List[str]:
        issues: List[str] = []
        required = (
            "SONG TITLE",
            "LYRICS",
            "SUNO PROMPT",
            "EXCLUDE",
            "WEIRDNESS",
            "STYLE INFLUENCE",
        )

        # Sections must exist, and appear in the required order (no missing / re-ordered).
        if parsed.order != required:
            issues.append(
                f"Sections must be exactly {list(required)} in order; got {list(parsed.order)}."
            )
        for key in required:
            if key not in parsed.sections:
                issues.append(f"Missing required section: {key}.")

        # SUNO PROMPT must be <= 500 chars.
        if parsed.suno_prompt and len(parsed.suno_prompt) > 500:
            issues.append("SUNO PROMPT exceeds 500 characters.")

        # EXCLUDE must be one line, comma-separated, no extra prose.
        exclude = parsed.exclude.strip()
        if "\n" in exclude or "\r" in exclude:
            issues.append("EXCLUDE must be one line only.")
        # Only flag dashes used as separators (space-dash-space), not hyphens in words like "hi-hats"
        if " - " in exclude or exclude.startswith("- ") or exclude.endswith(" -"):
            issues.append("EXCLUDE must use commas as separators, not dashes.")
        if exclude:
            # Allow simple comma-separated phrases. Disallow obvious prose separators.
            if any(token in exclude for token in (":", ";", "•", "—")):
                issues.append(
                    "EXCLUDE must be comma-separated values only (no prose/punctuation)."
                )
            if not re.fullmatch(r"[^,\n\r]+(,\s*[^,\n\r]+)*", exclude):
                issues.append(
                    "EXCLUDE must be comma-separated values (no empty items)."
                )

        # WEIRDNESS / STYLE INFLUENCE must be a single integer 0-100 in their sections.
        issues.extend(
            self._validate_percent_section(
                parsed.sections.get("WEIRDNESS", ""), "WEIRDNESS"
            )
        )
        issues.extend(
            self._validate_percent_section(
                parsed.sections.get("STYLE INFLUENCE", ""), "STYLE INFLUENCE"
            )
        )

        # Detect lazy "echo" outputs where the model just repeats the user prompt.
        suno_prompt_lower = (parsed.suno_prompt or "").lower().strip()
        lazy_patterns = [
            "make a song",
            "create a song",
            "write a song",
            "sounds like",
            "mixed with",
            "in the style of",
        ]
        for pattern in lazy_patterns:
            if (
                suno_prompt_lower.startswith(pattern)
                or f" {pattern}" in suno_prompt_lower[:100]
            ):
                issues.append(
                    f"SUNO PROMPT echoes input ('{pattern}'). Transform into style descriptors."
                )
                break

        # Detect lazy default values (both exactly 50% + empty EXCLUDE is a red flag)
        if parsed.weirdness == 50 and parsed.style_influence == 50:
            exclude_val = parsed.exclude.strip().lower()
            if not exclude_val or exclude_val in ("(none)", "none"):
                issues.append(
                    "Lazy defaults detected (50%/50%, empty EXCLUDE). Generate specific values."
                )

        # Enforce: do not mention real artists by name in SUNO PROMPT (lyrics not enforced).
        artists = context_pack.get("selected_artists") or []
        leaked = self._find_artist_leaks(parsed.suno_prompt, artists)
        if leaked:
            issues.append(
                "SUNO PROMPT mentions artist names that must be implied but not stated: "
                + ", ".join(leaked)
                + "."
            )

        return issues

    def _validate_percent_section(self, raw: str, label: str) -> List[str]:
        text = (raw or "").strip()
        match = re.fullmatch(r"\s*(\d{1,3})\s*%?\s*", text)
        if not match:
            return [f"{label} must be a single integer 0-100."]
        value = int(match.group(1))
        if value < 0 or value > 100:
            return [f"{label} must be between 0 and 100."]
        return []

    def _find_artist_leaks(self, suno_prompt: str, artists: Sequence[str]) -> List[str]:
        """
        Returns the subset of artist names that appear in the SUNO PROMPT (case-insensitive),
        using a conservative normalization to catch punctuation variants (e.g., will.i.am).
        """
        prompt = (suno_prompt or "").strip()
        if not prompt or not artists:
            return []

        prompt_norm = re.sub(r"[^a-z0-9]+", "", prompt.lower())
        leaked: List[str] = []
        for artist in artists:
            a = (artist or "").strip()
            if not a:
                continue
            a_norm = re.sub(r"[^a-z0-9]+", "", a.lower())
            if len(a_norm) < 3:
                continue
            if a_norm and a_norm in prompt_norm:
                leaked.append(a)
                continue
            # Also check simple word-boundary match for common cases.
            if re.search(rf"\b{re.escape(a.lower())}\b", prompt.lower()):
                leaked.append(a)
        # De-dupe while preserving order
        seen = set()
        out: List[str] = []
        for a in leaked:
            if a.lower() in seen:
                continue
            seen.add(a.lower())
            out.append(a)
        return out

    def _scrub_artist_names(self, text: str, artists: Sequence[str]) -> str:
        """
        Best-effort removal of artist names from a string, including punctuation variants.
        """
        if not text or not artists:
            return text

        out = text
        for artist in artists:
            a = (artist or "").strip()
            if not a:
                continue
            # Remove exact-ish case-insensitive occurrences
            out = re.sub(re.escape(a), "", out, flags=re.IGNORECASE)
        # Also remove any remaining double spaces from removals
        out = re.sub(r"\s{2,}", " ", out).strip()
        return out

    def _normalize_header(self, line: str) -> Optional[str]:
        normalized = line.strip().upper().rstrip(":")
        normalized = re.sub(r"^[A-F]\)\s*", "", normalized)
        if "SONG TITLE" in normalized or normalized == "TITLE":
            return "SONG TITLE"
        if normalized == "LYRICS":
            return "LYRICS"
        if "SUNO PROMPT" in normalized:
            return "SUNO PROMPT"
        if "EXCLUDE" in normalized:
            return "EXCLUDE"
        if "WEIRDNESS" in normalized:
            return "WEIRDNESS"
        if "STYLE INFLUENCE" in normalized:
            return "STYLE INFLUENCE"
        return None

    def _first_non_empty_line(self, text: str) -> str:
        for line in text.splitlines():
            if line.strip():
                return line.strip()
        return ""

    def _parse_percent(self, text: str) -> int:
        match = re.search(r"\d{1,3}", text)
        if not match:
            return 50
        return int(match.group(0))

    def _clamp_percent(self, value: int) -> int:
        return max(0, min(100, value))

    def _derive_title(self, song_prompt: str, lyrics_about: str) -> str:
        source = lyrics_about.strip() or song_prompt.strip()
        if not source:
            return "Untitled"
        words = re.findall(r"[A-Za-z0-9']+", source)
        title = " ".join(words[:4]).title() if words else "Untitled"
        return self._trim_text(title, 50)

    async def _generate_instrumental_title(
        self, user_prompt: str, tracer: "DebugTracer"
    ) -> str:
        """
        Generate a creative title for an instrumental track using the fast LLM.

        The title should evoke the mood/atmosphere of the music without being
        generic like "Epic Orchestral Soundtrack".

        Note: Only uses user_prompt (not suno_prompt) so it can run in parallel
        with style generation.
        """
        title_prompt = f"""Generate a creative, evocative title for an instrumental music track.

The music is described as: {user_prompt}

Requirements:
- Title should be 1-5 words
- Evoke mood, imagery, or atmosphere
- Sound like a real instrumental track title (not a description)
- Be creative and distinctive
- NO quotation marks in the output

Good examples: "Midnight in Kyoto", "The Last Horizon", "Velvet Thunder", "Drift", "Through Glass Canyons"
Bad examples: "Epic Orchestral Music", "Ambient Electronic Track", "Jazz Song"

Output ONLY the title, nothing else."""

        title_model = self.settings.title_generation_model
        system_content = "You generate creative, evocative titles for instrumental music tracks. Output ONLY the title, nothing else."

        with tracer.span("title.generate", "llm_call", model=title_model) as span:
            # Add input to debug trace
            span.set_artifact("system_prompt", system_content)
            span.set_artifact("user_message", title_prompt)
            span.set_meta("model", title_model)

            try:
                llm = self._get_or_create_llm(title_model)
                messages = [
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": title_prompt},
                ]
                response = await llm.ainvoke(messages)
                raw = (
                    response.content if hasattr(response, "content") else str(response)
                )

                # Add raw response to debug trace
                span.set_artifact("raw_response", raw)

                title = raw.strip().strip("\"'")
                # Clean up and limit length
                title = self._trim_text(title, 50)
                span.set_meta("generated_title", title)
                logger.info("Generated instrumental title: %s", title)
                return title if title else "Untitled"
            except Exception as e:
                logger.warning("Failed to generate instrumental title: %s", e)
                span.set_meta("error", str(e))
                span.set_artifact("exception", str(e))
                # Fallback to simple derivation
                fallback_title = self._derive_title(user_prompt, "")
                span.set_meta("fallback_title", fallback_title)
                return fallback_title

    def _create_generation_id(self, song_prompt: str, lyrics_about: str) -> str:
        content = f"{song_prompt}_{lyrics_about}_{time.time()}"
        return hashlib.md5(content.encode("utf-8")).hexdigest()[:12]

    def _hash_context(self, context_pack: Dict[str, Any]) -> str:
        payload = json.dumps(context_pack, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]

    def _trim_text(self, text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return f"{text[: max(0, limit - 3)]}..."
