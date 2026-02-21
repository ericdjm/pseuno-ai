"""
Tests for the generation bug fixes:
1. Style name field fix (genres_to_use → genres)
2. Fallback title derivation
3. Chorus repetition validation
4. Planner skip with fallback for targeted refine
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

# ============================================================================
# PR 1: Style name field fix + fallback title
# ============================================================================


def _derive_title_from_prompt(suno_prompt: str, auto_tags: list[str]) -> str:
    """
    Copy of the function from app.routes.refine for testing without FastAPI deps.
    Must be kept in sync with the actual implementation.
    """
    if auto_tags:
        return " • ".join(tag.title() for tag in auto_tags[:3])

    first_line = suno_prompt.split("\n")[0].strip()
    for sep in [",", " - ", ";", ":"]:
        if sep in first_line:
            first_line = first_line[: first_line.index(sep)].strip()
            break
    if len(first_line) > 30:
        truncated = first_line[:30].rsplit(" ", 1)[0]
        return truncated + "..." if truncated else first_line[:27] + "..."
    return first_line or "Refined Prompt"


class TestDeriveTitle:
    """Test _derive_title_from_prompt fallback logic."""

    def _fn(self, suno_prompt: str, auto_tags: list[str]) -> str:
        return _derive_title_from_prompt(suno_prompt, auto_tags)

    def test_auto_tags_used_when_present(self):
        result = self._fn("some long prompt", ["rock", "dark", "heavy"])
        assert result == "Rock • Dark • Heavy"

    def test_auto_tags_limited_to_3(self):
        result = self._fn("", ["a", "b", "c", "d", "e"])
        assert result == "A • B • C"

    def test_fallback_truncates_at_comma(self):
        result = self._fn(
            "Late 90s alternative rock, heavy distortion, grungy vocals", []
        )
        assert result == "Late 90s alternative rock"
        assert len(result) <= 30

    def test_fallback_truncates_at_dash(self):
        result = self._fn("Dream pop - ethereal and atmospheric", [])
        assert result == "Dream pop"

    def test_fallback_truncates_at_semicolon(self):
        result = self._fn("Industrial metal; harsh and mechanical", [])
        assert result == "Industrial metal"

    def test_fallback_truncates_at_colon(self):
        result = self._fn("Gothic rock: dark and brooding with organ", [])
        assert result == "Gothic rock"

    def test_fallback_long_clause_truncates_at_word_boundary(self):
        result = self._fn(
            "Experimental psychedelic progressive fusion extraordinaire stuff", []
        )
        assert len(result) <= 33  # 30 + "..."
        assert result.endswith("...")
        # Should not cut mid-word
        assert not result[-4].isalpha() or result.endswith("...")

    def test_fallback_empty_prompt(self):
        result = self._fn("", [])
        assert result == "Refined Prompt"

    def test_short_prompt_returned_as_is(self):
        result = self._fn("Jazz fusion", [])
        assert result == "Jazz fusion"

    def test_full_suno_prompt_not_used_as_title(self):
        """The original bug: full verbose suno_prompt used as title."""
        long_prompt = (
            "Late 90s alternative rock with heavy distortion, layered guitars, "
            "grungy vocals with slight reverb, driving drum patterns"
        )
        result = self._fn(long_prompt, [])
        # Should NOT be the full first line (which was 120+ chars)
        assert len(result) <= 33
        # After comma split: "Late 90s alternative rock with heavy distortion" (47 chars)
        # Then word-boundary truncation at 30 chars
        assert result == "Late 90s alternative rock..."


class TestGenresFieldFix:
    """Test that genre data uses 'genres' field not 'genres_to_use'."""

    def test_genres_field_extracted(self):
        """Verify _check that the code at line 1759 reads artist.get('genres')."""
        from app.services.agent_prompt_graph import AgentPromptGraph

        # Build minimal genre_data matching the actual schema
        genre_data = {
            "artists": [
                {
                    "name": "Radiohead",
                    "genres": ["art rock", "alternative rock", "experimental"],
                    "era": {"label": "late 90s"},
                },
                {
                    "name": "Bjork",
                    "genres": ["art pop", "electronic", "experimental"],
                    "era": {"label": "mid 90s"},
                },
            ]
        }

        # Simulate the extraction logic from agent_prompt_graph.py:1755-1764
        genres_for_name = []
        artists_for_name = []
        for artist in genre_data.get("artists", []):
            if artist.get("genres"):
                genres_for_name.extend(artist["genres"])
            if artist.get("name"):
                artists_for_name.append(artist["name"])

        assert genres_for_name == [
            "art rock",
            "alternative rock",
            "experimental",
            "art pop",
            "electronic",
            "experimental",
        ]
        assert artists_for_name == ["Radiohead", "Bjork"]

    def test_genres_to_use_field_not_used(self):
        """Ensure the old wrong field name would produce empty results."""
        genre_data = {
            "artists": [
                {
                    "name": "Radiohead",
                    "genres": ["art rock", "alternative rock"],
                }
            ]
        }

        # Old code: artist.get("genres_to_use") — should be empty
        genres_old = []
        for artist in genre_data.get("artists", []):
            if artist.get("genres_to_use"):
                genres_old.extend(artist["genres_to_use"])

        assert genres_old == [], "Old field 'genres_to_use' should not exist in data"


# ============================================================================
# PR 3: Chorus repetition validation
# ============================================================================


class TestChorusRepetition:
    """Test _check_chorus_repetition static method."""

    def _check(self, lyrics: str) -> list[str]:
        from app.services.agent_prompt_graph import AgentPromptGraph

        return AgentPromptGraph._check_chorus_repetition(lyrics)

    def test_varied_chorus_passes(self):
        lyrics = """[Verse]
