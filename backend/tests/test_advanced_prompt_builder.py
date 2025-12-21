"""
Tests for advanced vibe-first prompt builder
"""

import pytest
from app.services.advanced_prompt_builder import AdvancedPromptBuilder, MODE_PRESETS
from app.models_advanced import (
    AdvancedGenerateRequest,
    VibeIntent,
    VocalControls,
    RhythmControls,
    TextureControls,
    StructureControls,
    RuleBreaking,
    ContentTheme,
    ContrastIteration
)
from app.models import TasteProfile


def create_mock_taste_profile() -> TasteProfile:
    """Create a mock taste profile for testing"""
    return TasteProfile(
        top_genres=["indie rock", "electronic", "experimental"],
        mood_tags=["atmospheric", "intense", "raw"],
        summary_sentence="Your sound leans heavily into experimental indie with intense vibes.",
        banned_references=["Artist One", "Artist Two"]
    )


class TestVibeFirstGeneration:
    """Tests for vibe-first generation methodology"""
    
    def test_minimal_vibe_intent_generates(self):
        """Should generate with just vibe intent"""
        builder = AdvancedPromptBuilder()
        
        request = AdvancedGenerateRequest(
            vibe_intent=VibeIntent(
                primary_feeling="chills",
                sensory_goals=["goosebumps"]
            )
        )
        
        result = builder.generate(request)
        
        assert result["concept_title"]
        assert result["suno_prompt"]
        assert result["lyrics"]
        assert "chills" in result["suno_prompt"].lower()
    
    def test_mode_preset_applies_defaults(self):
        """Should apply mode preset defaults"""
        builder = AdvancedPromptBuilder()
        
        request = AdvancedGenerateRequest(
            vibe_intent=VibeIntent(primary_feeling="focused"),
            mode="ritual"
        )
        
        result = builder.generate(request)
        
        # Ritual mode should set certain defaults
        assert result["control_layers_used"]["vocals"]
        assert result["control_layers_used"]["rhythm"]
        assert "ritual" in result["debug_info"]["mode"]
    
    def test_all_mode_presets_work(self):
        """All mode presets should generate successfully"""
        builder = AdvancedPromptBuilder()
        
        for mode in ["ritual", "grief", "chaos", "work", "flow", "transition", "hope_threat"]:
            request = AdvancedGenerateRequest(
                vibe_intent=VibeIntent(primary_feeling="test"),
                mode=mode
            )
            
            result = builder.generate(request)
            
            assert result["concept_title"]
            assert result["suno_prompt"]
            assert len(result["lyrics"]) > 0


class TestOrthogonalControls:
    """Tests for orthogonal control layers"""
    
    def test_vocal_controls_affect_prompt(self):
        """Vocal controls should affect the generated prompt"""
        builder = AdvancedPromptBuilder()
        
        request = AdvancedGenerateRequest(
            vibe_intent=VibeIntent(primary_feeling="intense"),
            vocals=VocalControls(
                intensity="screaming",
                range="extreme",
                experimental=["throat singing", "distortion"]
            )
        )
        
        result = builder.generate(request)
        
        assert "scream" in result["suno_prompt"].lower()
        assert result["control_layers_used"]["vocals"]
    
    def test_rhythm_controls_affect_prompt(self):
        """Rhythm controls should affect the generated prompt"""
        builder = AdvancedPromptBuilder()
        
        request = AdvancedGenerateRequest(
            vibe_intent=VibeIntent(primary_feeling="chaotic"),
            rhythm=RhythmControls(
                complexity="polyrhythmic",
                drops="random",
                accents=["silence → slam"]
            )
        )
        
        result = builder.generate(request)
        
        assert "polyrhythmic" in result["suno_prompt"].lower()
        assert result["control_layers_used"]["rhythm"]
    
    def test_texture_controls_affect_prompt(self):
        """Texture controls should affect the generated prompt"""
        builder = AdvancedPromptBuilder()
        
        request = AdvancedGenerateRequest(
            vibe_intent=VibeIntent(primary_feeling="atmospheric"),
            texture=TextureControls(
                organic_vs_synthetic=90,
                atmosphere=["industrial", "factory"]
            )
        )
        
        result = builder.generate(request)
        
        assert "synthetic" in result["suno_prompt"].lower() or "electronic" in result["suno_prompt"].lower()
        assert result["control_layers_used"]["texture"]
    
    def test_structure_controls_affect_prompt(self):
        """Structure controls should affect the generated prompt"""
        builder = AdvancedPromptBuilder()
        
        request = AdvancedGenerateRequest(
            vibe_intent=VibeIntent(primary_feeling="unpredictable"),
            structure=StructureControls(
                fake_drops=True,
                unresolved=True,
                intentional_chaos=True
            )
        )
        
        result = builder.generate(request)
        
        assert result["control_layers_used"]["structure"]


