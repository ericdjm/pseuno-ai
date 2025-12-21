"""
Prompt and Lyrics Generator
Builds Suno AI prompts and original lyrics based on taste profile
"""

import random
from typing import Optional, Dict, Any

from app.models import TasteProfile

# Length limits for Suno AI
MAX_PROMPT_LENGTH = 700
MAX_LYRICS_LENGTH = 1800

# Title generation limits
MAX_TITLE_LENGTH = 50

# Template safety limits
MAX_TEMPLATE_FILL_ITERATIONS = 100


# Genre presets with style characteristics
GENRE_PRESETS = {
    "indie_rock": {
        "instruments": ["jangly guitars", "driving drums", "bass"],
        "style": "indie rock with raw energy",
        "tempo": "mid-tempo to upbeat",
        "vocals": "earnest, slightly raspy vocals"
    },
    "electronic": {
        "instruments": ["synthesizers", "drum machines", "pulsing bass"],
        "style": "electronic with atmospheric textures",
        "tempo": "driving beat",
        "vocals": "processed, ethereal vocals"
    },
    "hip_hop": {
        "instruments": ["808 bass", "crisp hi-hats", "sampled melodies"],
        "style": "modern hip-hop with bounce",
        "tempo": "confident groove",
        "vocals": "rhythmic flow, confident delivery"
    },
    "cinematic": {
        "instruments": ["orchestral strings", "piano", "epic percussion"],
        "style": "cinematic and dramatic",
        "tempo": "building intensity",
        "vocals": "powerful, soaring vocals"
    },
    "folk": {
        "instruments": ["acoustic guitar", "gentle percussion", "warm bass"],
        "style": "folk with intimate storytelling",
        "tempo": "relaxed, natural flow",
        "vocals": "warm, conversational vocals"
    },
    "synth_pop": {
        "instruments": ["retro synths", "punchy drums", "arpeggiated bass"],
        "style": "synth-pop with 80s nostalgia",
        "tempo": "upbeat dance groove",
        "vocals": "bright, catchy vocals"
    },
    "dream_pop": {
        "instruments": ["reverb-drenched guitars", "ambient synths", "soft drums"],
        "style": "dreamy and ethereal",
        "tempo": "slow to mid-tempo, floating",
        "vocals": "hushed, reverb-soaked vocals"
    },
    "r_and_b": {
        "instruments": ["smooth keys", "deep bass", "subtle percussion"],
        "style": "contemporary R&B with soul",
        "tempo": "slow groove",
        "vocals": "soulful, emotive vocals"
    }
}

# Energy descriptors
ENERGY_DESCRIPTORS = {
    (0, 25): ["calm", "serene", "gentle", "soft", "peaceful"],
    (25, 50): ["mellow", "laid-back", "relaxed", "smooth", "easygoing"],
    (50, 75): ["dynamic", "driving", "upbeat", "lively", "vibrant"],
    (75, 100): ["explosive", "powerful", "intense", "high-energy", "anthemic"]
}

# Darkness descriptors
DARKNESS_DESCRIPTORS = {
    (0, 25): ["bright", "uplifting", "hopeful", "joyful", "sunny"],
    (25, 50): ["warm", "nostalgic", "bittersweet", "reflective", "wistful"],
    (50, 75): ["moody", "atmospheric", "shadowy", "introspective", "brooding"],
    (75, 100): ["dark", "haunting", "melancholic", "heavy", "intense"]
}

# Rhythm complexity descriptors
RHYTHM_DESCRIPTORS = {
    (0, 25): ["simple", "steady", "minimal", "straightforward"],
    (25, 50): ["groovy", "flowing", "organic", "natural"],
    (50, 75): ["syncopated", "intricate", "layered", "textured"],
    (75, 100): ["complex", "polyrhythmic", "experimental", "unconventional"]
}

