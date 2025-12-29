"""
Unit tests for V8 channel split logic.

These tests are deterministic (no network, no LLM calls).
They test:
1. Artist name normalization
2. Split decision from schema (role fields)
3. Split decision from regex fallback
4. Style context formatter output
"""

import pytest

from app.services.agent_prompt_graph import (
    _normalize_artist_name_v8,
    SplitDecision,
    AgentPromptGraph,
)
from app.constants import V8_ROLE_CONFIDENCE_THRESHOLD


class TestNormalizeArtistNameV8:
    """Tests for _normalize_artist_name_v8()"""

    def test_empty_string(self):
        assert _normalize_artist_name_v8("") == ""

    def test_whitespace_trimming(self):
        assert _normalize_artist_name_v8("  TOOL  ") == "tool"

    def test_lowercase(self):
        assert _normalize_artist_name_v8("RAGE AGAINST THE MACHINE") == "rage against the machine"

    def test_ampersand_replacement(self):
        assert _normalize_artist_name_v8("Richy Mitch & The Coal Miners") == "richy mitch and the coal miners"

    def test_whitespace_collapse(self):
        assert _normalize_artist_name_v8("The   National") == "the national"

    def test_punctuation_stripping(self):
        assert _normalize_artist_name_v8("P!nk") == "p!nk"  # Only strips surrounding punctuation
        assert _normalize_artist_name_v8("(TOOL)") == "tool"
        assert _normalize_artist_name_v8("'Queen'") == "queen"

    def test_combined_normalization(self):
        assert _normalize_artist_name_v8("  Richy Mitch & The   Coal Miners!  ") == "richy mitch and the coal miners"


class TestSplitDecisionFromRoles:
    """Tests for _decide_style_split_v8_from_roles()"""

    @pytest.fixture
    def graph(self):
        """Create a minimal AgentPromptGraph for testing."""
        from app.config import Settings
        settings = Settings()
        return AgentPromptGraph(settings)

    def test_no_genre_data(self, graph):
        decision = graph._decide_style_split_v8_from_roles(None)
        assert decision.split_active is False
        assert decision.source == "none"

    def test_empty_artists(self, graph):
        decision = graph._decide_style_split_v8_from_roles({"artists": []})
        assert decision.split_active is False

    def test_single_artist_no_split(self, graph):
        genre_data = {
            "artists": [
                {"name": "TOOL", "role": "music_target", "role_confidence": 0.9}
            ]
        }
        decision = graph._decide_style_split_v8_from_roles(genre_data)
        assert decision.split_active is False

    def test_two_artists_both_unspecified(self, graph):
        genre_data = {
            "artists": [
                {"name": "TOOL", "role": "unspecified", "role_confidence": 0.0},
                {"name": "Deftones", "role": "unspecified", "role_confidence": 0.0},
            ]
        }
        decision = graph._decide_style_split_v8_from_roles(genre_data)
        assert decision.split_active is False

    def test_valid_split(self, graph):
        genre_data = {
            "artists": [
                {"name": "Steel Panther", "role": "vocal_reference", "role_confidence": 0.9},
                {"name": "TOOL", "role": "music_target", "role_confidence": 0.9},
            ]
        }
        decision = graph._decide_style_split_v8_from_roles(genre_data)
        assert decision.split_active is True
        assert decision.vocal_reference_artist == "Steel Panther"
        assert decision.music_target_artist == "TOOL"
        assert decision.source == "role_schema"
        assert decision.role_confidence == 0.9

    def test_low_confidence_no_split(self, graph):
        genre_data = {
            "artists": [
                {"name": "Steel Panther", "role": "vocal_reference", "role_confidence": 0.5},
                {"name": "TOOL", "role": "music_target", "role_confidence": 0.5},
            ]
        }
        decision = graph._decide_style_split_v8_from_roles(genre_data)
        assert decision.split_active is False  # Below threshold

    def test_same_artist_normalized_no_split(self, graph):
        genre_data = {
            "artists": [
                {"name": "David Bowie", "role": "vocal_reference", "role_confidence": 0.9},
                {"name": "DAVID BOWIE", "role": "music_target", "role_confidence": 0.9},
            ]
        }
        decision = graph._decide_style_split_v8_from_roles(genre_data)
        assert decision.split_active is False  # Same artist after normalization

    def test_two_vocal_references_no_split(self, graph):
        genre_data = {
            "artists": [
                {"name": "Thom Yorke", "role": "vocal_reference", "role_confidence": 0.9},
                {"name": "Bjork", "role": "vocal_reference", "role_confidence": 0.9},
                {"name": "Portishead", "role": "music_target", "role_confidence": 0.9},
            ]
        }
        decision = graph._decide_style_split_v8_from_roles(genre_data)
        assert decision.split_active is False  # Not exactly one of each

    def test_confidence_uses_minimum(self, graph):
        genre_data = {
            "artists": [
                {"name": "Artist A", "role": "vocal_reference", "role_confidence": 0.95},
                {"name": "Artist B", "role": "music_target", "role_confidence": 0.75},
            ]
        }
        decision = graph._decide_style_split_v8_from_roles(genre_data)
        assert decision.split_active is True
        assert decision.role_confidence == 0.75  # Uses minimum


