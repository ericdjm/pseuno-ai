"""
Advanced vibe-first prompt builder
Implements phenomenological music generation
"""

import random
import hashlib
from typing import Optional, Dict, Any, List

from app.models import TasteProfile
from app.models_advanced import (
    AdvancedGenerateRequest,
    VibeIntent,
    VocalControls,
    RhythmControls,
    TextureControls,
    StructureControls,
    RuleBreaking,
    ContentTheme,
    ContrastIteration,
    GenerationMode
)


# Mode presets that embody your signature
MODE_PRESETS = {
    "ritual": {
        "description": "Work as ritual, creation through friction",
        "vibe_keywords": ["focused", "meditative", "purposeful", "transformative"],
        "vocal_defaults": {"intensity": "conversational", "harmonies": True, "voice_as_instrument": True},
        "rhythm_defaults": {"complexity": "moderate", "accents": ["steady", "grounding"]},
        "texture_defaults": {"organic_vs_synthetic": 60, "atmosphere": ["ritual", "cathedral"]},
        "content_themes": ["building tools", "fixing bugs", "creation", "labor"]
    },
    "grief": {
        "description": "Emotional processing, cathartic release",
        "vibe_keywords": ["heavy", "releasing", "honest", "raw"],
        "vocal_defaults": {"intensity": "powerful", "range": "wide", "voice_as_instrument": True},
        "rhythm_defaults": {"complexity": "simple", "drops": "occasional"},
        "texture_defaults": {"organic_vs_synthetic": 30, "raw_vs_processed": 20, "atmosphere": ["empty", "vast"]},
        "content_themes": ["loss", "transition", "letting go", "acceptance"]
    },
    "chaos": {
        "description": "Intentional disorder, emotional rupture",
        "vibe_keywords": ["unpredictable", "intense", "rupturing", "overwhelming"],
        "vocal_defaults": {"intensity": "screaming", "range": "extreme", "experimental": ["glitches", "distortion"]},
        "rhythm_defaults": {"complexity": "chaotic", "drops": "random", "accents": ["random drops", "silence → slam"]},
        "texture_defaults": {"organic_vs_synthetic": 80, "raw_vs_processed": 90, "atmosphere": ["industrial", "collapsing"]},
        "content_themes": ["system failure", "overload", "breaking point", "chaos theory"]
    },
    "work": {
        "description": "Labor, process, building systems",
        "vibe_keywords": ["mechanical", "rhythmic", "purposeful", "building"],
        "vocal_defaults": {"intensity": "conversational", "experimental": ["techno chants", "spoken"]},
        "rhythm_defaults": {"complexity": "moderate", "accents": ["machine-like", "industrial"]},
        "texture_defaults": {"organic_vs_synthetic": 70, "atmosphere": ["factory", "workshop"]},
        "content_themes": ["building", "fixing", "optimizing", "systems thinking"]
    },
    "flow": {
        "description": "Continuity, trance, sustained movement",
        "vibe_keywords": ["flowing", "hypnotic", "continuous", "immersive"],
        "vocal_defaults": {"intensity": "soft", "harmonies": True, "experimental": ["layered", "looping"]},
        "rhythm_defaults": {"complexity": "polyrhythmic", "tempo_feel": "steady pulse"},
        "texture_defaults": {"organic_vs_synthetic": 50, "atmosphere": ["underwater", "cosmic"]},
        "content_themes": ["process", "journey", "navigation", "sustained effort"]
    },
    "transition": {
        "description": "Change, transformation, crossing thresholds",
        "vibe_keywords": ["shifting", "transforming", "liminal", "uncertain"],
        "vocal_defaults": {"intensity": "conversational", "range": "wide"},
        "rhythm_defaults": {"complexity": "moderate", "drops": "occasional", "tempo_feel": "accelerating"},
        "texture_defaults": {"organic_vs_synthetic": 50, "atmosphere": ["threshold", "doorway"]},
        "content_themes": ["leaving", "arriving", "portaging", "crossing over"]
    },
    "hope_threat": {
        "description": "Technology as both hope and threat, future ambiguity",
        "vibe_keywords": ["dual", "uncertain", "awe-inspiring", "ominous"],
        "vocal_defaults": {"intensity": "powerful", "experimental": ["processed", "AI-like"]},
        "rhythm_defaults": {"complexity": "polyrhythmic", "drops": "frequent"},
        "texture_defaults": {"organic_vs_synthetic": 85, "raw_vs_processed": 80, "atmosphere": ["digital", "vast"]},
        "content_themes": ["AI", "future", "technology", "humanity", "feedback loops"]
    }
}