# Lyric templates by theme/mood
LYRIC_TEMPLATES = {
    "journey": {
        "verses": [
            "Walking through the {place} tonight\nSearching for a {feeling} light\nEvery step brings {emotion}\n{action} until it feels right",
            "Miles behind me fade away\n{time_ref} becomes just yesterday\nI'm carrying this {object}\nToward a brighter day"
        ],
        "chorus": "We're on our way, we're on our way\nThrough the {weather} and the {obstacle}\nWe're on our way, we're finding home\nNever gonna walk alone",
        "bridge": "And when the road gets long\nAnd when the night feels wrong\nI'll remember why I started\n{realization}"
    },
    "love": {
        "verses": [
            "Your {feature} caught me by surprise\nLike {metaphor} in disguise\nI never knew that I could feel\nSomething this {intensity}",
            "We're dancing in the {place}\n{time_ref} standing still\nYou're everything I {wanted}\nMore than words can fill"
        ],
        "chorus": "You're the {comparison} in my sky\nThe reason that I {action}\nWith you I finally understand\nWhat it means to fly",
        "bridge": "Before you came along\nI thought I had it wrong\nBut now I see so clearly\nYou're where I belong"
    },
    "reflection": {
        "verses": [
            "Looking back at {time_ref}\nI see the {object} that I made\nEvery {feeling} led me here\nTo this {place} where I stayed",
            "The {weather} keeps on changing\nBut something in me knows\nThat every {obstacle} I've faced\nHelped me as I grow"
        ],
        "chorus": "I'm finding my way back\nThrough the noise and {emotion}\nPiece by piece I'm building\nSomething that feels real",
        "bridge": "These walls I built around me\nAre slowly coming down\n{realization}\nI'm finally being found"
    },
    "energy": {
        "verses": [
            "Feel the {intensity} rising up\nCan't hold back, I've had enough\nThe {place} is calling out my name\nNothing's ever gonna be the same",
            "Burning like a {metaphor}\nRunning {speed} without a care\n{time_ref} we take this higher\nNothing can compare"
        ],
        "chorus": "Light it up, light it up tonight\nWe're {action} until the morning light\nNo looking back, no compromise\nWatch us as we rise",
        "bridge": "This is our moment\nThis is our time\n{realization}\nWe're leaving fear behind"
    },
    "melancholy": {
        "verses": [
            "The {weather} falls like {metaphor}\nReminding me of what I've lost\nThese {place} hold our memories\nBut at what cost",
            "I still hear your {sound} sometimes\nEchoing through empty {place}\nThe {object} you left behind\nStill occupies this space"
        ],
        "chorus": "And I'm still here\nWaiting in the {weather}\nHolding onto {object}\nHoping you remember",
        "bridge": "Maybe someday I'll understand\nWhy you had to go\n{realization}\nBut right now I just don't know"
    }
}

# Fill-in options for templates
TEMPLATE_FILLS = {
    "place": ["city streets", "empty halls", "crowded room", "quiet shores", "midnight hour", "neon lights", "open road"],
    "feeling": ["fading", "burning", "growing", "healing", "changing", "breaking", "mending"],
    "emotion": ["hope", "fear", "wonder", "doubt", "peace", "fire", "silence"],
    "action": ["running", "searching", "dreaming", "believing", "breathing", "fighting", "rising"],
    "time_ref": ["yesterday", "tonight", "this moment", "these hours", "the morning", "the evening"],
    "object": ["heart", "dreams", "secrets", "memories", "story", "shadows", "echoes"],
    "weather": ["rain", "storm", "wind", "darkness", "sunlight", "mist", "thunder"],
    "obstacle": ["doubt", "fear", "distance", "silence", "walls", "shadows"],
    "feature": ["eyes", "smile", "voice", "presence", "spirit", "energy"],
    "metaphor": ["stars", "fire", "waves", "lightning", "sunrise", "echo", "hurricane"],
    "intensity": ["deep", "real", "strong", "true", "pure", "wild"],
    "comparison": ["light", "fire", "sun", "star", "anchor", "compass"],
    "wanted": ["needed", "dreamed of", "searched for", "hoped for"],
    "realization": ["I finally see the truth", "Everything makes sense now", "I know what I must do", "The answer was inside me"],
    "speed": ["wild", "free", "fast", "hard"],
    "sound": ["voice", "laugh", "whisper", "song"]
}


