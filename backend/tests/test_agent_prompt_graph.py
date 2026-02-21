"""
Tests for AgentPromptGraph — two-step (v5_hybrid) generation.

All tests use prompt_variant="v5_hybrid" which is the default two-step variant.
FakeLLM responses are consumed in this order:
  Non-instrumental: style → profile → lyrics → style_name (4 calls)
  Instrumental: style → title → style_name (3 calls)
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
    Returns a sequence of contents across successive `ainvoke` calls.
    After exhausting contents, returns empty string.
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


def _settings(**overrides) -> Settings:
    defaults = dict(spotify_client_id="test", openai_api_key="test")
    defaults.update(overrides)
    return Settings(**defaults)


# ---------------------------------------------------------------------------
# Output helpers for two-step v5_hybrid variant
# ---------------------------------------------------------------------------


def _valid_style_output(
    suno_prompt: str = "Funky pop, crisp drums, bright bass",
    exclude: str = "cheesy, country",
    weirdness: int = 50,
    style_influence: int = 60,
) -> str:
    """Valid output for the style branch."""
    return (
        f"SUNO PROMPT\n{suno_prompt}\n\n"
        f"EXCLUDE\n{exclude}\n\n"
        f"WEIRDNESS\n{weirdness}\n\n"
        f"STYLE INFLUENCE\n{style_influence}\n"
    )


def _valid_lyrics_output(
    song_title: str = "Hello World",
    lyrics: str = "[Verse]\nhello world\n",
) -> str:
    """Valid output for the lyrics branch."""
    return f"SONG TITLE\n{song_title}\n\nLYRICS\n{lyrics}\n"


def _valid_profile_output() -> str:
    """Valid per-section profile output for profile inference."""
    return (
        'Verse: {"lines_per_section": "4_lines", "line_length": "default", "pov": "first", '
        '"rhyme_scheme": "aabb", "directness": "balanced", "persona": "earnest", '
        '"humor": "none", "explicitness": "clean", "audience": "general"}\n'
        'Pre-Chorus: {"lines_per_section": "2_lines", "line_length": "short", "pov": "first", '
        '"rhyme_scheme": "aabb", "directness": "direct", "persona": "earnest", '
        '"humor": "none", "explicitness": "clean", "audience": "general"}\n'
        'Chorus: {"lines_per_section": "4_lines", "line_length": "short", "pov": "first", '
        '"rhyme_scheme": "aaaa", "directness": "direct", "persona": "earnest", '
        '"humor": "none", "explicitness": "clean", "audience": "general"}\n'
        'Post-Chorus: {"lines_per_section": "2_lines", "line_length": "sparse", "pov": "none", '
        '"rhyme_scheme": "aaaa", "directness": "direct", "persona": "earnest", '
        '"humor": "none", "explicitness": "clean", "audience": "general"}\n'
        'Bridge: {"lines_per_section": "4_lines", "line_length": "default", "pov": "second", '
        '"rhyme_scheme": "abab", "directness": "metaphor_heavy", "persona": "melancholic", '
        '"humor": "none", "explicitness": "clean", "audience": "general"}\n'
        'Structure: ["Intro", "Verse", "Chorus", "Verse", "Chorus", "Bridge", "Chorus", "Outro"]'
    )


def _style_name_output() -> str:
    """Valid output for style name generation."""
    return "Indie Pop Fusion"


def _happy_path_responses(
    style_output=None,
    profile_output=None,
    lyrics_output=None,
    style_name=None,
) -> list[str]:
    """Standard 4-response sequence for non-instrumental happy path."""
    return [
        style_output or _valid_style_output(),
        profile_output or _valid_profile_output(),
        lyrics_output or _valid_lyrics_output(),
        style_name or _style_name_output(),
    ]


def _instrumental_responses(
    style_output=None,
    title="The Last Horizon",
    style_name=None,
) -> list[str]:
    """Standard 3-response sequence for instrumental mode."""
    return [
        style_output or _valid_style_output(),
        title,
        style_name or _style_name_output(),
    ]


# ---------------------------------------------------------------------------
# Basic use cases (happy path)
# ---------------------------------------------------------------------------


def test_valid_output_no_repairs_needed():
    """When the LLM returns valid output on first try, no repairs are triggered."""
    llm = FakeLLM(_happy_path_responses())
    builder = AgentPromptGraph(_settings(), llm=llm)
    req = AdvancedGenerateRequest(
        user_prompt="Make a funky pop song",
        lyrics_about="dancing in the rain",
        selected_artists=[],
        tags=["pop", "funk"],
        prompt_variant="v5_hybrid",
    )

    result = asyncio.run(builder.generate(req))

    assert llm.calls == 4  # style + profile + lyrics + style_name
    assert result["debug_info"]["summary"]["repairs"] == 0
    assert result["lyrics"] == "[Verse]\nhello world"
    assert result["suno_prompt"] == "Funky pop, crisp drums, bright bass"
    assert result["exclude"] == "cheesy, country"
    assert result["weirdness"] == 50
    assert result["style_influence"] == 60


def test_extracts_all_response_fields():
    """All expected fields are present in the two-step response."""
    llm = FakeLLM(_happy_path_responses())
    builder = AgentPromptGraph(_settings(), llm=llm)
    req = AdvancedGenerateRequest(
        user_prompt="Cinematic orchestral piece",
        lyrics_about="stars colliding",
        prompt_variant="v5_hybrid",
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
    # DebugTrace format
    assert "summary" in result["debug_info"]
    assert "spans" in result["debug_info"]
    assert result["debug_info"]["summary"]["variant"] == "v5_hybrid"
    assert result["debug_info"]["summary"]["architecture"] == "two_step"


def test_concept_title_from_lyrics_branch():
    """In two-step, concept title comes from the lyrics branch song_title."""
    llm = FakeLLM(
        _happy_path_responses(
            lyrics_output=_valid_lyrics_output(song_title="Ants Marching On Mars"),
        )
    )
    builder = AgentPromptGraph(_settings(), llm=llm)
    req = AdvancedGenerateRequest(
        user_prompt="Make something epic",
        lyrics_about="ants marching on Mars",
        prompt_variant="v5_hybrid",
    )

    result = asyncio.run(builder.generate(req))

    assert result["concept_title"] == "Ants Marching On Mars"


def test_concept_title_instrumental_from_title_llm():
    """When lyrics_about is empty (instrumental), title comes from title LLM."""
    llm = FakeLLM(_instrumental_responses(title="Heavy Metal Thunder"))
    builder = AgentPromptGraph(_settings(), llm=llm)
    req = AdvancedGenerateRequest(
        user_prompt="heavy metal breakdown",
        lyrics_about="",
        prompt_variant="v5_hybrid",
    )

    result = asyncio.run(builder.generate(req))

    assert result["concept_title"] == "Heavy Metal Thunder"
    assert result["lyrics"] == ""


def test_generation_id_is_unique():
    """Each generation produces a unique generation_id."""
    # Provide enough responses for two full generations
    llm = FakeLLM(_happy_path_responses() + _happy_path_responses())
    builder = AgentPromptGraph(_settings(), llm=llm)
    req = AdvancedGenerateRequest(
        user_prompt="synth wave",
        lyrics_about="neon nights",
        prompt_variant="v5_hybrid",
    )

    result1 = asyncio.run(builder.generate(req))
    result2 = asyncio.run(builder.generate(req))

    assert result1["generation_id"] != result2["generation_id"]


# ---------------------------------------------------------------------------
# Style branch validation + repair tests
# ---------------------------------------------------------------------------


def test_suno_prompt_over_500_triggers_style_repairs():
    """SUNO PROMPT >500 chars triggers repair attempts in style branch."""
    long_prompt = "A" * 600
    bad_style = _valid_style_output(suno_prompt=long_prompt)
    llm = FakeLLM(
        [
            bad_style,  # #1: style.generate (bad)
            bad_style,  # #2: style.repair.1 (still bad)
            bad_style,  # #3: style.repair.2 (still bad)
            _valid_profile_output(),  # #4: lyrics.profile_infer
            _valid_lyrics_output(),  # #5: lyrics.generate
            _style_name_output(),  # #6: style.name_generate
        ]
    )
    builder = AgentPromptGraph(_settings(), llm=llm)
    req = AdvancedGenerateRequest(
        user_prompt="test prompt",
        lyrics_about="test topic",
        prompt_variant="v5_hybrid",
    )

    result = asyncio.run(builder.generate(req))

    assert llm.calls == 6  # style(3) + profile + lyrics + name
    # Style branch proceeded with issues
    assert len(result["suno_prompt"]) > 500
    # Debug trace shows repair attempts
    spans = result["debug_info"]["spans"]
    repair_spans = [s for s in spans if "repair" in s["name"]]
    assert len(repair_spans) == 2


def test_weirdness_out_of_range_triggers_style_repairs():
    """Weirdness >100 triggers repair attempts in style branch."""
    bad_style = _valid_style_output(weirdness=150)
    llm = FakeLLM(
        [
            bad_style,  # #1: style.generate (bad)
            bad_style,  # #2: style.repair.1 (still bad)
            bad_style,  # #3: style.repair.2 (still bad)
            _valid_profile_output(),  # #4: lyrics.profile_infer
            _valid_lyrics_output(),  # #5: lyrics.generate
            _style_name_output(),  # #6: style.name_generate
        ]
    )
    builder = AgentPromptGraph(_settings(), llm=llm)
    req = AdvancedGenerateRequest(
        user_prompt="test",
        lyrics_about="test",
        prompt_variant="v5_hybrid",
    )

    result = asyncio.run(builder.generate(req))

    assert llm.calls == 6
    assert result["weirdness"] == 150
    spans = result["debug_info"]["spans"]
    repair_spans = [s for s in spans if "repair" in s["name"]]
    assert len(repair_spans) == 2


def test_style_influence_out_of_range_triggers_style_repairs():
    """Style influence >100 triggers repair attempts in style branch."""
    bad_style = _valid_style_output(style_influence=200)
    llm = FakeLLM(
        [
            bad_style,  # #1: style.generate (bad)
            bad_style,  # #2: style.repair.1 (still bad)
            bad_style,  # #3: style.repair.2 (still bad)
            _valid_profile_output(),  # #4: lyrics.profile_infer
            _valid_lyrics_output(),  # #5: lyrics.generate
            _style_name_output(),  # #6: style.name_generate
        ]
    )
    builder = AgentPromptGraph(_settings(), llm=llm)
    req = AdvancedGenerateRequest(
        user_prompt="test",
        lyrics_about="test",
        prompt_variant="v5_hybrid",
    )

    result = asyncio.run(builder.generate(req))

    assert llm.calls == 6
    assert result["style_influence"] == 200
    spans = result["debug_info"]["spans"]
    repair_spans = [s for s in spans if "repair" in s["name"]]
    assert len(repair_spans) == 2


def test_tags_are_passed_through():
    """Tags from request don't break generation."""
    llm = FakeLLM(_happy_path_responses())
    builder = AgentPromptGraph(_settings(), llm=llm)
    req = AdvancedGenerateRequest(
        user_prompt="indie rock anthem",
        lyrics_about="summer nights",
        tags=["indie", "rock", "anthemic"],
        prompt_variant="v5_hybrid",
    )

    result = asyncio.run(builder.generate(req))

    assert result["debug_info"]["summary"]["repairs"] == 0
    assert result["suno_prompt"]  # output is valid