class AdvancedPromptBuilder:
    """
    Vibe-first prompt builder implementing phenomenological generation
    """
    
    def __init__(self, taste_profile: Optional[TasteProfile] = None):
        self.taste = taste_profile
        self.generation_history: Dict[str, Any] = {}
    
    def generate(self, request: AdvancedGenerateRequest) -> Dict[str, Any]:
        """
        Generate using vibe-first methodology
        """
        # Apply mode preset if specified
        if request.mode != "custom":
            request = self._apply_mode_preset(request)
        
        # Build vibe signature
        vibe_signature = self._build_vibe_signature(request)
        
        # Determine lyric density based on intensity
        lyric_density = self._calculate_lyric_density(request)
        
        # Generate prompt (machine-facing)
        suno_prompt = self._build_suno_prompt(request, vibe_signature)
        
        # Generate lyrics (human-facing)
        lyrics = self._build_lyrics(request, lyric_density, vibe_signature)
        
        # Generate title
        concept_title = self._generate_title(request, vibe_signature)
        
        # Create generation ID
        generation_id = self._create_generation_id(request, vibe_signature)
        
        # Store for iteration
        self.generation_history[generation_id] = {
            "request": request.model_dump(),
            "vibe_signature": vibe_signature,
            "timestamp": __import__("time").time()
        }
        
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
                "taste_influence": "enabled" if self.taste else "disabled"
            } if True else None  # Always include for now
        }
    
    def _apply_mode_preset(self, request: AdvancedGenerateRequest) -> AdvancedGenerateRequest:
        """Apply mode preset defaults"""
        preset = MODE_PRESETS.get(request.mode, {})
        
        # Apply vocal defaults if not specified
        if not request.vocals:
            vocal_defaults = preset.get("vocal_defaults", {})
            request.vocals = VocalControls(**vocal_defaults)
        
        # Apply rhythm defaults if not specified
        if not request.rhythm:
            rhythm_defaults = preset.get("rhythm_defaults", {})
            request.rhythm = RhythmControls(**rhythm_defaults)
        
        # Apply texture defaults if not specified
        if not request.texture:
            texture_defaults = preset.get("texture_defaults", {})
            request.texture = TextureControls(**texture_defaults)
        
        # Suggest content theme if not specified
        if not request.content_theme and "content_themes" in preset:
            theme_topic = random.choice(preset["content_themes"])
            request.content_theme = ContentTheme(
                theme_type=request.mode if request.mode in ["work", "transition", "ritual", "grief"] else "work",
                specific_topic=theme_topic
            )
        
        return request
    
    def _build_vibe_signature(self, request: AdvancedGenerateRequest) -> Dict[str, Any]:
        """Build a fingerprint of the intended vibe"""
        return {
            "primary_feeling": request.vibe_intent.primary_feeling,
            "sensory_goals": request.vibe_intent.sensory_goals,
            "mode": request.mode,
            "intensity_vector": {
                "vocal": self._vocal_intensity_score(request.vocals) if request.vocals else 50,
                "rhythmic": self._rhythm_intensity_score(request.rhythm) if request.rhythm else 50,
                "textural": request.texture.organic_vs_synthetic if request.texture else 50,
            },
            "rule_breaking_active": request.rule_breaking is not None,
            "iteration_mode": request.contrast is not None
        }
    
    def _vocal_intensity_score(self, vocals: VocalControls) -> int:
        """Calculate vocal intensity 0-100"""
        intensity_map = {"whisper": 10, "soft": 30, "conversational": 50, "powerful": 75, "screaming": 95}
        base = intensity_map.get(vocals.intensity, 50)
        if vocals.voice_as_instrument:
            base += 10
        if vocals.experimental:
            base += 5 * len(vocals.experimental)
        return min(100, base)
    
    def _rhythm_intensity_score(self, rhythm: RhythmControls) -> int:
        """Calculate rhythmic intensity 0-100"""
        complexity_map = {"simple": 20, "moderate": 50, "polyrhythmic": 75, "chaotic": 95}
        base = complexity_map.get(rhythm.complexity, 50)
        drops_map = {"none": 0, "occasional": 10, "frequent": 20, "random": 30}
        base += drops_map.get(rhythm.drops, 0)
        return min(100, base)
    
    def _calculate_lyric_density(self, request: AdvancedGenerateRequest) -> str:
        """
        Match semantic bandwidth to sensory bandwidth
        High intensity → low linguistic complexity
        """
        if request.lyric_density != "moderate":
            return request.lyric_density
        
        # Auto-calculate based on intensity
        avg_intensity = (
            self._vocal_intensity_score(request.vocals) if request.vocals else 50 +
            self._rhythm_intensity_score(request.rhythm) if request.rhythm else 50
        ) / 2
        
        if avg_intensity > 75:
            return "minimal"  # Chants, fragments, breath
        elif avg_intensity > 50:
            return "sparse"  # Short phrases, repetition
        elif avg_intensity < 30:
            return "rich"  # More reflection, complexity
        else:
            return "moderate"
    
    def _build_suno_prompt(self, request: AdvancedGenerateRequest, vibe_signature: Dict) -> str:
        """
        Build machine-facing prompt with orthogonal controls
        Structure suggested, not enforced
        """
        parts = []
        
        # Start with vibe intent
        parts.append(request.vibe_intent.primary_feeling)
        if request.vibe_intent.sensory_goals:
            parts.append(f"designed to evoke: {', '.join(request.vibe_intent.sensory_goals[:2])}")
        
        # Vocal layer
        if request.vocals:
            vocal_desc = self._describe_vocals(request.vocals)
            if vocal_desc:
                parts.append(vocal_desc)
        
        # Rhythm layer
        if request.rhythm:
            rhythm_desc = self._describe_rhythm(request.rhythm)
            if rhythm_desc:
                parts.append(rhythm_desc)
        
        # Texture layer
        if request.texture:
            texture_desc = self._describe_texture(request.texture)
            if texture_desc:
                parts.append(texture_desc)
        
        # Structure hints (not requirements)
        if request.structure:
            structure_desc = self._describe_structure(request.structure)
            if structure_desc:
                parts.append(f"Structure: {structure_desc}")
        
        # Rule breaking (explicit permissions)
        if request.rule_breaking:
            rule_breaks = self._describe_rule_breaking(request.rule_breaking)
            if rule_breaks:
                parts.append(f"Permission to: {rule_breaks}")
        
        # Contrast iteration
        if request.contrast:
            contrast_desc = self._describe_contrast(request.contrast)
            if contrast_desc:
                parts.append(contrast_desc)
        
        # Add taste profile influence if available
        if self.taste and self.taste.mood_tags:
            parts.append(f"Influenced by: {', '.join(self.taste.mood_tags[:2])}")
        
        prompt = ". ".join(parts)
        
        # Ensure under 700 chars
        if len(prompt) > 700:
            prompt = prompt[:697] + "..."
        
        return prompt
    
    def _describe_vocals(self, vocals: VocalControls) -> str:
        """Describe vocal layer physically"""
        parts = []
        parts.append(f"{vocals.intensity} vocals")
        
        if vocals.range != "moderate":
            parts.append(f"{vocals.range} range")
        
        if vocals.harmonies:
            parts.append("layered harmonies")
        
        if vocals.experimental:
            parts.append(f"experimental: {', '.join(vocals.experimental[:2])}")
        
        if vocals.voice_as_instrument:
            parts.append("voice as pure instrument")
        
        return ", ".join(parts) if parts else ""
    
    def _describe_rhythm(self, rhythm: RhythmControls) -> str:
        """Describe rhythm layer"""
        parts = []
        parts.append(f"{rhythm.complexity} rhythms")
        
        if rhythm.accents:
            parts.append(f"with {', '.join(rhythm.accents[:2])}")
        
        if rhythm.drops != "none":
            parts.append(f"{rhythm.drops} drops")
        
        if rhythm.tempo_feel:
            parts.append(rhythm.tempo_feel)
        
        return ", ".join(parts) if parts else ""
    
    def _describe_texture(self, texture: TextureControls) -> str:
        """Describe texture layer"""
        parts = []
        
        # Organic vs synthetic
        if texture.organic_vs_synthetic < 30:
            parts.append("organic, live feel")
        elif texture.organic_vs_synthetic > 70:
            parts.append("synthetic, electronic")
        
        # Raw vs processed
        if texture.raw_vs_processed < 30:
            parts.append("raw, unprocessed")
        elif texture.raw_vs_processed > 70:
            parts.append("hyper-processed")
        
        # Atmosphere
        if texture.atmosphere:
            parts.append(f"{', '.join(texture.atmosphere[:2])} atmosphere")
        
        return ", ".join(parts) if parts else ""
    
    def _describe_structure(self, structure: StructureControls) -> str:
        """Describe structure suggestions"""
        parts = []
        
        if structure.form_hints:
            parts.append(f"hints of {', '.join(structure.form_hints[:2])}")
        
        if structure.fake_drops:
            parts.append("fake drops")
        
        if structure.collapses:
            parts.append("intentional collapses")
        
        if structure.unresolved:
            parts.append("unresolved endings")
        
        if structure.intentional_chaos:
            parts.append("chaos that feels earned")
        
        return ", ".join(parts) if parts else ""
    
    def _describe_rule_breaking(self, rules: RuleBreaking) -> str:
        """Describe explicit rule violations"""
        breaks = []
        
        if rules.break_melody:
            breaks.append("leave melodies unresolved")
        
        if rules.break_rhythm:
            breaks.append("rhythm from breath not beats")
        
        if rules.break_structure:
            breaks.append("use silence as structure")
        
        if rules.break_vocals:
            breaks.append("push vocals beyond comfort")
        
        breaks.extend(rules.permission_to_violate[:2])
        
        return ", ".join(breaks) if breaks else ""
    
    def _describe_contrast(self, contrast: ContrastIteration) -> str:
        """Describe contrast iteration"""
        parts = []
        
        if contrast.less_of:
            parts.append(f"Less: {', '.join(contrast.less_of[:2])}")
        
        if contrast.more_of:
            parts.append(f"More: {', '.join(contrast.more_of[:2])}")
        
        if contrast.push_direction:
            parts.append(f"Push it: {contrast.push_direction}")
        
        return ". ".join(parts) if parts else ""
    
    def _build_lyrics(
        self,
        request: AdvancedGenerateRequest,
        lyric_density: str,
        vibe_signature: Dict
    ) -> str:
        """
        Generate human-facing lyrics
        Matches semantic bandwidth to sensory bandwidth
        """
        # Get content theme
        theme = request.content_theme
        if not theme:
            theme = ContentTheme(theme_type="work", specific_topic="the process")
        
        # Build based on density and theme
        if lyric_density == "minimal":
            return self._build_minimal_lyrics(theme, request.vibe_intent)
        elif lyric_density == "sparse":
            return self._build_sparse_lyrics(theme, request.vibe_intent)
        elif lyric_density == "rich":
            return self._build_rich_lyrics(theme, request.vibe_intent)
        else:
            return self._build_moderate_lyrics(theme, request.vibe_intent)
    
    def _build_minimal_lyrics(self, theme: ContentTheme, vibe: VibeIntent) -> str:
        """Chants, fragments, imperatives for high intensity"""
        topic = theme.specific_topic or "the work"
        feeling = vibe.primary_feeling
        
        # Create repetitive, chantable fragments
        fragments = [
            topic.split()[0] if topic else "push",
            feeling.split()[0] if feeling else "feel",
            "now",
            "more",
            "again"
        ]
        
        verse = "\n".join([fragments[0].upper()] * 2 + [fragments[1]] + [fragments[0].upper()])
        chorus = "\n".join([fragments[2], fragments[3], fragments[2], fragments[3]])
        
        return f"""[Verse]
{verse}

[Chorus]
{chorus}

[Drop]
{fragments[0].upper()}

[Chorus]
{chorus}"""
    
    def _build_sparse_lyrics(self, theme: ContentTheme, vibe: VibeIntent) -> str:
        """Short phrases with repetition"""
        topic = theme.specific_topic or "the process"
        
        return f"""[Verse 1]
{topic.capitalize()}
Piece by piece
Build it up
Make it real

[Chorus]
Feel it now
Feel it move
Feel it break
Feel it through

[Verse 2]
Step by step
Push it hard
Find the edge
Go beyond

[Chorus]
Feel it now
Feel it move
Feel it break
Feel it through

[Bridge]
This is it
This is now
This is everything

[Outro]
{topic.split()[0].upper() if topic else 'PUSH'}"""
    
    def _build_moderate_lyrics(self, theme: ContentTheme, vibe: VibeIntent) -> str:
        """Balanced structure with thematic depth"""
        topic = theme.specific_topic or "building something new"
        feeling = vibe.primary_feeling
        
        return f"""[Verse 1]
Started with nothing but an idea and time
{topic.capitalize()}, one line at a time
Every mistake becomes the blueprint
Every failure shows the way forward

[Chorus]
This is how we {feeling}
This is how we know it's real
Layer by layer, piece by piece
Until the vision becomes steel

[Verse 2]
The process is the product now
Creation through the friction
No shortcuts through the complexity
Just honest repetition

[Chorus]
This is how we {feeling}
This is how we know it's real
Layer by layer, piece by piece
Until the vision becomes steel

[Bridge]
And when it breaks
We'll build it better
And when it fails
We'll know the answer

[Chorus]
This is how we {feeling}
This is how we know it's real
Layer by layer, piece by piece
Until the vision becomes steel"""
    
    def _build_rich_lyrics(self, theme: ContentTheme, vibe: VibeIntent) -> str:
        """More complexity and reflection for low intensity"""
        topic = theme.specific_topic or "navigating the unknown"
        
        return f"""[Verse 1]
In the quiet hours before dawn breaks through
I'm {topic}, finding what is true
Every question leads to deeper questions still
But the seeking is its own reward, its own will

[Pre-Chorus]
These hands have built and broken down
Planted seeds in uncertain ground
Watched them grow despite my doubt

[Chorus]
We're all just finding our way through
Making sense of what we do
Transform the pain into something new
Trust the process to carry us through

[Verse 2]
There's wisdom in the work itself, they say
In showing up despite the disarray
The masterpiece is not the final form
But who we become weathering the storm

[Pre-Chorus]
These hands have built and broken down
Planted seeds in uncertain ground
Watched them grow despite my doubt

[Chorus]
We're all just finding our way through
Making sense of what we do
Transform the pain into something new
Trust the process to carry us through

[Bridge]
Maybe the meaning isn't in the end
But in the moment when we transcend
Our limitations and our fear
And find that we were always here

[Final Chorus]
We're all just finding our way through
Making sense of what we do
Transform the pain into something new
Trust the process to carry us through"""
    
    def _generate_title(self, request: AdvancedGenerateRequest, vibe_signature: Dict) -> str:
        """Generate title that reflects the vibe"""
        feeling = request.vibe_intent.primary_feeling.split()[0]
        mode = request.mode
        
        if request.content_theme and request.content_theme.specific_topic:
            topic_word = request.content_theme.specific_topic.split()[0]
            return f"{topic_word.capitalize()}: {feeling.capitalize()}"
        
        # Use mode-based titles
        mode_words = {
            "ritual": "Ritual",
            "grief": "Processing",
            "chaos": "Rupture",
            "work": "Labor",
            "flow": "Continuous",
            "transition": "Threshold",
            "hope_threat": "Duality"
        }
        
        mode_word = mode_words.get(mode, "")
        if mode_word:
            return f"{mode_word}: {feeling.capitalize()}"
        
        return feeling.capitalize()
    
    def _create_generation_id(self, request: AdvancedGenerateRequest, vibe_signature: Dict) -> str:
        """Create unique ID for this generation"""
        content = f"{request.vibe_intent.primary_feeling}_{request.mode}_{__import__('time').time()}"
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    def _get_active_controls(self, request: AdvancedGenerateRequest) -> Dict[str, bool]:
        """Return which control layers were used"""
        return {
            "vocals": request.vocals is not None,
            "rhythm": request.rhythm is not None,
            "texture": request.texture is not None,
            "structure": request.structure is not None,
            "rule_breaking": request.rule_breaking is not None,
            "contrast_iteration": request.contrast is not None,
            "content_theme": request.content_theme is not None,
            "taste_profile": self.taste is not None
        }
