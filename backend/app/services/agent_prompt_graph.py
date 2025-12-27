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
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, TypedDict

import httpx
from langgraph.graph import END, StateGraph

from app.config import Settings
from app.prompts import (
    get_variant,
    STYLE_AGENT_SYSTEM_PROMPT,
    LYRICS_AGENT_SYSTEM_PROMPT,
)
from app.schemas.advanced import AdvancedGenerateRequest, LyricControls

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


@dataclass(frozen=True)
class _ParsedLyricsOutput:
    """Output from the lyrics agent (Step 2)."""

    song_title: str
    lyrics: str
    raw: str


@dataclass(frozen=True)
class _LLMResponse:
    content: str


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
        # Build both graphs at init time
        self._graph_single_step = self._build_single_step_graph()
        self._graph_two_step = self._build_two_step_graph()
        self._debug_file = Path(__file__).parent.parent.parent / "debug_agent.log"

    def _debug_log(self, msg: str):
        """Write debug message to log file."""
        with open(self._debug_file, "a", encoding="utf-8") as f:
            f.write(msg + "\n")

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

    def _build_two_step_graph(self):
        """
        V3 two-step generation graph:
        build_context → generate_style → generate_lyrics → finalize

        Each step is focused on one task:
        - Style agent: SUNO PROMPT, EXCLUDE, WEIRDNESS, STYLE INFLUENCE
        - Lyrics agent: SONG TITLE, LYRICS
        """
        graph = StateGraph(_AgentState)

        graph.add_node("build_context", self._node_build_context)
        graph.add_node("generate_style", self._node_generate_style)
        graph.add_node("generate_lyrics", self._node_generate_lyrics)
        graph.add_node("finalize", self._node_finalize)
        graph.add_node("error", self._node_error)

        graph.set_entry_point("build_context")
        graph.add_edge("build_context", "generate_style")
        graph.add_conditional_edges(
            "generate_style",
            self._route_after_style,
            {"generate_lyrics": "generate_lyrics", "error": "error"},
        )
        graph.add_edge("generate_lyrics", "finalize")
        graph.add_edge("finalize", END)
        graph.add_edge("error", END)

        return graph.compile()

    async def generate(self, request: AdvancedGenerateRequest) -> Dict[str, Any]:
        logger.info("AgentPromptGraph.generate start")

        # Get variant - either from request or settings
        request_variant = getattr(request, "prompt_variant", None)
        variant_id = request_variant or self.settings.prompt_variant

        try:
            variant = get_variant(variant_id)
        except ValueError:
            # Fall back to v1 if variant not found
            variant = get_variant("v1")
            variant_id = "v1"

        self._active_variant = variant_id
        self._is_two_step = variant.two_step
        self._uses_lyric_profile = variant.uses_lyric_profile

        if self._is_two_step:
            # V3/V4 two-step: use style_agent and lyrics_agent prompts
            self._active_style_prompt = variant.style_agent
            self._active_style_repair_prompt = variant.style_repair_agent
            self._active_lyrics_prompt = variant.lyrics_agent
            self._active_lyrics_repair_prompt = variant.lyrics_repair_agent
            self._active_profile_inference_prompt = variant.profile_inference_agent
            logger.info(
                "Using two-step variant: %s (lyric_profile=%s)",
                variant_id,
                self._uses_lyric_profile,
            )
        else:
            # V1/V2 single-step: use song_agent and repair_agent prompts
            self._active_song_prompt = variant.song_agent
            self._active_repair_prompt = variant.repair_agent
            logger.info("Using single-step variant: %s", variant_id)

        # Check for per-request model override
        request_model = getattr(request, "model", None)
        if request_model:
            self._active_llm = self._get_or_create_llm(request_model)
            self._active_model = request_model
            logger.info("Using per-request model: %s", request_model)
        else:
            self._active_llm = self.llm
            self._active_model = self.settings.llm_model

        # Select the appropriate execution path based on variant
        if self._is_two_step:
            # V3/V4: Parallel two-step generation
            result = await self._generate_parallel_two_step(request)
        else:
            # V1/V2: Single-step graph with repair loop
            state = await self._graph_single_step.ainvoke({"request": request})
            result = state["result"]

        logger.info(
            "AgentPromptGraph.generate complete (two_step=%s)", self._is_two_step
        )
        return result

    def _get_or_create_llm(self, model: str):
        """Get or create an LLM client for the specified model."""
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
        self, request: AdvancedGenerateRequest
    ) -> Dict[str, Any]:
        """
        V3/V4 parallel two-step generation:

        [PARALLEL]
          ├── Style Branch: generate_style → validate → [repair loop]
          └── Lyrics Branch: [infer_profile] → generate_lyrics → validate → [repair loop]
        → merge results

        This achieves ~2x latency improvement over sequential execution.
        """
        logger.info("Starting parallel two-step generation")
        start_time = time.time()

        # Build context pack first (shared by both branches)
        context_pack = self._build_context_pack(request)
        lyric_controls_obj = getattr(request, "lyric_controls", None)
        user_lyric_controls = self._resolve_lyric_controls(lyric_controls_obj)

        # Run style and lyrics branches in parallel
        style_task = self._run_style_branch(context_pack)
        lyrics_task = self._run_lyrics_branch(context_pack, user_lyric_controls)

        style_result, lyrics_result = await asyncio.gather(
            style_task, lyrics_task, return_exceptions=True
        )

        # Handle exceptions
        if isinstance(style_result, Exception):
            logger.error("Style branch failed: %s", style_result)
            return self._create_error_result(
                "Style generation failed", str(style_result)
            )
        if isinstance(lyrics_result, Exception):
            logger.error("Lyrics branch failed: %s", lyrics_result)
            return self._create_error_result(
                "Lyrics generation failed", str(lyrics_result)
            )

        # Merge results
        elapsed = time.time() - start_time
        logger.info("Parallel two-step complete in %.2fs", elapsed)

        # For V5 hybrid: prepend MAX headers to V1-style prose output
        suno_prompt = style_result["suno_prompt"]
        if self._active_variant == "v5_hybrid":
            max_headers = (
                "[IS_MAX_MODE: MAX](MAX)\n"
                "[QUALITY: MAX](MAX)\n"
                "[REALISM: MAX](MAX)\n"
                "[REAL_INSTRUMENTS: MAX](MAX)\n"
            )
            # Only prepend if headers aren't already there
            if not suno_prompt.strip().startswith("[IS_MAX_MODE"):
                suno_prompt = max_headers + suno_prompt

        # Generate unique ID for this generation
        generation_id = hashlib.md5(
            f"{lyrics_result['song_title']}{suno_prompt}{time.time()}".encode()
        ).hexdigest()[:12]

        return {
            "concept_title": lyrics_result["song_title"],
            "lyrics": lyrics_result["lyrics"],
            "suno_prompt": suno_prompt,
            "exclude": style_result["exclude"],
            "weirdness": style_result["weirdness"],
            "style_influence": style_result["style_influence"],
            "generation_id": generation_id,
            "debug_info": {
                "variant": self._active_variant,
                "model": self._active_model,
                "fast_model": (
                    self.settings.profile_inference_model
                    if self._uses_lyric_profile
                    else None
                ),
                "lyric_profile": lyrics_result.get("lyric_profile"),
                "elapsed_seconds": round(elapsed, 2),
                "style_branch": style_result.get("debug"),
                "lyrics_branch": lyrics_result.get("debug"),
            },
        }

    async def _run_style_branch(self, context_pack: Dict[str, Any]) -> Dict[str, Any]:
        """
        Style branch: generate_style → validate → [repair loop]
        """
        logger.info("Style branch: starting")
        start_time = time.time()
        debug = {"step": "style", "repairs": []}

        # Format context for style generation
        style_context = self._format_style_context(context_pack)
        debug["user_message"] = style_context
        debug["system_prompt"] = self._active_style_prompt

        # Generate style
        style_prompt = self._active_style_prompt
        raw_output = await self._call_llm(style_prompt, style_context)
        debug["raw_response"] = raw_output

        # Parse and validate
        style_output = self._parse_style_output(raw_output)

        # Validate with repair loop
        max_repairs = self.settings.agent_max_repairs
        for attempt in range(max_repairs + 1):
            validate_start = time.time()
            issues = self._validate_style_output(style_output)
            validate_ms = int((time.time() - validate_start) * 1000)

            if not issues:
                break

            if attempt < max_repairs:
                logger.info(
                    "Style branch: repair attempt %d/%d", attempt + 1, max_repairs
                )
                repair_prompt = self._active_style_repair_prompt
                repair_context = (
                    f"Fix this output:\n\n{style_output.raw}\n\nIssues: {issues}"
                )

                llm_start = time.time()
                repair_output = await self._call_llm(repair_prompt, repair_context)
                llm_ms = int((time.time() - llm_start) * 1000)

                parse_start = time.time()
                style_output = self._parse_style_output(repair_output)
                parse_ms = int((time.time() - parse_start) * 1000)

                debug["repairs"].append(
                    {
                        "attempt": attempt + 1,
                        "issues": issues,
                        "output": repair_output,
                        "timing": {
                            "validate_ms": validate_ms,
                            "llm_ms": llm_ms,
                            "parse_ms": parse_ms,
                            "total_ms": validate_ms + llm_ms + parse_ms,
                        },
                    }
                )
                raw_output = repair_output
            else:
                logger.warning(
                    "Style branch: max repairs reached, proceeding with issues"
                )
                debug["final_issues"] = issues

        debug["elapsed_ms"] = int((time.time() - start_time) * 1000)
        logger.info(
            "Style branch: complete (suno_prompt=%d chars)",
            len(style_output.suno_prompt),
        )
        return {
            "suno_prompt": style_output.suno_prompt,
            "exclude": style_output.exclude,
            "weirdness": style_output.weirdness,
            "style_influence": style_output.style_influence,
            "debug": debug,
        }

    async def _run_lyrics_branch(
        self, context_pack: Dict[str, Any], user_lyric_controls: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Lyrics branch: [infer_profile] → generate_lyrics → validate → [repair loop]

        For V4: First infers lyric profile using fast model, then generates lyrics.
        For V3: Skips profile inference, generates lyrics directly.
        """
        logger.info(
            "Lyrics branch: starting (uses_profile=%s)", self._uses_lyric_profile
        )
        start_time = time.time()
        debug = {"step": "lyrics", "repairs": [], "profile_inference": None}

        lyric_profile = None
        if self._uses_lyric_profile:
            # V4: Infer lyric profile using fast model
            profile_start = time.time()
            inferred_profile, profile_debug = await self._infer_lyric_profile(
                context_pack
            )
            debug["profile_inference"] = {
                **profile_debug,
                "elapsed_ms": int((time.time() - profile_start) * 1000),
            }
            logger.info("Lyrics branch: inferred profile: %s", inferred_profile)

            # Merge user overrides: non-"auto" values override inferred values
            lyric_profile = inferred_profile.copy()
            for key, value in user_lyric_controls.items():
                if value and value != "auto":
                    lyric_profile[key] = value
                    logger.info("Lyrics branch: user override %s=%s", key, value)

            debug["profile_inference"]["user_overrides"] = {
                k: v for k, v in user_lyric_controls.items() if v and v != "auto"
            }
            debug["profile_inference"]["final_profile"] = lyric_profile

            # Build lyrics context with profile + style info
            lyrics_context = self._format_lyrics_context_v4_parallel(
                context_pack=context_pack,
                lyric_controls=lyric_profile,
            )
        else:
            # V3: No profile, use style_request for context
            lyrics_context = self._format_lyrics_context_simple_v3(context_pack)

        debug["user_message"] = lyrics_context
        debug["system_prompt"] = self._active_lyrics_prompt

        # Generate lyrics
        lyrics_prompt = self._active_lyrics_prompt
        raw_output = await self._call_llm(lyrics_prompt, lyrics_context)
        debug["raw_response"] = raw_output

        # Parse and validate
        lyrics_output = self._parse_lyrics_output(raw_output)

        # Validate with repair loop
        max_repairs = self.settings.agent_max_repairs
        for attempt in range(max_repairs + 1):
            validate_start = time.time()
            issues = self._validate_lyrics_output(lyrics_output)
            validate_ms = int((time.time() - validate_start) * 1000)

            if not issues:
                break

            if attempt < max_repairs:
                logger.info(
                    "Lyrics branch: repair attempt %d/%d", attempt + 1, max_repairs
                )
                repair_prompt = self._active_lyrics_repair_prompt
                repair_context = (
                    f"Fix this output:\n\n{lyrics_output.raw}\n\nIssues: {issues}"
                )

                llm_start = time.time()
                repair_output = await self._call_llm(repair_prompt, repair_context)
                llm_ms = int((time.time() - llm_start) * 1000)

                parse_start = time.time()
                lyrics_output = self._parse_lyrics_output(repair_output)
                parse_ms = int((time.time() - parse_start) * 1000)

                debug["repairs"].append(
                    {
                        "attempt": attempt + 1,
                        "issues": issues,
                        "output": repair_output,
                        "timing": {
                            "validate_ms": validate_ms,
                            "llm_ms": llm_ms,
                            "parse_ms": parse_ms,
                            "total_ms": validate_ms + llm_ms + parse_ms,
                        },
                    }
                )
                raw_output = repair_output
            else:
                logger.warning(
                    "Lyrics branch: max repairs reached, proceeding with issues"
                )
                debug["final_issues"] = issues

        debug["elapsed_ms"] = int((time.time() - start_time) * 1000)
        logger.info(
            "Lyrics branch: complete (title=%s)",
            lyrics_output.song_title[:30] if lyrics_output.song_title else "EMPTY",
        )
        return {
            "song_title": lyrics_output.song_title,
            "lyrics": lyrics_output.lyrics,
            "lyric_profile": lyric_profile,
            "debug": debug,
        }

    async def _infer_lyric_profile(
        self, context_pack: Dict[str, Any]
    ) -> Tuple[Dict[str, str], Dict[str, Any]]:
        """
        Infer lyric profile using the fast model (gpt-4.1-nano).
        Returns a tuple of (profile_dict, debug_info).
        """
        fast_llm = self._get_fast_llm()
        profile_prompt = self._active_profile_inference_prompt

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

        # Parse JSON response
        try:
            profile = json.loads(raw.strip())
            # Validate expected keys with defaults
            result = {
                "density": profile.get("density", "standard"),
                "pacing": profile.get("pacing", "mid"),
                "directness": profile.get("directness", "balanced"),
                "persona": profile.get("persona", "earnest"),
                "humor": profile.get("humor", "none"),
                "explicitness": profile.get("explicitness", "clean"),
                "audience": profile.get("audience", "general"),
            }
            return result, debug
        except json.JSONDecodeError:
            logger.warning(
                "Profile inference: failed to parse JSON, using defaults. Raw: %s",
                raw[:100],
            )
            debug["parse_error"] = True
            return {
                "density": "standard",
                "pacing": "mid",
                "directness": "balanced",
                "persona": "earnest",
                "humor": "none",
                "explicitness": "clean",
                "audience": "general",
            }, debug

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

    def _format_lyrics_context_v4_parallel(
        self, context_pack: Dict[str, Any], lyric_controls: Dict[str, str]
    ) -> str:
        """Format lyrics context for V4 parallel mode (includes style info + profile)."""
        lines = [
            "Generate SONG TITLE and LYRICS for:",
            f"  style_request: {context_pack.get('user_style_request', '')}",
            f"  reference_artists: {context_pack.get('selected_artists', [])}",
            f"  lyrics_about: {context_pack.get('lyrics_about', '')}",
            f"  tags: {context_pack.get('tags', [])}",
            "",
            "LYRIC PROFILE (apply these settings):",
            f"  density: {lyric_controls.get('density', 'standard')}",
            f"  pacing: {lyric_controls.get('pacing', 'mid')}",
            f"  directness: {lyric_controls.get('directness', 'balanced')}",
            f"  persona: {lyric_controls.get('persona', 'earnest')}",
            f"  audience: {lyric_controls.get('audience', 'general')}",
            f"  humor: {lyric_controls.get('humor', 'none')}",
            f"  explicitness: {lyric_controls.get('explicitness', 'clean')}",
        ]
        return "\n".join(lines)

    def _validate_style_output(self, output: _ParsedStyleOutput) -> List[str]:
        """Validate style output, return list of issues."""
        issues = []
        if not output.suno_prompt:
            issues.append("SUNO PROMPT is empty")
        elif len(output.suno_prompt) > 500:
            issues.append(f"SUNO PROMPT too long ({len(output.suno_prompt)} > 500)")
        else:
            # Check for structured format (V2+) - should have genre/instruments/style tags/recording
            prompt_lower = output.suno_prompt.lower()
            has_structured_format = (
                "genre:" in prompt_lower
                or "instruments:" in prompt_lower
                or "style tags:" in prompt_lower
            )
            # If it has MAX headers but no structured fields, it's wrong format
            if "[is_max_mode" in prompt_lower and not has_structured_format:
                issues.append(
                    "SUNO PROMPT has MAX headers but missing structured format (genre:/instruments:/style tags:/recording:)"
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
        """Create an error result dict."""
        return {
            "concept_title": "Generation Error",
            "lyrics": f"Error: {error_type}",
            "suno_prompt": "",
            "exclude": "",
            "weirdness": 50,
            "style_influence": 50,
            "generation_id": hashlib.md5(f"error{time.time()}".encode()).hexdigest()[
                :12
            ],
            "debug_info": {
                "variant": getattr(self, "_active_variant", "unknown"),
                "model": getattr(self, "_active_model", "unknown"),
                "error": f"{error_type}: {details}",
            },
        }

    async def _node_build_context(self, state: _AgentState) -> _AgentState:
        """Build context for both style and lyrics generation."""
        request = state["request"]
        context_pack = self._build_context_pack(request)

        # Get lyric controls directly from request (no LLM call needed)
        lyric_controls_obj = getattr(request, "lyric_controls", None)
        lyric_controls = self._resolve_lyric_controls(lyric_controls_obj)

        # Format style context (for Step 1 - no lyrics_about needed)
        # Format style context based on variant
        # V4 includes lyrics_about for profile inference
        uses_lyric_profile = getattr(self, "_uses_lyric_profile", False)
        if uses_lyric_profile:
            style_context = self._format_style_context_with_profile(context_pack)
        else:
            style_context = self._format_style_context(context_pack)

        logger.info(
            "agent.build_context prepared (tags=%s, artists=%s, uses_profile=%s)",
            len(context_pack.get("tags", [])),
            len(context_pack.get("selected_artists", [])),
            uses_lyric_profile,
        )
        return {
            **state,
            "context_pack": context_pack,
            "lyric_controls": lyric_controls,
            "style_context": style_context,
        }

    async def _node_generate_style(self, state: _AgentState) -> _AgentState:
        """Step 1: Generate style artifacts (SUNO PROMPT, EXCLUDE, params)."""
        uses_lyric_profile = getattr(self, "_uses_lyric_profile", False)
        logger.info(
            "agent.generate_style calling LLM (model=%s, generates_profile=%s)",
            self._active_model,
            uses_lyric_profile,
        )

        # Get active style prompt (V3 or V4)
        style_prompt = getattr(self, "_active_style_prompt", STYLE_AGENT_SYSTEM_PROMPT)

        # DEBUG: Write full request to log file
        self._debug_log("=" * 80)
        self._debug_log(
            f"STEP 1: STYLE GENERATION (generates_profile={uses_lyric_profile})"
        )
        self._debug_log(f"MODEL: {self._active_model}")
        self._debug_log("=" * 80)
        self._debug_log("\n--- STYLE AGENT PROMPT (truncated) ---")
        self._debug_log(style_prompt[:500] + "...")
        self._debug_log("\n--- STYLE CONTEXT ---")
        self._debug_log(state["style_context"])
        self._debug_log("\n--- END REQUEST ---\n")

        raw_output = await self._call_llm(style_prompt, state["style_context"])

        # DEBUG: Write raw response
        self._debug_log("\n--- STYLE AGENT RESPONSE ---")
        self._debug_log(raw_output)
        self._debug_log("\n--- END RESPONSE ---\n")

        # Parse the style output
        style_output = self._parse_style_output(raw_output)

        logger.info(
            "agent.generate_style complete (suno_prompt=%d chars, weirdness=%d)",
            len(style_output.suno_prompt),
            style_output.weirdness,
        )
        return {**state, "style_output": style_output}

    def _route_after_style(self, state: _AgentState) -> str:
        """Route after style generation - check for critical failures."""
        style_output = state.get("style_output")
        if not style_output or not style_output.suno_prompt:
            return "error"
        return "generate_lyrics"

    async def _node_generate_lyrics(self, state: _AgentState) -> _AgentState:
        """Step 2: Generate lyrics using the style context."""
        logger.info(
            "agent.generate_lyrics calling LLM (model=%s, uses_lyric_profile=%s)",
            self._active_model,
            getattr(self, "_uses_lyric_profile", False),
        )

        style_output = state["style_output"]
        context_pack = state["context_pack"]
        _lyric_controls = state.get("lyric_controls", {})  # Reserved for future use
        uses_lyric_profile = getattr(self, "_uses_lyric_profile", False)

        # Build lyrics context - with or without lyric profile based on variant
        if uses_lyric_profile:
            # V4: Use lyric profile generated by LLM in step 1
            # Fall back to defaults if parsing failed
            generated_profile = style_output.lyric_profile or {}
            profile_for_lyrics = {
                "density": generated_profile.get("density", "standard"),
                "pacing": generated_profile.get("pacing", "mid"),
                "directness": generated_profile.get("directness", "balanced"),
                "persona": generated_profile.get("persona", "earnest"),
                "audience": generated_profile.get("audience", "general"),
                "humor": generated_profile.get("humor", "none"),
                "explicitness": generated_profile.get("explicitness", "clean"),
            }
            lyrics_context = self._format_lyrics_context_with_profile(
                suno_prompt=style_output.suno_prompt,
                lyrics_about=context_pack.get("lyrics_about", ""),
                lyric_controls=profile_for_lyrics,
            )
            logger.info("V4: Using LLM-generated lyric profile: %s", generated_profile)
        else:
            # V3: No lyric profile, just style context
            lyrics_context = self._format_lyrics_context_simple(
                suno_prompt=style_output.suno_prompt,
                lyrics_about=context_pack.get("lyrics_about", ""),
            )

        # Get the active lyrics prompt (V3 or V4)
        lyrics_prompt = getattr(
            self, "_active_lyrics_prompt", LYRICS_AGENT_SYSTEM_PROMPT
        )

        # DEBUG: Write full request to log file
        self._debug_log("=" * 80)
        self._debug_log(
            f"STEP 2: LYRICS GENERATION (lyric_profile={uses_lyric_profile})"
        )
        self._debug_log(f"MODEL: {self._active_model}")
        self._debug_log("=" * 80)
        self._debug_log("\n--- LYRICS AGENT PROMPT (truncated) ---")
        self._debug_log(lyrics_prompt[:500] + "...")
        self._debug_log("\n--- LYRICS CONTEXT ---")
        self._debug_log(lyrics_context)
        self._debug_log("\n--- END REQUEST ---\n")

        raw_output = await self._call_llm(lyrics_prompt, lyrics_context)

        # DEBUG: Write raw response
        self._debug_log("\n--- LYRICS AGENT RESPONSE ---")
        self._debug_log(raw_output)
        self._debug_log("\n--- END RESPONSE ---\n")

        # Parse the lyrics output
        lyrics_output = self._parse_lyrics_output(raw_output)

        logger.info(
            "agent.generate_lyrics complete (title=%s, lyrics=%d chars)",
            lyrics_output.song_title[:30] if lyrics_output.song_title else "EMPTY",
            len(lyrics_output.lyrics),
        )
        return {
            **state,
            "lyrics_output": lyrics_output,
            "lyrics_context": lyrics_context,
        }

    def _node_error(self, state: _AgentState) -> _AgentState:
        """Return an error result when style generation fails."""
        style_output = state.get("style_output")
        error_msg = "Style generation failed"
        if style_output:
            error_msg = "Style generation produced empty SUNO PROMPT"

        logger.warning("agent.error: %s", error_msg)
        self._debug_log(f"\n--- GENERATION FAILED: {error_msg} ---\n")

        return {
            **state,
            "result": {
                "success": False,
                "error": error_msg,
                "style_raw": style_output.raw if style_output else "",
            },
        }

    def _resolve_lyric_controls(
        self, lyric_controls: Optional[LyricControls]
    ) -> Dict[str, Any]:
        """
        Resolve lyric controls to concrete values.
        'auto' values get sensible defaults (no LLM call needed).
        """
        defaults = {
            "audience": "general",
            "directness": "balanced",
            "humor": "none",
            "explicitness": "clean",
            "persona": "earnest",
            "density": "standard",
            "pacing": "mid",
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
        if lyric_controls.density != "auto":
            resolved["density"] = lyric_controls.density
        if lyric_controls.pacing != "auto":
            resolved["pacing"] = lyric_controls.pacing

        return resolved

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
            "LYRIC PROFILE (apply these settings):",
            f"  density: {lyric_controls.get('density', 'standard')}",
            f"  pacing: {lyric_controls.get('pacing', 'mid')}",
            f"  directness: {lyric_controls.get('directness', 'balanced')}",
            f"  persona: {lyric_controls.get('persona', 'earnest')}",
            f"  audience: {lyric_controls.get('audience', 'general')}",
            f"  humor: {lyric_controls.get('humor', 'none')}",
            f"  explicitness: {lyric_controls.get('explicitness', 'clean')}",
        ]
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
            # Validate expected keys
            valid_keys = {
                "density",
                "pacing",
                "directness",
                "persona",
                "audience",
                "humor",
                "explicitness",
            }
            return {k: v for k, v in profile.items() if k in valid_keys}
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

    def _node_finalize(self, state: _AgentState) -> _AgentState:
        """Combine outputs from both steps into final response."""
        logger.info("agent.finalize assembling response")
        context_pack = state["context_pack"]
        style_output = state["style_output"]
        lyrics_output = state["lyrics_output"]
        lyric_controls = state.get("lyric_controls", {})

        song_prompt = context_pack.get("user_style_request", "")
        lyrics_about = context_pack.get("lyrics_about", "")

        # Use LLM-generated title, fall back to derived if empty
        concept_title = lyrics_output.song_title.strip() or self._derive_title(
            song_prompt, lyrics_about
        )
        suno_prompt = style_output.suno_prompt.strip() or song_prompt.strip()
        suno_prompt = self._trim_text(suno_prompt, 500)
        lyrics = lyrics_output.lyrics.strip()
        exclude = style_output.exclude.strip()
        weirdness = self._clamp_percent(style_output.weirdness)
        style_influence = self._clamp_percent(style_output.style_influence)
        generation_id = self._create_generation_id(song_prompt, lyrics_about)
        context_hash = self._hash_context(context_pack)

        result = {
            "concept_title": concept_title,
            "lyrics": lyrics,
            "suno_prompt": suno_prompt,
            "exclude": exclude,
            "weirdness": weirdness,
            "style_influence": style_influence,
            "generation_id": generation_id,
            "debug_info": {
                "agent_model": getattr(self, "_active_model", self.settings.llm_model),
                "prompt_variant": getattr(
                    self, "_active_variant", self.settings.prompt_variant
                ),
                "context_hash": context_hash,
                "two_step": True,
                "lyric_controls": lyric_controls,
            },
        }
        return {**state, "result": result}

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
        logger.info("agent.generate_single calling LLM (model=%s)", self._active_model)
        start_time = time.time()

        context_text = state["context_text"]
        system_prompt = getattr(
            self, "_active_song_prompt", self.settings.song_agent_prompt
        )

        # DEBUG log
        self._debug_log("=" * 80)
        self._debug_log("SINGLE-STEP GENERATION (V1/V2)")
        self._debug_log(f"MODEL: {self._active_model}")
        self._debug_log("=" * 80)
        self._debug_log("\n--- SYSTEM PROMPT (truncated) ---")
        self._debug_log(system_prompt[:500] + "...")
        self._debug_log("\n--- USER CONTEXT ---")
        self._debug_log(context_text)
        self._debug_log("\n--- END REQUEST ---\n")

        raw = await self._call_llm(system_prompt, context_text)
        elapsed_ms = int((time.time() - start_time) * 1000)

        self._debug_log("\n--- RAW OUTPUT ---")
        self._debug_log(raw)
        self._debug_log("\n--- END OUTPUT ---\n")

        # Store debug info for finalize
        generation_debug = {
            "system_prompt": system_prompt,
            "user_message": context_text,
            "raw_response": raw,
            "elapsed_ms": elapsed_ms,
            "repairs": [],
        }

        return {**state, "raw_output": raw, "generation_debug": generation_debug}

    async def _node_parse_validate(self, state: _AgentState) -> _AgentState:
        """Parse and validate the single-step output."""
        raw = state.get("raw_output", "")
        parsed = self._parse_agent_output(raw)
        issues = self._validate_output(parsed, state["context_pack"])

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
        logger.info(
            "agent.repair attempting fix (repairs_left=%d)",
            state.get("repairs_left", 0),
        )

        issues = state.get("issues", [])
        raw_output = state.get("raw_output", "")
        context_text = state["context_text"]
        repairs_left = state.get("repairs_left", 0)

        # Build repair prompt
        repair_prompt = getattr(
            self, "_active_repair_prompt", self.settings.repair_agent_prompt
        )
        user_message = f"""The following output has validation issues:

ORIGINAL OUTPUT:
{raw_output}

ISSUES:
{chr(10).join(f"- {i}" for i in issues)}

ORIGINAL REQUEST:
{context_text}

Please fix the issues and regenerate the complete output with all 6 sections.
"""
        llm_start = time.time()
        raw = await self._call_llm(repair_prompt, user_message)
        llm_ms = int((time.time() - llm_start) * 1000)

        parse_start = time.time()
        # We'll parse later in validation, but measure the time here
        parse_ms = 0  # Parsing happens in validation step for single-step

        # Track repair in debug
        generation_debug = state.get("generation_debug", {"repairs": []})
        max_repairs = self.settings.agent_max_repairs
        generation_debug["repairs"].append(
            {
                "attempt": max_repairs - repairs_left + 1,
                "issues": issues,
                "output": raw,
                "timing": {
                    "llm_ms": llm_ms,
                    "parse_ms": parse_ms,
                    "total_ms": llm_ms,
                },
            }
        )

        return {
            **state,
            "raw_output": raw,
            "generation_debug": generation_debug,
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
        context_hash = self._hash_context(context_pack)

        # Get generation debug info
        generation_debug = state.get("generation_debug", {})
        elapsed_seconds = generation_debug.get("elapsed_ms", 0) / 1000

        result = {
            "concept_title": concept_title,
            "lyrics": lyrics,
            "suno_prompt": suno_prompt,
            "exclude": exclude,
            "weirdness": weirdness,
            "style_influence": style_influence,
            "generation_id": generation_id,
            "debug_info": {
                "variant": getattr(
                    self, "_active_variant", self.settings.prompt_variant
                ),
                "model": getattr(self, "_active_model", self.settings.llm_model),
                "elapsed_seconds": round(elapsed_seconds, 2),
                "context_hash": context_hash,
                "two_step": False,
                "repaired": state.get("repaired", False),
                # Detailed debug like parallel flow
                "generation": {
                    "system_prompt": generation_debug.get("system_prompt"),
                    "user_message": generation_debug.get("user_message"),
                    "raw_response": generation_debug.get("raw_response"),
                    "elapsed_ms": generation_debug.get("elapsed_ms"),
                    "repairs": generation_debug.get("repairs", []),
                },
            },
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
        self, system_prompt: str, user_prompt: str, temperature: Optional[float] = None
    ) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # Use active LLM (may be variant-specific) or fall back to default
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