def test_selected_artists_not_leaked_when_valid():
    """Selected artists don't appear in valid style output."""
    llm = FakeLLM(
        _happy_path_responses(
            style_output=_valid_style_output(
                suno_prompt="Retro funk, smooth bass, falsetto vocals"
            ),
        )
    )
    builder = AgentPromptGraph(_settings(), llm=llm)
    req = AdvancedGenerateRequest(
        user_prompt="Make it sound like Prince",
        lyrics_about="purple rain",
        selected_artists=["Prince"],
        prompt_variant="v5_hybrid",
    )

    result = asyncio.run(builder.generate(req))

    assert "prince" not in result["suno_prompt"].lower()
    assert result["debug_info"]["summary"]["repairs"] == 0


def test_style_repair_fixes_missing_sections():
    """Style branch repairs when initial output is missing required sections."""
    bad = "SUNO PROMPT\nsome prompt\n"  # Missing EXCLUDE, WEIRDNESS, STYLE INFLUENCE
    good = _valid_style_output(
        suno_prompt="some prompt",
        exclude="cheesy, country",
        weirdness=42,
        style_influence=55,
    )
    llm = FakeLLM(
        [
            bad,  # #1: style.generate (bad — missing EXCLUDE)
            good,  # #2: style.repair.1 (good)
            _valid_profile_output(),  # #3: lyrics.profile_infer
            _valid_lyrics_output(),  # #4: lyrics.generate
            _style_name_output(),  # #5: style.name_generate
        ]
    )
    builder = AgentPromptGraph(_settings(), llm=llm)
    req = AdvancedGenerateRequest(
        user_prompt="Make something big and cinematic",
        lyrics_about="ants on Mars",
        selected_artists=[],
        tags=["cinematic"],
        prompt_variant="v5_hybrid",
    )

    result = asyncio.run(builder.generate(req))

    assert llm.calls == 5  # style(2) + profile + lyrics + name
    spans = result["debug_info"]["spans"]
    repair_spans = [s for s in spans if "repair" in s["name"]]
    assert len(repair_spans) == 1
    assert result["suno_prompt"] == "some prompt"
    assert result["exclude"] == "cheesy, country"
    assert result["weirdness"] == 42
    assert result["style_influence"] == 55


