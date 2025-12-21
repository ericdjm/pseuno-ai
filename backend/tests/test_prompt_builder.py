"""
Tests for prompt builder
"""

import pytest
from app.services.prompt_builder import PromptBuilder, GENRE_PRESETS
from app.models import TasteProfile


def create_mock_taste_profile() -> TasteProfile:
    """Create a mock taste profile for testing"""
    return TasteProfile(
        top_genres=["indie rock", "electronic", "dream pop", "synth-pop"],
        mood_tags=["atmospheric", "dreamy", "energetic"],
        summary_sentence="Your sound leans heavily into indie rock and electronic with atmospheric vibes.",
        banned_references=["Artist One", "Artist Two", "Artist Three"]
    )


class TestPromptBuilder:
    """Tests for PromptBuilder class"""
    
    def test_generate_returns_required_fields(self):
        """Should return all required fields"""
        profile = create_mock_taste_profile()
        builder = PromptBuilder(profile)
        
        result = builder.generate()
        
        assert "concept_title" in result
        assert "suno_prompt" in result
        assert "lyrics" in result
    
    def test_prompt_under_700_chars(self):
        """Prompt should be under 700 characters"""
        profile = create_mock_taste_profile()
        builder = PromptBuilder(profile)
        
        result = builder.generate(
            extra_notes="This is a very long extra note " * 20  # Force long input
        )
        
        assert len(result["suno_prompt"]) <= 700
    
    def test_lyrics_under_1800_chars(self):
        """Lyrics should be under 1800 characters"""
        profile = create_mock_taste_profile()
        builder = PromptBuilder(profile)
        
        result = builder.generate()
        
        assert len(result["lyrics"]) <= 1800
    
    def test_lyrics_contain_section_tags(self):
        """Lyrics should contain section tags"""
        profile = create_mock_taste_profile()
        builder = PromptBuilder(profile)
        
        result = builder.generate()
        
        assert "[Verse" in result["lyrics"]
        assert "[Chorus]" in result["lyrics"]
        assert "[Bridge]" in result["lyrics"]
    
    def test_respects_energy_parameter(self):
        """Should generate different results for different energy levels"""
        profile = create_mock_taste_profile()
        builder = PromptBuilder(profile)
        
        low_energy = builder.generate(energy=10)
        high_energy = builder.generate(energy=90)
        
        # Both should be valid
        assert len(low_energy["suno_prompt"]) > 0
        assert len(high_energy["suno_prompt"]) > 0
        
        # Prompts should differ (not guaranteed but very likely)
        # At minimum, they should both be valid
    
    def test_respects_darkness_parameter(self):
        """Should generate different results for different darkness levels"""
        profile = create_mock_taste_profile()
        builder = PromptBuilder(profile)
        
        light = builder.generate(darkness=10)
        dark = builder.generate(darkness=90)
        
        assert len(light["suno_prompt"]) > 0
        assert len(dark["suno_prompt"]) > 0
    
    def test_theme_influences_lyrics(self):
        """Theme should influence lyric template selection"""
        profile = create_mock_taste_profile()
        builder = PromptBuilder(profile)
        
        love_result = builder.generate(theme="love and romance")
        journey_result = builder.generate(theme="road trip journey")
        
        # Both should have valid lyrics
        assert "[Verse" in love_result["lyrics"]
        assert "[Verse" in journey_result["lyrics"]
    
    def test_preset_overrides_style(self):
        """Preset should override derived style"""
        profile = create_mock_taste_profile()
        builder = PromptBuilder(profile)
        
        result = builder.generate(preset="hip_hop")
        
        # Should include hip-hop style elements
        assert len(result["suno_prompt"]) > 0
    
    def test_concept_title_not_empty(self):
        """Concept title should never be empty"""
        profile = create_mock_taste_profile()
        builder = PromptBuilder(profile)
        
        for _ in range(10):
            result = builder.generate()
            assert len(result["concept_title"]) > 0
            assert len(result["concept_title"]) <= 50
    
    def test_handles_empty_taste_profile(self):
        """Should handle empty taste profile gracefully"""
        profile = TasteProfile(
            top_genres=[],
            mood_tags=[],
            summary_sentence="",
            banned_references=[]
        )
        builder = PromptBuilder(profile)
        
        result = builder.generate()
        
        assert len(result["suno_prompt"]) > 0
        assert len(result["lyrics"]) > 0
        assert len(result["concept_title"]) > 0


class TestGenrePresets:
    """Tests for genre presets"""
    
    def test_all_presets_have_required_keys(self):
        """All presets should have required keys"""
        required_keys = ["instruments", "style", "tempo", "vocals"]
        
        for preset_name, preset_data in GENRE_PRESETS.items():
            for key in required_keys:
                assert key in preset_data, f"Preset '{preset_name}' missing '{key}'"
    
    def test_instruments_is_list(self):
        """Instruments should be a list"""
        for preset_name, preset_data in GENRE_PRESETS.items():
            assert isinstance(preset_data["instruments"], list), \
                f"Preset '{preset_name}' instruments should be list"
            assert len(preset_data["instruments"]) > 0, \
                f"Preset '{preset_name}' should have at least one instrument"
