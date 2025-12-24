"""
Tests for AgentPromptGraph — basic use cases + repair/validation behavior.
"""

import asyncio

from app.config import Settings
from app.schemas.advanced import AdvancedGenerateRequest
from app.services.agent_prompt_graph import AgentPromptGraph


class _FakeResponse:
    def __init__(self, content: str):
        self.content = content


class FakeLLM:
    """
    Minimal LLM stub for testing.
    It returns a sequence of contents across successive `ainvoke` calls.
    """

    def __init__(self, contents: list[str]):
        self._contents = list(contents)
        self.calls = 0
        self.temperature = 0.7

    async def ainvoke(self, _messages, temperature=None):
        self.calls += 1
        if not self._contents:
            return _FakeResponse("")
        return _FakeResponse(self._contents.pop(0))


def _settings() -> Settings:
    # Spotify is optional; provide a stub value for clarity.
    return Settings(spotify_client_id="test_spotify_client_id", openai_api_key="test")


def _valid_output(
    lyrics: str = "[Verse]\nhello world\n",
    suno_prompt: str = "Funky pop, crisp drums, bright bass",
    exclude: str = "cheesy, country",
    weirdness: int = 50,
    style_influence: int = 60,
) -> str:
    return (
        f"LYRICS\n{lyrics}\n\n"
        f"SUNO PROMPT\n{suno_prompt}\n\n"
        f"EXCLUDE\n{exclude}\n\n"
        f"WEIRDNESS\n{weirdness}\n\n"
        f"STYLE INFLUENCE\n{style_influence}\n"
    )


# ---------------------------------------------------------------------------
# Basic use cases (happy path)
# ---------------------------------------------------------------------------


def test_valid_output_no_repairs_needed():
    """When the LLM returns valid output on first try, no repairs are triggered."""
    output = _valid_output()
    llm = FakeLLM([output])
    builder = AgentPromptGraph(_settings(), llm=llm)
    req = AdvancedGenerateRequest(
        user_prompt="Make a funky pop song",
        lyrics_about="dancing in the rain",
        selected_artists=[],
        tags=["pop", "funk"],
    )

    result = asyncio.run(builder.generate(req))

    assert llm.calls == 1  # no repair calls
    assert result["debug_info"]["repaired"] is False
    assert result["lyrics"] == "[Verse]\nhello world"
    assert result["suno_prompt"] == "Funky pop, crisp drums, bright bass"
    assert result["exclude"] == "cheesy, country"
    assert result["weirdness"] == 50
    assert result["style_influence"] == 60


def test_extracts_all_response_fields():
    """All expected fields are present in the response."""
    output = _valid_output()
    llm = FakeLLM([output])
    builder = AgentPromptGraph(_settings(), llm=llm)
    req = AdvancedGenerateRequest(
        user_prompt="Cinematic orchestral piece",
        lyrics_about="stars colliding",
    )

    result = asyncio.run(builder.generate(req))

    assert "concept_title" in result
    assert "lyrics" in result
    assert "suno_prompt" in result
    assert "exclude" in result
    assert "weirdness" in result
    assert "style_influence" in result
    assert "generation_id" in result
    assert "debug_info" in result
    assert "agent_model" in result["debug_info"]
    assert "context_hash" in result["debug_info"]
    assert "repaired" in result["debug_info"]


def test_concept_title_derived_from_lyrics_about():
    """Concept title is derived from lyrics_about when provided."""
    output = _valid_output()
    llm = FakeLLM([output])
    builder = AgentPromptGraph(_settings(), llm=llm)
    req = AdvancedGenerateRequest(
        user_prompt="Make something epic",
        lyrics_about="ants marching on Mars",
    )

    result = asyncio.run(builder.generate(req))

    # Title should be derived from first few words of lyrics_about
    assert result["concept_title"] == "Ants Marching On Mars"


def test_concept_title_falls_back_to_user_prompt():
    """When lyrics_about is empty, concept title is derived from user_prompt."""
    output = _valid_output()
    llm = FakeLLM([output])
    builder = AgentPromptGraph(_settings(), llm=llm)
    req = AdvancedGenerateRequest(
        user_prompt="heavy metal breakdown",
        lyrics_about="",
    )

    result = asyncio.run(builder.generate(req))

    assert result["concept_title"] == "Heavy Metal Breakdown"


def test_generation_id_is_unique():
    """Each generation produces a unique generation_id."""
    output = _valid_output()
    llm = FakeLLM([output, output])
    builder = AgentPromptGraph(_settings(), llm=llm)
    req = AdvancedGenerateRequest(
        user_prompt="synth wave",
        lyrics_about="neon nights",
    )

    result1 = asyncio.run(builder.generate(req))
    result2 = asyncio.run(builder.generate(req))

    assert result1["generation_id"] != result2["generation_id"]