def test_artist_names_not_in_clean_suno_prompt():
    """Verify clean suno_prompt doesn't contain artist names."""
    clean_style = _valid_style_output(
        suno_prompt="Funky pop groove, bright bass, crisp drums, glossy modern mix",
    )
    llm = FakeLLM(_happy_path_responses(style_output=clean_style))
    builder = AgentPromptGraph(_settings(), llm=llm)
    req = AdvancedGenerateRequest(
        user_prompt="Make a song that sounds like Bruno Mars",
        lyrics_about="dancing alone",
        selected_artists=["Bruno Mars"],
        tags=["pop"],
        prompt_variant="v5_hybrid",
    )

    result = asyncio.run(builder.generate(req))

    assert llm.calls == 4
    assert "bruno" not in result["suno_prompt"].lower()


def test_style_branch_proceeds_after_max_repairs():
    """After exhausting repairs, style branch proceeds with issues."""
    invalid_style = "SUNO PROMPT\nblah\n"  # Missing EXCLUDE
    llm = FakeLLM(
        [
            invalid_style,  # #1: style.generate (bad)
            invalid_style,  # #2: style.repair.1 (still bad)
            invalid_style,  # #3: style.repair.2 (still bad)
            _valid_profile_output(),  # #4: lyrics.profile_infer
            _valid_lyrics_output(),  # #5: lyrics.generate
            _style_name_output(),  # #6: style.name_generate
        ]
    )
    builder = AgentPromptGraph(_settings(), llm=llm)
    req = AdvancedGenerateRequest(
        user_prompt="Make a song that sounds like Will.I.Am",
        lyrics_about="robots",
        selected_artists=["Will.I.Am"],
        tags=["electropop"],
        prompt_variant="v5_hybrid",
    )

    result = asyncio.run(builder.generate(req))

    assert llm.calls == 6  # style(3) + profile + lyrics + name
    # Result is still returned (two-step doesn't return error)
    assert "suno_prompt" in result
    spans = result["debug_info"]["spans"]
    repair_spans = [s for s in spans if "repair" in s["name"]]
    assert len(repair_spans) == 2