class TestLyricDensity:
    """Tests for lyric density matching intensity"""
    
    def test_high_intensity_produces_minimal_lyrics(self):
        """High intensity should produce minimal/chant-like lyrics"""
        builder = AdvancedPromptBuilder()
        
        request = AdvancedGenerateRequest(
            vibe_intent=VibeIntent(primary_feeling="overwhelming"),
            vocals=VocalControls(intensity="screaming", range="extreme"),
            rhythm=RhythmControls(complexity="chaotic", drops="random")
        )
        
        result = builder.generate(request)
        
        # Minimal lyrics should be shorter than rich lyrics
        assert len(result["lyrics"]) < 900
        # High intensity should produce minimal or moderate density
        assert result["debug_info"]["lyric_density"] in ["minimal", "moderate"]
    
    def test_low_intensity_produces_rich_lyrics(self):
        """Low intensity should produce richer lyrics"""
        builder = AdvancedPromptBuilder()
        
        request = AdvancedGenerateRequest(
            vibe_intent=VibeIntent(primary_feeling="contemplative"),
            vocals=VocalControls(intensity="soft", range="narrow"),
            rhythm=RhythmControls(complexity="simple", drops="none")
        )
        
        result = builder.generate(request)
        
        # Rich lyrics should be longer with more complexity
        assert len(result["lyrics"]) > 500
        assert result["debug_info"]["lyric_density"] in ["moderate", "rich"]
    
    def test_manual_density_override(self):
        """Manual lyric density should override auto-calculation"""
        builder = AdvancedPromptBuilder()
        
        request = AdvancedGenerateRequest(
            vibe_intent=VibeIntent(primary_feeling="test"),
            lyric_density="minimal",
            vocals=VocalControls(intensity="soft")  # Would normally be rich
        )
        
        result = builder.generate(request)
        
        assert result["debug_info"]["lyric_density"] == "minimal"


class TestRuleBreaking:
    """Tests for explicit rule breaking permissions"""
    
    def test_rule_breaking_appears_in_prompt(self):
        """Rule breaking instructions should appear in prompt"""
        builder = AdvancedPromptBuilder()
        
        request = AdvancedGenerateRequest(
            vibe_intent=VibeIntent(primary_feeling="experimental"),
            rule_breaking=RuleBreaking(
                break_melody=True,
                break_rhythm=True,
                permission_to_violate=["use silence as structure"]
            )
        )
        
        result = builder.generate(request)
        
        assert result["control_layers_used"]["rule_breaking"]
        assert "permission" in result["suno_prompt"].lower() or "unresolved" in result["suno_prompt"].lower()


class TestContentThemes:
    """Tests for content theme anchoring"""
    
    def test_theme_influences_lyrics(self):
        """Content theme should influence lyric content"""
        builder = AdvancedPromptBuilder()
        
        request = AdvancedGenerateRequest(
            vibe_intent=VibeIntent(primary_feeling="focused"),
            content_theme=ContentTheme(
                theme_type="work",
                specific_topic="building tools",
                repetition_style="chant"
            )
        )
        
        result = builder.generate(request)
        
        assert "build" in result["lyrics"].lower()
        assert result["control_layers_used"]["content_theme"]
    
    def test_different_themes_produce_different_content(self):
        """Different themes should produce meaningfully different lyrics"""
        builder = AdvancedPromptBuilder()
        
        work_request = AdvancedGenerateRequest(
            vibe_intent=VibeIntent(primary_feeling="focused"),
            content_theme=ContentTheme(theme_type="work", specific_topic="fixing bugs")
        )
        
        grief_request = AdvancedGenerateRequest(
            vibe_intent=VibeIntent(primary_feeling="heavy"),
            content_theme=ContentTheme(theme_type="grief", specific_topic="letting go")
        )
        
        work_result = builder.generate(work_request)
        grief_result = builder.generate(grief_request)
        
        # Lyrics should be different
        assert work_result["lyrics"] != grief_result["lyrics"]


class TestContrastIteration:
    """Tests for contrast-based iteration"""
    
    def test_contrast_iteration_recorded(self):
        """Contrast iteration should be recorded in result"""
        builder = AdvancedPromptBuilder()
        
        request = AdvancedGenerateRequest(
            vibe_intent=VibeIntent(primary_feeling="evolving"),
            contrast=ContrastIteration(
                reference_id="prev_gen_123",
                less_of=["country"],
                more_of=["drops"],
                push_direction="harder"
            )
        )
        
        result = builder.generate(request)
        
        assert result["control_layers_used"]["contrast_iteration"]