def test_suno_prompt_over_500_triggers_repair_and_then_error():
    """SUNO PROMPT >500 chars is invalid; after repairs are exhausted we return an error (no fallback)."""
    long_prompt = "A" * 600
    output = _valid_output(suno_prompt=long_prompt)
    llm = FakeLLM([output, output, output])
    builder = AgentPromptGraph(_settings(), llm=llm)
    req = AdvancedGenerateRequest(
        user_prompt="test prompt",
        lyrics_about="test topic",
    )

    result = asyncio.run(builder.generate(req))

    assert llm.calls == 3  # initial + 2 repairs (default)
    assert result["success"] is False
    assert "issues" in result and result["issues"]
    assert any(
        "SUNO PROMPT exceeds 500 characters" in issue for issue in result["issues"]
    )


def test_weirdness_out_of_range_triggers_repair_and_then_error():
    """Weirdness values outside 0-100 are invalid; after repairs we return an error (no fallback)."""
    # Value > 100 is invalid per validator
    output_high = _valid_output(weirdness=150)
    llm = FakeLLM([output_high, output_high, output_high])
    builder = AgentPromptGraph(_settings(), llm=llm)
    req = AdvancedGenerateRequest(user_prompt="test", lyrics_about="test")

    result = asyncio.run(builder.generate(req))

    assert llm.calls == 3
    assert result["success"] is False
    assert any(
        "WEIRDNESS must be between 0 and 100" in issue for issue in result["issues"]
    )


def test_style_influence_out_of_range_triggers_repair_and_then_error():
    """Style influence values outside 0-100 are invalid; after repairs we return an error (no fallback)."""
    output = _valid_output(style_influence=200)
    llm = FakeLLM([output, output, output])
    builder = AgentPromptGraph(_settings(), llm=llm)
    req = AdvancedGenerateRequest(user_prompt="test", lyrics_about="test")

    result = asyncio.run(builder.generate(req))

    assert llm.calls == 3
    assert result["success"] is False
    assert any(
        "STYLE INFLUENCE must be between 0 and 100" in issue
        for issue in result["issues"]
    )


def test_tags_are_passed_through():
    """Tags from request are included in context and don't break generation."""
    output = _valid_output()
    llm = FakeLLM([output])
    builder = AgentPromptGraph(_settings(), llm=llm)
    req = AdvancedGenerateRequest(
        user_prompt="indie rock anthem",
        lyrics_about="summer nights",
        tags=["indie", "rock", "anthemic"],
    )

    result = asyncio.run(builder.generate(req))

    assert result["debug_info"]["repaired"] is False
    assert result["suno_prompt"]  # output is valid


def test_selected_artists_not_leaked_when_valid():
    """Selected artists are used for context but don't appear in valid output."""
    # LLM returns valid output that doesn't mention artist
    output = _valid_output(suno_prompt="Retro funk, smooth bass, falsetto vocals")
    llm = FakeLLM([output])
    builder = AgentPromptGraph(_settings(), llm=llm)
    req = AdvancedGenerateRequest(
        user_prompt="Make it sound like Prince",
        lyrics_about="purple rain",
        selected_artists=["Prince"],
    )

    result = asyncio.run(builder.generate(req))

    assert "prince" not in result["suno_prompt"].lower()
    assert result["debug_info"]["repaired"] is False


def test_repairs_when_missing_sections():
    # First output is missing sections and order (invalid), second output is valid.
    bad = "LYRICS\n" "[Verse]\nhello\n" "\n" "SUNO PROMPT\n" "some prompt\n"
    good = (
        "LYRICS\n"
        "[Verse]\nhello\n\n"
        "SUNO PROMPT\n"
        "some prompt\n\n"
        "EXCLUDE\n"
        "cheesy, country\n\n"
        "WEIRDNESS\n"
        "42\n\n"
        "STYLE INFLUENCE\n"
        "55\n"
    )

    llm = FakeLLM([bad, good])
    builder = AgentPromptGraph(_settings(), llm=llm)
    req = AdvancedGenerateRequest(
        user_prompt="Make something big and cinematic",
        lyrics_about="ants on Mars",
        selected_artists=[],
        tags=["cinematic"],
    )

    result = asyncio.run(builder.generate(req))
    assert llm.calls == 2  # one repair pass
    assert result["debug_info"]["repaired"] is True
    assert result["suno_prompt"] == "some prompt"
    assert result["exclude"] == "cheesy, country"
    assert result["weirdness"] == 42
    assert result["style_influence"] == 55