# ---------------------------------------------------------------------------
# Config-driven repair behavior tests
# ---------------------------------------------------------------------------


def test_zero_max_repairs_skips_repair_attempts():
    """When agent_max_repairs=0, style branch skips repair attempts."""
    bad_style = "SUNO PROMPT\nblah\n"  # Missing EXCLUDE
    llm = FakeLLM(
        [
            bad_style,  # #1: style.generate (bad, no repair)
            _valid_profile_output(),  # #2: lyrics.profile_infer
            _valid_lyrics_output(),  # #3: lyrics.generate
            _style_name_output(),  # #4: style.name_generate
        ]
    )
    settings = _settings(agent_max_repairs=0)
    builder = AgentPromptGraph(settings, llm=llm)
    req = AdvancedGenerateRequest(
        user_prompt="test",
        lyrics_about="test",
        prompt_variant="v5_hybrid",
    )

    result = asyncio.run(builder.generate(req))

    assert llm.calls == 4  # style(1) + profile + lyrics + name
    spans = result["debug_info"]["spans"]
    repair_spans = [s for s in spans if "repair" in s["name"]]
    assert len(repair_spans) == 0


def test_custom_max_repairs_is_respected():
    """When agent_max_repairs is set to a custom value, it's respected."""
    invalid_style = "SUNO PROMPT\nblah\n"  # Missing EXCLUDE
    llm = FakeLLM(
        [invalid_style] * 6  # style: initial + 5 repairs
        + [_valid_profile_output()]  # lyrics.profile_infer
        + [_valid_lyrics_output()]  # lyrics.generate
        + [_style_name_output()]  # style.name_generate
    )
    settings = _settings(agent_max_repairs=5)
    builder = AgentPromptGraph(settings, llm=llm)
    req = AdvancedGenerateRequest(
        user_prompt="test",
        lyrics_about="test",
        prompt_variant="v5_hybrid",
    )

    result = asyncio.run(builder.generate(req))

    # 6 style calls + 2 lyrics + 1 name = 9
    assert llm.calls == 9
    spans = result["debug_info"]["spans"]
    repair_spans = [s for s in spans if "repair" in s["name"]]
    assert len(repair_spans) == 5