class PromptBuilder:
    """Builds Suno AI prompts and generates original lyrics"""
    
    def __init__(self, taste_profile: TasteProfile):
        self.taste = taste_profile
    
    def generate(
        self,
        theme: Optional[str] = None,
        energy: int = 50,
        rhythm_complexity: int = 50,
        darkness: int = 50,
        extra_notes: Optional[str] = None,
        preset: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a Suno prompt and lyrics
        
        TODO: Wire this to an LLM for more creative generation
        For MVP, uses templates and taste profile
        """
        # Determine style from preset or taste
        style_info = self._get_style_info(preset)
        
        # Get descriptors based on sliders
        energy_desc = self._get_descriptor(energy, ENERGY_DESCRIPTORS)
        darkness_desc = self._get_descriptor(darkness, DARKNESS_DESCRIPTORS)
        rhythm_desc = self._get_descriptor(rhythm_complexity, RHYTHM_DESCRIPTORS)
        
        # Build the prompt
        suno_prompt = self._build_prompt(
            style_info=style_info,
            energy_desc=energy_desc,
            darkness_desc=darkness_desc,
            rhythm_desc=rhythm_desc,
            extra_notes=extra_notes
        )
        
        # Generate lyrics
        lyrics = self._generate_lyrics(
            theme=theme,
            energy=energy,
            darkness=darkness
        )
        
        # Generate concept title
        concept_title = self._generate_title(theme, energy_desc, darkness_desc)
        
        return {
            "concept_title": concept_title,
            "suno_prompt": suno_prompt,
            "lyrics": lyrics
        }
    
    def _get_style_info(self, preset: Optional[str]) -> Dict[str, Any]:
        """Get style information from preset or taste profile"""
        if preset and preset in GENRE_PRESETS:
            return GENRE_PRESETS[preset]
        
        # Derive from taste profile
        genres = self.taste.top_genres
        moods = self.taste.mood_tags
        
        # Try to match a preset from genres
        for genre in genres[:3]:
            genre_lower = genre.lower().replace(" ", "_").replace("-", "_")
            for preset_key in GENRE_PRESETS:
                if preset_key in genre_lower or genre_lower in preset_key:
                    return GENRE_PRESETS[preset_key]
        
        # Build custom style from taste
        instruments = self._derive_instruments(genres)
        style = f"fusion of {', '.join(genres[:2]) if len(genres) >= 2 else genres[0] if genres else 'contemporary'}"
        
        return {
            "instruments": instruments,
            "style": style,
            "tempo": "dynamic tempo",
            "vocals": "expressive, authentic vocals"
        }
    
    def _derive_instruments(self, genres: list[str]) -> list[str]:
        """Derive likely instruments from genres"""
        instruments = set()
        
        genre_instruments = {
            "rock": ["electric guitar", "drums", "bass"],
            "electronic": ["synthesizers", "drum machines"],
            "hip hop": ["808 bass", "hi-hats"],
            "folk": ["acoustic guitar", "gentle percussion"],
            "pop": ["synths", "punchy drums"],
            "indie": ["jangly guitars", "bass"],
            "r&b": ["smooth keys", "bass"],
            "jazz": ["piano", "upright bass"],
            "metal": ["heavy guitars", "double bass drums"],
            "ambient": ["ambient pads", "textures"]
        }
        
        for genre in genres[:5]:
            genre_lower = genre.lower()
            for key, insts in genre_instruments.items():
                if key in genre_lower:
                    instruments.update(insts)
                    break
        
        if not instruments:
            instruments = {"modern production", "layered instruments"}
        
        return list(instruments)[:4]
    
    def _get_descriptor(self, value: int, descriptor_map: dict) -> str:
        """Get a descriptor based on value range"""
        for (low, high), descriptors in descriptor_map.items():
            if low <= value < high or (high == 100 and value == 100):
                return random.choice(descriptors)
        return random.choice(list(descriptor_map.values())[0])
    
    def _build_prompt(
        self,
        style_info: Dict[str, Any],
        energy_desc: str,
        darkness_desc: str,
        rhythm_desc: str,
        extra_notes: Optional[str]
    ) -> str:
        """Build the Suno AI prompt (max ~700 chars)"""
        
        # Core style elements
        instruments = ", ".join(style_info.get("instruments", ["modern production"])[:3])
        style = style_info.get("style", "contemporary")
        tempo = style_info.get("tempo", "dynamic")
        vocals = style_info.get("vocals", "expressive vocals")
        
        # Build prompt parts
        parts = [
            f"{energy_desc.capitalize()} {style}",
            f"featuring {instruments}",
            f"{tempo} with {rhythm_desc} rhythms",
            f"{darkness_desc} atmosphere",
            vocals
        ]
        
        # Add mood tags
        if self.taste.mood_tags:
            mood_part = f"Mood: {', '.join(self.taste.mood_tags[:3])}"
            parts.append(mood_part)
        
        # Add extra notes if provided
        if extra_notes:
            # Truncate if too long
            notes_truncated = extra_notes[:100] + "..." if len(extra_notes) > 100 else extra_notes
            parts.append(f"Notes: {notes_truncated}")
        
        prompt = ". ".join(parts)
        
        # Ensure under limit
        if len(prompt) > MAX_PROMPT_LENGTH:
            prompt = prompt[:MAX_PROMPT_LENGTH - 3] + "..."
        
        return prompt
    
    def _generate_lyrics(
        self,
        theme: Optional[str],
        energy: int,
        darkness: int
    ) -> str:
        """
        Generate original lyrics (max ~1800 chars)
        
        TODO: Wire to LLM for more creative, theme-aware lyrics
        For MVP, uses templates with random fills
        """
        # Select template based on theme/mood
        if theme:
            theme_lower = theme.lower()
            if any(word in theme_lower for word in ["love", "heart", "romance", "together"]):
                template_key = "love"
            elif any(word in theme_lower for word in ["journey", "road", "travel", "path"]):
                template_key = "journey"
            elif any(word in theme_lower for word in ["party", "dance", "night", "wild", "energy"]):
                template_key = "energy"
            elif any(word in theme_lower for word in ["sad", "loss", "gone", "miss", "rain"]):
                template_key = "melancholy"
            else:
                template_key = "reflection"
        else:
            # Choose based on energy and darkness
            if energy > 65:
                template_key = "energy"
            elif darkness > 65:
                template_key = "melancholy"
            elif darkness < 35:
                template_key = "love" if random.random() > 0.5 else "journey"
            else:
                template_key = "reflection"
        
        template = LYRIC_TEMPLATES[template_key]
        
        # Fill in templates
        verse1 = self._fill_template(random.choice(template["verses"]))
        verse2 = self._fill_template(template["verses"][-1])
        chorus = self._fill_template(template["chorus"])
        bridge = self._fill_template(template["bridge"])
        
        # Construct lyrics
        lyrics = f"""[Verse 1]
{verse1}

[Chorus]
{chorus}

[Verse 2]
{verse2}

[Chorus]
{chorus}

[Bridge]
{bridge}

[Chorus]
{chorus}"""
        
        # Ensure under limit (smarter truncation at section boundary)
        if len(lyrics) > MAX_LYRICS_LENGTH:
            # Try removing last chorus first
            truncated = lyrics.rsplit("\n\n[Chorus]\n", 1)[0]
            if len(truncated) <= MAX_LYRICS_LENGTH:
                lyrics = truncated
            else:
                # Last resort: hard truncate
                lyrics = lyrics[:MAX_LYRICS_LENGTH - 3] + "..."
        
        return lyrics
    
    def _fill_template(self, template: str) -> str:
        """Fill a template string with random options (safe from infinite loops)"""
        result = template
        iterations = 0
        
        for key, options in TEMPLATE_FILLS.items():
            placeholder = "{" + key + "}"
            # Process all instances of this placeholder
            while placeholder in result and iterations < MAX_TEMPLATE_FILL_ITERATIONS:
                # Choose option that doesn't contain the same placeholder
                safe_options = [opt for opt in options if placeholder not in opt]
                if not safe_options:
                    # Fallback to first option if all contain placeholder (shouldn't happen)
                    replacement = options[0].replace(placeholder, "thing")
                else:
                    replacement = random.choice(safe_options)
                result = result.replace(placeholder, replacement, 1)
                iterations += 1
            
            if iterations >= MAX_TEMPLATE_FILL_ITERATIONS:
                print(f"⚠️  Template filling hit iteration limit for key: {key}")
                break
        
        return result
    
    def _generate_title(
        self,
        theme: Optional[str],
        energy_desc: str,
        darkness_desc: str
    ) -> str:
        """Generate a concept title"""
        
        title_templates = [
            "{mood} {noun}",
            "The {noun} of {abstract}",
            "{verb}ing {direction}",
            "{time} {mood}",
            "{color} {noun}"
        ]
        
        fills = {
            "mood": [energy_desc.capitalize(), darkness_desc.capitalize(), 
                    random.choice(self.taste.mood_tags).capitalize() if self.taste.mood_tags else "Endless"],
            "noun": ["Horizon", "Echo", "Signal", "Pulse", "Wave", "Light", "Storm", "Dream"],
            "abstract": ["Tomorrow", "Memory", "Motion", "Silence", "Everything", "Nothing"],
            "verb": ["Break", "Run", "Fall", "Rise", "Burn", "Fade", "Chase", "Float"],
            "direction": ["Forward", "Home", "Away", "Higher", "Through"],
            "time": ["Midnight", "Dawn", "Endless", "Fleeting", "Infinite"],
            "color": ["Neon", "Golden", "Silver", "Crimson", "Electric"]
        }
        
        template = random.choice(title_templates)
        title = template
        
        for key, options in fills.items():
            placeholder = "{" + key + "}"
            if placeholder in title:
                title = title.replace(placeholder, random.choice(options), 1)
        
        # If theme is provided, maybe incorporate it
        if theme and len(theme) < 20 and random.random() > 0.6:
            words = theme.split()
            if words:
                title = f"{random.choice(words).capitalize()} {title}"
        
        return title[:MAX_TITLE_LENGTH]  # Limit length