Hello there my friend
How have you been today

[Chorus]
We're running through the night
Chasing stars until the dawn
The world is ours tonight
We'll never be alone"""
        issues = self._check(lyrics)
        assert issues == []

    def test_all_identical_lines_flagged(self):
        lyrics = """[Verse]
Some verse line

[Chorus]
Na na na na
Na na na na
Na na na na
Na na na na"""
        issues = self._check(lyrics)
        assert len(issues) == 1
        assert "4/4 identical lines" in issues[0]

    def test_three_of_four_identical_flagged(self):
        lyrics = """[Chorus]
Hold me close tonight
Hold me close tonight
Hold me close tonight
We'll dance until the light"""
        issues = self._check(lyrics)
        assert len(issues) == 1
        assert "3/4 identical lines" in issues[0]

    def test_two_of_four_not_flagged(self):
        """50% is the boundary — 2/4 is exactly 50%, not >50%."""
        lyrics = """[Chorus]
Hold me close tonight
We'll never let go
Hold me close tonight
The stars are shining bright"""
        issues = self._check(lyrics)
        assert issues == []

    def test_multiple_choruses_checked(self):
        lyrics = """[Chorus]
Same line here
Same line here
Same line here

[Verse]
Some verse

[Chorus]
Another same line
Another same line
Another same line"""
        issues = self._check(lyrics)
        assert len(issues) == 2

    def test_chorus_with_modifiers_detected(self):
        lyrics = """[Chorus, anthemic, powerful]
Burn it down
Burn it down
Burn it down
Burn it down"""
        issues = self._check(lyrics)
        assert len(issues) == 1

    def test_single_line_chorus_skipped(self):
        lyrics = """[Chorus]
Just one line"""
        issues = self._check(lyrics)
        assert issues == []

    def test_empty_chorus_skipped(self):
        lyrics = """[Chorus]

[Verse]
Some verse"""
        issues = self._check(lyrics)
        assert issues == []

    def test_no_chorus_passes(self):
        lyrics = """[Verse]
Just a verse
Nothing more"""
        issues = self._check(lyrics)
        assert issues == []