def test_debug_info_has_trace_format():
    """Debug info uses DebugTrace format with summary and spans."""
    llm = FakeLLM(_happy_path_responses())
    settings = _settings(agent_max_repairs=3)
    builder = AgentPromptGraph(settings, llm=llm)
    req = AdvancedGenerateRequest(
        user_prompt="test",
        lyrics_about="test",
        prompt_variant="v5_hybrid",
    )

    result = asyncio.run(builder.generate(req))

    debug = result["debug_info"]
    # DebugTrace v1 structure
    assert debug["version"] == 1
    assert "summary" in debug
    assert "spans" in debug
    summary = debug["summary"]
    assert summary["variant"] == "v5_hybrid"
    assert summary["architecture"] == "two_step"
    assert summary["repairs"] == 0
    assert summary["success"] is True
    assert summary["llm_calls"] >= 2


# ---------------------------------------------------------------------------
# Instrumental mode tests (two-step variants)
# ---------------------------------------------------------------------------


def test_instrumental_with_blank_lyrics_about_returns_empty_lyrics():
    """When lyrics_about is blank, instrumental mode returns empty lyrics."""
    llm = FakeLLM(_instrumental_responses(title="The Last Horizon"))
    builder = AgentPromptGraph(_settings(), llm=llm)
    req = AdvancedGenerateRequest(
        user_prompt="Epic orchestral soundtrack",
        lyrics_about="",
        prompt_variant="v5_hybrid",
    )

    result = asyncio.run(builder.generate(req))

    assert result["lyrics"] == ""
    assert result["concept_title"] == "The Last Horizon"
    assert result["suno_prompt"] == "Funky pop, crisp drums, bright bass"
    assert result["exclude"] == "cheesy, country"
    assert result["weirdness"] == 50
    assert result["style_influence"] == 60
    assert llm.calls == 3  # style + title + style_name


def test_instrumental_with_keyword_returns_empty_lyrics():
    """When lyrics_about contains 'instrumental', returns empty lyrics."""
    llm = FakeLLM(_instrumental_responses(title="Drift"))
    builder = AgentPromptGraph(_settings(), llm=llm)
    req = AdvancedGenerateRequest(
        user_prompt="Ambient electronic",
        lyrics_about="instrumental track",
        prompt_variant="v5_hybrid",
    )

    result = asyncio.run(builder.generate(req))

    assert result["lyrics"] == ""
    assert llm.calls == 3  # style + title + style_name


