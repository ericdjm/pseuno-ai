"""
LangChain-based agent for Suno prompt + lyrics generation.
"""

import hashlib
import json
import re
import time
from typing import Any, Dict, Optional

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from app.config import Settings
from app.models_advanced import AdvancedGenerateRequest


class AgentPromptBuilder:
    """
    LangChain agent to generate song artifacts using a minimal context pack.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
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

    async def generate(self, request: AdvancedGenerateRequest) -> Dict[str, Any]:
        context_pack = self._build_context_pack(request)
        context_text = self._format_context_pack(context_pack)

        messages = self.prompt.format_messages(context_pack=context_text)
        response = await self.llm.ainvoke(messages)
        raw_output = response.content or ""

        parsed = self._parse_agent_output(raw_output)
        song_prompt = context_pack.get("song_prompt", "")
        lyrics_about = context_pack.get("lyrics_about", "")

        concept_title = self._derive_title(song_prompt, lyrics_about)
        suno_prompt = parsed["suno_prompt"].strip() or song_prompt.strip()
        suno_prompt = self._trim_text(suno_prompt, 500)
        lyrics = parsed["lyrics"].strip()
        exclude = parsed["exclude"].strip()
        weirdness = self._clamp_percent(parsed["weirdness"])
        style_influence = self._clamp_percent(parsed["style_influence"])
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
            },
        }

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

    def _parse_agent_output(self, text: str) -> Dict[str, Any]:
        sections: Dict[str, str] = {}
        current_key = None
        buffer: list[str] = []

        for line in text.splitlines():
            header = self._normalize_header(line)
            if header:
                if current_key is not None:
                    sections[current_key] = "\n".join(buffer).strip()
                current_key = header
                buffer = []
                continue
            if current_key is not None:
                buffer.append(line)

        if current_key is not None:
            sections[current_key] = "\n".join(buffer).strip()

        lyrics = sections.get("LYRICS", "").strip()
        suno_prompt = sections.get("SUNO PROMPT", "").strip()
        exclude = self._first_non_empty_line(sections.get("EXCLUDE", ""))
        weirdness = self._parse_percent(sections.get("WEIRDNESS", ""))
        style_influence = self._parse_percent(sections.get("STYLE INFLUENCE", ""))

        return {
            "lyrics": lyrics,
            "suno_prompt": suno_prompt,
            "exclude": exclude,
            "weirdness": weirdness,
            "style_influence": style_influence,
        }

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