def test_repairs_when_artist_name_leaks_in_suno_prompt_only():
    # First output leaks an artist name in SUNO PROMPT; second output fixes it.
    bad = (
        "LYRICS\n"
        "[Verse]\nhello\n\n"
        "SUNO PROMPT\n"
        "In the style of Bruno Mars, funky pop groove\n\n"
        "EXCLUDE\n"
        "cheesy\n\n"
        "WEIRDNESS\n"
        "50\n\n"
        "STYLE INFLUENCE\n"
        "60\n"
    )
    good = (
        "LYRICS\n"
        "[Verse]\nhello\n\n"
        "SUNO PROMPT\n"
        "Funky pop groove, bright bass, crisp drums, glossy modern mix\n\n"
        "EXCLUDE\n"
        "cheesy\n\n"
        "WEIRDNESS\n"
        "50\n\n"
        "STYLE INFLUENCE\n"
        "60\n"
    )

    llm = FakeLLM([bad, good])
    builder = AgentPromptGraph(_settings(), llm=llm)
    req = AdvancedGenerateRequest(
        user_prompt="Make a song that sounds like Bruno Mars",
        lyrics_about="dancing alone",
        selected_artists=["Bruno Mars"],
        tags=["pop"],
    )

    result = asyncio.run(builder.generate(req))
    assert llm.calls == 2
    assert result["debug_info"]["repaired"] is True
    assert "bruno" not in result["suno_prompt"].lower()


def test_falls_back_after_two_failed_repairs():
    # Provide three invalid outputs (initial + 2 repairs). Builder should return an error (no fallback).
    invalid = "SUNO PROMPT\nblah\n"
    llm = FakeLLM([invalid, invalid, invalid])
    builder = AgentPromptGraph(_settings(), llm=llm)
    req = AdvancedGenerateRequest(
        user_prompt="Make a song that sounds like Will.I.Am",
        lyrics_about="robots",
        selected_artists=["Will.I.Am"],
        tags=["electropop"],
    )

    result = asyncio.run(builder.generate(req))
    assert llm.calls == 3  # initial + 2 repairs
    assert result["success"] is False
    assert "issues" in result and result["issues"]


# ---------------------------------------------------------------------------
# Config-driven repair behavior tests
# ---------------------------------------------------------------------------


def test_repair_disabled_skips_repair_attempts():
    """When agent_repair_enabled=False, no repair attempts are made."""
    # First output is invalid (missing sections)
    invalid = "SUNO PROMPT\nblah\n"
    llm = FakeLLM([invalid])
    settings = Settings(
        spotify_client_id="test",
        openai_api_key="test",
        agent_repair_enabled=False,
    )
    builder = AgentPromptGraph(settings, llm=llm)
    req = AdvancedGenerateRequest(
        user_prompt="test",
        lyrics_about="test",
    )

    result = asyncio.run(builder.generate(req))

    # Should only call LLM once (no repairs), then return error
    assert llm.calls == 1
    assert result["success"] is False
    assert "issues" in result and result["issues"]


def test_custom_max_repairs_is_respected():
    """When agent_max_repairs is set to a custom value, it's respected."""
    invalid = "SUNO PROMPT\nblah\n"
    # Provide enough invalid outputs for 5 repairs
    llm = FakeLLM([invalid] * 6)
    settings = Settings(
        spotify_client_id="test",
        openai_api_key="test",
        agent_repair_enabled=True,
        agent_max_repairs=5,
    )
    builder = AgentPromptGraph(settings, llm=llm)
    req = AdvancedGenerateRequest(
        user_prompt="test",
        lyrics_about="test",
    )

    result = asyncio.run(builder.generate(req))

    # Should call LLM 6 times: initial + 5 repairs
    assert llm.calls == 6
    assert result["success"] is False
    assert "issues" in result and result["issues"]


def test_zero_max_repairs_goes_straight_to_fallback():
    """When agent_max_repairs=0, invalid output immediately returns error (no fallback)."""
    invalid = "SUNO PROMPT\nblah\n"
    llm = FakeLLM([invalid])
    settings = Settings(
        spotify_client_id="test",
        openai_api_key="test",
        agent_repair_enabled=True,
        agent_max_repairs=0,
    )
    builder = AgentPromptGraph(settings, llm=llm)
    req = AdvancedGenerateRequest(
        user_prompt="test",
        lyrics_about="test",
    )

    result = asyncio.run(builder.generate(req))

    # Only 1 LLM call (initial), then immediate error
    assert llm.calls == 1
    assert result["success"] is False
    assert "issues" in result and result["issues"]


def test_debug_info_includes_repair_config():
    """Debug info includes repair_enabled and max_repairs from config."""
    output = _valid_output()
    llm = FakeLLM([output])
    settings = Settings(
        spotify_client_id="test",
        openai_api_key="test",
        agent_repair_enabled=True,
        agent_max_repairs=3,
    )
    builder = AgentPromptGraph(settings, llm=llm)
    req = AdvancedGenerateRequest(
        user_prompt="test",
        lyrics_about="test",
    )

    result = asyncio.run(builder.generate(req))

    assert result["debug_info"]["repair_enabled"] is True
    assert result["debug_info"]["max_repairs"] == 3
    assert result["debug_info"]["repaired"] is False