def test_instrumental_with_no_vocals_keyword_returns_empty_lyrics():
    """When lyrics_about contains 'no vocals', returns empty lyrics."""
    llm = FakeLLM(_instrumental_responses(title="Velvet Thunder"))
    builder = AgentPromptGraph(_settings(), llm=llm)
    req = AdvancedGenerateRequest(
        user_prompt="Jazz fusion",
        lyrics_about="no vocals, just instruments",
        prompt_variant="v5_hybrid",
    )

    result = asyncio.run(builder.generate(req))

    assert result["lyrics"] == ""
    assert llm.calls == 3  # style + title + style_name


def test_instrumental_with_tag_returns_empty_lyrics():
    """When tags include 'instrumental', returns empty lyrics."""
    llm = FakeLLM(_instrumental_responses(title="Through Glass Canyons"))
    builder = AgentPromptGraph(_settings(), llm=llm)
    req = AdvancedGenerateRequest(
        user_prompt="Post-rock soundscape",
        lyrics_about="the sunset",
        tags=["instrumental", "post-rock"],
        prompt_variant="v5_hybrid",
    )

    result = asyncio.run(builder.generate(req))

    assert result["lyrics"] == ""
    assert llm.calls == 3  # style + title + style_name


def test_instrumental_debug_trace_includes_skipped_span():
    """Instrumental mode includes a lyrics.skipped span in debug trace."""
    llm = FakeLLM(_instrumental_responses(title="Midnight in Kyoto"))
    builder = AgentPromptGraph(_settings(), llm=llm)
    req = AdvancedGenerateRequest(
        user_prompt="Cinematic score",
        lyrics_about="",
        prompt_variant="v5_hybrid",
    )

    result = asyncio.run(builder.generate(req))

    debug_info = result.get("debug_info", {})
    spans = debug_info.get("spans", [])
    skipped_spans = [s for s in spans if s.get("name") == "lyrics.skipped"]
    assert len(skipped_spans) == 1
    assert skipped_spans[0].get("kind") == "branch"
    assert skipped_spans[0].get("meta", {}).get("reason") == "instrumental_request"


def test_is_instrumental_request_helper():
    """Test the _is_instrumental_request helper directly."""
    # Test blank lyrics_about
    req1 = AdvancedGenerateRequest(user_prompt="test", lyrics_about="")
    assert AgentPromptGraph._is_instrumental_request(req1) is True

    # Test whitespace-only
    req2 = AdvancedGenerateRequest(user_prompt="test", lyrics_about="   ")
    assert AgentPromptGraph._is_instrumental_request(req2) is True

    # Test "instrumental" keyword
    req3 = AdvancedGenerateRequest(
        user_prompt="test", lyrics_about="an instrumental piece"
    )
    assert AgentPromptGraph._is_instrumental_request(req3) is True

    # Test "no vocals" keyword
    req4 = AdvancedGenerateRequest(
        user_prompt="test", lyrics_about="no vocals needed"
    )
    assert AgentPromptGraph._is_instrumental_request(req4) is True

    # Test "no lyrics" keyword
    req5 = AdvancedGenerateRequest(
        user_prompt="test", lyrics_about="no lyrics please"
    )
    assert AgentPromptGraph._is_instrumental_request(req5) is True

    # Test instrumental tag
    req6 = AdvancedGenerateRequest(
        user_prompt="test", lyrics_about="the sunset", tags=["instrumental"]
    )
    assert AgentPromptGraph._is_instrumental_request(req6) is True

    # Test non-instrumental request
    req7 = AdvancedGenerateRequest(
        user_prompt="test", lyrics_about="love and heartbreak"
    )
    assert AgentPromptGraph._is_instrumental_request(req7) is False

    # Test non-instrumental with tags
    req8 = AdvancedGenerateRequest(
        user_prompt="test", lyrics_about="summer vibes", tags=["pop", "summer"]
    )
    assert AgentPromptGraph._is_instrumental_request(req8) is False