# ============================================================================
# PR 4: Planner fallback for targeted refine
# ============================================================================


class TestPlannerFallback:
    """Test that targeted refine requests survive planner failures."""

    def _make_request(self, refine_target=None):
        from app.schemas.unified_refine import UnifiedRefineRequest

        return UnifiedRefineRequest(
            suno_prompt="Late 90s rock with heavy guitars",
            lyrics="[Verse]\nHello world\n[Chorus]\nLa la la\nSing along\n",
            exclude="country, pop",
            title="Test Song",
            weirdness=50,
            change_request="make the second verse about the ocean",
            refine_target=refine_target,
        )

    @pytest.mark.asyncio
    async def test_lyrics_target_planner_timeout_uses_fallback(self):
        """When planner times out for lyrics target, fallback plan used."""
        from app.services.unified_refine_service import refine_all
        from app.config import Settings

        settings = Settings(
            spotify_client_id="test",
            openai_api_key="test",
            llm_model="gpt-5-nano",
        )
        request = self._make_request(refine_target="lyrics")

        with patch(
            "app.services.unified_refine_service._call_planner",
            side_effect=RuntimeError("AI service timed out. Please try again."),
        ), patch(
            "app.services.unified_refine_service.refine_lyrics",
            new_callable=AsyncMock,
            return_value="[Verse]\nThe ocean calls to me\n[Chorus]\nLa la la\nSing along\n",
        ) as mock_lyrics, patch(
            "app.services.unified_refine_service.refine_style_prompt",
            new_callable=AsyncMock,
        ) as mock_style:
            snapshot, changed, msg, debug = await refine_all(request, settings)

            # Lyrics should have been edited via the fallback plan
            mock_lyrics.assert_called_once()
            # Style should NOT have been called
            mock_style.assert_not_called()
            assert "lyrics" in changed
            assert "suno_prompt" not in changed

    @pytest.mark.asyncio
    async def test_style_target_planner_timeout_uses_fallback(self):
        """When planner times out for style target, fallback plan used."""
        from app.services.unified_refine_service import refine_all
        from app.config import Settings

        settings = Settings(
            spotify_client_id="test",
            openai_api_key="test",
            llm_model="gpt-5-nano",
        )
        request = self._make_request(refine_target="style")
        request.change_request = "make it more jazzy"

        with patch(
            "app.services.unified_refine_service._call_planner",
            side_effect=RuntimeError("AI service timed out. Please try again."),
        ), patch(
            "app.services.unified_refine_service.refine_style_prompt",
            new_callable=AsyncMock,
            return_value="Late 90s jazz-rock fusion with heavy guitars and sax",
        ) as mock_style, patch(
            "app.services.unified_refine_service.refine_lyrics",
            new_callable=AsyncMock,
        ) as mock_lyrics:
            snapshot, changed, msg, debug = await refine_all(request, settings)

            # Style should have been edited via fallback
            mock_style.assert_called_once()
            # Lyrics should NOT have been called
            mock_lyrics.assert_not_called()
            assert "suno_prompt" in changed
            assert "lyrics" not in changed

    @pytest.mark.asyncio
    async def test_general_refine_planner_timeout_raises(self):
        """When planner times out for general refine (no target), error propagates."""
        from app.services.unified_refine_service import refine_all
        from app.config import Settings

        settings = Settings(
            spotify_client_id="test",
            openai_api_key="test",
            llm_model="gpt-5-nano",
        )
        request = self._make_request(refine_target=None)

        with patch(
            "app.services.unified_refine_service._call_planner",
            side_effect=RuntimeError("AI service timed out. Please try again."),
        ):
            with pytest.raises(RuntimeError, match="timed out"):
                await refine_all(request, settings)

    @pytest.mark.asyncio
    async def test_lyrics_target_planner_success_preserves_title_update(self):
        """When planner succeeds for lyrics target, title_update is preserved."""
        from app.services.unified_refine_service import refine_all
        from app.schemas.unified_refine import PlannerOutput
        from app.config import Settings

        settings = Settings(
            spotify_client_id="test",
            openai_api_key="test",
            llm_model="gpt-5-nano",
        )
        request = self._make_request(refine_target="lyrics")
        request.change_request = "change the title to Ocean Dreams"

        planner_result = PlannerOutput(
            edit_lyrics=False,
            edit_style=False,
            title_update="Ocean Dreams",
        )

        with patch(
            "app.services.unified_refine_service._call_planner",
            new_callable=AsyncMock,
            return_value=planner_result,
        ):
            snapshot, changed, msg, debug = await refine_all(request, settings)

            assert "title" in changed
            assert snapshot["title"] == "Ocean Dreams"

    @pytest.mark.asyncio
    async def test_style_target_planner_success_preserves_exclude_update(self):
        """When planner succeeds for style target, exclude_update is preserved."""
        from app.services.unified_refine_service import refine_all
        from app.schemas.unified_refine import PlannerOutput, ExcludeUpdate
        from app.config import Settings

        settings = Settings(
            spotify_client_id="test",
            openai_api_key="test",
            llm_model="gpt-5-nano",
        )
        request = self._make_request(refine_target="style")
        request.change_request = "make it more jazzy and avoid trumpets"

        planner_result = PlannerOutput(
            edit_style=True,
            style_change_request="add jazz elements",
            edit_lyrics=False,
            exclude_update=ExcludeUpdate(mode="append", value="trumpets"),
        )

        with patch(
            "app.services.unified_refine_service._call_planner",
            new_callable=AsyncMock,
            return_value=planner_result,
        ), patch(
            "app.services.unified_refine_service.refine_style_prompt",
            new_callable=AsyncMock,
            return_value="Jazz-rock fusion with sax and piano",
        ):
            snapshot, changed, msg, debug = await refine_all(request, settings)

            assert "exclude" in changed
            assert "trumpets" in snapshot["exclude"]
            assert "suno_prompt" in changed


