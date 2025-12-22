"""
LangGraph-based agent for Suno prompt + lyrics generation.
"""

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

logger = logging.getLogger(__name__)

from app.config import Settings
from app.models_advanced import AdvancedGenerateRequest
from app.prompts import REPAIR_AGENT_SYSTEM_PROMPT

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
    lyrics: str
    suno_prompt: str
    exclude: str
    weirdness: int
    style_influence: int


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

    async def ainvoke(self, messages: List[Dict[str, str]]):
        payload = {
            "model": self.model,
            "input": self._format_messages(messages),
        }
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        timeout = httpx.Timeout(self.timeout)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                try:
                    response = await client.post(
                        "https://api.openai.com/v1/responses",
                        json=payload,
                        headers=headers,
                    )
                except httpx.ReadTimeout:
                    # Retry once with a longer timeout to handle slow model responses.
                    retry_timeout = httpx.Timeout(
                        max(self.timeout * 2, self.timeout + 30)
                    )
                    async with httpx.AsyncClient(timeout=retry_timeout) as retry_client:
                        response = await retry_client.post(
                            "https://api.openai.com/v1/responses",
                            json=payload,
                            headers=headers,
                        )

                if response.status_code >= 400:
                    # Some models do not support temperature; retry without it if needed.
                    if self._is_unsupported_temperature(response):
                        payload.pop("temperature", None)
                        retry = await client.post(
                            "https://api.openai.com/v1/responses",
                            json=payload,
                            headers=headers,
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

    async def ainvoke(self, messages: List[Dict[str, str]]):
        """
        Invoke the Gemini model with the given messages.
        Gemini uses a different format - we convert from OpenAI-style messages.
        """
        import asyncio

        # Run synchronous Gemini call in executor to avoid blocking
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, self._sync_generate, messages)
        return _LLMResponse(content=response or "")

    def _sync_generate(self, messages: List[Dict[str, str]]) -> str:
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
            temperature=self.temperature,
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
    """

    def __init__(self, settings: Settings, llm: Optional[Any] = None):
        self.settings = settings
        self.llm = llm or self._create_llm_client(settings)
        self._graph = self._build_graph()
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

    def _build_graph(self):
        graph = StateGraph(_AgentState)

        graph.add_node("build_context", self._node_build_context)
        graph.add_node("generate", self._node_generate)
        graph.add_node("parse_validate", self._node_parse_validate)
        graph.add_node("repair", self._node_repair)
        graph.add_node("error", self._node_error)
        graph.add_node("finalize", self._node_finalize)

        graph.set_entry_point("build_context")
        graph.add_edge("build_context", "generate")
        graph.add_edge("generate", "parse_validate")
        graph.add_edge("repair", "parse_validate")
        graph.add_edge("error", END)

        graph.add_conditional_edges(
            "parse_validate",
            self._route_after_validation,
            {
                "finalize": "finalize",
                "repair": "repair",
                "error": "error",
            },
        )

        graph.add_edge("finalize", END)
        return graph.compile()

    async def generate(self, request: AdvancedGenerateRequest) -> Dict[str, Any]:
        state = await self._graph.ainvoke({"request": request})
        return state["result"]

    async def _node_build_context(self, state: _AgentState) -> _AgentState:
        request = state["request"]
        context_pack = self._build_context_pack(request)
        context_text = self._format_context_pack(context_pack)
        max_repairs = (
            self.settings.agent_max_repairs if self.settings.agent_repair_enabled else 0
        )
        return {
            **state,
            "context_pack": context_pack,
            "context_text": context_text,
            "repairs_left": max_repairs,
            "repaired": False,
        }

    async def _node_generate(self, state: _AgentState) -> _AgentState:
        logger.info("agent.generate calling LLM (model=%s)", self.settings.llm_model)

        # DEBUG: Write full request to log file
        self._debug_log("=" * 80)
        self._debug_log(f"MODEL: {self.settings.llm_model}")
        self._debug_log("=" * 80)
        self._debug_log("\n--- SYSTEM PROMPT ---")
        self._debug_log(
            self.settings.song_agent_prompt[:500] + "..."
            if len(self.settings.song_agent_prompt) > 500
            else self.settings.song_agent_prompt
        )
        self._debug_log("\n--- USER CONTEXT ---")
        self._debug_log(state["context_text"])
        self._debug_log("\n--- END REQUEST ---\n")

        raw_output = await self._call_llm(
            self.settings.song_agent_prompt, state["context_text"]
        )

        # DEBUG: Write raw response
        self._debug_log("\n--- RAW LLM RESPONSE ---")
        self._debug_log(raw_output)
        self._debug_log("\n--- END RESPONSE ---\n")

        logger.info("agent.generate received LLM output (chars=%s)", len(raw_output))
        return {**state, "raw_output": raw_output}

    async def _node_parse_validate(self, state: _AgentState) -> _AgentState:
        parsed = self._parse_agent_output(state.get("raw_output", ""))
        issues = self._validate_output(parsed, state["context_pack"])

        # DEBUG: Write parsed output and issues
        self._debug_log("\n--- PARSED OUTPUT ---")
        self._debug_log(f"order: {parsed.order}")
        self._debug_log(
            f"suno_prompt: {parsed.suno_prompt[:200]}..."
            if len(parsed.suno_prompt) > 200
            else f"suno_prompt: {parsed.suno_prompt}"
        )
        self._debug_log(f"exclude: {parsed.exclude}")
        self._debug_log(f"weirdness: {parsed.weirdness}")
        self._debug_log(f"style_influence: {parsed.style_influence}")
        self._debug_log(f"\nISSUES FOUND: {len(issues)}")
        for issue in issues:
            self._debug_log(f"  - {issue}")
        self._debug_log("--- END PARSED ---\n")

        if issues:
            logger.info("agent.parse_validate found issues (count=%s)", len(issues))
        else:
            logger.info("agent.parse_validate ok")
        return {**state, "parsed": parsed, "issues": issues}

    def _route_after_validation(self, state: _AgentState) -> str:
        issues = state.get("issues") or []
        if not issues:
            return "finalize"
        if state.get("repairs_left", 0) > 0:
            return "repair"
        return "error"

    async def _node_repair(self, state: _AgentState) -> _AgentState:
        repairs_left = max(0, state.get("repairs_left", 0) - 1)
        issues = state.get("issues") or []
        issues_text = "\n".join(f"- {issue}" for issue in issues)
        repair_input = (
            f"{state['context_text']}\n\n"
            "BEGIN_PREVIOUS_OUTPUT\n"
            f"{state.get('raw_output', '')}\n"
            "END_PREVIOUS_OUTPUT\n\n"
            "BEGIN_ISSUES\n"
            f"{issues_text}\n"
            "END_ISSUES\n"
        )
        raw_output = await self._call_llm(
            REPAIR_AGENT_SYSTEM_PROMPT,
            repair_input,
            temperature=0.0,
        )
        return {
            **state,
            "raw_output": raw_output,
            "repairs_left": repairs_left,
            "repaired": True,
        }

    def _node_error(self, state: _AgentState) -> _AgentState:
        """Return an error result with validation issues — no silent fallback."""
        issues = state.get("issues") or []
        logger.warning("agent.error validation failed (issues=%s)", len(issues))

        # Log the issues for debugging
        for issue in issues:
            logger.warning("  - %s", issue)
        self._debug_log("\n--- VALIDATION FAILED (NO FALLBACK) ---")
        for issue in issues:
            self._debug_log(f"  - {issue}")
        self._debug_log("--- END ERROR ---\n")

        return {
            **state,
            "result": {
                "success": False,
                "error": "Validation failed after all repair attempts",
                "issues": issues,
                "raw_output": state.get("raw_output", ""),
            },
        }

    def _node_finalize(self, state: _AgentState) -> _AgentState:
        context_pack = state["context_pack"]
        parsed = state["parsed"]
        song_prompt = context_pack.get("user_style_request", "")
        lyrics_about = context_pack.get("lyrics_about", "")

        concept_title = self._derive_title(song_prompt, lyrics_about)
        suno_prompt = parsed.suno_prompt.strip() or song_prompt.strip()
        suno_prompt = self._trim_text(suno_prompt, 500)
        lyrics = parsed.lyrics.strip()
        exclude = parsed.exclude.strip()
        weirdness = self._clamp_percent(parsed.weirdness)
        style_influence = self._clamp_percent(parsed.style_influence)
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
                "agent_model": self.settings.llm_model,
                "context_hash": context_hash,
                "repaired": state.get("repaired", False),
                "repair_enabled": self.settings.agent_repair_enabled,
                "max_repairs": self.settings.agent_max_repairs,
            },
        }
        return {**state, "result": result}

    async def _call_llm(
        self, system_prompt: str, user_prompt: str, temperature: Optional[float] = None
    ) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        if temperature is not None and hasattr(self.llm, "temperature"):
            original = getattr(self.llm, "temperature")
            try:
                setattr(self.llm, "temperature", temperature)
                response = await self.llm.ainvoke(messages)
            finally:
                setattr(self.llm, "temperature", original)
        else:
            response = await self.llm.ainvoke(messages)

        return response.content or ""

    def _build_context_pack(self, request: AdvancedGenerateRequest) -> Dict[str, Any]:
        return {
            "selected_artists": request.selected_artists or [],
            "user_style_request": request.user_prompt or "",
            "lyrics_about": request.lyrics_about or "",
            "tags": request.tags or [],
        }

    def _format_context_pack(self, context_pack: Dict[str, Any]) -> str:
        # Format context with clear instructions about what each field is
        lines = [
            "USER INPUT (transform this into SUNO PROMPT - do NOT copy verbatim):",
            f"  style_request: {context_pack.get('user_style_request', '')}",
            f"  lyrics_about: {context_pack.get('lyrics_about', '')}",
            f"  reference_artists: {context_pack.get('selected_artists', [])}",
            f"  tags: {context_pack.get('tags', [])}",
        ]
        return "\n".join(lines)

    def _parse_agent_output(self, text: str) -> _ParsedAgentOutput:
        order, sections = self._extract_sections(text)

        lyrics = sections.get("LYRICS", "").strip()
        suno_prompt = sections.get("SUNO PROMPT", "").strip()
        exclude = self._first_non_empty_line(sections.get("EXCLUDE", ""))
        weirdness = self._parse_percent(sections.get("WEIRDNESS", ""))
        style_influence = self._parse_percent(sections.get("STYLE INFLUENCE", ""))

        return _ParsedAgentOutput(
            order=order,
            sections=sections,
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
        required = ("LYRICS", "SUNO PROMPT", "EXCLUDE", "WEIRDNESS", "STYLE INFLUENCE")

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
        normalized = re.sub(r"^[A-E]\)\s*", "", normalized)
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