class TestTasteProfileIntegration:
    """Tests for taste profile integration"""
    
    def test_taste_profile_influences_generation(self):
        """Taste profile should influence the output"""
        taste = create_mock_taste_profile()
        builder = AdvancedPromptBuilder(taste)
        
        request = AdvancedGenerateRequest(
            vibe_intent=VibeIntent(primary_feeling="personal")
        )
        
        result = builder.generate(request)
        
        assert result["control_layers_used"]["taste_profile"]
        # Should include taste influence in prompt
        assert any(tag in result["suno_prompt"].lower() for tag in ["atmospheric", "intense", "raw"])
    
    def test_generation_without_taste_profile(self):
        """Should work without taste profile"""
        builder = AdvancedPromptBuilder(None)
        
        request = AdvancedGenerateRequest(
            vibe_intent=VibeIntent(primary_feeling="test")
        )
        
        result = builder.generate(request)
        
        assert not result["control_layers_used"]["taste_profile"]


class TestGenerationArtifacts:
    """Tests for separated artifacts"""
    
    def test_generates_separate_artifacts(self):
        """Should generate both lyrics and prompt as separate artifacts"""
        builder = AdvancedPromptBuilder()
        
        request = AdvancedGenerateRequest(
            vibe_intent=VibeIntent(primary_feeling="test"),
            separate_artifacts=True
        )
        
        result = builder.generate(request)
        
        assert result["lyrics"]
        assert result["suno_prompt"]
        assert result["lyrics"] != result["suno_prompt"]
    
    def test_prompt_under_700_chars(self):
        """Suno prompt should always be under 700 characters"""
        builder = AdvancedPromptBuilder()
        
        request = AdvancedGenerateRequest(
            vibe_intent=VibeIntent(
                primary_feeling="extremely complex feeling with many layers",
                sensory_goals=["goal1", "goal2", "goal3", "goal4"]
            ),
            vocals=VocalControls(
                intensity="screaming",
                experimental=["throat singing", "distortion", "glitches", "breath"]
            ),
            rhythm=RhythmControls(
                complexity="chaotic",
                accents=["random", "off-beat", "silence → slam"]
            ),
            texture=TextureControls(
                atmosphere=["industrial", "cathedral", "cosmic", "underground"]
            )
        )
        
        result = builder.generate(request)
        
        assert len(result["suno_prompt"]) <= 700
    
    def test_lyrics_contain_section_tags(self):
        """Lyrics should contain proper section tags"""
        builder = AdvancedPromptBuilder()
        
        request = AdvancedGenerateRequest(
            vibe_intent=VibeIntent(primary_feeling="test")
        )
        
        result = builder.generate(request)
        
        # Should have section markers
        assert "[" in result["lyrics"] and "]" in result["lyrics"]


class TestGenerationID:
    """Tests for generation ID and history"""
    
    def test_generation_id_created(self):
        """Each generation should have a unique ID"""
        builder = AdvancedPromptBuilder()
        
        request = AdvancedGenerateRequest(
            vibe_intent=VibeIntent(primary_feeling="test")
        )
        
        result = builder.generate(request)
        
        assert result["generation_id"]
        assert len(result["generation_id"]) > 0
    
    def test_generation_stored_in_history(self):
        """Generation should be stored in history for iteration"""
        builder = AdvancedPromptBuilder()
        
        request = AdvancedGenerateRequest(
            vibe_intent=VibeIntent(primary_feeling="test")
        )
        
        result = builder.generate(request)
        gen_id = result["generation_id"]
        
        assert gen_id in builder.generation_history


class TestVibeSignature:
    """Tests for vibe signature fingerprinting"""
    
    def test_vibe_signature_generated(self):
        """Each generation should have a vibe signature"""
        builder = AdvancedPromptBuilder()
        
        request = AdvancedGenerateRequest(
            vibe_intent=VibeIntent(primary_feeling="unique")
        )
        
        result = builder.generate(request)
        
        assert result["vibe_signature"]
        assert "primary_feeling" in result["vibe_signature"]
        assert result["vibe_signature"]["primary_feeling"] == "unique"
    
    def test_intensity_vector_calculated(self):
        """Vibe signature should include intensity vector"""
        builder = AdvancedPromptBuilder()
        
        request = AdvancedGenerateRequest(
            vibe_intent=VibeIntent(primary_feeling="test"),
            vocals=VocalControls(intensity="screaming"),
            rhythm=RhythmControls(complexity="chaotic")
        )
        
        result = builder.generate(request)
        
        assert "intensity_vector" in result["vibe_signature"]
        assert "vocal" in result["vibe_signature"]["intensity_vector"]
        assert "rhythmic" in result["vibe_signature"]["intensity_vector"]
        
        # Screaming and chaotic should have high intensity
        assert result["vibe_signature"]["intensity_vector"]["vocal"] > 70
        assert result["vibe_signature"]["intensity_vector"]["rhythmic"] > 70