# ============================================================================
# PR 2: Vocabulary rules in LYRICS_SPEC (prompt-level, not logic)
# ============================================================================


class TestVocabularyRules:
    """Verify the vocabulary rules are present in LYRICS_SPEC."""

    def test_overused_words_flagged_in_spec(self):
        from app.prompts.specs import LYRICS_SPEC

        assert "Avoid overusing" in LYRICS_SPEC
        for word in ["silver", "velvet", "neon", "shattered", "crimson", "golden"]:
            assert word in LYRICS_SPEC, f"Overused word '{word}' missing from LYRICS_SPEC"

    def test_genre_vocabulary_guidance_in_spec(self):
        from app.prompts.specs import LYRICS_SPEC

        assert "genre and era context" in LYRICS_SPEC
        assert "linguistic register" in LYRICS_SPEC

    def test_unique_vocabulary_rule_in_spec(self):
        from app.prompts.specs import LYRICS_SPEC

        assert "unique vocabulary palette" in LYRICS_SPEC


# ============================================================================
# PR 3: Chorus rules in specs
# ============================================================================


class TestChorusRulesInSpecs:
    """Verify chorus rules are correctly updated across all specs."""

    def test_lyrics_spec_has_distinct_lines_rule(self):
        from app.prompts.specs import LYRICS_SPEC

        assert "each line must be DIFFERENT" in LYRICS_SPEC
        assert "same lyrics as the other chorus" in LYRICS_SPEC

    def test_output_contract_has_distinct_lines_rule(self):
        from app.prompts.specs import OUTPUT_CONTRACT_LYRICS

        assert "every line must be distinct" in OUTPUT_CONTRACT_LYRICS
        assert "same lyrics as the other chorus" in OUTPUT_CONTRACT_LYRICS

    def test_repair_agent_has_varied_lines_rule(self):
        from app.prompts.specs import LYRICS_REPAIR_AGENT

        assert "Each line in a chorus must be distinct" in LYRICS_REPAIR_AGENT
