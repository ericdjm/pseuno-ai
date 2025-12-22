"""
LangChain-based agent for Suno prompt + lyrics generation.
"""

import hashlib
import json
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from langchain_core.prompts import ChatPromptTemplate

from app.config import Settings
from app.models_advanced import AdvancedGenerateRequest
from app.prompts import REPAIR_AGENT_SYSTEM_PROMPT


@dataclass(frozen=True)
class _ParsedAgentOutput:
    order: Tuple[str, ...]
    sections: Dict[str, str]
    lyrics: str
    suno_prompt: str
    exclude: str
    weirdness: int
    style_influence: int


class AgentPromptBuilder:
    """
    LangChain agent to generate song artifacts using a minimal context pack.
    """

    def __init__(self, settings: Settings, llm: Optional[Any] = None):
        self.settings = settings
        if llm is not None:
            self.llm = llm
        else:
            try:
                from langchain_openai import ChatOpenAI  # type: ignore
            except ModuleNotFoundError as e:  # pragma: no cover
                raise RuntimeError(
                    "langchain-openai is required to use AgentPromptBuilder without a custom LLM. "
                    "Install it (pip install langchain-openai) or pass a compatible `llm=`."
                ) from e

            self.llm = ChatOpenAI(
                api_key=settings.openai_api_key,
                model=settings.openai_model,
                temperature=settings.openai_temperature,
            )
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", settings.song_agent_prompt),
                ("human", "{context_pack}"),
            ]
        )
        self._repair_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", REPAIR_AGENT_SYSTEM_PROMPT),
                (
                    "human",
                    (
                        "{context_pack}\n\n"
                        "BEGIN_PREVIOUS_OUTPUT\n"
                        "{previous_output}\n"
                        "END_PREVIOUS_OUTPUT\n\n"
                        "BEGIN_ISSUES\n"
                        "{issues}\n"
                        "END_ISSUES\n"
                    ),
                ),
            ]
        )

    async def generate(self, request: AdvancedGenerateRequest) -> Dict[str, Any]:
        context_pack = self._build_context_pack(request)
        context_text = self._format_context_pack(context_pack)

        # Use config for repair behavior (0 repairs if disabled)
        max_repairs = (
            self.settings.agent_max_repairs if self.settings.agent_repair_enabled else 0
        )

        raw_output, parsed, repaired = await self._generate_with_repairs(
            context_pack=context_pack,
            context_text=context_text,
            max_repairs=max_repairs,
        )
        song_prompt = context_pack.get("song_prompt", "")
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

        return {
            "concept_title": concept_title,
            "lyrics": lyrics,
            "suno_prompt": suno_prompt,
            "exclude": exclude,
            "weirdness": weirdness,
            "style_influence": style_influence,
            "generation_id": generation_id,
            "debug_info": {
                "agent_model": self.settings.openai_model,
                "context_hash": context_hash,
                "repaired": repaired,
                "repair_enabled": self.settings.agent_repair_enabled,
                "max_repairs": self.settings.agent_max_repairs,
            },
        }

    async def _generate_with_repairs(
        self,
        context_pack: Dict[str, Any],
        context_text: str,
        max_repairs: int,
    ) -> Tuple[str, _ParsedAgentOutput, bool]:
        """
        Run the agent, validate output, and attempt up to `max_repairs` repair passes.
        Repairs are triggered by invalid formatting/sections or SUNO PROMPT artist leakage.
        """
        repaired = False

        # Attempt 0: original generation
        raw_output = await self._call_llm(self.prompt, {"context_pack": context_text})
        parsed = self._parse_agent_output(raw_output)
        issues = self._validate_output(parsed, context_pack)

        for _ in range(max_repairs):
            if not issues:
                return raw_output, parsed, repaired

            repaired = True
            raw_output = await self._call_llm(
                self._repair_prompt,
                {
                    "context_pack": context_text,
                    "previous_output": raw_output,
                    "issues": "\n".join(f"- {issue}" for issue in issues),
                },
                # Reduce randomness for repairs (best-effort; fake LLMs can ignore this).
                temperature=0.0,
            )
            parsed = self._parse_agent_output(raw_output)
            issues = self._validate_output(parsed, context_pack)

        if not issues:
            return raw_output, parsed, repaired

        # Final fallback (deterministic, always returns a valid shape).
        fallback_raw, fallback_parsed = self._build_fallback(context_pack)
        return fallback_raw, fallback_parsed, True

    async def _call_llm(
        self,
        prompt: ChatPromptTemplate,
        variables: Dict[str, Any],
        temperature: Optional[float] = None,
    ) -> str:
        messages = prompt.format_messages(**variables)

        # Best-effort: if the underlying LLM exposes a `temperature` attribute, override it
        # for this call (useful for repair stability). Fake LLMs can ignore this.
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
            "song_prompt": request.user_prompt or "",
            "lyrics_about": request.lyrics_about or "",
            "tags": request.tags or [],
        }

    def _format_context_pack(self, context_pack: Dict[str, Any]) -> str:
        context_json = json.dumps(context_pack, indent=2, ensure_ascii=True)
        return f"BEGIN_CONTEXT\n{context_json}\nEND_CONTEXT"

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
        """
        sections: Dict[str, str] = {}
        order: List[str] = []
        current_key: Optional[str] = None
        buffer: list[str] = []

        for line in text.splitlines():
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

        # EXCLUDE must be one line, comma-separated, no dashes, no extra prose.
        exclude = parsed.exclude.strip()
        if "\n" in exclude or "\r" in exclude:
            issues.append("EXCLUDE must be one line only.")
        if "-" in exclude:
            issues.append("EXCLUDE must not contain dashes.")
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

    def _build_fallback(
        self, context_pack: Dict[str, Any]
    ) -> Tuple[str, _ParsedAgentOutput]:
        """
        Deterministic fallback: always returns a valid 5-section output,
        and scrubs artist names from SUNO PROMPT.
        """
        song_prompt = (context_pack.get("song_prompt") or "").strip()
        lyrics_about = (context_pack.get("lyrics_about") or "").strip()
        tags = context_pack.get("tags") or []
        artists = context_pack.get("selected_artists") or []

        # SUNO PROMPT: keep it short and descriptive; do not include artist names.
        base_prompt = (
            song_prompt
            or "Original song with clear instrumentation and strong production details."
        )
        if tags:
            base_prompt = f"{base_prompt} | tags: {', '.join(str(t) for t in tags if str(t).strip())}"
        suno_prompt = self._trim_text(
            self._scrub_artist_names(base_prompt, artists).strip(), 500
        )

        # Lyrics: simple, valid bracket structure; not enforcing lyric artist leakage per requirements.
        topic = lyrics_about or "a vivid scene with strong emotion"
        lyrics = (
            "[Verse]\n"
            f"{self._trim_text(topic, 80)}\n\n"
            "[Chorus]\n"
            f"{self._trim_text(topic, 80)}\n"
        )

        exclude = ""
        weirdness = 50
        style_influence = 50

        raw = (
            "LYRICS\n"
            f"{lyrics}\n\n"
            "SUNO PROMPT\n"
            f"{suno_prompt}\n\n"
            "EXCLUDE\n"
            f"{exclude}\n\n"
            "WEIRDNESS\n"
            f"{weirdness}\n\n"
            "STYLE INFLUENCE\n"
            f"{style_influence}\n"
        )
        parsed = self._parse_agent_output(raw)
        return raw, parsed

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