class TestSplitDecisionFromRegex:
    """Tests for _decide_style_split_v8_from_regex()"""

    @pytest.fixture
    def graph(self):
        from app.config import Settings
        settings = Settings()
        return AgentPromptGraph(settings)

    def test_empty_string(self, graph):
        decision = graph._decide_style_split_v8_from_regex("")
        assert decision.split_active is False

    def test_lead_singer_of_singing_for(self, graph):
        decision = graph._decide_style_split_v8_from_regex(
            "lead singer of Steel Panther singing for TOOL"
        )
        assert decision.split_active is True
        assert decision.vocal_reference_artist == "Steel Panther"
        assert decision.music_target_artist == "TOOL"
        assert decision.source == "regex"

    def test_singer_of_for(self, graph):
        decision = graph._decide_style_split_v8_from_regex(
            "singer of Flipturn for Richy Mitch"
        )
        assert decision.split_active is True
        assert decision.vocal_reference_artist == "Flipturn"
        assert decision.music_target_artist == "Richy Mitch"

    def test_vocals_with_instrumentation(self, graph):
        decision = graph._decide_style_split_v8_from_regex(
            "Phoebe Bridgers vocals with Radiohead instrumentation"
        )
        assert decision.split_active is True
        assert decision.vocal_reference_artist == "Phoebe Bridgers"
        assert decision.music_target_artist == "Radiohead"

    def test_ambiguous_meets_no_split(self, graph):
        decision = graph._decide_style_split_v8_from_regex("TOOL meets Deftones")
        assert decision.split_active is False

    def test_ambiguous_blend_no_split(self, graph):
        decision = graph._decide_style_split_v8_from_regex("A blend of TOOL and Deftones")
        assert decision.split_active is False


class TestFormatStyleContextV8:
    """Tests for _format_style_context_v8()"""

    @pytest.fixture
    def graph(self):
        from app.config import Settings
        settings = Settings()
        return AgentPromptGraph(settings)

    def test_no_split_returns_basic_context(self, graph):
        context_pack = {
            "user_style_request": "Just some style",
            "selected_artists": ["TOOL"],
            "tags": ["metal"],
        }
        split = SplitDecision(split_active=False, source="none")
        result = graph._format_style_context_v8(context_pack, split, None)

        assert "MUSIC_TARGET" not in result
        assert "VOCAL_REFERENCE" not in result
        assert "Just some style" in result

    def test_split_active_includes_blocks(self, graph):
        context_pack = {
            "user_style_request": "Singer of X for Y",
            "selected_artists": ["X", "Y"],
            "tags": [],
        }
        split = SplitDecision(
            split_active=True,
            music_target_artist="Y",
            vocal_reference_artist="X",
            source="role_schema",
            role_confidence=0.9,
        )
        result = graph._format_style_context_v8(context_pack, split, None)

        assert "MUSIC_TARGET" in result
        assert "VOCAL_REFERENCE" in result
        assert "ARTIST: Y" in result
        assert "ARTIST: X" in result

    def test_split_includes_hard_rules(self, graph):
        context_pack = {
            "user_style_request": "test",
            "selected_artists": [],
            "tags": [],
        }
        split = SplitDecision(
            split_active=True,
            music_target_artist="Pink Floyd",
            vocal_reference_artist="RATM",
            source="role_schema",
            role_confidence=0.9,
        )
        result = graph._format_style_context_v8(context_pack, split, None)

        assert "HARD RULE" in result
        assert "Do NOT borrow genre/instruments/production from VOCAL_REFERENCE" in result
        assert "All non-vocal musical content MUST be derived from MUSIC_TARGET only" in result

    def test_split_with_genre_data_routes_correctly(self, graph):
        context_pack = {
            "user_style_request": "test",
            "selected_artists": [],
            "tags": [],
        }
        split = SplitDecision(
            split_active=True,
            music_target_artist="Pink Floyd",
            vocal_reference_artist="RATM",
            source="role_schema",
            role_confidence=0.9,
        )
        genre_data = {
            "artists": [
                {
                    "name": "Pink Floyd",
                    "role": "music_target",
                    "genres": ["progressive rock", "psychedelic rock"],
                    "terms_to_use": ["atmospheric", "spacey"],
                    "instruments_to_use": ["Fender Rhodes", "Hammond organ"],
                    "vocal_style_to_use": [],  # Should be empty for music_target
                },
                {
                    "name": "RATM",
                    "role": "vocal_reference",
                    "genres": ["funk metal", "rap rock"],  # Should NOT appear
                    "terms_to_use": [],  # Should be empty for vocal_reference
                    "instruments_to_use": [],  # Should be empty for vocal_reference
                    "vocal_style_to_use": ["aggressive rapping", "shouted delivery"],
                },
            ],
            "global_notes": ["Test global note"],
        }
        result = graph._format_style_context_v8(context_pack, split, genre_data)

        # MUSIC_TARGET block should have genre/instrument info
        assert "GENRE_TARGETS: progressive rock, psychedelic rock" in result
        assert "Fender Rhodes" in result

        # VOCAL_REFERENCE block should have vocal info
        assert "aggressive rapping" in result or "shouted delivery" in result

        # Global notes should appear
        assert "Test global note" in result

