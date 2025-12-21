"""
LangChain-based agent for Suno prompt + lyrics generation.
"""

import hashlib
import json
import random
import time
from typing import Any, Dict, List, Optional

from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.config import Settings
from app.models import SpotifyArtist, TasteProfile
from app.models_advanced import (
    AdvancedGenerateRequest,
    VibeIntent,
    VocalControls,
    RhythmControls,
    TextureControls,
    ContentTheme,
)
from app.services.advanced_prompt_builder import MODE_PRESETS


class SongAgentOutput(BaseModel):
    concept_title: str = Field(description="Short concept title")
    suno_prompt: str = Field(description="Machine-facing prompt, <= 700 chars")
    lyrics: str = Field(description="Human-facing lyrics, <= 1800 chars")


class AgentPromptBuilder:
    """
    LangChain agent to generate song artifacts using isolated context packs.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.llm = ChatOpenAI(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            temperature=settings.openai_temperature,
        )
        self.output_parser = PydanticOutputParser(pydantic_object=SongAgentOutput)
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", settings.song_agent_prompt),
                ("system", "Schema:\n{format_instructions}"),
                ("human", "{context_pack}"),
            ]
        )
        self.chain = self.prompt | self.llm | self.output_parser

    async def generate(
        self,
        request: AdvancedGenerateRequest,
        taste_profile: TasteProfile,
        top_artists: List[SpotifyArtist],
    ) -> Dict[str, Any]:
        request = self._apply_mode_preset(request)
        vibe_signature = self._build_vibe_signature(request)
        lyric_density = self._calculate_lyric_density(request)

        context_pack = self._build_context_pack(
            request=request,
            taste_profile=taste_profile,
            top_artists=top_artists,
            lyric_density=lyric_density,
        )
        context_text = self._format_context_pack(context_pack)

        agent_output = await self.chain.ainvoke(
            {
                "context_pack": context_text,
                "format_instructions": self.output_parser.get_format_instructions(),
            }
        )

        concept_title = self._trim_text(agent_output.concept_title, 50)
        suno_prompt = self._trim_text(agent_output.suno_prompt, 700)
        lyrics = self._trim_text(agent_output.lyrics, 1800)
        generation_id = self._create_generation_id(request)
        context_hash = self._hash_context(context_pack)

        return {
            "concept_title": concept_title,
            "lyrics": lyrics,
            "suno_prompt": suno_prompt,
            "vibe_signature": vibe_signature,
            "control_layers_used": self._get_active_controls(request),
            "generation_id": generation_id,
            "debug_info": {
                "lyric_density": lyric_density,
                "mode": request.mode,
                "taste_influence": "enabled" if taste_profile else "disabled",
                "agent_model": self.settings.openai_model,
                "context_hash": context_hash,
            },
        }

    def _apply_mode_preset(self, request: AdvancedGenerateRequest) -> AdvancedGenerateRequest:
        """Apply mode preset defaults to fill missing controls."""
        preset = MODE_PRESETS.get(request.mode, {})

        if not request.vocals:
            vocal_defaults = preset.get("vocal_defaults", {})
            request.vocals = VocalControls(**vocal_defaults)

        if not request.rhythm:
            rhythm_defaults = preset.get("rhythm_defaults", {})
            request.rhythm = RhythmControls(**rhythm_defaults)

        if not request.texture:
            texture_defaults = preset.get("texture_defaults", {})
            request.texture = TextureControls(**texture_defaults)

        if not request.content_theme and "content_themes" in preset:
            theme_topic = random.choice(preset["content_themes"])
            request.content_theme = ContentTheme(
                theme_type=request.mode if request.mode in ["work", "transition", "ritual", "grief"] else "work",
                specific_topic=theme_topic,
            )

        return request

    def _build_vibe_signature(self, request: AdvancedGenerateRequest) -> Dict[str, Any]:
        vibe_intent = self._get_vibe_intent(request)
        return {
            "primary_feeling": vibe_intent.primary_feeling if vibe_intent else "",
            "sensory_goals": vibe_intent.sensory_goals if vibe_intent else [],
            "mode": request.mode,
            "intensity_vector": {
                "vocal": self._vocal_intensity_score(request.vocals) if request.vocals else 50,
                "rhythmic": self._rhythm_intensity_score(request.rhythm) if request.rhythm else 50,
                "textural": request.texture.organic_vs_synthetic if request.texture else 50,
            },
            "rule_breaking_active": request.rule_breaking is not None,
            "iteration_mode": request.contrast is not None,
        }

    def _vocal_intensity_score(self, vocals: VocalControls) -> int:
        intensity_map = {
            "whisper": 10,
            "soft": 30,
            "conversational": 50,
            "powerful": 75,
            "screaming": 95,
        }
        base = intensity_map.get(vocals.intensity, 50)
        if vocals.voice_as_instrument:
            base += 10
        if vocals.experimental:
            base += 5 * len(vocals.experimental)
        return min(100, base)

    def _rhythm_intensity_score(self, rhythm: RhythmControls) -> int:
        complexity_map = {
            "simple": 20,
            "moderate": 50,
            "polyrhythmic": 75,
            "chaotic": 95,
        }
        base = complexity_map.get(rhythm.complexity, 50)
        drops_map = {"none": 0, "occasional": 10, "frequent": 20, "random": 30}
        base += drops_map.get(rhythm.drops, 0)
        return min(100, base)

    def _calculate_lyric_density(self, request: AdvancedGenerateRequest) -> str:
        if request.lyric_density != "moderate":
            return request.lyric_density

        avg_intensity = (
            self._vocal_intensity_score(request.vocals) if request.vocals else 50
        ) + (self._rhythm_intensity_score(request.rhythm) if request.rhythm else 50)
        avg_intensity /= 2

        if avg_intensity > 75:
            return "minimal"
        if avg_intensity > 50:
            return "sparse"
        if avg_intensity < 30:
            return "rich"
        return "moderate"

    def _build_context_pack(
        self,
        request: AdvancedGenerateRequest,
        taste_profile: TasteProfile,
        top_artists: List[SpotifyArtist],
        lyric_density: str,
    ) -> Dict[str, Any]:
        top_artist_names = [artist.name for artist in top_artists]
        selected_artists = request.selected_artists or top_artist_names[:10]
        excluded_set = {name.lower() for name in request.excluded_artists}
        selected_artists = [
            artist for artist in selected_artists if artist.lower() not in excluded_set
        ]

        selected_genres = request.selected_genres or taste_profile.top_genres[:5]
        custom_vibes = request.custom_vibes or taste_profile.mood_tags
        vibe_intent = self._get_vibe_intent(request)

        return {
            "taste_context": {
                "top_artists": top_artist_names[:20],
                "top_genres": taste_profile.top_genres,
                "mood_tags": taste_profile.mood_tags,
                "summary_sentence": taste_profile.summary_sentence,
                "banned_references": taste_profile.banned_references,
            },
            "user_selection": {
                "selected_artists": selected_artists,
                "excluded_artists": request.excluded_artists,
                "selected_genres": selected_genres,
                "custom_vibes": custom_vibes,
            },
            "generation_controls": {
                "mode": request.mode,
                "vibe_intent": vibe_intent.model_dump() if vibe_intent else {},
                "vocals": request.vocals.model_dump() if request.vocals else None,
                "rhythm": request.rhythm.model_dump() if request.rhythm else None,
                "texture": request.texture.model_dump() if request.texture else None,
                "structure": request.structure.model_dump() if request.structure else None,
                "content_theme": request.content_theme.model_dump() if request.content_theme else None,
                "rule_breaking": request.rule_breaking.model_dump() if request.rule_breaking else None,
                "contrast": request.contrast.model_dump() if request.contrast else None,
                "lyric_density": lyric_density,
            },
            "user_prompt": request.user_prompt or "",
            "extra_notes": request.extra_notes or "",
        }

    def _format_context_pack(self, context_pack: Dict[str, Any]) -> str:
        context_json = json.dumps(context_pack, indent=2, ensure_ascii=True)
        return f"BEGIN_CONTEXT\n{context_json}\nEND_CONTEXT"

    def _hash_context(self, context_pack: Dict[str, Any]) -> str:
        payload = json.dumps(context_pack, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]

    def _get_vibe_intent(self, request: AdvancedGenerateRequest) -> Optional[VibeIntent]:
        return request.vibe_intent

    def _create_generation_id(self, request: AdvancedGenerateRequest) -> str:
        primary = (
            request.vibe_intent.primary_feeling
            if request.vibe_intent and request.vibe_intent.primary_feeling
            else (request.user_prompt or "song")
        )
        content = f"{primary}_{request.mode}_{time.time()}"
        return hashlib.md5(content.encode("utf-8")).hexdigest()[:12]

    def _get_active_controls(self, request: AdvancedGenerateRequest) -> Dict[str, bool]:
        return {
            "vocals": request.vocals is not None,
            "rhythm": request.rhythm is not None,
            "texture": request.texture is not None,
            "structure": request.structure is not None,
            "rule_breaking": request.rule_breaking is not None,
            "contrast_iteration": request.contrast is not None,
            "content_theme": request.content_theme is not None,
            "taste_profile": True,
        }

    def _trim_text(self, text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return f"{text[: max(0, limit - 3)]}..."
